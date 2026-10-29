#!/usr/bin/env python3
"""Actual X keyboard events in Wine, plus NVDA clipboard/repeat history isolation."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


def exercise_shortcuts(wine,env,prefix,log,output,command,wait):
    base=Path(prefix)/'drive_c/winlator-nvda';config=base/'config'
    (config/'winlator-test-block-injection').write_text('CI only')
    attempts=config/'winlator-test-injection-attempts';attempts.unlink(missing_ok=True)
    (base/'touch-fixture.json').unlink(missing_ok=True)
    fixture=subprocess.Popen([wine,str(Path(__file__).with_name('touch-fixture.exe'))],env=env,stdout=output,stderr=output)
    snapshot=lambda:json.loads((base/'touch-fixture.json').read_text())
    def physical(value):
        print('SHORTCUT: '+value,flush=True)
        reply=command('shortcut',value)
        assert reply['effect']=='external',reply
        # Equivalent X key events to the Android X server route. No Win32 SendInput.
        names={'control':'ctrl','windows':'super','up':'Up','down':'Down','left':'Left','right':'Right','tab':'Tab','enter':'Return','escape':'Escape','home':'Home','end':'End'}
        keys='+'.join(names.get(part,part.upper() if part.startswith('f') and part[1:].isdigit() else part) for part in value.split('+'))
        subprocess.run(['xdotool','key','--clearmodifiers',keys],env=env,stdout=output,stderr=output,timeout=5,check=True)
        time.sleep(.12)
        command('external_feedback')
    try:
        wait(lambda:snapshot()['focus']==101 and snapshot()['activated']==0)
        windows=subprocess.check_output(['xdotool','search','--onlyvisible','--name','^NVDA touch navigation test$'],env=env,text=True).splitlines()
        assert windows,'No X window for the real Windows fixture'
        subprocess.run(['xdotool','windowfocus','--sync',windows[-1]],env=env,stdout=output,stderr=output,timeout=5,check=True)
        physical('down');wait(lambda:snapshot()['selected']==1)
        physical('f12');wait(lambda:snapshot()['lastKey']==123)
        physical('tab');wait(lambda:snapshot()['focus']==1)
        physical('tab');wait(lambda:snapshot()['focus']==102)
        physical('tab');wait(lambda:snapshot()['focus']==103)
        subprocess.run(['xdotool','type','--clearmodifiers','Custom shortcut 123'],env=env,stdout=output,stderr=output,timeout=8,check=True)
        wait(lambda:snapshot()['text']=='Custom shortcut 123')
        physical('control+a')
        # Bare Win32 Edit does not supply an application Ctrl+A handler. Select
        # using its native Shift+Home behavior before asserting Ctrl+C contents.
        physical('shift+home');physical('control+c')
        wait(lambda:snapshot()['lastKey']==67 and snapshot()['controlSeen']==1)
        request=dict(id=str(uuid.uuid4()),operation='clipboard');temporary=config/'winlator-test-inspect.tmp'
        temporary.write_text(json.dumps(request));os.replace(temporary,config/'winlator-test-inspect.json')
        def clipboard():
            data=json.loads((config/'winlator-test-observed.json').read_text())
            return data if data.get('id')==request['id'] else None
        observed=wait(clipboard);assert observed.get('clipboardText')=='Custom shortcut 123',observed
        print('PASS: custom arrows, Tab, F12 and Ctrl+C reach real Windows controls through X keyboard events with bridge injection blocked',flush=True)
        command('focus');history=command('copy_last')['text']
        assert 'Custom shortcut 123' in history,history
        command('message','Đang giữ Ctrl');command('message','Đã sao chép câu gần nhất.')
        assert command('copy_last')['text']==history,'Control confirmation replaced actual NVDA content'
        start=len(log.read_text(errors='replace'));command('repeat_last')
        wait(lambda:history in log.read_text(errors='replace')[start:])
        assert command('copy_last')['text']==history,'Repeat replaced saved content'
        for value in ['control+control+a','f13','control+c+v','rm -rf','control+;']:
            command('shortcut',value,ok=False)
        assert not attempts.exists() or not attempts.read_text().strip(),'Custom shortcut fell back to blocked Win32 injection'
        print('PASS: recent NVDA sentence repeats and copies identically; control notices do not replace it; malformed shortcuts are rejected',flush=True)
    finally:
        print('Shortcut final state: '+str(snapshot()),flush=True)
        print('Shortcut blocked injection attempts: '+(attempts.read_text() if attempts.exists() else 'none'),flush=True)
        (config/'winlator-test-block-injection').unlink(missing_ok=True)
        fixture.terminate()
        try:fixture.wait(timeout=5)
        except subprocess.TimeoutExpired:fixture.kill()
