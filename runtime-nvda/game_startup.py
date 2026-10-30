# SPDX-License-Identifier: MIT
"""Reversible, hash-pinned fix for Zetianji's zero-idle CPU sampling loop."""
import hashlib
import json
from pathlib import Path
import struct
if __package__:
    from . import game_voice
else:
    import game_voice

ORIGINAL_SHA256='678d22fbf2383bf4f8fedb9fc3bb04be7771a051fa65f2d8820943880aa2089d'
BACKUP='winlator-startup-original.bin'
MANIFEST='winlator-startup-backup.json'
BRANCH=0x18ed3c
CAVE=0x18e601
ERROR_RETURN=0x18edfe
CONTINUE=0x18ed42

def digest(data):return hashlib.sha256(data).hexdigest()

def offset(data,rva,length):
    try:
        pe=struct.unpack_from('<I',data,0x3c)[0]
        machine,count=struct.unpack_from('<HH',data,pe+4)
        optional=struct.unpack_from('<H',data,pe+20)[0]
        if data[:2]!=b'MZ' or data[pe:pe+4]!=b'PE\0\0' or machine!=0x14c or struct.unpack_from('<H',data,pe+24)[0]!=0x10b:
            raise ValueError('Unsupported PE32')
        for i in range(min(count,96)):
            at=pe+24+optional+40*i
            virtual,start,size,raw=struct.unpack_from('<IIII',data,at+8)
            if start<=rva and rva-start+length<=min(virtual,size):
                result=raw+rva-start
                if result+length<=len(data):return result
    except (struct.error,IndexError) as error:raise ValueError('Invalid executable') from error
    raise ValueError('Invalid code address')

def patch_bytes(original):
    if digest(original)!=ORIGINAL_SHA256:raise ValueError('Unsupported Zetianji executable')
    branch=offset(original,BRANCH,6);cave=offset(original,CAVE,15)
    if original[branch:branch+6]!=bytes.fromhex('74 a8 db 44 24 74') or original[cave:cave+15]!=b'\x90'*15:
        raise ValueError('Unexpected CPU sampler instructions')
    # Preserve ZF, the original FILD and both nonzero-counter paths. A still-zero
    # cached idle value takes the function's existing -1/error epilogue.
    jump=b'\xe9'+struct.pack('<i',CAVE-(BRANCH+5))+b'\x90'
    stub=b'\x0f\x84'+struct.pack('<i',ERROR_RETURN-(CAVE+6))+bytes.fromhex('db 44 24 74')
    stub+=b'\xe9'+struct.pack('<i',CONTINUE-(CAVE+15))
    patched=bytearray(original);patched[branch:branch+6]=jump;patched[cave:cave+15]=stub
    return bytes(patched)

def configure(path,enabled,trace=lambda row:None):
    path=Path(path)
    if path.name.lower()!='zetianji.exe':raise ValueError('Select zetianji.exe')
    backup=path.parent/BACKUP;manifest=path.parent/MANIFEST
    stage='read-target'
    try:
        trace(dict(stage=stage));current=game_voice.small_file(path,8*1024*1024)
        trace(dict(stage='target-identity',sha256=digest(current),bytes=len(current)))
        if backup.exists():
            stage='verify-backup';trace(dict(stage=stage));original=game_voice.small_file(backup,8*1024*1024)
        else:original=current
        stage='verify-instructions';trace(dict(stage=stage))
        fixed=patch_bytes(original);known=(digest(original),digest(fixed))
        if manifest.exists():
            metadata=json.loads(game_voice.small_file(manifest,4096).decode('utf-8'))
            if metadata.get('kind')!='zetianji-zero-idle' or metadata.get('originalSha256')!=known[0] or metadata.get('patchedSha256')!=known[1]:
                raise ValueError('Unknown startup manifest')
        if digest(current) not in known:raise ValueError('Executable has other modifications')
        if enabled:
            if not backup.exists():
                stage='backup-original';trace(dict(stage=stage));game_voice.atomic_write(backup,original)
            stage='write-manifest';trace(dict(stage=stage))
            game_voice.atomic_write(manifest,json.dumps(dict(version=1,kind='zetianji-zero-idle',originalSha256=known[0],patchedSha256=known[1],target='zetianji.exe')).encode())
            stage='write-executable';trace(dict(stage=stage));game_voice.atomic_write(path,fixed)
            result='startup-fix-enabled'
        else:
            stage='restore-original';trace(dict(stage=stage));game_voice.atomic_write(path,original)
            if manifest.exists():manifest.unlink()
            result='startup-fix-restored'
        trace(dict(stage='complete',result=result,sha256=digest(game_voice.small_file(path,8*1024*1024)),bytes=len(original)))
        return result
    except (OSError,ValueError) as error:
        error.diagnosticStage=stage;raise
