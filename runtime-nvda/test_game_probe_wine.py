#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check a truly blocked message pump, without blocking NVDA's own GUI thread."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
def exercise():
    with tempfile.TemporaryDirectory(prefix='winlator-probe-test-') as temporary:
        prefix=Path(temporary)/'prefix';config=prefix/'drive_c/winlator-nvda/config';config.mkdir(parents=True)
        fixture=Path(temporary)/'fixture.exe'
        subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-mwindows',
                        str(ROOT/'runtime-nvda/game-probe-fixture.c'),'-o',str(fixture),'-luser32'],check=True)
        abort_probe=Path(temporary)/'abort-probe.exe'
        subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-DPROBE_TEST_ABORT',
                        str(ROOT/'runtime-nvda/game-probe.c'),'-o',str(abort_probe),'-luser32'],check=True)
        env=dict(os.environ,WINEPREFIX=str(prefix),WINEDEBUG='-all',WINEDLLOVERRIDES='mscoree,mshtml=')
        wine=shutil.which('wine') or '/usr/lib/wine/wine64'
        def wait_json(path):
            end=time.monotonic()+40
            while time.monotonic()<end:
                try:return json.loads(path.read_text())
                except (OSError,ValueError):time.sleep(.05)
            raise AssertionError('Fixture did not publish a bounded diagnostic result')
        def heartbeat():
            try:return int((config/'probe-heartbeat.txt').read_text())
            except (OSError,ValueError):return 0
        def progressing(previous):
            end=time.monotonic()+5
            while time.monotonic()<end:
                if heartbeat()>previous:return
                time.sleep(.05)
            raise AssertionError('Target did not resume after diagnostic debugger detached')
        try:
            for number,mode in enumerate(('responsive','blocked')):
                path=config/'probe-fixture.json';path.unlink(missing_ok=True)
                process=subprocess.Popen([wine,str(fixture),mode],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    identity=wait_json(path);identifier=f'{number+1:032x}'
                    args=[str(identity['pid']),identifier,str(identity['created']),'deep']
                    subprocess.run([wine,str(ROOT/'app/app/src/main/assets/nvda/game-probe-x86.exe'),*args],env=env,check=True,timeout=10)
                    frame=wait_json(config/f'game-probe-{identifier}.json')
                    assert frame['id']==identifier and frame['pid']==identity['pid'] and frame['observerBits']==32
                    assert frame['creationTime']>0 and frame['moduleSnapshotError']==0 and frame['modules']
                    row=next(row for row in frame['windows'] if row['hwnd']==identity['hwnd'])
                    assert row['visible'] is False
                    assert row['wmNullDelivered']==(mode=='responsive'),row
                    assert frame['elapsedMs']<5000
                    assert 'Private fixture caption' not in json.dumps(frame)
                    if mode=='responsive':assert 'threadSnapshot' not in frame
                    else:
                        snapshot=frame['threadSnapshot']
                        assert snapshot['attached'] and snapshot['detachOnExit'] and snapshot['detached'],snapshot
                        assert snapshot['capturedBeforeAttachBreakpoint'] and snapshot['sawAttachBreakpoint'],snapshot
                        assert snapshot['waitError']==0 and snapshot['continueError']==0,snapshot
                        sample=next(row for row in snapshot['samples'] if row['tid']==frame['windows'][0]['thread'])
                        assert sample['contextOk'] and sample['instruction']['address']>0,sample
                        assert sample['instruction'].get('module'),sample
                        progressing(heartbeat())
                        print('PASS: debugger captured main-thread code address, detached and target resumed',flush=True)
                        args[1]='f'*32;args[3]='basic'
                        subprocess.run([wine,str(ROOT/'app/app/src/main/assets/nvda/game-probe-x86.exe'),*args],env=env,check=True,timeout=10)
                        assert 'threadSnapshot' not in wait_json(config/f'game-probe-{args[1]}.json')
                        # Wrong creation time must refuse before debugging or querying other target data.
                        args[1]='e'*32;args[2]=str(identity['created']+1);args[3]='deep'
                        subprocess.run([wine,str(ROOT/'app/app/src/main/assets/nvda/game-probe-x86.exe'),*args],env=env,check=True,timeout=10)
                        rejected=wait_json(config/f'game-probe-{args[1]}.json')
                        assert rejected['identityRejected'] and 'threadSnapshot' not in rejected
                        # Aborting an observer during a paused debug event must leave the game alive.
                        args[1]='d'*32;args[2]=str(identity['created'])
                        observer=subprocess.Popen([wine,str(abort_probe),*args],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                        try:
                            end=time.monotonic()+8;stopped=False
                            while time.monotonic()<end:
                                previous=heartbeat();time.sleep(.5)
                                if previous>0 and previous==heartbeat():stopped=True;break
                            assert stopped,'Abort fixture did not reach paused debug event'
                            observer.kill();observer.wait(timeout=5)
                            progressing(previous)
                            assert process.poll() is None,'Diagnostic helper exit terminated the game'
                            print('PASS: helper killed during debug event; target survived and resumed',flush=True)
                        finally:
                            if observer.poll() is None:observer.kill();observer.wait(timeout=5)
                    print('PASS: PE32 module observer and bounded hidden-window ping: '+mode,flush=True)
                finally:process.terminate();process.wait(timeout=5)
        finally:subprocess.run(['/usr/lib/wine/wineserver','-k'],env=env,timeout=10,check=False)

if __name__=='__main__':exercise()
