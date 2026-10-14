#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import hashlib,json,subprocess,sys
from pathlib import Path
root,dist=map(Path,sys.argv[1:])
try:commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL).strip()
except subprocess.CalledProcessError:commit=None
provenance=json.loads((root/'build-support/provenance.json').read_text())
result={'source_commit':commit,'ksu_version':33294,'ksu_tag':'v3.4.0-legacy',
 'toolchain':provenance['toolchain'],'files':{},'stock_boot_included':False,
 'vendor_module_binaries_included':False,'runtime_tested_image':provenance['tested_boot_sha256'],
 'note':'This build is from the validated source with packaging-only changes; hash need not equal the tested image.'}
for name in ['Image.gz-dtb','Module.symvers','kernel.config','validation.json']:
    data=(dist/name).read_bytes();result['files'][name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
(dist/'build-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
