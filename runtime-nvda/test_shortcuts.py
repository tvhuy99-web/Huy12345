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
    def fast_command(value,ok=True):
        state=json.loads((config/'winlator-status.json').read_text())
        wait(lambda:(config/'winlator-key-status.json').exists())
        request=dict(version=1,session=state['session'],id=str(uuid.uuid4()),created=time.time(),action='shortcut',text=value)
        temporary=config/'winlator-key-command.tmp';temporary.write_text(json.dumps(request))
        os.replace(temporary,config/'winlator-key-command.json')
        def reply():
            data=json.loads((config/'winlator-key-reply.json').read_text())
            return data if data.get('id')==request['id'] else None
        result=wait(reply);assert result['ok'] is ok,result
        return result
    def physical(value):
        print('SHORTCUT: '+value,flush=True)
        reply=fast_command(value)
        assert reply['effect']=='external',reply
        # Equivalent X key events to the Android X server route. No Win32 SendInput.
        names={'control':'ctrl','windows':'super','up':'Up','down':'Down','left':'Left','right':'Right','tab':'Tab','enter':'Return','escape':'Escape','home':'Home','end':'End'}
        keys='+'.join(names.get(part,part.upper() if part.startswith('f') and part[1:].isdigit() else part) for part in value.split('+'))
        subprocess.run(['xdotool','key','--clearmodifiers',keys],env=env,stdout=output,stderr=output,timeout=5,check=True)
        time.sleep(.12)
        command('external_feedback',reply['id'])
        return reply
    try:
        wait(lambda:snapshot()['focus']==101 and snapshot()['activated']==0)
        windows=subprocess.check_output(['xdotool','search','--onlyvisible','--name','^NVDA touch navigation test$'],env=env,text=True).splitlines()
        assert windows,'No X window for the real Windows fixture'
        subprocess.run(['xdotool','windowfocus','--sync',windows[-1]],env=env,stdout=output,stderr=output,timeout=5,check=True)
        request=dict(id=str(uuid.uuid4()),operation='stall');temporary=config/'winlator-test-inspect.tmp'
        temporary.write_text(json.dumps(request));os.replace(temporary,config/'winlator-test-inspect.json')
        wait(lambda:(config/'winlator-test-stall-active').exists())
        started=time.monotonic();reply=fast_command('f12')
        assert time.monotonic()-started<1.5,'Key route blocked behind NVDA GUI thread'
        assert reply['effect']=='external',reply
        subprocess.run(['xdotool','key','--clearmodifiers','F12'],env=env,stdout=output,stderr=output,timeout=5,check=True)
        wait(lambda:snapshot()['lastKey']==123)
        wait(lambda:not(config/'winlator-test-stall-active').exists())
        print('PASS: independent key mailbox acknowledges a foreign key while NVDA GUI is deliberately blocked for 3.4 seconds',flush=True)
        physical('down');wait(lambda:snapshot()['selected']==1)
        physical('f12');wait(lambda:snapshot()['lastKey']==123)
        physical('tab');wait(lambda:snapshot()['focus']==1)
        physical('tab');wait(lambda:snapshot()['focus']==102)
        physical('tab');wait(lambda:snapshot()['focus']==103)
        subprocess.run(['xdotool','type','--clearmodifiers','--delay','40','Custom shortcut 123'],env=env,stdout=output,stderr=output,timeout=8,check=True)
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
            fast_command(value,ok=False)
        assert not attempts.exists() or not attempts.read_text().strip(),'Custom shortcut fell back to blocked Win32 injection'
        print('PASS: recent NVDA sentence repeats and copies identically; control notices do not replace it; malformed shortcuts are rejected',flush=True)
        for unused in range(12):
            if snapshot()['focus']==111:break
            physical('tab')
        wait(lambda:snapshot()['focus']==111)
        start=len(log.read_text(errors='replace'));command('focus')
        wait(lambda:'Windows Forms test. Nút.' in log.read_text(errors='replace')[start:])
        print('PASS: real superclassed WindowsForms10.BUTTON control is read as a button rather than unknown',flush=True)
        request=dict(id=str(uuid.uuid4()),operation='snapshot');temporary=config/'winlator-test-inspect.tmp'
        temporary.write_text(json.dumps(request));os.replace(temporary,config/'winlator-test-inspect.json')
        def actual_role():
            data=json.loads((config/'winlator-test-observed.json').read_text())
            return data if data.get('id')==request['id'] else None
        observed=wait(actual_role);assert observed.get('nvdaRole')=='BUTTON',observed
        command('inspect_controls')
        command('object_next')
        activated=snapshot()['activated'];command('object_activate');wait(lambda:snapshot()['activated']==activated+1)
        command('object_previous')
        reply=fast_command('alt+f4');assert reply['effect']=='pending',reply
        wait(lambda:fixture.poll() is not None)
        print('PASS: Alt+F4 uses one native system-close request and actually closes the Windows window without X replay',flush=True)
        (base/'touch-fixture.json').unlink(missing_ok=True)
        fixture=subprocess.Popen([wine,str(Path(__file__).with_name('touch-fixture.exe'))],env=env,stdout=output,stderr=output)
        wait(lambda:snapshot()['focus']==101)
        command('close_window');wait(lambda:fixture.poll() is not None)
        print('PASS: explicit native close command closes the actual Windows fixture; no process termination',flush=True)
        (base/'touch-fixture.json').unlink(missing_ok=True)
        fixture=subprocess.Popen([wine,str(Path(__file__).with_name('touch-fixture.exe')),'editor','confirm'],env=env,stdout=output,stderr=output)
        wait(lambda:snapshot()['focus']==103)
        windows=subprocess.check_output(['xdotool','search','--onlyvisible','--name','^NVDA touch navigation test$'],env=env,text=True).splitlines()
        subprocess.run(['xdotool','windowfocus','--sync',windows[-1]],env=env,stdout=output,stderr=output,timeout=5,check=True)
        time.sleep(.3)
        before_navigation=max(row['seq'] for row in json.loads((config/'winlator-diagnostics.json').read_text())['events'])
        physical('down')
        request=dict(id=str(uuid.uuid4()),operation='read-focus',action='down')
        temporary=config/'winlator-test-inspect.tmp';temporary.write_text(json.dumps(request));os.replace(temporary,config/'winlator-test-inspect.json')
        def editor_line():
            data=json.loads((config/'winlator-test-observed.json').read_text())
            return data if data.get('id')==request['id'] else None
        observed=wait(editor_line)
        assert observed.get('nativeFocusText')=='SECOND_LINE',observed
        journal=json.loads((config/'winlator-diagnostics.json').read_text())['events']
        assert not any(row['seq']>before_navigation and row['kind']=='speech' and all(word in row['details'] for word in ('FIRST_LINE','SECOND_LINE','THIRD_LINE')) for row in journal),'Navigation read the whole editor document'
        reply=fast_command('alt+f4');assert reply['effect']=='pending',reply
        def confirmation():
            request=dict(id=str(uuid.uuid4()),operation='snapshot');temporary=config/'winlator-test-inspect.tmp'
            temporary.write_text(json.dumps(request));os.replace(temporary,config/'winlator-test-inspect.json')
            def result():
                data=json.loads((config/'winlator-test-observed.json').read_text())
                return data if data.get('id')==request['id'] else None
            return wait(result)
        wait(lambda:confirmation().get('foregroundTitle')=='NVDA close confirmation')
        assert fixture.poll() is None,'System close bypassed the save/confirmation dialog'
        physical('escape')
        wait(lambda:confirmation().get('foregroundClass')=='NvdaTouchFixture')
        assert fixture.poll() is None,'Cancel should retain the original document window'
        fast_command('alt+f4')
        wait(lambda:confirmation().get('foregroundTitle')=='NVDA close confirmation')
        physical('enter');wait(lambda:fixture.poll() is not None)
        print('PASS: real multiline Edit reads the caret line; Alt+F4 keeps the confirmation dialog and Cancel retains the document',flush=True)
        (base/'touch-fixture.json').unlink(missing_ok=True)
        custom_start=len(log.read_text(errors='replace'))
        fixture=subprocess.Popen([wine,str(Path(__file__).with_name('touch-fixture.exe')),'custom'],env=env,stdout=output,stderr=output)
        wait(lambda:snapshot()['focus']==0)
        windows=subprocess.check_output(['xdotool','search','--onlyvisible','--name','^ÓïÒô¿âÅäÖÃ$'],env=env,text=True).splitlines()
        assert windows,'No X window for the custom root-focus fixture'
        subprocess.run(['xdotool','windowfocus','--sync',windows[-1]],env=env,stdout=output,stderr=output,timeout=5,check=True)
        # Each fixture starts with no held synthetic keys from the preceding Alt+F4 test.
        for modifier in ('Control_L','Control_R','Alt_L','Alt_R','Shift_L','Shift_R','Super_L','Super_R'):
            subprocess.run(['xdotool','keyup',modifier],env=env,stdout=output,stderr=output,timeout=5,check=True)
        # This fixture intentionally ignores Tab, like the root-only-focus symptom in the phone log.
        physical('tab');wait(lambda:snapshot()['lastKey']==9);assert snapshot()['focus']==0,snapshot()
        command('inspect_controls');command('object_activate');wait(lambda:snapshot()['focus']==101)
        physical('down');wait(lambda:snapshot()['selected']==1)
        command('object_next')
        activated=snapshot()['activated'];command('object_activate');wait(lambda:snapshot()['activated']==activated+1)
        command('focus')
        wait(lambda:'语音库配置' in log.read_text(errors='replace')[custom_start:])
        command('close_window');wait(lambda:fixture.poll() is not None)
        print('PASS: WTWindow root-only focus ignores Tab but real controls remain reviewable/activatable; known broken Chinese title is recovered',flush=True)
    finally:
        print('Shortcut final state: '+str(snapshot()),flush=True)
        print('Shortcut blocked injection attempts: '+(attempts.read_text() if attempts.exists() else 'none'),flush=True)
        (config/'winlator-test-block-injection').unlink(missing_ok=True)
        fixture.terminate()
        try:fixture.wait(timeout=5)
        except subprocess.TimeoutExpired:fixture.kill()
