#!/usr/bin/env python3
"""Send the same protocol as Android, assert actual Windows state and NVDA speech."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from test_android_speech import exercise_android_speech


def exercise(wine, env, prefix, log, output):
    base = Path(prefix) / 'drive_c/winlator-nvda'
    config = base / 'config'
    state = json.loads((config / 'winlator-status.json').read_text())
    assert state['commandProtocol'] == 1
    session = state['session']

    def wait(predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                value = predicate()
                if value:
                    return value
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(.05)
        detail = (base / 'touch-fixture.json').read_text() if (base / 'touch-fixture.json').exists() else 'no fixture'
        raise AssertionError('Windows/NVDA did not reach expected test state: ' + detail)

    def command(action, text='', ok=True, request_session=session, created=None):
        request = {'version': 1, 'session': request_session, 'id': str(uuid.uuid4()),
                   'created': time.time() if created is None else created, 'action': action, 'text': text}
        temporary = config / 'winlator-command.tmp'
        temporary.write_text(json.dumps(request), encoding='utf-8')
        os.replace(temporary, config / 'winlator-command.json')

        def replied():
            reply = json.loads((config / 'winlator-reply.json').read_text())
            return reply if reply.get('id') == request['id'] else None
        if ok is not None:
            reply = wait(replied)
            assert reply['session'] == session and reply['ok'] is ok, reply
            if reply.get('effect') == 'pending' and action in ('enter', 'backspace'):
                def completed():
                    journal=json.loads((config/'winlator-diagnostics.json').read_text())
                    return next((row for row in journal['events'] if row['kind']=='operation.completed' and 'id='+request['id']+';' in row['details']),None)
                event=wait(completed,timeout=12)
                assert '; state=done;' in event['details'],event
                import re
                effect=re.search(r'; effect=(\d+)',event['details'])[1]
                assert effect!='0',event
                reply=dict(reply,effect={'1':'handled','2':'changed','3':'boundary'}[effect])
            return reply
        return request

    fixture = subprocess.Popen([wine, str(Path(__file__).with_name('touch-fixture.exe'))],
                               env=env, stdout=output, stderr=output)
    try:
        snapshot = lambda: json.loads((base / 'touch-fixture.json').read_text())
        wait(lambda: snapshot()['focus'] == 101)
        speech_start = len(log.read_text(errors='replace'))
        command('down')
        wait(lambda: snapshot()['selected'] == 1)
        # Require the selected item in NVDA's own speech log, not just an acknowledgement.
        wait(lambda: 'Beta' in log.read_text(errors='replace')[speech_start:])
        print('PASS: touch Down changes real list selection and NVDA speaks Beta', flush=True)
        command('up'); wait(lambda: snapshot()['selected'] == 0)
        command('tab'); wait(lambda: snapshot()['focus'] == 1)
        command('enter'); wait(lambda: snapshot()['activated'] == 1)
        command('tab'); wait(lambda: snapshot()['focus'] == 102)
        command('space'); wait(lambda: snapshot()['checked'] == 1)
        command('tab'); wait(lambda: snapshot()['focus'] == 103)
        command('text', 'Tiếng Việt 123')
        wait(lambda: snapshot()['text'] == 'Tiếng Việt 123')
        command('shift_tab'); wait(lambda: snapshot()['focus'] == 102)
        print('PASS: Tab, Shift+Tab, Enter, Space and Vietnamese text reach real Windows controls', flush=True)
        command('tab'); wait(lambda: snapshot()['focus'] == 103)
        command('tab'); wait(lambda: snapshot()['focus'] == 104)
        command('focus')
        assert 'SECRET_MUST_NOT_LEAK' not in log.read_text(errors='replace'), 'Password spoken or logged'
        print('PASS: protected input is not spoken or logged by touch fallback', flush=True)
        journal = wait(lambda: json.loads((config/'winlator-diagnostics.json').read_text()))
        assert journal['session'] == session
        events = journal['events']
        assert any(row['kind']=='command' for row in events), events
        assert any(row['kind']=='reply' for row in events), events
        assert any(row['kind']=='context' and 'before ' in row['details'] for row in events), events
        assert any(row['kind']=='context' and 'after ' in row['details'] for row in events), events
        assert any(row['kind']=='speech' for row in events), events
        assert 'SECRET_MUST_NOT_LEAK' not in json.dumps(events), 'Password in diagnostic journal'
        assert len(json.dumps(journal).encode()) <= 262144
        print('PASS: live NVDA diagnostics contain commands, replies, before/after focus and speech; password stays hidden', flush=True)

        # Unknown, expired and previous-process commands must not type or activate anything.
        command('not_a_command', ok=False)
        command('enter', ok=False, created=time.time()-30)
        command('enter', ok=None, request_session='0'*32)
        time.sleep(.3)
        assert snapshot()['activated'] == 1
        print('PASS: unsupported, stale and wrong-session commands rejected', flush=True)
    finally:
        if (base / 'touch-fixture.json').exists():
            print('Final fixture state: ' + (base / 'touch-fixture.json').read_text(), flush=True)
        print('Fixture return code: ' + str(fixture.poll()), flush=True)
        fixture.terminate()
        try:
            fixture.wait(timeout=5)
        except subprocess.TimeoutExpired:
            fixture.kill()

    binary = Path(__file__).resolve().parents[1] / 'app/app/src/main/assets/nvda/wfm.exe'
    # Reproduce the phone symptom: forbid both injection methods used by the old path.
    (config / 'winlator-test-block-injection').write_text('CI only')
    command('down', ok=False)
    attempts = config / 'winlator-test-injection-attempts'
    assert attempts.exists() and attempts.read_text().strip(), 'CI injection guard was not active'
    attempts.unlink()
    print('PASS: negative control confirms the old key injection path is blocked', flush=True)
    # Exercise the actual program opened by Winlator, not a ListBox substitute.
    manager = subprocess.Popen([wine, str(binary)], env=env, stdout=output, stderr=output)
    try:
        def says(action, expected, text=''):
            start = len(log.read_text(errors='replace'))
            reply = command(action, text)
            wait(lambda: expected in log.read_text(errors='replace')[start:])
            return reply
        time.sleep(1)
        says('focus', 'Ổ đĩa')
        assert says('up', 'Đã ở đầu danh sách')['effect'] == 'boundary'
        assert says('down', 'Mục 2 trên')['effect'] == 'changed'
        assert says('up', 'Mục 1 trên')['effect'] == 'changed'
        assert command('end')['effect'] in ('changed', 'boundary')
        assert says('down', 'Không có mục tiếp theo theo hướng này')['effect'] == 'boundary'
        assert command('home')['effect'] in ('changed', 'boundary')
        says('enter', 'Thư mục')
        print('PASS: WFM direct commands change drive selection and open it with keyboard injection blocked', flush=True)
    finally:
        manager.terminate()
        try: manager.wait(timeout=5)
        except subprocess.TimeoutExpired: manager.kill()


    from test_operations import exercise_operations
    exercise_operations(wine,env,prefix,log,output,command,wait)

    folders = Path(prefix) / 'drive_c/NVDA File Manager Test'
    (folders/'Alpha Folder').mkdir(parents=True)
    (folders/'Beta Folder').mkdir()
    (folders/'Beta Folder/First file.txt').write_text('fixture text')
    (folders/'Beta Folder/Second file.txt').write_text('another fixture')
    manager = subprocess.Popen([wine, str(binary), r'C:\NVDA File Manager Test'], env=env, stdout=output, stderr=output)
    try:
        time.sleep(1)
        says('focus', 'Alpha Folder')
        says('right', 'Beta Folder')
        says('left', 'Alpha Folder')
        assert says('down', 'Beta Folder')['effect'] == 'changed'
        assert says('space', 'Chưa chọn')['effect'] == 'changed'
        assert says('space', 'Đã chọn')['effect'] == 'changed'
        says('enter', 'First file.txt')
        says('backspace', 'Alpha Folder')
        says('tab', 'Cây thư mục')
        says('shift_tab', 'Alpha Folder')
        command('tab'); command('tab')  # Address field, via the same focus cycle as gestures.
        command('text', r'C:\NVDA File Manager Test\Beta Folder')
        says('enter', 'First file.txt')
        attempts = config / 'winlator-test-injection-attempts'
        assert not attempts.exists() or not attempts.read_text().strip(), 'WFM tried the old injection path'
        print('PASS: WFM folders, Enter, parent navigation, Space, Tab/Shift+Tab and address with zero injection attempts', flush=True)
    finally:
        manager.terminate()
        try: manager.wait(timeout=5)
        except subprocess.TimeoutExpired: manager.kill()

    exercise_android_speech(config, command)

    from test_shortcuts import exercise_shortcuts
    exercise_shortcuts(wine, env, prefix, log, output, command, wait)
    from test_runtime_audit import exercise_runtime_audit
    exercise_runtime_audit(wine, env, prefix, log, output, command, wait)
