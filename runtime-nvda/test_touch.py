#!/usr/bin/env python3
"""Send the same protocol as Android, assert actual Windows state and NVDA speech."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


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
    # Exercise the actual program opened by Winlator, not a ListBox substitute.
    manager = subprocess.Popen([wine, str(binary)], env=env, stdout=output, stderr=output)
    try:
        def says(action, expected, text=''):
            start = len(log.read_text(errors='replace'))
            command(action, text)
            wait(lambda: expected in log.read_text(errors='replace')[start:])
        time.sleep(1)
        says('focus', 'Ổ đĩa')
        says('down', 'Mục 2 trên')
        says('up', 'Mục 1 trên')
        says('enter', 'Thư mục')
        print('PASS: real WFM Computer starts on a drive, moves selection and opens it with Enter', flush=True)
    finally:
        manager.terminate()
        try: manager.wait(timeout=5)
        except subprocess.TimeoutExpired: manager.kill()

    folders = Path(prefix) / 'drive_c/NVDA File Manager Test'
    (folders/'Alpha Folder').mkdir(parents=True)
    (folders/'Beta Folder').mkdir()
    (folders/'Beta Folder/First file.txt').write_text('fixture text')
    (folders/'Beta Folder/Second file.txt').write_text('another fixture')
    manager = subprocess.Popen([wine, str(binary), r'C:\NVDA File Manager Test'], env=env, stdout=output, stderr=output)
    try:
        time.sleep(1)
        says('focus', 'Alpha Folder')
        says('down', 'Beta Folder')
        says('enter', 'First file.txt')
        says('backspace', 'Alpha Folder')
        says('tab', 'Cây thư mục')
        says('shift_tab', 'Alpha Folder')
        command('tab'); command('tab')  # Address field, via the same focus cycle as gestures.
        command('text', r'C:\NVDA File Manager Test\Beta Folder')
        says('enter', 'First file.txt')
        print('PASS: real WFM folder names, Enter, parent navigation, Tab/Shift+Tab and typed address', flush=True)
    finally:
        manager.terminate()
        try: manager.wait(timeout=5)
        except subprocess.TimeoutExpired: manager.kill()
