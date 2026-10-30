#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import game_voice as voice


class GameVoiceTests(unittest.TestCase):
    def test_unknown_dll_is_rejected_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp,'xinyitts.dll');target.write_bytes(b'unknown')
            with self.assertRaises(ValueError):voice.configure(temp,b'proxy',True,'0'*64)
            self.assertEqual(target.read_bytes(),b'unknown');self.assertFalse(Path(temp,voice.ORIGINAL).exists())

    def test_install_restore_and_changed_backup_protection(self):
        expected=dict(zip(voice.EXPORTS,range(1,len(voice.EXPORTS)+1)))
        with tempfile.TemporaryDirectory() as temp, patch.object(voice,'pe_exports',return_value=expected):
            folder=Path(temp);target=folder/'xinyitts.dll';target.write_bytes(b'original');sha=voice.digest(b'original')
            self.assertEqual(voice.configure(folder,b'proxy',True,sha),'enabled')
            self.assertEqual(target.read_bytes(),b'proxy');self.assertEqual((folder/voice.ORIGINAL).read_bytes(),b'original')
            self.assertEqual(voice.configure(folder,b'proxy',True,sha),'already-enabled')
            (folder/voice.ORIGINAL).write_bytes(b'changed')
            with self.assertRaises(ValueError):voice.configure(folder,b'proxy',False,sha)
            self.assertEqual(target.read_bytes(),b'proxy')
            (folder/voice.ORIGINAL).write_bytes(b'original')
            self.assertEqual(voice.configure(folder,b'proxy',False,sha),'disabled')
            self.assertEqual(target.read_bytes(),b'original');self.assertFalse((folder/voice.ORIGINAL).exists())

    def test_partial_install_is_restorable_and_never_overwrites_unrelated_dll(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);target=folder/'xinyitts.dll';backup=folder/voice.ORIGINAL
            backup.write_bytes(b'original');target.write_bytes(b'original')
            (folder/voice.MANIFEST).write_text(json.dumps(dict(originalSha256=voice.digest(b'original'),proxySha256=voice.digest(b'proxy'))))
            self.assertEqual(voice.configure(folder,b'proxy',False,voice.digest(b'original')),'disabled')
            backup.write_bytes(b'unrelated')
            with self.assertRaises(ValueError):voice.configure(folder,b'proxy',True,voice.digest(b'original'))
            self.assertEqual(backup.read_bytes(),b'unrelated')

    def test_reader_handles_partial_lines_rotation_and_pid_reuse(self):
        reader=voice.TraceReader()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp,'game-voice-42.jsonl')
            def event(seq,instance=1):return json.dumps(dict(pid=42,instance=instance,seq=seq,phase='begin'))+'\n'
            path.write_text(event(1)+'{"broken":')
            self.assertEqual(len(reader.collect(temp)),1);self.assertEqual(reader.collect(temp),[])
            path.write_text(event(4));events=reader.collect(temp)
            self.assertEqual(events[0]['missing'],2);self.assertEqual(events[1]['seq'],4)
            path.write_text(event(1,2));self.assertEqual(reader.collect(temp)[0]['instance'],2)

    def test_malformed_pe_is_rejected(self):
        for data in (b'',b'MZ'+b'\0'*100,b'not a dll'):
            with self.assertRaises(ValueError):voice.pe_exports(data)

if __name__=='__main__':unittest.main()
