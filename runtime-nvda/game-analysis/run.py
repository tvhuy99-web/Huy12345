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
    Path('/work/prefix').mkdir(mode=0o700)
    Path('/tmp/runtime-user').mkdir(mode=0o700)
    env=dict(os.environ,WINEDLLOVERRIDES='mscoree,mshtml=',WINEDEBUG='-all')
    xvfb=subprocess.Popen(['Xvfb',':99','-screen','0','1280x800x24','-nolisten','tcp'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['pulseaudio','--start','--exit-idle-time=-1'],env=env,check=True)
    subprocess.run(['pactl','load-module','module-null-sink','sink_name=probe'],env=env,check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['pactl','set-default-sink','probe'],env=env,check=True)
    wine='/usr/lib/wine/wine64'
    boot=subprocess.run([wine,'wineboot','-u'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
    (results/'wineboot.txt').write_bytes(boot.stdout[-64000:])
    boot.check_returncode()
    subprocess.run([wine,'reg','add',r'HKCU\Software\Wine\Drivers','/v','Audio','/t','REG_SZ','/d','pulse','/f'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,check=True)
    game=Path('/work/prefix/drive_c/game');shutil.copytree('/input/game',game)
    if name=='reset-voice':
        (game/'usrvoice.ini').rename(game/'usrvoice.ini.before-probe')
    if name.startswith('legacy-reader'):
        for path in (game/'读屏').iterdir():
            if path.is_file():shutil.copyfile(path,game/path.name)
        (game/'tts.ini').write_text('[tts]\r\ntype=NVDA\r\n',encoding='utf-16')
    base=Path('/work/prefix/drive_c/winlator-nvda');base.mkdir()
    sys.path.insert(0,'/input/nvda')
    import game_voice
    identity=json.loads(Path('/input/nvda/voice-trace-original.json').read_text())
    game_voice.configure(game,Path('/input/nvda/voice-trace-x86.dll').read_bytes(),True,identity['sha256'])
    status=dict(scenario=name,withNvda=with_nvda,network=os.environ.get('PROBE_NETWORK'),platform='Ubuntu 24.04 Wine amd64/i386; not Android/Box64',nvdaReady=False)
    nvda_process=None;nvda_trace=None
    if with_nvda:
        source=Path('/input/nvda');manifest=json.loads((source/'manifest.json').read_text())
        archive=source/'nvda-portable.zip'
        assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()==manifest['archiveSha256']
        runtime='runtime-'+manifest['version']+'-'+manifest['archiveSha256'][:12]
        with zipfile.ZipFile(archive) as z:z.extractall(base/runtime)
        config=base/'config';plugin=config/'addons/winlatorStartup/globalPlugins/winlatorStartup';plugin.mkdir(parents=True)
        shutil.copyfile(source/'config-template.ini',config/'nvda.ini')
        shutil.copyfile(source/'addon-manifest.ini',plugin.parent.parent/'manifest.ini')
        shutil.copyfile(source/'winlatorStartup.py',plugin/'__init__.py')
        shutil.copyfile(source/'game_voice.py',plugin/'game_voice.py')
        synth=plugin.parent.parent/'synthDrivers';synth.mkdir()
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
    def input_test():
        time.sleep(25)
        matches=[]
        found=subprocess.run(['xdotool','search','--onlyvisible','--class','.'],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        for window in found.stdout.decode().splitlines():
            identified=subprocess.run(['xdotool','getwindowpid',window],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            try:
                pid=int(identified.stdout.strip());command=Path('/proc',str(pid),'cmdline').read_bytes()
                if b'zetianji' not in command.lower():continue
                geometry=subprocess.check_output(['xdotool','getwindowgeometry','--shell',window],env=env).decode()
                values=dict(line.split('=',1) for line in geometry.splitlines() if '=' in line)
                matches.append((int(values.get('WIDTH',0))*int(values.get('HEIGHT',0)),window))
            except (ValueError,OSError,subprocess.SubprocessError):pass
        with (results/'input-test.txt').open('ab') as out:out.write(('Matching game X windows: '+repr(matches)+'\n').encode())
        if matches:
            selected=max(matches)[1]
            focused=subprocess.run(['xdotool','windowfocus','--sync',selected],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=5)
            with (results/'input-test.txt').open('ab') as out:out.write(b'Focus: '+focused.stdout+b'\n')
        if name.startswith('legacy-reader'):
            for key in ('Home','Down','Down','Down','Tab','Return'):
                subprocess.run(['xdotool','key','--clearmodifiers',key],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                time.sleep(.3)
            time.sleep(2)
            found=subprocess.run(['xdotool','search','--onlyvisible','--classname','zetianji.exe'],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            candidates=found.stdout.decode().splitlines()
            if candidates:subprocess.run(['xdotool','windowfocus','--sync',candidates[-1]],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
        for key in ('Down','Up','Return','Down'):
            result=subprocess.run(['xdotool','key','--clearmodifiers',key],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            with (results/'input-test.txt').open('ab') as out:out.write((key+' code='+str(result.returncode)+'\n').encode()+result.stdout)
            time.sleep(2)
    input_thread=threading.Thread(target=input_test,daemon=True);input_thread.start()
    with (results/'observations.jsonl').open('wb') as observed:
        arguments=[wine,r'Z:\tools\probe.exe']+(['choose-voice'] if name=='reset-voice' or name.startswith('legacy-reader') else [])
        game_process=subprocess.Popen(arguments,env=probe_env,stdout=observed,stderr=subprocess.PIPE)
        trace=Trace(game_process.stderr)
        try:status['observerReturnCode']=game_process.wait(timeout=78)
        except subprocess.TimeoutExpired:
            status['observerTimedOut']=True;game_process.terminate();game_process.wait(timeout=5)
        trace.thread.join(timeout=2);trace.save(results/'wine-debug.txt')
    input_thread.join(timeout=1)
    game_audio=dict(audio);game_audio['rms']=math.sqrt(game_audio['sumSquares']/max(1,game_audio['samples']))
    status['audio']=game_audio
    events=[]
    for line in (results/'observations.jsonl').read_text(errors='replace').splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    started=[row['pid'] for row in events if row.get('event')=='started']
    if started:
        try:
            stacks=subprocess.run([wine,r'Z:\tools\stack-probe.exe',str(started[0])],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
            (results/'thread-snapshots.txt').write_bytes(stacks.stdout[-128000:])
        except subprocess.TimeoutExpired as error:
            (results/'thread-snapshots.txt').write_bytes((error.stdout or b'')[-128000:])
    try:
        client=subprocess.run([wine,r'Z:\tools\tts-probe.exe']+['proxy'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=25)
        (results/'controller-client.txt').write_bytes(client.stdout[-64000:])
        status['controllerProbeReturnCode']=client.returncode
    except subprocess.TimeoutExpired as error:
        status['controllerProbeTimedOut']=True
        (results/'controller-client.txt').write_bytes((error.stdout or b'')[-64000:])
    time.sleep(4)
    recorder.terminate();recorder.wait(timeout=5);thread.join(timeout=1)
    status['controllerAudioActiveSamples']=audio['activeSamples']-game_audio['activeSamples']
    if (base/'game-screen.bmp').exists():shutil.copyfile(base/'game-screen.bmp',results/'game-screen.bmp')
    for config_name in ('usrvoice.ini','tts.ini','api.ini','yuyn.ini'):
        source=game/config_name
        if source.exists():(results/('config-'+config_name+'.txt')).write_text(read_text(source.read_bytes()))
    for path in game.rglob('*'):
        if not path.is_file() or path.stat().st_size>256000:continue
        if '日志' in path.name or path.suffix.lower()=='.log':
            target=results/('game-log-'+path.name+'.txt');target.write_text(read_text(path.read_bytes())[-128000:])
    for path in Path('/work/prefix/drive_c').rglob('*'):
        if path.is_file() and path.suffix.lower() in ('.log','.txt') and any(word in path.name.lower() for word in ('xytts','xiny','usrvoice','proxy','trace')) and path.stat().st_size<=256000:
            target=results/('adapter-log-'+str(len(list(results.glob('adapter-log-*'))))+'.txt')
            target.write_text(str(path.relative_to('/work/prefix/drive_c'))+'\n'+read_text(path.read_bytes())[-128000:])
    for source,target in [(base/'nvda.log','nvda.log'),(base/'stdio.txt','nvda-stdio.txt'),(base/'config/winlator-diagnostics.json','nvda-diagnostics.json')]:
        if source.exists(): (results/target).write_bytes(source.read_bytes()[-2*1024**2:])
    if nvda_trace:nvda_trace.save(results/'nvda-wine-debug.txt')
    traces=[]
    for path in (base/'config').glob('game-voice-*.jsonl'):
        shutil.copyfile(path,results/path.name)
        for line in path.read_text().splitlines():
            try:traces.append(json.loads(line))
            except ValueError:pass
    game_rows=[row for row in traces if started and row.get('pid')==started[0]]
    status['gameVoiceCalls']=len(game_rows)
    status['gameVoiceApis']=sorted({row['api'] for row in game_rows})
    status['gameSpeechBegins']=sum(row.get('phase')=='begin' and row.get('api','').startswith('xyttsSpeak') for row in game_rows)
    status['directProxyCalls']=len(traces)-len(game_rows)
    assert any(row.get('api')=='xyttsInitA' and row.get('phase')=='end' for row in traces), 'Recorder did not capture known initialization'
    assert status.get('controllerProbeReturnCode')==0, 'Direct proxy verification failed'

    (results/'result.json').write_text(json.dumps(status,ensure_ascii=False,indent=2))
    print(json.dumps(status,ensure_ascii=False),flush=True)
    subprocess.run(['/usr/lib/wine/wineserver','-k'],env=env,timeout=10)
    xvfb.terminate()


if __name__=='__main__':main()
