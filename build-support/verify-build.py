#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import argparse,collections,hashlib,json,struct,subprocess,zlib
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--nm',required=True);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();checks={}
cfg=(a.out/'.config').read_text().splitlines()
required=['CONFIG_KSU=y','CONFIG_KSU_MANUAL_HOOK=y','CONFIG_MODVERSIONS=y',
 '# CONFIG_KPROBES is not set','# CONFIG_KSU_DEBUG is not set',
 'CONFIG_SND_SOC_MSM_STUB=y','CONFIG_SND_SOC_MSM_HDMI_CODEC_RX=y','CONFIG_SND_SOC_TAS2559=y']
checks['required_config']=all(x in cfg for x in required)
checks['manager_and_policy_enabled']=not any(x in cfg for x in ['CONFIG_KSU_DISABLE_MANAGER=y','CONFIG_KSU_DISABLE_POLICY=y'])
def symvers(path):
    return {v[1]:int(v[0],16) for l in path.read_text().splitlines() if len(v:=l.split())>=3}
ref=symvers(a.root/'build-support/reference/tested.Module.symvers')
actual=symvers(a.out/'Module.symvers')
bad=[k for k,v in ref.items() if actual.get(k)!=v]
extra=sorted(set(actual)-set(ref))
checks['all_tested_export_crcs_match']=not bad and not extra
symbols=subprocess.check_output([a.nm,str(a.out/'vmlinux')],text=True)
linked={l.split()[-1] for l in symbols.splitlines() if len(l.split())>=3}
checks['ksu_linked']=all(x in linked for x in ['kernelsu_init','ksu_load_allow_list','is_ksu_transition','ksu_filp_open_nonotify_compat'])
data=(a.out/'arch/arm64/boot/Image.gz-dtb').read_bytes()
d=zlib.decompressobj(31);raw=d.decompress(data)+d.flush()
checks['arm64_gzip']=d.eof and raw[0x38:0x3c]==b'ARM\x64'
tail=d.unused_data;dtbs=[]
while tail:
    assert tail[:4]==b'\xd0\x0d\xfe\xed','Malformed DTB trailer'
    n=struct.unpack_from('>I',tail,4)[0];assert 40<=n<=len(tail)
    dtbs.append({'bytes':n,'sha256':hashlib.sha256(tail[:n]).hexdigest()})
    tail=tail[n:]
tested_dtbs=json.loads((a.root/'build-support/reference/tested-dtbs.json').read_text())
checks['dtbs_identical_to_tested_image']=len(dtbs)==54 and collections.Counter(x['sha256'] for x in dtbs)==collections.Counter(tested_dtbs['sha256'])
result={'checks':checks,'passed':all(checks.values()),'export_count':len(actual),
 'mismatched_or_missing_exports':bad,'unexpected_exports':extra,'dtbs':dtbs,
 'kernel_sha256':hashlib.sha256(data).hexdigest(),
 'limits':'Export comparison covers the tested kernel interface; this is not a phone runtime test.'}
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'checks':checks,'passed':result['passed'],'exports':len(actual)}))
assert result['passed'],'Do not publish artifacts from a failed validation'
