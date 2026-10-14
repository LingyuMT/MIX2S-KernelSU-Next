#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile actual edited C functions with fault-injection stubs."""
from pathlib import Path
import subprocess, json
r = Path(__file__).resolve().parents[2]
src = r
out = r/'.host-tests'
out.mkdir(exist_ok=True)
a = (src/'kernel/kernelsu/policy/allowlist.c').read_text()
h = (src/'security/selinux/hooks.c').read_text()
def function(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        if text[end] == '{': depth += 1
        elif text[end] == '}': depth -= 1
        end += 1
    return text[start:end]
header = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <limits.h>
typedef uint32_t u32;
#define U16_MAX 65535
#define FILE_MAGIC 0x7f4b5355
#define FILE_FORMAT_VERSION 4
#define KERNEL_SU_ALLOWLIST "fixture"
#define CONFIG_KSU 1
#define LSM_UNSAFE_NO_NEW_PRIVS 1
#define pr_err(...) ((void)0)
#define pr_info(...) ((void)0)
#define IS_ERR(p) ((intptr_t)(p) < 0)
#define PTR_ERR(p) ((long)(p))
struct inode { int i_mode; loff_t size; };
struct mount { bool suid; };
struct file { struct inode inode; struct { struct mount *mnt; } f_path; };
struct cred { int tag; };
struct cred elevated, original;
const struct cred *ksu_cred = &elevated, *active = &original;
struct file f;
unsigned char disk[4096];
size_t disk_size, step;
int read_error, write_error, opens_error, installed, migrations, restore_count;
struct app_profile { u32 version; char key[256]; char rest[524]; };
struct perm_data { struct app_profile profile; };
struct callback_head { int dummy; };
struct perm_data items[2];
int item_count=2, fsync_error, fsync_calls, freed, allowlist_mutex;
#define hash_for_each(table,i,p,list) for ((i)=0; (i)<item_count && ((p)=&items[i]); (i)++)
void mutex_lock(int *p) {(void)p;}
void mutex_unlock(int *p) {(void)p;}
void kfree(void *p) {freed++;free(p);}
int vfs_fsync(struct file *p,int datasync) {(void)p;(void)datasync;fsync_calls++;return fsync_error;}
const struct cred *override_creds(const struct cred *c) { const struct cred *s=active; active=c;return s; }
void revert_creds(const struct cred *c) { active=c; restore_count++; }
struct file *filp_open(const char *p,int flags,int mode) { (void)p;(void)flags;(void)mode; if(active!=ksu_cred)abort(); return opens_error ? (struct file *)(intptr_t)opens_error : &f; }
struct file *ksu_filp_open_compat(const char *p,int flags,int mode) {return filp_open(p,flags,mode);}
void filp_close(struct file *p,void *owner) {(void)p;(void)owner;}
struct inode *file_inode(struct file *p) { return &p->inode; }
loff_t i_size_read(struct inode *p) { return p->size; }
ssize_t ksu_kernel_read_compat(struct file *p,void *buf,size_t count,loff_t *off) {
 (void)p;if(read_error)return read_error;
 size_t n=disk_size-*off;if(n>count)n=count;if(step&&n>step)n=step;
 memcpy(buf,disk+*off,n);*off+=n;return n;
}
ssize_t ksu_kernel_write_compat(struct file *p,const void *buf,size_t count,loff_t *off) {
 (void)p;if(write_error)return write_error==-999?0:write_error;
 size_t n=count;if(step&&n>step)n=step;memcpy(disk+*off,buf,n);*off+=n;return n;
}
void migrate_profile(u32 version,struct app_profile *p) {(void)version;p->version=4;}
int ksu_set_app_profile(struct app_profile *p) { if(!memchr(p->key,0,sizeof(p->key)))abort();installed++;return 0; }
void ksu_persistent_allow_list(void) {migrations++;}
struct task_security_struct { u32 sid; };
struct linux_binprm { int unsafe;struct file *file;const char *filename; };
bool mnt_may_suid(struct mount *m) {return m->suid;}
bool is_ksu_transition(const struct task_security_struct *a,const struct task_security_struct *b) {return a->sid==73&&b->sid==74;}
int bounded_error;
int security_bounded_transition(u32 a,u32 b) {(void)a;(void)b;return bounded_error;}
int cases;
#define CHECK(c) do {cases++;if(!(c)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#c);exit(1);}}while(0)
void fixture(u32 version,size_t record) {
 memset(disk,0,sizeof(disk)); u32 magic=FILE_MAGIC;memcpy(disk,&magic,4);memcpy(disk+4,&version,4);
 memcpy(disk+8,&version,4);memcpy(disk+12,"shell",6);disk_size=8+record;
 f.inode.i_mode=S_IFREG;f.inode.size=disk_size;step=read_error=write_error=opens_error=installed=migrations=restore_count=0;active=&original;
}
'''
body = '\n'.join(function(a,s) for s in ['static ssize_t ksu_allowlist_read_full(', 'static ssize_t ksu_allowlist_write_full(', 'static void do_persistent_allow_list(', 'void ksu_load_allow_list()'])
body += '\n'+function(h,'static int check_nnp_nosuid(')
tests = r'''
int main(void) {
 loff_t off=0;char buf[8]={0};
 fixture(4,784);step=1;CHECK(ksu_allowlist_read_full(&f,buf,8,&off)==8&&off==8);
 fixture(4,784);read_error=-EACCES;off=0;CHECK(ksu_allowlist_read_full(&f,buf,8,&off)==-EACCES&&off==0);
 fixture(4,784);disk_size=3;off=0;CHECK(ksu_allowlist_read_full(&f,buf,8,&off)==3&&off==3);
 fixture(4,784);step=2;off=0;CHECK(ksu_allowlist_write_full(&f,"12345678",8,&off)==8&&off==8&&!memcmp(disk,"12345678",8));
 fixture(4,784);write_error=-ENOSPC;off=0;CHECK(ksu_allowlist_write_full(&f,buf,8,&off)==-ENOSPC&&off==0);
 fixture(4,784);write_error=-999;off=0;CHECK(ksu_allowlist_write_full(&f,buf,8,&off)==-EIO);
 fixture(4,784);ksu_load_allow_list();CHECK(installed==1&&active==&original&&restore_count==1&&migrations==0);
 fixture(4,784);step=1;ksu_load_allow_list();CHECK(installed==1&&active==&original);
 fixture(3,776);ksu_load_allow_list();CHECK(installed==1&&migrations==1&&active==&original);
 fixture(2,776);step=3;ksu_load_allow_list();CHECK(installed==1&&migrations==1);
 fixture(4,0);ksu_load_allow_list();CHECK(installed==0&&active==&original);
 fixture(4,784);opens_error=-ENOENT;ksu_load_allow_list();CHECK(installed==0&&active==&original&&restore_count==1);
 fixture(4,784);read_error=-EACCES;ksu_load_allow_list();CHECK(installed==0&&active==&original);
 fixture(4,784);disk[0]=0;ksu_load_allow_list();CHECK(installed==0&&active==&original);
 fixture(5,784);ksu_load_allow_list();CHECK(installed==0&&migrations==0);
 fixture(4,783);ksu_load_allow_list();CHECK(installed==0&&active==&original);
 fixture(3,775);ksu_load_allow_list();CHECK(installed==0&&migrations==0);
 fixture(4,784);memset(disk+12,'X',256);ksu_load_allow_list();CHECK(installed==0&&active==&original);
 fixture(4,784);f.inode.i_mode=S_IFDIR;ksu_load_allow_list();CHECK(installed==0&&active==&original);
 fixture(4,784);f.inode.size=800;ksu_load_allow_list();CHECK(installed==0);
 fixture(4,784);disk_size=400;ksu_load_allow_list();CHECK(installed==0&&active==&original&&migrations==0);
 fixture(4,784);ksu_cred=NULL;ksu_load_allow_list();CHECK(installed==0&&restore_count==0);ksu_cred=&elevated;
 fixture(4,784);step=3;do_persistent_allow_list(calloc(1,sizeof(struct callback_head)));CHECK(active==&original&&restore_count==1&&fsync_calls==1&&freed==1);
 fixture(4,784);write_error=-ENOSPC;do_persistent_allow_list(calloc(1,sizeof(struct callback_head)));CHECK(active==&original&&restore_count==1&&fsync_calls==1&&freed==2);
 fixture(4,784);opens_error=-EACCES;do_persistent_allow_list(calloc(1,sizeof(struct callback_head)));CHECK(active==&original&&restore_count==1&&fsync_calls==1&&freed==3);
 fixture(4,784);fsync_error=-EIO;do_persistent_allow_list(calloc(1,sizeof(struct callback_head)));CHECK(active==&original&&restore_count==1&&fsync_calls==2&&freed==4);
 struct mount m={false};f.f_path.mnt=&m;struct linux_binprm b={0,&f,"/data/adb/ksud"};
 struct task_security_struct old={73},new={74};bounded_error=-EACCES;
 CHECK(check_nnp_nosuid(&b,&old,&new)==0);
 b.unsafe=LSM_UNSAFE_NO_NEW_PRIVS;CHECK(check_nnp_nosuid(&b,&old,&new)==-EPERM);
 b.unsafe=0;b.filename="/data/adb/other";CHECK(check_nnp_nosuid(&b,&old,&new)==-EACCES);
 b.filename=NULL;CHECK(check_nnp_nosuid(&b,&old,&new)==-EACCES);
 b.filename="/data/adb/ksud";old.sid=99;CHECK(check_nnp_nosuid(&b,&old,&new)==-EACCES);
 old.sid=73;new.sid=99;CHECK(check_nnp_nosuid(&b,&old,&new)==-EACCES);
 new.sid=73;CHECK(check_nnp_nosuid(&b,&old,&new)==0);
 new.sid=74;m.suid=true;CHECK(check_nnp_nosuid(&b,&old,&new)==0);
 printf("%d fault-injection assertions passed\n",cases);return 0;
}
'''
(out/'regression.c').write_text(header+body+tests)
subprocess.run(['gcc','-Wall','-Wextra','-Werror','-Wno-sign-compare','-fsanitize=address,undefined','-g',str(out/'regression.c'),'-o',str(out/'regression')],check=True)
result=subprocess.run([str(out/'regression')],check=True,capture_output=True,text=True)
print(result.stdout)
(out/'regression.json').write_text(json.dumps({'result':result.stdout.strip(),'actual_functions_extracted':True,'asan_ubsan':True,'limits':'Host stubs do not validate on-phone SELinux, filesystem or module execution.'},indent=2))
