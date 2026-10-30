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


def small_file(path, maximum=2*1024*1024):
    if path.stat().st_size>maximum:raise ValueError('Diagnostic input is too large')
    with path.open('rb') as source:data=source.read(maximum+1)
    if len(data)>maximum:raise ValueError('Diagnostic input grew beyond limit')
    return data


def environment(folder):
    """Known speech options only; never arbitrary INI contents, tokens or account details."""
    folder=Path(folder);result={}
    for name in ('xinyitts.dll',ORIGINAL,MANIFEST,'usrvoice.dll','tts.ini','usrvoice.ini','yuyn.ini'):
        try:
            path=folder/name
            if not path.is_file():result[name]=dict(exists=False);continue
            row=dict(exists=True,bytes=path.stat().st_size);result[name]=row
            limit=2*1024*1024 if name.endswith('.dll') else 4096
            if row['bytes']>limit:row['limited']=True;continue
            data=small_file(path,limit);row['sha256']=digest(data)
            if name.endswith('.ini'):
                encoding='utf-16' if data[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig'
                try:text=data.decode(encoding)
                except UnicodeError:text=data.decode('gb18030',errors='replace')
                if name=='yuyn.ini':
                    first=text.splitlines()[0].strip() if text.splitlines() else ''
                    row['firstFlag']=first if first in ('是','否','0','1') else 'unrecognized'
                else:
                    options={}
                    for line in text.splitlines():
                        key,sep,value=line.partition('=');key=key.strip().lower();value=value.strip()
                        if sep and ((name=='tts.ini' and key=='type' and value in ('BY','NVDA','ZD','ZDC')) or
                                    (name=='usrvoice.ini' and key in ('engine','numericmode') and value.isdigit() and len(value)<4)):
                            options[key]=value
                    row['options']=options
        except (OSError,ValueError) as error:result[name]=dict(error=type(error).__name__,errno=getattr(error,'errno',None),winerror=getattr(error,'winerror',None))
    return result


def atomic_write(path, data):
    descriptor,name=tempfile.mkstemp(prefix='.winlator-voice-',suffix='.tmp',dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(descriptor,'wb') as output:
            output.write(data); output.flush(); os.fsync(output.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists(): temporary.unlink()


def configure(folder, proxy, enabled, original_sha, trace=None):
    """Caller must establish that no process from this game folder is running."""
    folder=Path(folder); target=folder/'xinyitts.dll'; backup=folder/ORIGINAL; manifest=folder/MANIFEST
    stage='read-target'
    def event(phase,**details):
        nonlocal stage
        stage=phase
        if trace:trace(dict(stage=stage,**details))
    try:
        event('read-target');current=small_file(target);saved=None
        if manifest.exists():
            event('verify-backup');saved=json.loads(small_file(manifest,4096).decode('utf-8'))
            if digest(small_file(backup)) != original_sha or saved['originalSha256'] != original_sha:
                raise ValueError('Backup changed')
            allowed={saved['originalSha256'],saved['proxySha256'],saved.get('previousProxySha256')}
            if digest(current) not in allowed:raise ValueError('Installed DLL changed')
        if enabled:
            event('verify-proxy')
            expected=dict(zip(EXPORTS,range(1,len(EXPORTS)+1)))
            if pe_exports(proxy)!=expected:raise ValueError('Invalid diagnostic DLL')
            if saved:
                if digest(current)==digest(proxy):return 'already-enabled'
            elif digest(current)!=original_sha or pe_exports(current)!=expected:
                raise ValueError('Unsupported game voice DLL')
            event('backup-original')
            if backup.exists():
                if digest(small_file(backup))!=original_sha:raise ValueError('Backup name in use')
            else:atomic_write(backup,current)
            updated=dict(version=2,originalSha256=original_sha,proxySha256=digest(proxy))
            if saved:updated['previousProxySha256']=saved['proxySha256']
            event('write-manifest');atomic_write(manifest,(json.dumps(updated)+'\n').encode())
            event('write-proxy');atomic_write(target,proxy)
            event('installed',sha256=digest(proxy))
            return 'updated' if saved else 'enabled'
        if not saved:return 'already-disabled'
        event('restore-original');atomic_write(target,small_file(backup))
        event('remove-manifest');manifest.unlink();backup.unlink()
        event('restored',sha256=original_sha)
        return 'disabled'
    except (OSError,ValueError,KeyError) as error:
        error.diagnosticStage=stage
        raise


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
