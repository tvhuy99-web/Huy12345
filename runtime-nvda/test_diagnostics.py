#!/usr/bin/env python3
"""Exercise production diagnostic methods without requiring NVDA/Wine for these unit checks."""
import ast
from collections import deque
from pathlib import Path
import json
import time
import types
import unittest
import threading
import ctypes
from ctypes import wintypes
import os
import re

source = ast.parse(Path(__file__).with_name('winlatorStartup.py').read_text())
plugin = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == 'GlobalPlugin')
names = {'_trace', '_flush_diagnostics', '_spoke', '_reply', '_key_loop', '_execute_key_on_gui', '_foreign_foreground', '_check_pending_key', '_key_cancelled', '_clean_key_cancellations', '_wfm_start', '_wfm_poll', '_close_window', '_close_poll', 'chooseNVDAObjectOverlayClasses'}
methods = [node for node in plugin.body if isinstance(node, ast.FunctionDef) and node.name in names]
namespace = dict(time=time, deque=deque, ctypes=ctypes, wintypes=wintypes, os=os, re=re, shortcut_action=lambda text: None)
helpers = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in {'control_family', 'native_window_text', 'recover_legacy_text', 'dialog_brief'}]
exec(compile(ast.fix_missing_locations(ast.Module(body=helpers+[ast.ClassDef(name='Trace', bases=[], keywords=[], body=methods, decorator_list=[])], type_ignores=[])), '<production diagnostics>', 'exec'), namespace)


class DiagnosticTests(unittest.TestCase):
    def subject(self):
        obj = namespace['Trace']()
        obj._diagnosticEvents = deque(); obj._diagnosticCharacters = 0
        obj._diagnosticSequence = 0; obj._diagnosticDirty = False; obj._diagnosticFlush = 0
        obj._diagnosticLock=threading.RLock(); obj._closed=False
        obj._requestLock=threading.RLock();obj._pendingGuiKey=None;obj._latestKeyId=None;obj._wfmPending=None
        obj._key_cancelled=lambda request: False;obj._clean_key_cancellations=lambda: None
        obj._session = 'a'*32; obj._controlSpeech = 0; obj._speechText = ''; obj._lastContent = ''
        obj._protected_focus = lambda: False
        obj.saved = []
        obj._write = lambda name, data: obj.saved.append((name, data))
        return obj

    def test_ring_evicts_oldest_and_retains_complete_latest_unicode_speech(self):
        obj = self.subject()
        for n in range(100):
            obj._trace('speech', f'old {n} ' + 'ế'*1000)
        obj._trace('speech', 'LATEST😀')
        self.assertLessEqual(obj._diagnosticCharacters, 32000)
        self.assertNotIn('old 0 ', ''.join(e['details'] for e in obj._diagnosticEvents))
        self.assertEqual(obj._diagnosticEvents[-1]['details'], 'LATEST😀')

    def test_long_speech_keeps_more_than_old_repeat_cache_and_masks_password(self):
        obj = self.subject(); text = 'ế'*9000 + 'END'
        obj._spoke([text, object()])
        self.assertEqual(''.join(e['details'] for e in obj._diagnosticEvents), text)
        self.assertEqual(len(obj._lastContent), 2048)
        obj._protected_focus = lambda: True
        obj._spoke(['SECRET_MUST_NOT_LEAK'])
        self.assertNotIn('SECRET_MUST_NOT_LEAK', json.dumps(list(obj._diagnosticEvents)))
        self.assertIn('hidden', obj._diagnosticEvents[-1]['details'])

    def test_flush_is_bounded_atomic_writer_input_with_live_session_and_sequences(self):
        obj = self.subject(); obj._trace('command', 'id=1; action=tab'); obj._flush_diagnostics(True)
        name, frame = obj.saved[-1]
        self.assertEqual(name, 'winlator-diagnostics.json'); self.assertEqual(frame['session'], 'a'*32)
        self.assertEqual(frame['events'][0]['seq'], 1)
        count = len(obj.saved); obj._flush_diagnostics(True); self.assertEqual(count, len(obj.saved))
        self.assertLess(len(json.dumps(frame).encode()), 262144)

    def test_reply_logs_correlation_and_context_without_copying_clipboard_payload(self):
        obj = self.subject(); obj._trace_context = lambda *a, **kw: obj._trace('context', a[0])
        namespace['wx'] = types.SimpleNamespace(CallLater=lambda *args: None)
        obj._erase_reply = lambda identifier: None
        obj._reply(dict(id='request-42', action='copy_last'), True, 'clipboard', 'PRIVATE_CLIPBOARD')
        history = json.dumps(list(obj._diagnosticEvents))
        self.assertIn('request-42', history); self.assertIn('after copy_last', history)
        self.assertNotIn('PRIVATE_CLIPBOARD', history)

    def test_windows_forms_class_families_are_normalized_without_guessing_custom_controls(self):
        family = namespace['control_family']
        self.assertEqual(family('WindowsForms10.BUTTON.app.0.abcd'), 'button')
        self.assertEqual(family('WindowsForms10.EDIT.app.0.abcd'), 'edit')
        self.assertEqual(family('Button'), 'button')
        self.assertEqual(family('UnknownCustomCanvas'), 'unknowncustomcanvas')

    def test_dialog_text_includes_message_body_and_never_edit_values(self):
        snapshot = dict(title='Installer', controls=[dict(family='static', text='Installation failed: missing component.'),
            dict(family='button', text='OK'), dict(family='button', role='group', text='Install options'), dict(family='edit', text='SECRET_MUST_NOT_LEAK')])
        text = namespace['native_window_text'](snapshot)
        self.assertIn('missing component', text); self.assertNotIn('SECRET', text)
        all_text = namespace['native_window_text'](snapshot, True)
        self.assertIn('OK', all_text); self.assertNotIn('SECRET', all_text)
        self.assertIn('Install options. Nhóm', all_text); self.assertNotIn('Install options. Nút', all_text)

    def test_foreign_key_route_does_not_call_the_blocked_nvda_gui(self):
        obj = self.subject()
        class Stop:
            stopped = False
            def is_set(self): return self.stopped
            def wait(self, seconds): self.stopped = True
        class User32:
            def GetForegroundWindow(self): return 55
            def GetClassNameW(self, hwnd, buffer, size): buffer.value = 'WindowsForms10.Window.app.fixture'
            def GetWindowThreadProcessId(self, hwnd, pid): pid._obj.value = os.getpid()+1; return 7
        namespace['USER32'] = User32()
        obj._keyStop = Stop(); obj._trace_context = lambda *a, **kw: None
        obj._read_request = lambda name: dict(id='key-42', action='shortcut', text='enter', created=time.time())
        obj._key_loop()
        reply = next(value for name, value in obj.saved if name=='winlator-key-reply.json')
        self.assertTrue(reply['ok']); self.assertEqual(reply['effect'], 'external')
        self.assertEqual(reply['id'], 'key-42')

    def test_expired_native_key_never_executes_after_the_gui_unblocks(self):
        obj = self.subject(); obj._trace_context = lambda *a, **kw: None
        executed = []; obj._execute = executed.append
        obj._execute_key_on_gui(dict(id='expired-1', action='shortcut', text='enter', created=time.time()-8, _keyChannel=True))
        self.assertEqual(executed, [])
        reply = next(value for name,value in obj.saved if name=='winlator-key-reply.json')
        self.assertFalse(reply['ok']); self.assertEqual(reply['effect'], 'expired')

    def test_window_transition_reroutes_a_waiting_key_without_executing_it_twice(self):
        obj=self.subject();obj._trace_context=lambda *a,**kw: None
        request=dict(id='transition-1', action='shortcut', text='enter', created=time.time(), _keyChannel=True, _guiState='queued')
        obj._pendingGuiKey=request;obj._foreign_foreground=lambda: True
        executed=[];obj._execute=executed.append
        obj._check_pending_key();obj._execute_key_on_gui(request)
        self.assertEqual(executed,[])
        replies=[value for name,value in obj.saved if name=='winlator-key-reply.json']
        self.assertEqual(len(replies),1);self.assertEqual(replies[0]['effect'],'external')

    def test_late_old_key_acknowledgement_cannot_overwrite_a_newer_key(self):
        obj=self.subject();obj._trace_context=lambda *a,**kw: None;obj._latestKeyId='new-request'
        obj._reply(dict(id='old-request',action='shortcut',_keyChannel=True),True,'external')
        self.assertFalse(any(name=='winlator-key-reply.json' for name,value in obj.saved))

    def test_cancelled_native_key_does_not_execute_even_if_the_gui_recovers_quickly(self):
        obj=self.subject();obj._trace_context=lambda *a,**kw: None;obj._key_cancelled=lambda request: True
        request=dict(id='cancelled-1', action='shortcut', text='enter', created=time.time(), _keyChannel=True, _guiState='queued')
        executed=[];obj._execute=executed.append
        obj._execute_key_on_gui(request)
        self.assertEqual(executed,[])
        reply=next(value for name,value in obj.saved if name=='winlator-key-reply.json')
        self.assertFalse(reply['ok']);self.assertEqual(reply['effect'],'cancelled')

    def test_native_role_survives_nvdas_later_unknown_generic_client_overlay(self):
        obj=self.subject()
        namespace['controlTypes']=types.SimpleNamespace(Role=types.SimpleNamespace(UNKNOWN=0,BUTTON=9))
        marker=type('NativeOverlay',(),{});generic=type('ContentGenericClient',(),{'role':0})
        namespace['WinlatorNativeControl']=marker;namespace['native_role']=lambda hwnd:'BUTTON'
        classes=[generic]
        # Reproduces NVDA: the initial object's native fallback is BUTTON, but the
        # pending ContentGenericClient class would replace it with literal UNKNOWN.
        obj.chooseNVDAObjectOverlayClasses(types.SimpleNamespace(role=9,IAccessibleChildID=0,windowHandle=42),classes)
        self.assertIs(classes[0],marker)
        self.assertTrue(any(e['kind']=='role.repair' and 'hwnd=42' in e['details'] for e in obj._diagnosticEvents))

    def test_encoding_repair_is_reversible_and_keeps_vietnamese_and_input_intact(self):
        recover=namespace['recover_legacy_text']
        self.assertEqual(recover('ÐÅÏ¢£º'), '信息：')
        self.assertEqual(recover('ÓïÒô¿âÅäÖÃ vùng đang có focus'), '语音库配置 vùng đang có focus')
        for text in ['Tiếng Việt, cài đặt', 'café déjà vu', 'plain ASCII 123', 'ÐÓÎÏ not a known phrase']:
            self.assertEqual(recover(text),text)

    def test_technical_dialog_summary_retains_the_failure_and_full_log_remains_available(self):
        raw='The method or operation is not implemented.\n at System.Runtime.InteropServices.RegistrationServices.RegisterAssembly (...)'
        brief=namespace['dialog_brief'](raw)
        self.assertIn('Không hoàn tất',brief);self.assertIn('.NET',brief)
        self.assertNotIn('Install finished',brief);self.assertNotIn('RegisterAssembly',brief)
        self.assertIn('RegisterAssembly',raw)
        result=namespace['dialog_brief']('Install finished. Right click any executable.',True)
        self.assertIn('Chưa thể xác nhận',result)
        self.assertNotEqual(result,namespace['dialog_brief']('Install finished. Right click any executable.',False))

    def test_async_file_operation_reports_pending_before_completion_and_never_replays(self):
        obj=self.subject();obj._trace_context=lambda *a,**kw:None
        tasks=[];namespace['wx']=types.SimpleNamespace(CallLater=lambda *args:tasks.append(args))
        namespace['ui']=types.SimpleNamespace(message=lambda text:None)
        clock=types.SimpleNamespace(now=100.0)
        old_time=namespace['time'];old_ctypes=namespace['ctypes']
        class User32:
            posts=[]
            text='WFM-NVDA-3'
            def GetDlgItem(self,root,cid):return cid
            def GetWindowTextW(self,hwnd,buffer,size):buffer.value=self.text
            def PostMessageW(self,*args):self.posts.append(args);return True
            def GetForegroundWindow(self):return 77
        user=User32();namespace['USER32']=user
        namespace['ctypes']=types.SimpleNamespace(create_unicode_buffer=ctypes.create_unicode_buffer,windll=types.SimpleNamespace(kernel32=types.SimpleNamespace(GetTickCount=lambda:1000)))
        namespace['time']=types.SimpleNamespace(monotonic=lambda:clock.now,time=time.time)
        namespace['secrets']=types.SimpleNamespace(randbelow=lambda n:41)
        namespace['WFM_ACTIONS']={'enter':7}
        try:
            obj._wfm_start(dict(id='slow-enter',action='enter'),77,'enter')
            reply=next(value for name,value in obj.saved if name=='winlator-reply.json')
            self.assertEqual(reply['effect'],'pending');self.assertEqual(len(user.posts),1)
            pending=obj._wfmPending;clock.now=105.1;user.text='42|done|1'
            obj._collect_launches=lambda root:None
            namespace['native_focus_text']=lambda:'Real selected item'
            namespace['speech']=types.SimpleNamespace(cancelSpeech=lambda:None)
            obj._wfm_poll(pending)
            self.assertIsNone(obj._wfmPending);self.assertEqual(len(user.posts),1)
            self.assertTrue(any(e['kind']=='operation.completed' and '5100' in e['details'] for e in obj._diagnosticEvents))
        finally:
            namespace['time']=old_time;namespace['ctypes']=old_ctypes

    def test_native_close_sends_one_system_close_and_does_not_close_the_next_window(self):
        obj=self.subject();obj._trace_context=lambda *a,**kw:None
        tasks=[];namespace['wx']=types.SimpleNamespace(CallLater=lambda *args:tasks.append(args))
        spoken=[];obj._control_message=spoken.append
        class User32:
            posts=[]
            def GetForegroundWindow(self):return 77
            def GetWindowThreadProcessId(self,hwnd,pid):pid._obj.value=os.getpid()+1
            def IsWindowEnabled(self,hwnd):return True
            def PostMessageW(self,*args):self.posts.append(args);return True
            def IsWindow(self,hwnd):return False
        user=User32();namespace['USER32']=user
        obj._close_window(dict(id='close-1',action='close_window'))
        self.assertEqual(user.posts,[(77,0x112,0xf060,0)])
        obj._close_poll('close-1',77,os.getpid()+1,0)
        self.assertEqual(len(user.posts),1);self.assertIn('Đã đóng cửa sổ.',spoken)


if __name__ == '__main__':
    unittest.main()
