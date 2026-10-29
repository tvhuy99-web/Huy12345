#!/usr/bin/env python3
"""Broad, evidence-based audit. These inspection hooks exist only in the CI add-on."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


def exercise_runtime_audit(wine, env, prefix, log, output, command, wait):
    config = Path(prefix) / 'drive_c/winlator-nvda/config'
    report = []

    def inspect(operation='snapshot', **arguments):
        request = dict(id=str(uuid.uuid4()), operation=operation, **arguments)
        temporary = config / 'winlator-test-inspect.tmp'
        temporary.write_text(json.dumps(request))
        os.replace(temporary, config / 'winlator-test-inspect.json')
        def answer():
            reply = json.loads((config / 'winlator-test-observed.json').read_text())
            return reply if reply.get('id') == request['id'] else None
        return wait(answer)

    def scenario(name, exercise, required=True):
        start = len(log.read_text(errors='replace'))
        try:
            evidence = exercise() or inspect()
            row = dict(name=name, status='limited' if isinstance(evidence,dict) and 'limitation' in evidence else 'pass', required=required, evidence=evidence)
        except Exception as error:
            try: observed = inspect()
            except Exception: observed = {}
            row = dict(name=name, status='fail', required=required, error=str(error), evidence=observed)
        speech = [line.split('Speaking ', 1)[-1] for line in log.read_text(errors='replace')[start:].splitlines()
                  if 'Speaking ' in line]
        row['speech'] = speech[-12:]
        report.append(row)
        print('AUDIT ' + json.dumps(row, ensure_ascii=False), flush=True)
        return row

    def says(action, expected, text='', ok=True):
        start = len(log.read_text(errors='replace'))
        reply = command(action, text, ok=ok)
        wait(lambda: expected in log.read_text(errors='replace')[start:])
        return reply

    def assert_that(value, detail):
        assert value, detail

    (config/'winlator-test-block-injection').unlink(missing_ok=True)
    binary = Path(__file__).resolve().parents[1]/'app/app/src/main/assets/nvda/wfm.exe'
    manager = subprocess.Popen([wine, str(binary)], env=env, stdout=output, stderr=output)
    try:
        wait(lambda: inspect()['foregroundClass'] == 'WFM-MainWnd')
        scenario('startup-computer', lambda: (command('focus'), assert_that('Ổ đĩa' in log.read_text(errors='replace')[-10000:], 'Drive not spoken'), inspect())[-1])
        def root_parent():
            command('enter'); command('backspace')
            observed = inspect()
            assert observed['foregroundClass'] == 'WFM-MainWnd', observed
            command('focus')
            return observed
        scenario('drive-back-to-computer', root_parent)
        def nvda_menu():
            says('nvda_menu', 'Trình đơn NVDA')
            return wait(lambda: (s if s.get('touchMenu') else None) if (s:=inspect()) else None)
        (config/'winlator-test-block-injection').write_text('CI only')
        scenario('nvda-menu-open', nvda_menu)
        def next_menu():
            before = inspect()['touchMenu']
            expected = before['items'][before['selected']+1]
            says('down', expected)
            after = inspect()
            assert after['touchMenu']['selected'] == before['selected']+1, after
            return after
        scenario('nvda-menu-next-speaks-real-item', next_menu)
        def read_menu_tree():
            spoken=[]
            def walk(depth=0):
                items=inspect()['touchMenu']['items']
                command('home')
                for index,item in enumerate(items):
                    if index:
                        command('down')
                    says('focus', item)
                    spoken.append(item)
                    if '. Trình đơn con' in item and '. Không khả dụng' not in item and depth<3:
                        command('enter'); walk(depth+1); command('escape')
            walk()
            command('home')
            assert len(spoken)>=30, spoken
            return dict(inspect(), menuLabelsChecked=len(spoken))
        scenario('nvda-all-menu-and-submenu-labels', read_menu_tree)
        def settings_menu():
            command('home'); command('enter')
            submenu = inspect()['touchMenu']
            assert submenu['title'] != 'Trình đơn NVDA', submenu
            says('focus', submenu['items'][0])
            return inspect()
        scenario('nvda-preferences-submenu', settings_menu)
        def settings_open():
            command('enter')
            return wait(lambda: (s if s['windows'] and not s.get('touchMenu') and s.get('wxFocus') else None) if (s:=inspect()) else None)
        scenario('nvda-settings-open-real-dialog', settings_open)
        def settings_focus():
            before=inspect()['wxFocus']
            says('focus', before['label'])
            return inspect()
        scenario('nvda-settings-read-current-control', settings_focus)
        def settings_category():
            before=inspect()['wxFocus']
            command('down')
            after=inspect()
            assert after['wxFocus']['label'] != before['label'], after
            says('focus', after['wxFocus']['label'])
            return after
        scenario('nvda-settings-change-category', settings_category)
        for i in range(8):
            def tab_control():
                before=inspect()['wxFocus']
                command('tab')
                after=inspect()
                assert after['wxFocus']['handle'] != before['handle'], after
                says('focus', after['wxFocus']['label'])
                return after
            scenario('nvda-settings-tab-'+str(i+1), tab_control)
        metadata=inspect().get('settings')
        if metadata:
            for unused in range(50):
                if inspect()['wxFocus']['handle']==metadata['handle']:
                    break
                command('tab')
            command('home')
            for category in range(metadata['count']):
                def scan_page(category=category):
                    observed=inspect()
                    assert observed['settings']['selected']==category, observed
                    category_name=observed['wxFocus']['label']
                    says('focus', category_name)
                    controls=[]; generic=[]
                    for unused in range(50):
                        command('tab'); observed=inspect()
                        if observed['wxFocus']['handle']==metadata['handle']:
                            break
                        focused=observed['wxFocus']
                        if focused.get('labelError'):
                            generic.append(focused)
                        else:
                            says('focus', focused['label'])
                        controls.append(focused)
                        if focused['label'] in ('listBox','listCtrl','panel','choice','comboBox','Điều khiển NVDA') or focused['label'].startswith('Thanh trượt.'):
                            generic.append(focused)
                    else:
                        raise AssertionError('Tab did not complete a cycle in '+category_name)
                    evidence=dict(category=category_name,controlsChecked=len(controls),genericLabels=generic)
                    if generic:
                        evidence['limitation']='Some controls have only a generic label'
                    return evidence
                scenario('nvda-settings-category-'+str(category+1), scan_page, required=False)
                if category+1<metadata['count']:
                    command('down')
        scenario('nvda-settings-cancel', lambda: (says('escape', 'Đã đóng hộp thoại NVDA'), inspect())[-1])
        scenario('nvda-menu-reopen', nvda_menu)
        scenario('nvda-menu-close', lambda: (says('escape', 'Đã đóng trình đơn NVDA'), assert_that(inspect()['foregroundClass']=='WFM-MainWnd','Menu did not return to WFM'), inspect())[-1])
        # Reproduce the phone: no synthetic keyboard input is available.
        (config/'winlator-test-block-injection').write_text('CI only')
        scenario('nvda-menu-without-key-injection', nvda_menu)
        scenario('nvda-menu-move-without-key-injection', next_menu)
        scenario('nvda-menu-close-without-key-injection', lambda: (says('escape', 'Đã đóng trình đơn NVDA'), inspect())[-1])
        # A second actual application. Switching must change the real foreground HWND.
        fixture = subprocess.Popen([wine, str(Path(__file__).with_name('touch-fixture.exe'))], env=env, stdout=output, stderr=output)
        try:
            wait(lambda: inspect()['foregroundClass'] == 'NvdaTouchFixture')
            def switch():
                command('alt_tab')
                return wait(lambda: (s if s['foregroundClass']=='WFM-MainWnd' else None) if (s:=inspect()) else None)
            scenario('switch-between-two-windows-no-injection', switch)
            def window_list():
                says('windows', 'Cửa sổ đang mở')
                state=inspect()
                assert len(state['touchMenu']['items'])>=2, state
                expected=state['touchMenu']['items'][1]
                command('down'); command('enter')
                observed=inspect()
                assert observed['foregroundTitle']==expected, observed
                return observed
            scenario('window-list-choose-actual-window', window_list)
            scenario('return-to-file-manager', lambda: (command('files'), assert_that(inspect()['foregroundClass']=='WFM-MainWnd', 'WFM not activated'), inspect())[-1])
            def desktop():
                says('desktop', 'chưa cung cấp màn hình nền')
                return dict(inspect(), limitation='No Progman shell in this Wine test prefix; explicit explanation instead of repeating C:')
            scenario('no-desktop-shell-explicit-feedback', desktop)
            def start_menu():
                says('start_menu', 'không có trình đơn Start')
                return dict(inspect(), limitation='No visible shell Start button; a tray window alone does not provide Start')
            scenario('no-start-shell-explicit-feedback', start_menu)
            (config/'winlator-test-block-injection').unlink(missing_ok=True)
        finally:
            fixture.terminate()
            try: fixture.wait(timeout=4)
            except subprocess.TimeoutExpired: fixture.kill()
    finally:
        manager.terminate()
        try: manager.wait(timeout=4)
        except subprocess.TimeoutExpired: manager.kill()
        destination = Path(__file__).parent/'probe-results/runtime-audit.json'
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps({'cases':report, 'deviceTest':False}, indent=2, ensure_ascii=False))
    (config/'winlator-test-block-injection').unlink(missing_ok=True)
    fixture = subprocess.Popen([wine, str(Path(__file__).with_name('touch-fixture.exe'))], env=env, stdout=output, stderr=output)
    try:
        wait(lambda: inspect()['foregroundClass']=='NvdaTouchFixture')
        def tab_to(identifier):
            for unused in range(15):
                observed=json.loads((Path(prefix)/'drive_c/winlator-nvda/touch-fixture.json').read_text())
                if observed['focus']==identifier:
                    return inspect()
                command('tab')
            raise AssertionError('Tab did not reach control '+str(identifier))
        scenario('win32-list-selection-and-speech', lambda: (says('down','Beta'), inspect())[-1])
        scenario('win32-button-label', lambda: (tab_to(1), says('focus','Activate test'), inspect())[-1])
        scenario('win32-checkbox-state', lambda: (tab_to(102), says('space','Đã chọn'), inspect())[-1])
        scenario('win32-edit-vietnamese', lambda: (tab_to(103), command('text','Tiếng Việt mô phỏng'), says('focus','Tiếng Việt mô phỏng'), inspect())[-1])
        def password():
            tab_to(104); says('focus','Nội dung ẩn')
            assert 'SECRET_MUST_NOT_LEAK' not in log.read_text(errors='replace')
            return inspect()
        scenario('win32-password-hidden', password)
        def combo():
            tab_to(105); says('down','Option Beta')
            observed=inspect(); assert observed['controls']['combo']==1, observed
            return observed
        scenario('win32-combobox-selection', combo)
        def radio():
            tab_to(106); says('space','Đã chọn')
            observed=inspect(); assert observed['controls']['radio']==1, observed
            return observed
        scenario('win32-radio-state', radio)
        def slider():
            tab_to(107); command('down')
            observed=inspect(); assert observed['controls']['slider']!=50, observed
            says('focus',str(observed['controls']['slider']))
            return observed
        scenario('win32-slider-value', slider)
        def question():
            tab_to(108); command('enter')
            wait(lambda: inspect()['foregroundTitle']=='NVDA audit question')
            says('focus','OK')
            command('escape')
            return wait(lambda: (s if s['foregroundClass']=='NvdaTouchFixture' else None) if (s:=inspect()) else None)
        scenario('win32-modal-question-button-and-cancel', question, required=False)
        def file_dialog():
            tab_to(109); command('enter')
            wait(lambda: inspect()['foregroundTitle']=='NVDA audit choose file')
            command('focus'); command('tab'); command('focus')
            return dict(inspect(), limitation='Only edit and Tab sampled; file list and all views not yet validated')
        scenario('win32-common-open-file-dialog', file_dialog, required=False)
        command('escape')
        def popup():
            tab_to(110); command('enter')
            wait(lambda: inspect()['menuMode'])
            says('end','Audit menu Beta'); says('up','Audit menu Alpha')
            return inspect()
        scenario('win32-native-popup-item-speech', popup, required=False)
        command('escape')
        def blocked_generic():
            tab_to(101)
            before=json.loads((Path(prefix)/'drive_c/winlator-nvda/touch-fixture.json').read_text())['selected']
            (config/'winlator-test-block-injection').write_text('CI only')
            command('down',ok=False)
            after=json.loads((Path(prefix)/'drive_c/winlator-nvda/touch-fixture.json').read_text())['selected']
            assert before==after
            (config/'winlator-test-block-injection').unlink()
            return dict(inspect(), limitation='Generic foreign controls still require keyboard delivery; WFM and NVDA direct bridges do not')
        scenario('foreign-controls-with-key-injection-unavailable', blocked_generic)
    finally:
        fixture.terminate()
        try: fixture.wait(timeout=4)
        except subprocess.TimeoutExpired: fixture.kill()
        destination.write_text(json.dumps({'cases':report, 'deviceTest':False}, indent=2, ensure_ascii=False))
    failures=[row['name'] for row in report if row['required'] and row['status']=='fail']
    assert not failures, 'Required runtime audit failed: '+', '.join(failures)
    return report
