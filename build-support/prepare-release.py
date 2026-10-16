#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Validate a successful build artifact and prepare kernel-only release assets."""
import argparse
import hashlib
import json
import re
import shutil
import zipfile
import zlib
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--dist',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--commit',required=True)
p.add_argument('--run-id',required=True)
p.add_argument('--repository',required=True)
a=p.parse_args()
assert re.fullmatch(r'[0-9a-f]{40}',a.commit)
assert re.fullmatch(r'[0-9]+',a.run_id)
assert re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',a.repository)
required={'Image.gz-dtb','Module.symvers','kernel.config','SHA256SUMS','validation.json','build-manifest.json','provenance.json','COPYING','build.log'}
assert {f.name for f in a.dist.iterdir()}==required,'Unexpected or missing artifact files'
assert all(f.is_file() and not f.is_symlink() for f in a.dist.iterdir())
manifest=json.loads((a.dist/'build-manifest.json').read_text())
assert manifest['source_commit']==a.commit,'Artifact source commit does not match build run'
assert manifest['stock_boot_included'] is False and manifest['vendor_module_binaries_included'] is False
for name,info in manifest['files'].items():
    assert name in required
    data=(a.dist/name).read_bytes()
    assert len(data)==info['bytes'] and hashlib.sha256(data).hexdigest()==info['sha256'],name
assert {'Image.gz-dtb','Module.symvers','kernel.config','validation.json'}<=set(manifest['files'])
checked=set()
for line in (a.dist/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split()
    assert name in required and name not in checked
    assert hashlib.sha256((a.dist/name).read_bytes()).hexdigest()==digest,name
    checked.add(name)
assert {'Image.gz-dtb','Module.symvers','kernel.config'}<=checked
validation=json.loads((a.dist/'validation.json').read_text())
assert validation['passed'] is True and all(validation['checks'].values())
image=(a.dist/'Image.gz-dtb').read_bytes()
assert hashlib.sha256(image).hexdigest()==validation['kernel_sha256']
d=zlib.decompressobj(31);kernel=d.decompress(image)+d.flush()
assert d.eof and kernel[0x38:0x3c]==b'ARM\x64'
assert d.unused_data[:4]==b'\xd0\x0d\xfe\xed'
a.output.mkdir(parents=True,exist_ok=True)
assert not any(a.output.iterdir()),'Release output directory must be empty'
bundle=a.output/f'polaris-ksunext-{a.commit[:12]}.zip'
with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in sorted(required):
        info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o100644<<16
        z.writestr(info,(a.dist/name).read_bytes())
shutil.copyfile(a.dist/'Image.gz-dtb',a.output/'Image.gz-dtb')
(a.output/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}\n' for f in [bundle,a.output/'Image.gz-dtb']))
tag=manifest['ksu_tag']
assert re.fullmatch(r'[A-Za-z0-9_.+-]+',tag)
(a.output/'title.txt').write_text(f'MIX 2S KernelSU Next {tag} · {a.commit[:8]}')
(a.output/'RELEASE.md').write_text(f'''适用于小米 MIX 2S（polaris），MIUI V12.5.1.0.QDGCNXM / Android 10。

- KernelSU Next：`{tag}`（{manifest['ksu_version']}）。
- 对应源码：[{a.commit[:12]}](https://github.com/{a.repository}/tree/{a.commit})。
- 成功构建及校验：[Actions 记录](https://github.com/{a.repository}/actions/runs/{a.run_id})。

下载 `polaris-ksunext-{a.commit[:12]}.zip` 可取得内核、配置、符号表、来源、许可证、验证报告及构建日志；`Image.gz-dtb` 同时提供单独下载。`SHA256SUMS` 用于核对这两份附件。

**这些附件不是完整 boot.img，不要将 Image.gz-dtb 直接刷入 boot 分区。** 请按照[对应版本 README](https://github.com/{a.repository}/blob/{a.commit}/README.md#本地打包-bootimg)，使用自己保存的匹配系统原版 boot 在本地打包。

附件不含原厂 boot、ramdisk 或厂商驱动二进制。自动校验通过不等于这份新构建镜像已完成实机测试。对应完整源码可通过本 Release 的 Source code 下载，许可证及构建说明均在源码中保留。
''')
print(json.dumps({'commit':a.commit,'run_id':a.run_id,'assets':[bundle.name,'Image.gz-dtb','SHA256SUMS'],'validated':True}))
