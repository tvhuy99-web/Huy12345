#!/usr/bin/env python3
"""Run the bundled NVDA itself in Wine; save evidence rather than assuming speech."""
import argparse
import array
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import zipfile
import wave

ROOT = Path(__file__).resolve().parents[1]


def probe():
    wine = '/usr/lib/wine/wine64'
    with tempfile.TemporaryDirectory(prefix='nvda-wine-probe-') as prefix:
        prefix = Path(prefix)
        env = dict(os.environ, WINEPREFIX=str(prefix), WINEARCH='win64', WINEDEBUG='-all', WINEDLLOVERRIDES='mscoree,mshtml=')
        logs = ROOT / 'runtime-nvda/probe-results'
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / 'wine.log').open('w') as output:
            subprocess.run([wine, 'wineboot', '-u'], env=env, stdout=output, stderr=output, timeout=90, check=True)
            subprocess.run([wine,'reg','add',r'HKCU\Software\Wine\Drivers','/v','Audio','/t','REG_SZ','/d','pulse','/f'],
                           env=env,stdout=output,stderr=output,timeout=15,check=True)
            subprocess.run(['pactl','load-module','module-null-sink','sink_name=nvda_test'],check=True,stdout=output)
            subprocess.run(['pactl','set-default-sink','nvda_test'],check=True)
            recording=(logs/'voice.raw').open('wb')
            recorder=subprocess.Popen(['parec','--device=nvda_test.monitor','--format=s16le','--rate=22050','--channels=1'],stdout=recording,stderr=output)
            folder = prefix / 'drive_c/winlator-nvda'
            manifest = json.loads((ROOT / 'app/app/src/main/assets/nvda/manifest.json').read_text())
            runtime = 'runtime-' + manifest['version'] + '-' + manifest['archiveSha256'][:12]
            with zipfile.ZipFile(ROOT / 'app/app/src/main/assets/nvda/nvda-portable.zip') as archive:
                archive.extractall(folder / runtime)
            config = folder / 'config'
            plugin = config / 'addons/winlatorStartup/globalPlugins'
            plugin.mkdir(parents=True)
            shutil.copyfile(ROOT / 'runtime-nvda/default.ini', config / 'nvda.ini')
            shutil.copyfile(ROOT / 'runtime-nvda/winlatorStartup.py', plugin / 'winlatorStartup.py')
            shutil.copyfile(ROOT / 'runtime-nvda/manifest.ini', plugin.parent / 'manifest.ini')
            binary = folder / runtime / 'nvda.exe'
            launcher = prefix / 'drive_c/windows/nvda-launcher.exe'
            shutil.copyfile(ROOT / 'app/app/src/main/assets/nvda/nvda-launcher.exe', launcher)
            log = folder / 'nvda.log'
            process = subprocess.Popen([wine, str(launcher), 'probe', runtime], env=env, stdout=output, stderr=output)
            deadline = time.monotonic() + 45
            ready = False
            while time.monotonic() < deadline:
                state = config / 'winlator-status.json'
                if state.exists():
                    data = json.loads(state.read_text())
                    ready = data.get('state') == 'ready'
                    if ready: break
                if process.poll() is not None: break
                time.sleep(.5)
            time.sleep(3 if ready else .1)
            recorder.terminate();recorder.wait(timeout=10);recording.close()
            pcm=(logs/'voice.raw').read_bytes()
            samples=array.array('h');samples.frombytes(pcm[:len(pcm)//2*2])
            audible=any(abs(sample)>100 for sample in samples)
            with wave.open(str(logs/'voice.wav'),'wb') as voice:
                voice.setnchannels(1);voice.setsampwidth(2);voice.setframerate(22050);voice.writeframes(pcm)
            (logs/'voice.raw').unlink()
            if log.exists(): shutil.copyfile(log, logs / 'nvda.log')
            for index, crash in enumerate(prefix.glob('drive_c/users/*/AppData/Roaming/nvda.log')):
                shutil.copyfile(crash, logs / f'bootstrap-{index}.log')
                print('NVDA bootstrap error:\n' + crash.read_text(errors='replace')[-20000:],flush=True)
            subprocess.run([wine,str(launcher),'diagnose'],env=env,stdout=output,stderr=output,timeout=15)
            for name in ['stdio.txt','windows.txt']:
                path=folder / name
                if path.exists():
                    shutil.copyfile(path,logs / name)
                    print(name + ':\n' + path.read_text(errors='replace')[-16000:],flush=True)
            initialized=log.exists() and 'NVDA initialized' in log.read_text(errors='replace')
            speechDriver=log.exists() and 'Loaded synthDriver espeak' in log.read_text(errors='replace')
            result = {'nvda': '2026.3', 'ready': ready, 'initialized':initialized, 'espeak':speechDriver, 'audioSignal': audible, 'returnCode': process.poll(),
                      'note': 'Wine on Linux is a compatibility probe, not a Winlator device test.'}
            (logs / 'result.json').write_text(json.dumps(result, indent=2))
            print(json.dumps(result, indent=2), flush=True)
            output.flush()
            print((logs / 'wine.log').read_text(errors='replace')[-20000:], flush=True)
            if log.exists():
                lines = log.read_text(errors='replace').splitlines()
                print('\n'.join(lines[-65:]), flush=True)
            subprocess.run([wine, str(launcher), 'stop', runtime], env=env, stdout=output, stderr=output, timeout=15)
            subprocess.run(['/usr/lib/wine/wineserver', '-k'], env=env, timeout=15)
            return ready and initialized and speechDriver and audible


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--require-ready',action='store_true');args=parser.parse_args()
    passed=probe()
    if args.require_ready and not passed: raise SystemExit('NVDA did not initialize and produce speech audio')
