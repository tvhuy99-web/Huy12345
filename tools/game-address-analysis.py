#!/usr/bin/env python3
"""Inspect code at phone-observed addresses without executing or publishing the game."""
import hashlib,json,subprocess,sys
from pathlib import Path,PurePosixPath
import rarfile,pefile
from capstone import Cs,CS_ARCH_X86,CS_MODE_32,CS_GRP_CALL,CS_OP_IMM,CS_OP_MEM

archive,destination,results=map(Path,sys.argv[1:4])
destination.mkdir(parents=True,exist_ok=True);results.mkdir(parents=True,exist_ok=True)
digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
assert digest=='dc7a617ca3e08e9e9f7d1e3bf6b636534e9e70bc7fee676d6293de506f12d831'
with rarfile.RarFile(archive) as package:
    package.setpassword('ztj');entries=package.infolist()
    for row in entries:
        path=PurePosixPath(row.filename.replace('\\','/'))
        assert not path.is_absolute() and '..' not in path.parts and ':' not in path.parts[0] and not row.is_symlink()
    games=[row.filename for row in entries if PurePosixPath(row.filename.replace('\\','/')).name.lower()=='zetianji.exe']
    assert len(games)==1
    parent=str(PurePosixPath(games[0].replace('\\','/')).parent)
    wanted=[row.filename for row in entries if str(PurePosixPath(row.filename.replace('\\','/')).parent)==parent
            and PurePosixPath(row.filename.replace('\\','/')).name.lower() in ('zetianji.exe','resource.irf')]
    assert len(wanted)==2
subprocess.run(['unrar','x','-pztj','-o+','-idq',str(archive),*wanted,str(destination)+'/'],check=True)
engine=Cs(CS_ARCH_X86,CS_MODE_32);engine.detail=True;engine.skipdata=True
summary={'archiveSha256':digest,'images':[]}
for name,points in [('zetianji.exe',[0x18ed09,0x18e5f0,0xa2d0b,0x10a53b,0x213bf]),('resource.irf',[0xc2685f,0x1f24,0x20e9,0x10db5,0xfe4c,0x11f898])]:
    found=list(destination.rglob(name));assert len(found)==1
    path=found[0];raw=path.read_bytes();pe=pefile.PE(data=raw)
    base=pe.OPTIONAL_HEADER.ImageBase;image=pe.get_memory_mapped_image()
    imports={entry.address:(module.dll.decode(errors='replace')+'!'+(entry.name.decode(errors='replace') if entry.name else '#'+str(entry.ordinal)))
             for module in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]) for entry in module.imports}
    exports={base+entry.address:(entry.name.decode(errors='replace') if entry.name else '#'+str(entry.ordinal))
             for entry in getattr(getattr(pe,'DIRECTORY_ENTRY_EXPORT',None),'symbols',[])}
    info={'name':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'base':hex(base),
          'imports':{hex(k):v for k,v in imports.items()},'exports':{hex(k):v for k,v in exports.items()},'points':[hex(p) for p in points]}
    summary['images'].append(info)
    lines=[]
    for point in points:
        start=max(0,point-0x200);prolog=image.rfind(b'\x55\x8b\xec',max(0,point-0x800),point)
        if prolog>=0:start=prolog
        stop=min(len(image),point+0x250)
        lines.append('\nPOINT RVA '+hex(point)+' image VA '+hex(base+point)+' decode start '+hex(base+start)+'\n')
        for ins in engine.disasm(image[start:stop],base+start):
            hint=''
            if ins.id:
                for op in ins.operands:
                    if op.type==CS_OP_MEM and not op.mem.base and not op.mem.index:
                        target=op.mem.disp&0xffffffff
                        if target in imports:hint+=' ; '+imports[target]
                    if op.type==CS_OP_IMM and ins.group(CS_GRP_CALL):
                        target=op.imm&0xffffffff
                        hint+=' ; CALL RVA '+hex((target-base)&0xffffffff)
                        if target in exports:hint+=' '+exports[target]
            lines.append(f'{ins.address:08x}: {ins.bytes.hex():24s} {ins.mnemonic:8s} {ins.op_str}'+hint)
    (results/(name+'-phone-addresses.txt')).write_text('\n'.join(lines),encoding='utf-8')
(results/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print('Verified archive; saved disassembly around exact phone-observed code addresses, without game binaries')

# Run only the pinned CPU routine, never the game entry point.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'runtime-nvda'))
import game_startup,os,tempfile,shutil
wine=shutil.which('wine') or '/usr/lib/wine/wine64'
game=next(destination.rglob('zetianji.exe'));original=game.read_bytes()
fixed=game_startup.patch_bytes(original);patched=game.with_name('game-patched.exe');patched.write_bytes(fixed)
fixture=destination/'cpu-fixture.exe'
subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-cast-function-type','-Wl,--image-base,0x20000000','-Wl,--disable-dynamicbase',
               'tools/game-cpu-fixture.c','-o',str(fixture)],check=True)
reports={}
with tempfile.TemporaryDirectory(prefix='game-cpu-prefix-') as temporary:
    env=dict(os.environ,WINEPREFIX=temporary,WINEARCH='win64',WINEDEBUG='-all',WINEDLLOVERRIDES='mscoree,mshtml=')
    try:
        for label,path,mode in [('original-zero',game,'zero'),('fixed-zero',patched,'zero'),('original-normal',game,'normal'),('fixed-normal',patched,'normal'),('original-failure',game,'failure'),('fixed-failure',patched,'failure')]:
            row=subprocess.run([wine,str(fixture),str(path),mode],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
            output=row.stdout.decode(errors='replace');reports[label]={'exit':row.returncode,'output':output[-6000:]}
            if label=='original-zero':assert row.returncode==77, reports[label]
            else:
                assert row.returncode==0,reports[label]
                reports[label]['value']=json.loads(output.strip().splitlines()[-1])
            print(label,reports[label],flush=True)
        assert reports['fixed-zero']['value']['result']==-1 and reports['fixed-zero']['value']['sleeps']==1
        assert reports['original-normal']['value']==reports['fixed-normal']['value']
        assert reports['original-failure']['value']==reports['fixed-failure']['value']
        assert reports['fixed-failure']['value']['result']==-1
        assert game.read_bytes()==original
        game_startup.configure(game,True);assert game.read_bytes()==fixed
        game_startup.configure(game,True);assert game.read_bytes()==fixed
        game_startup.configure(game,False);assert game.read_bytes()==original
        reports['roundtrip']='byte-for-byte original restored; repeated apply preserves original backup'
        reports['patchedSha256']=hashlib.sha256(fixed).hexdigest()
    finally:
        (results/'cpu-regression.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
        subprocess.run(['/usr/lib/wine/wineserver','-k'],env=env,timeout=10,check=False)
