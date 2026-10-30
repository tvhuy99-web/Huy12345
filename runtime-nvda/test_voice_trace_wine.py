#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute the real PE32 diagnostic DLL against an ABI sentinel in disposable Wine."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from game_voice import EXPORTS, configure, digest, pe_exports, TraceReader

ROOT=Path(__file__).resolve().parents[1]
def exercise():
    with tempfile.TemporaryDirectory(prefix='winlator-voice-trace-') as temporary:
        work=Path(temporary);prefix=work/'prefix';folder=prefix/'drive_c/Voice Trace Test';folder.mkdir(parents=True)
        config=prefix/'drive_c/winlator-nvda/config';config.mkdir(parents=True)
        mapping=dict(xyttsInitA='fixtureInitA@8',xyttsInitW='fixtureInitW@8',xyttsSpeakA='fixtureSpeakA@4',
                     xyttsSpeakW='fixtureSpeakW@4',xyttsSpeak2A='fixtureSpeakA@4',xyttsSpeak2W='fixtureSpeakW@4',
                     xyttsSetNotify='fixtureNotify@12',xyttsUninit='fixtureUninit@4')
        definition=work/'fixture.def'
        definition.write_text('LIBRARY xinyitts\nEXPORTS\n'+'\n'.join(
            f'{name}={mapping.get(name,"fixtureNoArgs@0")} @{i}' for i,name in enumerate(EXPORTS,1)))
        subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared',
                        str(ROOT/'runtime-nvda/voice-trace-fixture.c'),str(definition),'-o',str(folder/'xinyitts.dll')],check=True)
        driver=folder/'voice-trace-test.exe'
        subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                        str(ROOT/'runtime-nvda/voice-trace-test.c'),'-o',str(driver)],check=True)
        original=(folder/'xinyitts.dll').read_bytes();proxy=(ROOT/'app/app/src/main/assets/nvda/voice-trace-x86.dll').read_bytes()
        assert configure(folder,proxy,True,digest(original))=='enabled'
        env=dict(os.environ,WINEPREFIX=str(prefix),WINEDEBUG='-all',WINEDLLOVERRIDES='mscoree,mshtml=')
        wine=shutil.which('wine') or '/usr/lib/wine/wine64'
        try:
            subprocess.run([wine,str(driver)],env=env,check=True,timeout=90)
            paths=list(config.glob('game-voice-*.jsonl'));assert paths
            assert all(path.stat().st_size<=65536 for path in paths)
            rows=TraceReader().collect(config);assert any(row.get('phase')=='end' and row.get('result')==108 for row in rows)
            assert any(row.get('event')=='gap' for row in rows),'Rotation must be reported, not silently lost'
            assert not any('REPEATED' in path.read_text() or 'Tiếng' in path.read_text() for path in paths)
            assert configure(folder,proxy,False,digest(original))=='disabled'
            assert (folder/'xinyitts.dll').read_bytes()==original
            print('PASS: original DLL restored byte-for-byte; trace bounded, private text excluded, rotation gaps visible',flush=True)
        finally:subprocess.run(['/usr/lib/wine/wineserver','-k'],env=env,timeout=10,check=False)

if __name__=='__main__':exercise()
