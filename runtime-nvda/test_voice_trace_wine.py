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
        openal_def=work/'openal.def';sound_def=work/'sound3d.def';openal_import=work/'libOpenAL32.a'
        openal_def.write_text('LIBRARY OpenAL32\nEXPORTS\nalBufferData=fixtureAlBufferData\nalSourcePlay=fixtureAlSourcePlay\n')
        sound_def.write_text('LIBRARY Sound3D\nEXPORTS\nexerciseAudioHook=fixtureExerciseAudioHook\n')
        subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-DBUILD_OPENAL',
                        str(ROOT/'runtime-nvda/audio-hook-fixture.c'),str(openal_def),
                        '-Wl,--out-implib,'+str(openal_import),'-o',str(folder/'OpenAL32.dll')],check=True)
        subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-DBUILD_SOUND3D',
                        str(ROOT/'runtime-nvda/audio-hook-fixture.c'),str(sound_def),str(openal_import),
                        '-o',str(folder/'Sound3D.dll')],check=True)
        driver=folder/'voice-trace-test.exe'
        subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                        str(ROOT/'runtime-nvda/voice-trace-test.c'),'-o',str(driver),'-lwinmm'],check=True)
        preload_folder=prefix/'drive_c/Audio Preload Test';preload_folder.mkdir(parents=True)
        preload_driver=preload_folder/'zetianji.exe'
        subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                        str(ROOT/'runtime-nvda/audio-preload-test.c'),'-o',str(preload_driver),'-lwinmm','-luser32'],check=True)
        original=(folder/'xinyitts.dll').read_bytes();proxy=(ROOT/'app/app/src/main/assets/nvda/voice-trace-x86.dll').read_bytes()
        assert configure(folder,proxy,True,digest(original))=='enabled'
        env=dict(os.environ,WINEPREFIX=str(prefix),WINEDEBUG='-all',WINEDLLOVERRIDES='mscoree,mshtml=')
        wine=shutil.which('wine') or '/usr/lib/wine/wine64'
        try:
            subprocess.run([wine,str(driver)],env=env,check=True,timeout=90)
            paths=list(config.glob('game-voice-*.jsonl'));assert paths
            assert all(path.stat().st_size<=65536 for path in paths)
            rows=TraceReader().collect(config);assert any(row.get('phase')=='end' and row.get('result')==108 for row in rows)
            # Early hook-status rows may rotate out; validate through the later audio events.
            audio=[row for row in rows if row.get('event')=='audio']
            assert any(row.get('api')=='waveOutWrite' and row.get('source')=='zetianji.exe' and row.get('nonZeroBytes',0)>0 for row in audio),audio
            assert any(row.get('api')=='alBufferData' and row.get('source')=='Sound3D.dll' and row.get('nonZeroBytes',0)>0 for row in audio),audio
            assert any(row.get('api')=='alSourcePlay' and row.get('source')=='Sound3D.dll' for row in audio),audio
            assert any(row.get('event')=='gap' for row in rows),'Rotation must be reported, not silently lost'
            assert not any('REPEATED' in path.read_text() or 'Tiếng' in path.read_text() for path in paths)
            assert configure(folder,proxy,False,digest(original))=='disabled'
            assert (folder/'xinyitts.dll').read_bytes()==original

            for path in config.glob('game-voice-*.jsonl'):
                path.unlink()
            loader=ROOT/'app/app/src/main/assets/nvda/game-audio-loader-x86.exe'
            probe=ROOT/'app/app/src/main/assets/nvda/voice-trace-x86.dll'
            target=subprocess.Popen([wine,str(preload_driver)],env=env,stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,text=True)
            pid_line=target.stdout.readline().strip()
            assert pid_line.isdigit(),(pid_line,target.stderr.read())
            injected=subprocess.run([wine,str(loader),pid_line,str(probe)],env=env,text=True,
                                    capture_output=True,timeout=30)
            assert injected.returncode==0,(injected.returncode,injected.stdout,injected.stderr)
            assert '"state":"loaded"' in injected.stdout,injected.stdout
            assert target.wait(timeout=30)==0
            preload_rows=TraceReader().collect(config)
            assert any(row.get('event')=='audio-preload' and row.get('state')=='started' for row in preload_rows),preload_rows
            assert any(row.get('event')=='audio' and row.get('api')=='waveOutWrite'
                       and row.get('source')=='zetianji.exe' and row.get('nonZeroBytes',0)>0 for row in preload_rows),preload_rows
            print('PASS: original DLL restored byte-for-byte; name-based hooks survive mismatched IAT addresses; PID-scoped loader catches an early Zetianji waveOutWrite before xinyitts loads; private text excluded',flush=True)
        finally:subprocess.run(['/usr/lib/wine/wineserver','-k'],env=env,timeout=10,check=False)

if __name__=='__main__':exercise()
