#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import subprocess,json
r=Path(__file__).resolve().parents[2]
s=r/'kernel/kernelsu/compat/kernel_compat.c'
o=r/'.host-tests'
o.mkdir(exist_ok=True)
t=s.read_text();start=t.index('static struct file *ksu_open_with_init_keyring(');end=t.index('struct file *ksu_filp_open_compat(',start)
fn=t[start:end]
assert 'commit_creds' not in fn
prefix=r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <errno.h>
#include <sys/types.h>
#include <fcntl.h>
#define KERNEL_VERSION(a,b,c) ((a)*65536+(b)*256+(c))
#ifndef LINUX_VERSION_CODE
#define LINUX_VERSION_CODE KERNEL_VERSION(4,9,186)
#endif
#define READ_ONCE(x) (x)
#define ERR_PTR(x) ((void *)(intptr_t)(x))
#define PTR_ERR(x) ((intptr_t)(x))
#define LOOKUP_FOLLOW 1
#define __FMODE_NONOTIFY 0x4000000
typedef unsigned short umode_t;
struct key {int serial;};
struct cred { struct key *session_keyring; int uid,sid; };
struct path {int dummy;};
struct file {int dummy;};
struct key initkey={1}, ownkey={2};
struct key *init_session_keyring=&initkey;
struct cred caller={NULL,0,74};
const struct cred *subjective=&caller;
int allocation_error,install_error,path_error,open_error,allocations,releases,overrides,reverts,cases;
struct file output;
const struct cred *current_cred(void) {return subjective;}
struct cred *prepare_creds(void) {if(allocation_error)return NULL;struct cred *c=malloc(sizeof(*c));*c=*subjective;allocations++;return c;}
int install_session_keyring_to_cred(struct cred *c,struct key *k) {if(install_error)return install_error;c->session_keyring=k;return 0;}
void abort_creds(struct cred *c) {releases++;free(c);}
void put_cred(struct cred *c) {releases++;free(c);}
const struct cred *override_creds(const struct cred *c) {const struct cred *s=subjective;subjective=c;overrides++;return s;}
void revert_creds(const struct cred *c) {subjective=c;reverts++;}
void verify_open(void) {
 if(subjective->uid!=caller.uid||subjective->sid!=caller.sid)abort();
#if LINUX_VERSION_CODE < KERNEL_VERSION(4,10,0)
 if(init_session_keyring&&!caller.session_keyring&&subjective->session_keyring!=init_session_keyring)abort();
#endif
}
struct file *filp_open(const char *p,int flags,umode_t mode) {(void)p;(void)flags;(void)mode;verify_open();return open_error?ERR_PTR(open_error):&output;}
int kern_path(const char *p,int flags,struct path *out) {(void)p;(void)flags;(void)out;verify_open();return path_error;}
struct file *dentry_open(struct path *p,int flags,const struct cred *c) {(void)p;(void)flags;if(c!=subjective)abort();verify_open();return open_error?ERR_PTR(open_error):&output;}
void path_put(struct path *p) {(void)p;}
#define CHECK(c) do {cases++;if(!(c)){fprintf(stderr,"FAIL %d: %s\n",__LINE__,#c);exit(1);}}while(0)
void reset(void) {caller.session_keyring=NULL;subjective=&caller;init_session_keyring=&initkey;allocation_error=install_error=path_error=open_error=allocations=releases=overrides=reverts=0;}
void restored(void) {CHECK(subjective==&caller&&caller.session_keyring==NULL&&allocations==releases&&overrides==reverts);}
'''
tests=r'''
int main(void) {
 reset();CHECK(ksu_open_with_init_keyring("file",0,0,false)==&output);restored();
 reset();CHECK(ksu_open_with_init_keyring("file",O_NOFOLLOW,0,true)==&output);restored();
 reset();path_error=-ENOENT;CHECK(PTR_ERR(ksu_open_with_init_keyring("file",0,0,true))==-ENOENT);restored();
 reset();open_error=-EACCES;CHECK(PTR_ERR(ksu_open_with_init_keyring("file",0,0,false))==-EACCES);restored();
 reset();open_error=-EACCES;CHECK(PTR_ERR(ksu_open_with_init_keyring("file",0,0,true))==-EACCES);restored();
#if LINUX_VERSION_CODE < KERNEL_VERSION(4,10,0)
 reset();allocation_error=1;CHECK(PTR_ERR(ksu_open_with_init_keyring("file",0,0,true))==-ENOMEM);restored();
 reset();install_error=-EINVAL;CHECK(PTR_ERR(ksu_open_with_init_keyring("file",0,0,false))==-EINVAL);restored();
#endif
 reset();init_session_keyring=NULL;CHECK(ksu_open_with_init_keyring("file",0,0,false)==&output);CHECK(allocations==0);restored();
 reset();caller.session_keyring=&ownkey;CHECK(ksu_open_with_init_keyring("file",0,0,true)==&output);CHECK(allocations==0&&subjective==&caller&&caller.session_keyring==&ownkey);
 printf("%d keyring/credential assertions passed\n",cases);return 0;
}
'''
(o/'keyring-regression.c').write_text(prefix+fn+tests)
results=[]
for version,label in [(0x0409ba,'4.9'),(0x040a00,'4.10')]:
    binary=o/('keyring-regression-'+label)
    subprocess.run(['gcc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g','-DLINUX_VERSION_CODE='+str(version),str(o/'keyring-regression.c'),'-o',str(binary)],check=True)
    result=subprocess.run([str(binary)],capture_output=True,text=True,check=True)
    results.append({'version':label,'result':result.stdout.strip()})
(o/'keyring-regression.json').write_text(json.dumps({'actual_function_extracted':True,'asan_ubsan':True,'no_commit_creds':True,'results':results,'limits':'Host stubs do not recreate Android fscrypt or manager discovery.'},indent=2))
print(json.dumps(results))
