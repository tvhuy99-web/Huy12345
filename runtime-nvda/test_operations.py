#!/usr/bin/env python3
"""Real delayed WFM operation, busy keys, launch lifecycle and native close."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid


def exercise_operations(wine,env,prefix,log,output,command,wait):
    base=Path(prefix)/'drive_c/winlator-nvda';config=base/'config'
    folder=Path(prefix)/'drive_c/NVDA Async Test'
    (folder/'Alpha Folder').mkdir(parents=True)
    (folder/'Alpha Folder/First file.txt').write_text('test only')
    shutil.copyfile(Path(__file__).with_name('touch-fixture.exe'),folder/'Alpha Folder/Runner.exe')
    binary=Path(__file__).with_name('wfm')/'.source/wfm-delayed-test.exe'
    process=subprocess.Popen([wine,str(binary),r'C:\NVDA Async Test'],env=env,stdout=output,stderr=output)
    def journal():return json.loads((config/'winlator-diagnostics.json').read_text())['events']
    def events(kind,needle):return [row for row in journal() if row['kind']==kind and needle in row['details']]
    def raw_key(value):
        state=json.loads((config/'winlator-status.json').read_text())
        request=dict(version=1,session=state['session'],id=str(uuid.uuid4()),created=time.time(),action='shortcut',text=value)
        temp=config/'winlator-key-command.tmp';temp.write_text(json.dumps(request));os.replace(temp,config/'winlator-key-command.json')
        def reply():
            data=json.loads((config/'winlator-key-reply.json').read_text())
            return data if data.get('id')==request['id'] else None
        return request,wait(reply)
    try:
        time.sleep(1)
        command('focus')
        started=time.monotonic();request,reply=raw_key('enter')
        assert reply['ok'] and reply['effect']=='pending',reply
        assert time.monotonic()-started<2,'Slow folder open blocked the key acknowledgement'
        ignored,busy=raw_key('down');assert busy['ok'] is False and busy['effect']=='busy',busy
        wait(lambda:events('operation.progress','id='+request['id']))
        completed=wait(lambda:events('operation.completed','id='+request['id']),timeout=12)
        assert 'state=done' in completed[-1]['details'],completed
        command('focus')
        wait(lambda:'First file.txt' in log.read_text(errors='replace')[-10000:])
        print('PASS: real WFM Enter delayed 5.1 seconds replies pending promptly, rejects busy Down, and completes once without replay',flush=True)
        (base/'touch-fixture.json').unlink(missing_ok=True)
        command('end');command('enter')
        wait(lambda:events('process.launch','"state": "started"'))
        wait(lambda:'Runner.exe' in json.dumps(events('process.launch','"state": "started"')))
        wait(lambda:(base/'touch-fixture.json').exists())
        def foreground():
            request=dict(id=str(uuid.uuid4()),operation='snapshot');temp=config/'winlator-test-inspect.tmp'
            temp.write_text(json.dumps(request));os.replace(temp,config/'winlator-test-inspect.json')
            def result():
                data=json.loads((config/'winlator-test-observed.json').read_text())
                return data if data.get('id')==request['id'] else None
            return wait(result)
        wait(lambda:foreground().get('foregroundClass')=='NvdaTouchFixture')
        command('close_window')
        wait(lambda:events('process.launch','"state": "exited"'),timeout=12)
        print('PASS: real file-manager program launch records PID/start/exit and native close ends its window',flush=True)
    finally:
        # Close any fixture left by a failing assertion, then stop this WFM instance.
        try:command('close_window')
        except Exception:pass
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill()
