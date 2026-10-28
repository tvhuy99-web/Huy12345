# SPDX-License-Identifier: MIT
"""NVDA add-on: startup speech and local health, with no captured UI content."""
import json
import os
import time
import globalVars
import globalPluginHandler
import synthDriverHandler
import ui
import wx


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super().__init__()
        self._closed = False
        self._path = os.path.join(globalVars.appArgs.configPath, 'winlator-status.json')
        self._timer = wx.CallLater(2500, self._started)

    def _started(self):
        if self._closed:
            return
        synth = synthDriverHandler.getSynth()
        marker = os.path.join(globalVars.appArgs.configPath, 'winlator-voice-configured')
        if synth and synth.name == 'espeak' and not os.path.exists(marker):
            voices = [(identifier, info) for identifier, info in synth.availableVoices.items()
                      if (getattr(info, 'language', '') or '').replace('_', '-').lower().split('-')[0] == 'vi']
            if voices:
                voices.sort(key=lambda item: (getattr(item[1], 'language', '').lower() != 'vi', item[0]))
                synth.voice = voices[0][0]
                synth.saveSettings()
                with open(marker, 'w', encoding='utf-8') as stream:
                    stream.write(voices[0][0])
        ui.message('NVDA đã khởi động. Bạn có thể dùng các phím điều hướng Windows.')
        self._heartbeat()

    def _heartbeat(self):
        if self._closed:
            return
        synth = synthDriverHandler.getSynth()
        state = {'version': 1, 'pid': os.getpid(), 'heartbeat': int(time.time()), 'state': 'ready',
                 'synth': synth.name if synth else 'silence'}
        temporary = self._path + '.tmp'
        try:
            with open(temporary, 'w', encoding='utf-8') as stream:
                json.dump(state, stream)
            os.replace(temporary, self._path)
        except OSError:
            pass
        self._timer = wx.CallLater(3000, self._heartbeat)

    def terminate(self):
        self._closed = True
        if self._timer:
            self._timer.Stop()
        try:
            os.remove(self._path)
        except OSError:
            pass
        super().terminate()
