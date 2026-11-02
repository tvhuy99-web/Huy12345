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
        dsound_def=work/'dsound-fixture.def';bass_def=work/'bass-fixture.def'
        dsound_def.write_text('LIBRARY dsound\nEXPORTS\nDirectSoundCreate=fixtureDirectSoundCreate@12\nDirectSoundCreate8=fixtureDirectSoundCreate8@12\n')
        bass_def.write_text('LIBRARY bass\nEXPORTS\nBASS_Init=fixtureBassInit@20\nBASS_GetVersion=fixtureBassGetVersion@0\nBASS_ErrorGetCode=fixtureBassErrorGetCode@0\nBASS_GetInfo=fixtureBassGetInfo@4\nBASS_StreamCreateFile=fixtureBassStreamCreateFile@28\nBASS_StreamFree=fixtureBassStreamFree@4\nBASS_ChannelGetInfo=fixtureBassChannelGetInfo@8\nBASS_ChannelSetDSP=fixtureBassChannelSetDSP@16\nBASS_ChannelRemoveDSP=fixtureBassChannelRemoveDSP@8\nBASS_ChannelPlay=fixtureBassChannelPlay@8\nBASS_Test=fixtureBassTest\n')
        subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-DBUILD_DSOUND',
                        str(ROOT/'runtime-nvda/bass-dsound-fixture.c'),str(dsound_def),'-o',str(preload_folder/'dsound.dll')],check=True)
        subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-DBUILD_BASS',
                        str(ROOT/'runtime-nvda/bass-dsound-fixture.c'),str(bass_def),'-o',str(preload_folder/'bass.dll')],check=True)
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

            for legacy in (False,True):
                for path in config.glob('game-voice-*.jsonl'):
                    path.unlink()
                loader=ROOT/'app/app/src/main/assets/nvda/game-audio-loader-x86.exe'
                probe=ROOT/'app/app/src/main/assets/nvda/voice-trace-x86.dll'
                preload_env=dict(env,WINEDLLOVERRIDES='dsound=n;mscoree,mshtml=')
                if legacy:preload_env['BASS_FIXTURE_LEGACY']='1'
                target=subprocess.Popen([wine,str(preload_driver)],env=preload_env,stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,text=True,cwd=preload_folder)
                pid_line=target.stdout.readline().strip()
                assert pid_line.isdigit(),(pid_line,target.stderr.read())
                injected=subprocess.run([wine,str(loader),pid_line,str(probe)],env=preload_env,text=True,
                                        capture_output=True,timeout=30)
                assert injected.returncode==0,(injected.returncode,injected.stdout,injected.stderr)
                assert '"state":"loaded"' in injected.stdout,injected.stdout
                target_code=target.wait(timeout=30)
                target_stdout=target.stdout.read()
                target_stderr=target.stderr.read()
                assert target_code==0,(target_code,target_stdout,target_stderr)
                preload_rows=TraceReader().collect(config)
                assert any(row.get('event')=='audio-preload' and row.get('state')=='started' for row in preload_rows),preload_rows
                assert any(row.get('event')=='audio' and row.get('api')=='waveOutWrite'
                           and row.get('source')=='zetianji.exe' and row.get('nonZeroBytes',0)>0 for row in preload_rows),preload_rows
                assert any(row.get('event')=='audio-dynamic' and row.get('source')=='zetianji.exe'
                           and row.get('module','').lower()=='bass.dll' for row in preload_rows),preload_rows
                assert any(row.get('event')=='audio-cache-hook' and row.get('source')=='bass.dll'
                           and row.get('api')=='GetProcAddress(cache)' and row.get('patches',0)>0 for row in preload_rows),preload_rows
                assert any(row.get('event')=='audio-cache-hook' and row.get('source')=='bass.dll'
                           and row.get('api')=='LoadLibraryA(cache)' and row.get('patches',0)>0 for row in preload_rows),preload_rows
                assert any(row.get('event')=='audio-backend' and row.get('source')=='bass.dll'
                           and row.get('backendConfirmed') is False and row.get('result') is True
                           and bool(row.get('forcedFlags',0)&0x40000)==(not legacy)
                           and bool(row.get('reportedFlags',0)&0x40000)==(not legacy)
                           for row in preload_rows),preload_rows
                assert any(row.get('event')=='audio' and row.get('api')=='BASS_ChannelSetDSP'
                           and row.get('source')=='bass.dll' and row.get('result')==1 for row in preload_rows),preload_rows
                assert any(row.get('event')=='audio' and row.get('api')=='BASS_DSP'
                           and row.get('source')=='bass.dll' and row.get('nonZeroBytes',0)>0 for row in preload_rows),preload_rows
                assert any(row.get('event')=='audio-dynamic' and row.get('source')=='bass.dll'
                           and row.get('api')=='DirectSoundCreate8' for row in preload_rows),preload_rows
                assert any(row.get('event')=='audio' and row.get('api')=='DirectSoundBuffer::Unlock'
                           and row.get('nonZeroBytes',0)>0 for row in preload_rows),preload_rows
                assert any(row.get('event')=='audio' and row.get('api')=='DirectSoundBuffer::Play' for row in preload_rows),preload_rows
                calls=[row for row in preload_rows if row.get('event')=='audio-bass-call']
                assert calls and all(row['bassErrorAvailable'] for row in calls),calls
                assert all(row['bassVersion']==(0x02040900 if legacy else 0x02041200) for row in calls),calls
                inits=[row for row in calls if row['api']=='BASS_Init']
                assert [(row['result'],row['bassError']) for row in inits]==[(True,0),(False,14)],inits
                streams=[row for row in calls if row['api']=='BASS_StreamCreateFile']
                assert len(streams)==5,streams
                assert [row['bassError'] for row in streams]==[2,2,20,0,0],streams
                assert streams[0]['offset']==0x100000001 and streams[0]['length']==0x200000002,streams
                assert 'missing-quote".ogg' in streams[0]['path'],streams
                assert 'missing-音效.ogg' in streams[1]['path'],streams
                assert streams[0]['fileState']=='attributes-failed' and not streams[0]['fileExists'],streams
                assert streams[2]['sourceKind']=='memory' and streams[2]['path']=='' and not streams[2]['fileReadable'],streams
                assert streams[4]['fileReadable'] and streams[4]['fileBytes']==16 and streams[4]['cwdReady'],streams
                memory=[row for row in preload_rows if row.get('event')=='audio-bass-memory']
                assert len(memory)==2,memory
                assert memory[0]['state']=='unreadable-header' and not memory[0]['repaired'] and not memory[0]['result'],memory
                assert memory[1]['state']=='riff-wave-readable' and memory[1]['repaired'] and memory[1]['result'],memory
                assert memory[1]['originalLength']==0 and memory[1]['usedLength']==52,memory
                assert memory[1]['callerModule'].lower()=='zetianji.exe' and memory[1]['callerRva']>0,memory
                plays=[row for row in calls if row['api']=='BASS_ChannelPlay']
                assert [(row['result'],row['bassError']) for row in plays]==[(False,5),(True,0)],plays
                attachments=[row for row in preload_rows if row.get('api')=='BASS_ChannelSetDSP']
                assert len(attachments)==2,'Only successful streams may attach DSP'
                print('PASS: BASS version',hex(calls[0]['bassVersion']),'original errors, paths and DSP regression',flush=True)
        finally:subprocess.run(['/usr/lib/wine/wineserver','-k'],env=env,timeout=10,check=False)

if __name__=='__main__':exercise()
