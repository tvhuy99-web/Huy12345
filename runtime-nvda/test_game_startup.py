#!/usr/bin/env python3
"""Verify backup integrity and interrupted-transaction recovery without shipping game data."""
import struct
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import game_startup as startup

def fixture():
    data=bytearray(0x1a0200);data[:2]=b'MZ';struct.pack_into('<I',data,0x3c,0x80)
    data[0x80:0x84]=b'PE\0\0';struct.pack_into('<HH',data,0x84,0x14c,1)
    struct.pack_into('<H',data,0x94,0xe0);struct.pack_into('<H',data,0x98,0x10b)
    struct.pack_into('<IIII',data,0x178+8,0x1a0000,0x1000,0x1a0000,0x200)
    for rva,value in ((startup.BRANCH,bytes.fromhex('74 a8 db 44 24 74')),(startup.CAVE,b'\x90'*15)):
        at=startup.offset(data,rva,len(value));data[at:at+len(value)]=value
    return bytes(data)

class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name,'zetianji.exe');self.original=fixture();self.path.write_bytes(self.original)
        self.pin=patch.object(startup,'ORIGINAL_SHA256',startup.digest(self.original));self.pin.start();self.addCleanup(self.pin.stop)
    def test_apply_repeat_restore_keeps_original_and_only_changes_expected_code_ranges(self):
        startup.configure(self.path,True);fixed=self.path.read_bytes();startup.configure(self.path,True)
        self.assertEqual(self.path.read_bytes(),fixed)
        self.assertEqual(self.path.with_name(startup.BACKUP).read_bytes(),self.original)
        allowed=set()
        for rva,size in ((startup.BRANCH,6),(startup.CAVE,15)):
            at=startup.offset(self.original,rva,size);allowed.update(range(at,at+size))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(self.original,fixed)) if a!=b))
        self.assertEqual(len(fixed),len(self.original));startup.configure(self.path,False)
        self.assertEqual(self.path.read_bytes(),self.original);self.assertFalse(self.path.with_name(startup.MANIFEST).exists())
    def test_unknown_executable_is_never_modified(self):
        self.path.write_bytes(b'unknown');self.assertRaises(ValueError,startup.configure,self.path,True)
        self.assertEqual(self.path.read_bytes(),b'unknown');self.assertFalse(self.path.with_name(startup.BACKUP).exists())
    def test_modified_target_is_not_overwritten_on_restore(self):
        startup.configure(self.path,True);changed=self.path.read_bytes()+b'user-change';self.path.write_bytes(changed)
        self.assertRaises(ValueError,startup.configure,self.path,False);self.assertEqual(self.path.read_bytes(),changed)
    def test_modified_backup_blocks_both_apply_and_restore(self):
        startup.configure(self.path,True);fixed=self.path.read_bytes();self.path.with_name(startup.BACKUP).write_bytes(b'changed')
        for enabled in (True,False):self.assertRaises(ValueError,startup.configure,self.path,enabled)
        self.assertEqual(self.path.read_bytes(),fixed)
    def test_interrupted_target_write_can_retry_without_replacing_backup(self):
        atomic=startup.game_voice.atomic_write
        def write(path,data):
            if path==self.path:raise OSError('simulated interrupted target write')
            atomic(path,data)
        with patch.object(startup.game_voice,'atomic_write',side_effect=write):
            self.assertRaises(OSError,startup.configure,self.path,True)
        self.assertEqual(self.path.read_bytes(),self.original)
        startup.configure(self.path,True);startup.configure(self.path,False)
        self.assertEqual(self.path.read_bytes(),self.original)
    def test_unknown_manifest_and_invalid_pe_are_rejected(self):
        self.path.with_name(startup.MANIFEST).write_text('{"kind":"user-file"}')
        self.assertRaises(ValueError,startup.configure,self.path,True);self.assertEqual(self.path.read_bytes(),self.original)
        self.path.with_name(startup.MANIFEST).unlink();bad=b'MZ'+b'\0'*100;self.path.write_bytes(bad)
        with patch.object(startup,'ORIGINAL_SHA256',startup.digest(bad)):
            self.assertRaises(ValueError,startup.configure,self.path,True)

if __name__=='__main__':unittest.main()
