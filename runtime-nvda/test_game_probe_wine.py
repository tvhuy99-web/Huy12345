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
        env=dict(os.environ,WINEPREFIX=str(prefix),WINEDEBUG='-all',WINEDLLOVERRIDES='mscoree,mshtml=')
        wine=shutil.which('wine') or '/usr/lib/wine/wine64'
        def wait_json(path):
            end=time.monotonic()+40
            while time.monotonic()<end:
                try:return json.loads(path.read_text())
                except (OSError,ValueError):time.sleep(.05)
            raise AssertionError('Fixture did not publish a bounded diagnostic result')
        try:
            for number,mode in enumerate(('responsive','blocked')):
                path=config/'probe-fixture.json';path.unlink(missing_ok=True)
                process=subprocess.Popen([wine,str(fixture),mode],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    identity=wait_json(path);identifier=f'{number+1:032x}'
                    subprocess.run([wine,str(ROOT/'app/app/src/main/assets/nvda/game-probe-x86.exe'),str(identity['pid']),identifier],env=env,check=True,timeout=10)
                    frame=wait_json(config/f'game-probe-{identifier}.json')
                    assert frame['id']==identifier and frame['pid']==identity['pid'] and frame['observerBits']==32
                    assert frame['creationTime']>0 and frame['moduleSnapshotError']==0 and frame['modules']
                    row=next(row for row in frame['windows'] if row['hwnd']==identity['hwnd'])
                    assert row['visible'] is False
                    assert row['wmNullDelivered']==(mode=='responsive'),row
                    assert frame['elapsedMs']<5000
                    assert 'Private fixture caption' not in json.dumps(frame)
                    print('PASS: PE32 module observer and bounded hidden-window ping: '+mode,flush=True)
                finally:process.terminate();process.wait(timeout=5)
        finally:subprocess.run(['/usr/lib/wine/wineserver','-k'],env=env,timeout=10,check=False)

if __name__=='__main__':exercise()
