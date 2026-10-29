#!/usr/bin/env python3
"""Exercise production diagnostic methods without requiring NVDA/Wine for these unit checks."""
import ast
from collections import deque
from pathlib import Path
import json
import time
import types
import unittest

source = ast.parse(Path(__file__).with_name('winlatorStartup.py').read_text())
plugin = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == 'GlobalPlugin')
names = {'_trace', '_flush_diagnostics', '_spoke', '_reply'}
methods = [node for node in plugin.body if isinstance(node, ast.FunctionDef) and node.name in names]
namespace = dict(time=time, deque=deque)
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='Trace', bases=[], keywords=[], body=methods, decorator_list=[])], type_ignores=[])), '<production diagnostics>', 'exec'), namespace)


class DiagnosticTests(unittest.TestCase):
    def subject(self):
        obj = namespace['Trace']()
        obj._diagnosticEvents = deque(); obj._diagnosticCharacters = 0
        obj._diagnosticSequence = 0; obj._diagnosticDirty = False; obj._diagnosticFlush = 0
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


if __name__ == '__main__':
    unittest.main()
