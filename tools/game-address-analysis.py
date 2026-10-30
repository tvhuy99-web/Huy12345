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

# Emulate the exact x86 routine with controlled NT replies; no game entry point.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'runtime-nvda'))
import game_startup
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_FPCW
import struct,tempfile
game=next(destination.rglob('zetianji.exe'));original=game.read_bytes();fixed=game_startup.patch_bytes(original)
def evaluate(data,mode):
    pe=pefile.PE(data=data);mapped=pe.get_memory_mapped_image()
    uc=Uc(UC_ARCH_X86,UC_MODE_32);uc.mem_map(0x400000,(len(mapped)+4095)&~4095);uc.mem_write(0x400000,mapped)
    uc.mem_map(0x10000000,0x20000);uc.mem_map(0x0f000000,0x2000)
    resolve,module,sleep,query,finish=0x0f000100,0x0f000200,0x0f000300,0x0f000400,0x0f000f00
    for rva,value in [(0x1cd2d8,resolve),(0x1cd2dc,module),(0x1cd310,sleep)]:uc.mem_write(0x400000+rva,struct.pack('<I',value))
    esp=0x1000f000;uc.mem_write(esp,struct.pack('<I',finish));uc.reg_write(UC_X86_REG_ESP,esp)
    uc.reg_write(UC_X86_REG_ECX,0x10010000);uc.reg_write(UC_X86_REG_FPCW,0x37f)
    state=dict(sleeps=0,clockReads=0,idleReads=0,loop=False,finished=False,ntCalls=[])
    def intercept(uc,address,size,unused):
        if address==finish:state['finished']=True;uc.emu_stop();return
        if address not in (0x58e8b0,resolve,module,sleep,query):return
        stack=uc.reg_read(UC_X86_REG_ESP)
        def word(index):return struct.unpack('<I',uc.mem_read(stack+4*index,4))[0]
        result=0;arguments=0
        if address==0x58e8b0:result=1
        elif address==module:arguments=1;result=0x7bc00000
        elif address==resolve:arguments=2;result=query
        elif address==sleep:
            arguments=1;assert word(1)==800;state['sleeps']+=1
            if state['sleeps']>2:state['loop']=True;uc.emu_stop();return
        elif address==query:
            arguments=4;kind,buffer,length,returned=[word(i) for i in range(1,5)]
            state['ntCalls'].append(kind);uc.mem_write(buffer,bytes(length))
            if mode=='failure':result=0xc0000001
            elif kind==0 and length==44:uc.mem_write(buffer+40,b'\x04')
            elif kind==3 and length==32:
                state['clockReads']+=1;uc.mem_write(buffer+8,struct.pack('<Q',100000000+state['clockReads']*8000000))
            elif kind==2 and length==312:
                state['idleReads']+=1;uc.mem_write(buffer,struct.pack('<Q',0 if mode=='zero' else 1000000+state['idleReads']*4000000))
            else:raise AssertionError((kind,length))
            if returned:uc.mem_write(returned,struct.pack('<I',length))
        uc.reg_write(UC_X86_REG_EAX,result);uc.reg_write(UC_X86_REG_EIP,word(0));uc.reg_write(UC_X86_REG_ESP,stack+4*(arguments+1))
    uc.hook_add(UC_HOOK_CODE,intercept)
    uc.emu_start(0x58eb40,0,count=1000000)
    value=uc.reg_read(UC_X86_REG_EAX);state['result']=value if value<0x80000000 else value-0x100000000
    assert state['loop'] or state['finished'],'Instruction budget expired'
    return state
reports={'engine':'Unicorn x86 instruction emulation of the pinned game CPU routine'}
for label,data,mode in [('original-zero',original,'zero'),('fixed-zero',fixed,'zero'),('original-normal',original,'normal'),('fixed-normal',fixed,'normal'),('original-failure',original,'failure'),('fixed-failure',fixed,'failure')]:
    reports[label]=evaluate(data,mode);print(label,reports[label],flush=True)
assert reports['original-zero']['loop']
assert reports['fixed-zero']['finished'] and reports['fixed-zero']['result']==-1 and reports['fixed-zero']['sleeps']==1
assert reports['original-normal']==reports['fixed-normal']
assert reports['original-failure']==reports['fixed-failure']
assert reports['fixed-failure']['result']==-1
game_startup.configure(game,True);assert game.read_bytes()==fixed
game_startup.configure(game,True);assert game.read_bytes()==fixed
game_startup.configure(game,False);assert game.read_bytes()==original
reports['roundtrip']='byte-for-byte original restored; repeat apply preserves original'
reports['patchedSha256']=hashlib.sha256(fixed).hexdigest()
(results/'cpu-regression.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
