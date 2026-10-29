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
            row = dict(name=name, status='pass', required=required, evidence=evidence)
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

    def assert_that(value, detail):
        assert value, detail

    (config/'winlator-test-block-injection').unlink(missing_ok=True)
    binary = Path(__file__).resolve().parents[1]/'app/app/src/main/assets/nvda/wfm.exe'
    manager = subprocess.Popen([wine, str(binary)], env=env, stdout=output, stderr=output)
    try:
        wait(lambda: inspect()['foregroundClass'] == 'WFM-MainWnd')
        initial = inspect()
        scenario('startup-computer', lambda: (command('focus'), assert_that('Ổ đĩa' in log.read_text(errors='replace')[-10000:], 'Drive not spoken'), inspect())[-1])
        def root_parent():
            command('enter'); command('backspace')
            observed = inspect()
            assert observed['foregroundClass'] == 'WFM-MainWnd', observed
            command('focus')
            return observed
        scenario('drive-back-to-computer', root_parent)
        def nvda_menu():
            command('nvda_menu')
            observed = wait(lambda: (s if s['menuMode'] or s.get('touchMenu') else None) if (s:=inspect()) else None)
            return observed
        scenario('nvda-menu-open', nvda_menu)
        scenario('nvda-menu-next', lambda: (command('down'), inspect())[-1])
        scenario('nvda-menu-close', lambda: (command('escape'), inspect())[-1])
        # A second actual application. Switching must change the real foreground HWND.
        fixture = subprocess.Popen([wine, str(Path(__file__).with_name('touch-fixture.exe'))], env=env, stdout=output, stderr=output)
        try:
            wait(lambda: inspect()['foregroundClass'] == 'NvdaTouchFixture')
            def switch():
                command('alt_tab')
                return wait(lambda: (s if s['foregroundClass']=='WFM-MainWnd' else None) if (s:=inspect()) else None)
            scenario('switch-between-two-windows', switch)
            def desktop():
                command('desktop')
                observed = inspect()
                assert observed['foregroundClass'] != 'WFM-MainWnd', observed
                return observed
            scenario('show-desktop', desktop, required=False)
            def start_menu():
                command('start_menu')
                observed=inspect()
                assert observed['menuMode'] or observed['foregroundClass'] in ('Shell_TrayWnd','DV2ControlHost'), observed
                return observed
            scenario('shell-start-menu', start_menu, required=False)
            command('escape', ok=None)
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
    # Audit is diagnostic initially: results are not replaced by a green build badge.
    return report
