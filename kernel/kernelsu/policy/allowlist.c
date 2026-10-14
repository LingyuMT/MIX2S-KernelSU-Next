/* Polaris Linux 4.9 integration changes: 2026-10-13/14; see build-support/CHANGES.md. */
#include <linux/rcupdate.h>
#include <linux/limits.h>
#include <linux/rculist.h>
#include <linux/mutex.h>
#include <linux/task_work.h>
#include <linux/capability.h>
#include <linux/compiler.h>
#include <linux/fs.h>
#include <linux/gfp.h>
#include <linux/kernel.h>
#include <linux/list.h>
#include <linux/printk.h>
#include <linux/slab.h>
#include <linux/types.h>
#include <linux/compiler.h>
#include <linux/hashtable.h>
#include <linux/kref.h>

#include "klog.h" // IWYU pragma: keep
#include "ksu.h"
#include "compat/kernel_compat.h"
#include "runtime/ksud_boot.h"
#include "selinux/selinux.h"
#include "policy/allowlist.h"
#include "manager/manager_identity.h"
#include "infra/su_mount_ns.h"

#define FILE_MAGIC 0x7f4b5355 // ' KSU', u32
#define FILE_FORMAT_VERSION 4 // u32

#define KSU_APP_PROFILE_PRESERVE_UID 9999 // NOBODY_UID
#define KSU_DEFAULT_SELINUX_DOMAIN "u:r:" KERNEL_SU_DOMAIN ":s0"

static DEFINE_MUTEX(allowlist_mutex);

// default profiles, these may be used frequently, so we cache it
static struct root_profile default_root_profile;
static struct non_root_profile default_non_root_profile;

static void __init init_default_profiles()
{
	kernel_cap_t full_cap = CAP_FULL_SET;

    default_root_profile.uid = 0;
    default_root_profile.gid = 0;
    default_root_profile.groups_count = 1;
    default_root_profile.groups[0] = 0;
    memcpy(&default_root_profile.capabilities.effective, &full_cap,
           sizeof(default_root_profile.capabilities.effective));
    default_root_profile.namespaces = KSU_NS_INHERITED;
    strcpy(default_root_profile.selinux_domain, KSU_DEFAULT_SELINUX_DOMAIN);

	// This means that we will umount modules by default!
	default_non_root_profile.umount_modules = true;

	default_root_profile.flags = 0;
}

struct perm_data {
    struct hlist_node list;
    struct rcu_head rcu;
    struct kref ref;
    struct app_profile profile;
};

// protected by rcu
#define ALLOW_LIST_BITS 8
static DEFINE_HASHTABLE(allow_list, ALLOW_LIST_BITS);
static u16 allow_list_count = 0;

#define KERNEL_SU_ALLOWLIST "/data/adb/ksu/.allowlist"

void ksu_persistent_allow_list(void);

void ksu_show_allow_list(void)
{
    int i;
    struct perm_data *p = NULL;
    pr_info("ksu_show_allow_list\n");
    rcu_read_lock();
    hash_for_each_rcu (allow_list, i, p, list) {
        pr_info("uid :%d, allow: %d\n", p->profile.curr_uid, p->profile.allow_su);
    }
    rcu_read_unlock();
}

struct app_profile *ksu_get_app_profile(uid_t uid)
{
    struct perm_data *p = NULL;
    bool found;

retry:
    found = false;
    hash_for_each_possible_rcu (allow_list, p, list, uid) {
        if (uid == p->profile.curr_uid) {
            // found it, override it with ours
            found = true;
            break;
        }
    }

    if (!found)
        return NULL;

    if (!kref_get_unless_zero(&p->ref)) {
        goto retry;
    }

    return &p->profile;
}

static inline bool forbid_system_uid(uid_t uid)
{
#define SHELL_UID 2000
#define SYSTEM_UID 1000
	return uid < SHELL_UID && uid != SYSTEM_UID;
}

static bool profile_valid(struct app_profile *profile)
{
	if (!profile) {
		return false;
	}

	if (strnlen(profile->key, sizeof(profile->key)) >= sizeof(profile->key)) {
		pr_err("invalid app_profile key\n");
		return false;
	}

	if (profile->version != KSU_APP_PROFILE_VER) {
		pr_info("Unsupported profile version: %d\n", profile->version);
		return false;
	}

	if (profile->allow_su) {
#ifndef CONFIG_KSU_DISABLE_POLICY
		if (profile->rp_config.profile.groups_count > KSU_MAX_GROUPS) {
			pr_err("invalid groups_count in app_profile: %s\n", profile->key);
			return false;
		}

		static const size_t domain_len = sizeof(profile->rp_config.profile.selinux_domain);
		size_t len = strnlen(profile->rp_config.profile.selinux_domain, domain_len);

		if (len == 0 || len >= domain_len) {
			pr_err("invalid selinux_domain in app_profile: %s\n", profile->key);
			return false;
		}
#endif
	}

	return true;
}


static void release_perm_data(struct kref *ref)
{
    struct perm_data *p = container_of(ref, struct perm_data, ref);
    kfree_rcu(p, rcu);
}

static void put_perm_data(struct perm_data *data)
{
    kref_put(&data->ref, release_perm_data);
}

int ksu_set_app_profile(struct app_profile *profile)
{
    struct perm_data *p, *np;
    int result = 0;

    if (!profile_valid(profile)) {
        pr_err("Failed to set app profile: invalid profile!\n");
        return -EINVAL;
    }

#ifdef CONFIG_KSU_DISABLE_POLICY
    if (profile->allow_su) {
        profile->rp_config.use_default = true;
        memset(profile->rp_config.template_name, 0, sizeof(profile->rp_config.template_name));
        memset(&profile->rp_config.profile, 0, sizeof(profile->rp_config.profile));
    } else {
        profile->nrp_config.use_default = true;
        memset(&profile->nrp_config.profile, 0, sizeof(profile->nrp_config.profile));
    }
#endif


    // only allow default non root profile
    if (unlikely(profile->curr_uid == KSU_APP_PROFILE_PRESERVE_UID && strcmp(profile->key, "$") != 0)) {
        return -EINVAL;
    }

    mutex_lock(&allowlist_mutex);

    hash_for_each_possible (allow_list, p, list, profile->curr_uid) {
        if (profile->curr_uid == p->profile.curr_uid) {
            if (strcmp(profile->key, p->profile.key) != 0) {
                pr_warn("ksu_set_app_profile: key changed: uid=%d orig=%s new=%s\n", profile->curr_uid, p->profile.key,
                        profile->key);
            }
            // found it, just override it all!
            np = (struct perm_data *)kzalloc(sizeof(struct perm_data),
                                             GFP_KERNEL);
            if (!np) {
                result = -ENOMEM;
                goto out_unlock;
            }
            kref_init(&np->ref);
            memcpy(&np->profile, profile, sizeof(*profile));
            hlist_replace_rcu(&p->list, &np->list);
            put_perm_data(p);
            goto out;
        }
    }

    if (unlikely(allow_list_count == U16_MAX)) {
        pr_err("too many app profile\n");
        result = -E2BIG;
        goto out_unlock;
    }

    // not found, alloc a new node!
    np = (struct perm_data *)kzalloc(sizeof(struct perm_data), GFP_KERNEL);
    if (!np) {
        pr_err("ksu_set_app_profile alloc failed\n");
        result = -ENOMEM;
        goto out_unlock;
    }

    kref_init(&np->ref);
    memcpy(&np->profile, profile, sizeof(*profile));
    if (profile->allow_su) {
        pr_info("set root profile, key: %s, uid: %d, gid: %d, context: %s\n", profile->key, profile->curr_uid,
                profile->rp_config.profile.gid,
                profile->rp_config.profile.selinux_domain);
    } else {
        pr_info("set app profile, key: %s, uid: %d, umount modules: %d\n", profile->key, profile->curr_uid,
                profile->nrp_config.profile.umount_modules);
    }

    hash_add_rcu(allow_list, &np->list, np->profile.curr_uid);
    ++allow_list_count;

out:
    result = 0;

    if (unlikely(profile->curr_uid == KSU_APP_PROFILE_PRESERVE_UID)) {
        // set default non root profile
        default_non_root_profile.umount_modules = profile->nrp_config.profile.umount_modules;
    }

out_unlock:
    mutex_unlock(&allowlist_mutex);
    return result;
}

bool __ksu_is_allow_uid(uid_t uid)
{
	struct perm_data *p;

	if (forbid_system_uid(uid)) {
		// do not bother going through the list if it's system
		return false;
	}

	if (unlikely(is_uid_manager(uid))) {
		// manager is always allowed!
		return true;
	}

	if (unlikely(allow_shell) && uid == SHELL_UID) {
		return true;
	}

	rcu_read_lock();
	hash_for_each_possible_rcu (allow_list, p, list, uid) {
		if (uid == p->profile.curr_uid && p->profile.allow_su) {
			rcu_read_unlock();
			return true;
		}
	}
	rcu_read_unlock();

	return false;
}

bool __ksu_is_allow_uid_for_current(uid_t uid)
{
	if (unlikely(uid == 0)) {
		// already root, but only allow our domain.
		return is_ksu_domain();
	}
	return __ksu_is_allow_uid(uid);
}

bool ksu_uid_should_umount(uid_t uid)
{
    struct app_profile *profile;
    bool res;
    if (likely(ksu_is_manager_appid_valid()) && unlikely(ksu_get_manager_appid() == uid % PER_USER_RANGE)) {
        // we should not umount on manager!
        return false;
    }
#ifdef CONFIG_KSU_DISABLE_POLICY
    return !__ksu_is_allow_uid(uid);
#else
    rcu_read_lock();
    profile = ksu_get_app_profile(uid);
    if (!profile) {
        // no app profile found, it must be non root app
        res = default_non_root_profile.umount_modules;
    } else if (profile->allow_su) {
        // if found and it is granted to su, we shouldn't umount for it
        res = false;
    } else {
        // found an app profile
        if (profile->nrp_config.use_default) {
            res = default_non_root_profile.umount_modules;
        } else {
            res = profile->nrp_config.profile.umount_modules;
        }
    }
    rcu_read_unlock();

    if (profile)
        ksu_put_app_profile(profile);
    return res;
#endif
}

void ksu_put_app_profile(struct app_profile *profile)
{
    struct perm_data *p = container_of(profile, struct perm_data, profile);
    put_perm_data(p);
}

struct root_profile *ksu_get_root_profile(uid_t uid)
{
#ifdef CONFIG_KSU_DISABLE_POLICY
    (void)uid;
    return &default_root_profile;
#else
    struct perm_data *p = NULL;
    struct root_profile *res;

    rcu_read_lock();
    if (is_uid_manager(uid)) {
        goto use_default;
    }

    if (unlikely(allow_shell && uid == SHELL_UID)) {
        goto use_default;
    }

retry:
    res = NULL;
    hash_for_each_possible_rcu (allow_list, p, list, uid) {
        if (uid == p->profile.curr_uid && p->profile.allow_su) {
            if (!p->profile.rp_config.use_default) {
                if (!kref_get_unless_zero(&p->ref)) {
                    goto retry;
                }
                res = &p->profile.rp_config.profile;
            }
            break;
        }
    }

    if (unlikely(!res)) {
    use_default:
        res = &default_root_profile;
    }

    rcu_read_unlock();
    return res;
#endif
}

void ksu_put_root_profile(struct root_profile *profile)
{
    if (likely(profile == &default_root_profile))
        return;
    struct perm_data *p = container_of(profile, struct perm_data, profile.rp_config.profile);
    put_perm_data(p);
}

bool ksu_get_allow_list(int *array, u16 length, u16 *out_length, u16 *out_total,
                        bool allow)
{
    struct perm_data *p = NULL;
    u16 i = 0, j = 0;
    int iter;
    rcu_read_lock();
    hash_for_each_rcu (allow_list, iter, p, list) {
        // pr_info("get_allow_list uid: %d allow: %d\n", p->uid, p->allow);
        if (p->profile.allow_su == allow && !is_uid_manager(p->profile.curr_uid)) {
            if (j < length) {
                array[j++] = p->profile.curr_uid;
            }
            ++i;
        }
    }
    rcu_read_unlock();
    if (out_length) {
        *out_length = j;
    }
    if (out_total) {
        *out_total = i;
    }

	return true;
}

/* Old kernel APIs may return short I/O; preserve the real errno. */
static ssize_t ksu_allowlist_read_full(struct file *fp, void *buf,
                                     size_t size, loff_t *off)
{
    size_t done = 0;
    ssize_t ret;
    while (done < size) {
        ret = ksu_kernel_read_compat(fp, (char *)buf + done, size - done, off);
        if (ret < 0)
            return ret;
        if (!ret)
            break;
        done += ret;
    }
    return done;
}

static ssize_t ksu_allowlist_write_full(struct file *fp, const void *buf,
                                      size_t size, loff_t *off)
{
    size_t done = 0;
    ssize_t ret;
    while (done < size) {
        ret = ksu_kernel_write_compat(fp, (const char *)buf + done,
                                      size - done, off);
        if (ret < 0)
            return ret;
        if (!ret)
            return -EIO;
        done += ret;
    }
    return done;
}

// TODO: move to kernel thread or work queue
static void do_persistent_allow_list(struct callback_head *_cb)
{
    u32 magic = FILE_MAGIC, version = FILE_FORMAT_VERSION;
    struct perm_data *p = NULL;
    struct file *fp;
    const struct cred *saved;
    loff_t off = 0;
    ssize_t ret;
    int i;

    if (!ksu_cred) {
        pr_err("save_allow_list: KSU credentials unavailable\n");
        goto free_cb;
    }
    saved = override_creds(ksu_cred);
    fp = ksu_filp_open_compat(KERNEL_SU_ALLOWLIST, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (IS_ERR(fp)) {
        pr_err("save_allow_list create file failed: %ld\n", PTR_ERR(fp));
        goto restore;
    }
    ret = ksu_allowlist_write_full(fp, &magic, sizeof(magic), &off);
    if (ret != sizeof(magic))
        goto write_error;
    ret = ksu_allowlist_write_full(fp, &version, sizeof(version), &off);
    if (ret != sizeof(version))
        goto write_error;

    mutex_lock(&allowlist_mutex);
    hash_for_each(allow_list, i, p, list) {
        ret = ksu_allowlist_write_full(fp, &p->profile, sizeof(p->profile), &off);
        if (ret != sizeof(p->profile))
            break;
    }
    mutex_unlock(&allowlist_mutex);
    if (ret < 0)
        goto write_error;
    ret = vfs_fsync(fp, 0);
    if (ret) {
        pr_err("save_allow_list fsync failed: %zd\n", ret);
        goto close_file;
    }
    pr_info("save_allow_list complete: %lld bytes\n", off);
    goto close_file;
write_error:
    pr_err("save_allow_list write failed: %zd at offset %lld\n", ret, off);
close_file:
    filp_close(fp, NULL);
restore:
    revert_creds(saved);
free_cb:
    kfree(_cb);
}

void ksu_persistent_allow_list()
{
	struct task_struct *tsk;

	rcu_read_lock();
	tsk = get_pid_task(find_vpid(1), PIDTYPE_PID);
	if (!tsk) {
		rcu_read_unlock();
		pr_err("save_allow_list find init task err\n");
		return;
	}
	rcu_read_unlock();

	struct callback_head *cb =
		kzalloc(sizeof(struct callback_head), GFP_KERNEL);
	if (!cb) {
		pr_err("save_allow_list alloc cb err\b");
		goto put_task;
	}
	cb->func = do_persistent_allow_list;
	if (task_work_add(tsk, cb, TWA_RESUME)) {
		kfree(cb);
		pr_warn("save_allow_list add task_work failed\n");
	}

put_task:
	put_task_struct(tsk);
}

static void migrate_profile(u32 version, struct app_profile *profile)
{
    char *domain;
    static const size_t domain_len = sizeof(profile->rp_config.profile.selinux_domain);

    switch (version) {
    case 2:
        if (profile->allow_su) {
            domain = profile->rp_config.profile.selinux_domain;
            if (strncmp(domain, "u:r:su:s0", domain_len) == 0) {
                __strscpy_pad(domain, KSU_DEFAULT_SELINUX_DOMAIN, domain_len);
                pr_info("migrated domain of profile: %s\n", profile->key);
            }
        }
        /* fall through */
    case 3:
        if (profile->allow_su) {
            profile->rp_config.profile.flags = FLAG_KSU_NO_NEW_PRIVS;
        }
        break;
    }

    profile->version = KSU_APP_PROFILE_VER;
}

void ksu_load_allow_list()
{
#ifdef CONFIG_KSU_DISABLE_POLICY
    pr_info("allowlist load skipped because policy is disabled\n");
    return;
#endif
    loff_t off = 0, file_size;
    ssize_t ret;
    struct file *fp;
    const struct cred *saved;
    u32 magic = 0, version = 0;
    unsigned int loaded = 0;
    size_t app_profile_size;
    bool complete = false;

    /* Same privileged subjective credentials as the save path. */
    if (!ksu_cred) {
        pr_err("load_allow_list: KSU credentials unavailable\n");
        return;
    }
    saved = override_creds(ksu_cred);
    fp = ksu_filp_open_compat(KERNEL_SU_ALLOWLIST, O_RDONLY, 0);
    if (IS_ERR(fp)) {
        pr_err("load_allow_list open file failed: %ld\n", PTR_ERR(fp));
        goto restore;
    }
    if (!S_ISREG(file_inode(fp)->i_mode)) {
        pr_err("load_allow_list: not a regular file\n");
        goto close_file;
    }
    ret = ksu_allowlist_read_full(fp, &magic, sizeof(magic), &off);
    if (ret != sizeof(magic)) {
        pr_err("allowlist read magic failed: %zd at offset %lld\n", ret, off);
        goto close_file;
    }
    if (magic != FILE_MAGIC) {
        pr_err("allowlist invalid magic: 0x%08x\n", magic);
        goto close_file;
    }
    ret = ksu_allowlist_read_full(fp, &version, sizeof(version), &off);
    if (ret != sizeof(version)) {
        pr_err("allowlist read version failed: %zd\n", ret);
        goto close_file;
    }
    if (version < 2 || version > FILE_FORMAT_VERSION) {
        pr_err("invalid allowlist version: %u\n", version);
        goto close_file;
    }
    app_profile_size = version < FILE_FORMAT_VERSION ? 776 : sizeof(struct app_profile);
    file_size = i_size_read(file_inode(fp));
    if (file_size < off || (file_size - off) % app_profile_size ||
        (file_size - off) / app_profile_size > U16_MAX) {
        pr_err("allowlist invalid file size: %lld, record size: %zu\n",
               file_size, app_profile_size);
        goto close_file;
    }
    while (off < file_size) {
        struct app_profile profile = { 0 };
        ret = ksu_allowlist_read_full(fp, &profile, app_profile_size, &off);
        if (ret != app_profile_size) {
            pr_err("load_allow_list read failed: %zd at offset %lld\n", ret, off);
            goto close_file;
        }
        /* Validate before logging any strings or applying a grant. */
        if (strnlen(profile.key, sizeof(profile.key)) >= sizeof(profile.key)) {
            pr_err("load_allow_list invalid record at offset %lld\n", off);
            goto close_file;
        }
        migrate_profile(version, &profile);
        ret = ksu_set_app_profile(&profile);
        if (ret) {
            pr_err("load_allow_list set profile failed: %zd\n", ret);
            goto close_file;
        }
        loaded++;
    }
    complete = true;
    pr_info("load_allow_list complete: version %u, %u profiles\n", version, loaded);
close_file:
    filp_close(fp, NULL);
restore:
    revert_creds(saved);
    /* Never rewrite a failed/truncated read as a successful migration. */
    if (complete && version < FILE_FORMAT_VERSION)
        ksu_persistent_allow_list();
}

void ksu_prune_allowlist(bool (*is_uid_valid)(uid_t, char *, void *),
				void *data)
{
    struct perm_data *np = NULL;
    struct hlist_node *tmp;
    int i;

    if (!ksu_boot_completed) {
        pr_info("boot not completed, skip prune\n");
        return;
    }

    bool modified = false;
    mutex_lock(&allowlist_mutex);
    hash_for_each_safe (allow_list, i, tmp, np, list) {
        uid_t uid = np->profile.curr_uid;
        char *package = np->profile.key;
        // we use this uid for special cases, don't prune it!
        bool is_preserved_uid = uid == KSU_APP_PROFILE_PRESERVE_UID || uid == WEBVIEW_ZYGOTE_UID;
        if (!is_preserved_uid && !is_uid_valid(uid, package, data)) {
            modified = true;
            pr_info("prune uid: %d, package: %s\n", uid, package);
            hlist_del_rcu(&np->list);
            put_perm_data(np);
            --allow_list_count;
        }
    }
    mutex_unlock(&allowlist_mutex);

    if (modified) {
        smp_mb();
        ksu_persistent_allow_list();
    }
}

void __init ksu_allowlist_init(void)
{
	init_default_profiles();
}

void __exit ksu_allowlist_exit(void)
{
	struct perm_data *np = NULL;
	struct hlist_node *tmp;
	int i;

	// free allowlist
	mutex_lock(&allowlist_mutex);
	hash_for_each_safe (allow_list, i, tmp, np, list) {
		hlist_del(&np->list);
		put_perm_data(np);
	}
	mutex_unlock(&allowlist_mutex);
}