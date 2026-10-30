# SPDX-License-Identifier: MIT
"""Explicit, reversible instrumentation of the examined x86 xinyitts ABI only."""
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile

EXPORTS = ('xyttsGetCount xyttsGetDeviceCount xyttsGetDeviceNameA xyttsGetDeviceNameW '
           'xyttsGetFirstVoiceA xyttsGetFirstVoiceW xyttsGetNextVoiceA xyttsGetNextVoiceW '
           'xyttsGetPitch xyttsGetSpeed xyttsGetVoiceA xyttsGetVoiceW xyttsGetVolume '
           'xyttsInitA xyttsInitW xyttsPause xyttsResume xyttsSave xyttsSetDevice '
           'xyttsSetNotify xyttsSetPitch xyttsSetSpeed xyttsSetVoiceA xyttsSetVoiceW '
           'xyttsSetVolume xyttsSpeak2A xyttsSpeak2W xyttsSpeakA xyttsSpeakW '
           'xyttsStop xyttsUninit').split()
ORIGINAL = 'winlator-voice-original.dll'
MANIFEST = 'winlator-voice-backup.json'


def pe_exports(data):
    """Validate PE32 and return named ordinal exports without loading game code."""
    def u16(at): return struct.unpack_from('<H', data, at)[0]
    def u32(at): return struct.unpack_from('<I', data, at)[0]
    try:
        pe = u32(0x3c)
        if data[:2] != b'MZ' or data[pe:pe+4] != b'PE\0\0' or u16(pe+4) != 0x14c or u16(pe+24) != 0x10b:
            raise ValueError('Unsupported PE32')
        sections = pe+24+u16(pe+20)
        def offset(rva):
            for i in range(min(u16(pe+6), 96)):
                at=sections+40*i; size=u32(at+16); start=u32(at+12)
                if start <= rva < start+size:
                    value=u32(at+20)+rva-start
                    if value >= len(data): break
                    return value
            raise ValueError('Invalid RVA')
        at=offset(u32(pe+24+96)); base=u32(at+16); count=u32(at+24)
        if u32(at+20) != count: raise ValueError('Unnamed exports are not supported')
        if not 1 <= count <= 128: raise ValueError('Invalid export count')
        names=offset(u32(at+32)); ordinals=offset(u32(at+36)); found={}
        for i in range(count):
            start=offset(u32(names+4*i)); end=data.index(b'\0',start,start+128)
            found[data[start:end].decode('ascii')]=base+u16(ordinals+2*i)
        return found
    except (IndexError, struct.error, UnicodeError) as error:
        raise ValueError('Invalid PE32') from error


def digest(data): return hashlib.sha256(data).hexdigest()


def atomic_write(path, data):
    descriptor,name=tempfile.mkstemp(prefix='.winlator-voice-',suffix='.tmp',dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(descriptor,'wb') as output:
            output.write(data); output.flush(); os.fsync(output.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists(): temporary.unlink()


def configure(folder, proxy, enabled, original_sha):
    """Caller must establish that no process from this game folder is running."""
    folder=Path(folder); target=folder/'xinyitts.dll'; backup=folder/ORIGINAL; manifest=folder/MANIFEST
    current=target.read_bytes()
    if enabled:
        if manifest.exists():
            saved=json.loads(manifest.read_text(encoding='utf-8'))
            if digest(backup.read_bytes()) != saved['originalSha256']: raise ValueError('Backup changed')
            if digest(current) != saved['proxySha256']: raise ValueError('Installed DLL changed')
            return 'already-enabled'
        expected=dict(zip(EXPORTS,range(1,len(EXPORTS)+1)))
        if digest(current) != original_sha or pe_exports(current) != expected:
            raise ValueError('Unsupported game voice DLL')
        if pe_exports(proxy) != expected: raise ValueError('Invalid diagnostic DLL')
        if backup.exists():
            if digest(backup.read_bytes())!=original_sha:raise ValueError('Backup name in use')
        else:atomic_write(backup,current)
        saved=dict(version=1,originalSha256=digest(current),proxySha256=digest(proxy))
        # Manifest is committed before changing the live DLL; a partial install can be restored.
        atomic_write(manifest,(json.dumps(saved)+'\n').encode())
        atomic_write(target,proxy)
        return 'enabled'
    if not manifest.exists(): return 'already-disabled'
    saved=json.loads(manifest.read_text(encoding='utf-8')); original=backup.read_bytes()
    if digest(original) != saved['originalSha256'] or saved['originalSha256'] != original_sha:
        raise ValueError('Backup changed')
    if digest(current) not in (saved['originalSha256'],saved['proxySha256']):
        raise ValueError('Installed DLL changed')
    atomic_write(target,original)
    manifest.unlink(); backup.unlink()
    return 'disabled'


class TraceReader:
    def __init__(self): self.sequences={}

    def collect(self, folder):
        events=[]
        paths=sorted(Path(folder).glob('game-voice-*.jsonl'),key=lambda p:p.stat().st_mtime,reverse=True)
        for stale in paths[8:]:
            try:stale.unlink()
            except OSError:pass
        paths=paths[:8]
        for path in paths:
            if path.stat().st_size > 65536: continue
            for line in path.read_text(encoding='ascii',errors='replace').splitlines():
                try:
                    row=json.loads(line); key=(row['pid'],row['instance'])
                    if not isinstance(row['seq'],int) or row['seq'] <= self.sequences.get(key,0): continue
                    previous=self.sequences.get(key,0)
                    if row['seq'] > previous+1: events.append(dict(event='gap',pid=row['pid'],missing=row['seq']-previous-1))
                    self.sequences[key]=row['seq']; events.append(row)
                except (ValueError,KeyError,TypeError): continue  # Concurrent trailing writes are retried next poll.
        if len(self.sequences)>64:
            self.sequences=dict(list(self.sequences.items())[-32:])
        return events
