#!/usr/bin/env python3
"""Container-only runner. No account credentials, network or writable host source mounts."""
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import threading
import time
import zipfile


class Trace:
    def __init__(self, stream):
        self.parts=deque();self.size=0;self.head=b'';self.stream=stream
        self.thread=threading.Thread(target=self.read,daemon=True);self.thread.start()
    def read(self):
        while True:
            block=self.stream.read(8192)
            if not block:break
            if len(self.head)<65536:self.head=(self.head+block)[:65536]
            self.parts.append(block);self.size+=len(block)
            while self.size>2*1024**2:self.size-=len(self.parts.popleft())
    def save(self,path):
        path.write_bytes(self.head+b'\n[bounded recent trace]\n'+b''.join(tuple(self.parts)))


def read_text(data):
    if data.startswith((b'\xff\xfe',b'\xfe\xff')):return data.decode('utf-16',errors='replace')
    for enc in ('utf-8-sig','gb18030'):
        try:return data.decode(enc)
        except UnicodeError:pass
    return data.decode('cp1252',errors='replace')


def main():
    name=sys.argv[1];with_nvda=sys.argv[2]=='nvda'
    results=Path('/work/results');results.mkdir();Path('/work/home').mkdir()
    Path('/tmp/runtime-user').mkdir(mode=0o700)
    env=dict(os.environ,WINEDLLOVERRIDES='mscoree,mshtml=',WINEDEBUG='-all')
    xvfb=subprocess.Popen(['Xvfb',':99','-screen','0','1280x800x24','-nolisten','tcp'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['pulseaudio','--start','--exit-idle-time=-1'],env=env,check=True)
    subprocess.run(['pactl','load-module','module-null-sink','sink_name=probe'],env=env,check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['pactl','set-default-sink','probe'],env=env,check=True)
    wine='/usr/lib/wine/wine64'
    boot=subprocess.run([wine,'wineboot','-u'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
    (results/'wineboot.txt').write_bytes(boot.stdout[-64000:])
    subprocess.run([wine,'reg','add',r'HKCU\Software\Wine\Drivers','/v','Audio','/t','REG_SZ','/d','pulse','/f'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,check=True)
    game=Path('/work/prefix/drive_c/game');shutil.copytree('/input/game',game)
    base=Path('/work/prefix/drive_c/winlator-nvda');base.mkdir()
    status=dict(scenario=name,withNvda=with_nvda,network=os.environ.get('PROBE_NETWORK'),platform='Ubuntu 24.04 Wine amd64/i386; not Android/Box64',nvdaReady=False)
    nvda_process=None;nvda_trace=None
    if with_nvda:
        source=Path('/input/nvda');manifest=json.loads((source/'manifest.json').read_text())
        archive=source/'nvda-portable.zip'
        assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()==manifest['archiveSha256']
        runtime='runtime-'+manifest['version']+'-'+manifest['archiveSha256'][:12]
        with zipfile.ZipFile(archive) as z:z.extractall(base/runtime)
        config=base/'config';plugin=config/'addons/winlatorStartup/globalPlugins';plugin.mkdir(parents=True)
        shutil.copyfile(source/'config-template.ini',config/'nvda.ini')
        shutil.copyfile(source/'addon-manifest.ini',plugin.parent/'manifest.ini')
        shutil.copyfile(source/'winlatorStartup.py',plugin/'winlatorStartup.py')
        synth=plugin.parent/'synthDrivers';synth.mkdir()
        shutil.copyfile(source/'winlatorAndroid.py',synth/'winlatorAndroid.py')
        shutil.copyfile(source/'nvda-launcher.exe',Path('/work/prefix/drive_c/windows/nvda-launcher.exe'))
        nvda_process=subprocess.Popen([wine,r'C:\windows\nvda-launcher.exe','probe',runtime],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        nvda_trace=Trace(nvda_process.stdout)
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            state=config/'winlator-status.json'
            if state.exists():
                status['nvdaReady']=True
                frame=json.loads(state.read_text())
                request=dict(version=1,session=frame['session'],id='00000000-0000-4000-8000-000000000001',created=time.time(),action='silence')
                temporary=config/'winlator-command.tmp';temporary.write_text(json.dumps(request));temporary.replace(config/'winlator-command.json')
                break
            time.sleep(.25)
        time.sleep(.5)
    recorder=subprocess.Popen(['parec','--device=probe.monitor','--format=s16le','--rate=22050','--channels=1'],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    audio=dict(samples=0,activeSamples=0,sumSquares=0,peak=0)
    def measure():
        while True:
            block=recorder.stdout.read(4096)
            if not block:break
            values=struct.unpack('<'+'h'*(len(block)//2),block[:len(block)//2*2])
            audio['samples']+=len(values);audio['activeSamples']+=sum(abs(v)>100 for v in values)
            audio['sumSquares']+=sum(v*v for v in values);audio['peak']=max([audio['peak']]+[abs(v) for v in values])
    thread=threading.Thread(target=measure,daemon=True);thread.start()
    probe_env=dict(env,WINEDEBUG='+timestamp,+seh,+loaddll,+winediag')
    with (results/'observations.jsonl').open('wb') as observed:
        game_process=subprocess.Popen([wine,r'Z:\tools\probe.exe'],env=probe_env,stdout=observed,stderr=subprocess.PIPE)
        trace=Trace(game_process.stderr)
        try:status['observerReturnCode']=game_process.wait(timeout=78)
        except subprocess.TimeoutExpired:
            status['observerTimedOut']=True;game_process.terminate();game_process.wait(timeout=5)
        trace.thread.join(timeout=2);trace.save(results/'wine-debug.txt')
    recorder.terminate();recorder.wait(timeout=5);thread.join(timeout=1)
    audio['rms']=math.sqrt(audio['sumSquares']/max(1,audio['samples']))
    status['audio']=audio
    for path in game.rglob('*'):
        if not path.is_file() or path.stat().st_size>256000:continue
        if '日志' in path.name or path.suffix.lower()=='.log':
            target=results/('game-log-'+path.name+'.txt');target.write_text(read_text(path.read_bytes())[-128000:])
    for source,target in [(base/'nvda.log','nvda.log'),(base/'stdio.txt','nvda-stdio.txt'),(base/'config/winlator-diagnostics.json','nvda-diagnostics.json')]:
        if source.exists(): (results/target).write_bytes(source.read_bytes()[-2*1024**2:])
    if nvda_trace:nvda_trace.save(results/'nvda-wine-debug.txt')
    (results/'result.json').write_text(json.dumps(status,ensure_ascii=False,indent=2))
    print(json.dumps(status,ensure_ascii=False),flush=True)
    subprocess.run(['/usr/lib/wine/wineserver','-k'],env=env,timeout=10)
    xvfb.terminate()


if __name__=='__main__':main()
