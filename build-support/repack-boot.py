# SPDX-License-Identifier: GPL-2.0-only
#!/usr/bin/env python3
"""Package verified kernels with an unchanged stock v1 ramdisk; never flash."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

def sha(data): return hashlib.sha256(data).hexdigest()
def aligned(size,page): return (size+page-1)//page*page
def parse(data):
    assert data[:8]==b'ANDROID!', 'Unexpected boot magic'
    values=struct.unpack_from('<10I',data,8)
    keys=['kernel_size','kernel_addr','ramdisk_size','ramdisk_addr','second_size','second_addr','tags_addr','page_size','header_version','os_version']
    h=dict(zip(keys,values))
    assert h['header_version']==1, 'Only audited v1 format supported'
    assert h['page_size']==4096
    size,offset,header_size=struct.unpack_from('<IQI',data,1632)
    assert size==offset==0 and header_size==1648, 'Unexpected recovery DTBO'
    h.update(recovery_dtbo_size=size,recovery_dtbo_offset=offset,header_size=header_size)
    h['board']=data[48:64].split(b'\0')[0].decode('ascii')
    h['cmdline']=(data[64:576].split(b'\0')[0]+data[608:1632].split(b'\0')[0]).decode('ascii')
    pos=h['page_size']; parts={}
    for name in ['kernel','ramdisk','second']:
        size=h[name+'_size']
        assert pos+size<=len(data)
        parts[name]=data[pos:pos+size]
        pos+=aligned(size,h['page_size'])
    h['payload_end']=pos
    return h,parts,data[pos:]

def cpio_entries(compressed):
    raw=gzip.decompress(compressed); pos=0; entries={}
    while pos+110<=len(raw):
        assert raw[pos:pos+6] in (b'070701',b'070702'), 'Unexpected ramdisk CPIO format'
        fields=[int(raw[pos+6+i*8:pos+14+i*8],16) for i in range(13)]
        size,namesize=fields[6],fields[11]
        name=raw[pos+110:pos+110+namesize-1].decode('utf-8')
        begin=aligned(pos+110+namesize,4)
        content=raw[begin:begin+size]
        assert len(content)==size
        pos=aligned(begin+size,4)
        if name=='TRAILER!!!': break
        entries[name]=content
    else: raise RuntimeError('CPIO trailer absent')
    return entries

def kernel_info(raw):
    d=zlib.decompressobj(31); image=d.decompress(raw)+d.flush()
    assert d.eof and image[0x38:0x3c]==b'ARM\x64'
    tail=d.unused_data; dtbs=[]
    while tail:
        assert tail[:4]==b'\xd0\x0d\xfe\xed'
        size=struct.unpack_from('>I',tail,4)[0]
        assert 40<=size<=len(tail)
        dtbs.append({'bytes':size,'sha256':sha(tail[:size]),'polaris':b'polaris' in tail[:size]})
        tail=tail[size:]
    assert dtbs
    return {'uncompressed_bytes':len(image),'dtbs':dtbs}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--stock',required=True,type=Path)
    ap.add_argument('--kernel',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args()
    raw=args.stock.read_bytes()
    assert sha(raw)=='729d574ce3c67ce7516b2a65a1d7aaf7acc3a5e69a0f0cbfcee7098216689de2', 'Use the validated original MIUI boot.img; do not supply a patched boot'
    h,parts,tail=parse(raw)
    assert args.output.resolve() not in (args.stock.resolve(),args.kernel.resolve()), 'Never overwrite inputs'
    assert not args.output.exists(), 'Choose a new output filename'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    import tempfile
    tool=Path(__file__).with_name('mkbootimg.py')
    assert sha(tool.read_bytes())=='4d87cfb5482efcd556008cfe563ae442a934acb7ef0df082d422307f26a120b7'
    info=kernel_info(args.kernel.read_bytes())
    from collections import Counter
    tested=json.loads(Path(__file__).with_name('reference').joinpath('tested-dtbs.json').read_text())
    assert len(info['dtbs'])==54 and Counter(d['sha256'] for d in info['dtbs'])==Counter(tested['sha256'])
    with tempfile.TemporaryDirectory(prefix='polaris-boot-') as tmp:
        tmp=Path(tmp)
        (tmp/'ramdisk').write_bytes(parts['ramdisk'])
        version=h['os_version'];a,b,c=(version>>25)&127,(version>>18)&127,(version>>11)&127
        year=2000+((version>>4)&127);month=version&15
        cmd=[sys.executable,str(tool),'--header_version','1','--pagesize',str(h['page_size']),'--base','0','--kernel_offset',str(h['kernel_addr']),'--ramdisk_offset',str(h['ramdisk_addr']),'--second_offset',str(h['second_addr']),'--tags_offset',str(h['tags_addr']),'--board',h['board'],'--cmdline',h['cmdline'],'--os_version',f'{a}.{b}.{c}','--os_patch_level',f'{year}-{month:02d}-01','--ramdisk',str(tmp/'ramdisk')]
        if parts['second']:
            (tmp/'second').write_bytes(parts['second']);cmd+=['--second',str(tmp/'second')]
        entries=cpio_entries(parts['ramdisk'])
        assert not any(any(x in n.lower() for x in ['magisk','kitsune','.backup','.magisk']) for n in entries), 'Root-patched ramdisk'
        (tmp/'stock-kernel').write_bytes(parts['kernel'])
        subprocess.run(cmd+['--kernel',str(tmp/'stock-kernel'),'--output',str(tmp/'roundtrip')],check=True)
        assert (tmp/'roundtrip').read_bytes()==raw[:h['payload_end']], 'Header roundtrip differs'
        subprocess.run(cmd+['--kernel',str(args.kernel),'--output',str(tmp/'packed')],check=True)
        packed=(tmp/'packed').read_bytes();nh,np,nt=parse(packed)
        expected=dict(h);expected['kernel_size']=args.kernel.stat().st_size;expected['payload_end']=len(packed)
        assert nh==expected and not nt
        assert np['ramdisk']==parts['ramdisk'] and np['second']==parts['second'] and np['kernel']==args.kernel.read_bytes()
        subprocess.run(cmd+['--kernel',str(args.kernel),'--output',str(tmp/'repeat')],check=True)
        assert (tmp/'repeat').read_bytes()==packed
        args.output.write_bytes(packed)
    report={'bytes':len(packed),'sha256':sha(packed),'stock_ramdisk_unchanged':True,'repeat_identical':True,'boot_signature_removed':True,'kernel_sha256':sha(np['kernel']),'runtime_tested':False}
    args.output.with_suffix(args.output.suffix+'.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
