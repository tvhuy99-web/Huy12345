# SPDX-License-Identifier: MIT
"""CI-only NVDA add-on. Never copied to APK assets or the portable package."""
import ctypes
import os
import globalVars
import globalPluginHandler
import keyboardHandler


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super().__init__()
        self._config = globalVars.appArgs.configPath
        self._original_key = keyboardHandler.KeyboardInputGesture.send
        self._original_input = ctypes.windll.user32.SendInput

        def check():
            if os.path.exists(os.path.join(self._config, 'winlator-test-block-injection')):
                with open(os.path.join(self._config, 'winlator-test-injection-attempts'), 'a', encoding='ascii') as stream:
                    stream.write('1\n')
                raise RuntimeError('CI deliberately blocked the old keyboard injection path')

        def key(gesture, *args, **kwargs):
            check()
            return self._original_key(gesture, *args, **kwargs)

        def send_input(*args):
            check()
            return self._original_input(*args)

        keyboardHandler.KeyboardInputGesture.send = key
        ctypes.windll.user32.SendInput = send_input

    def terminate(self):
        keyboardHandler.KeyboardInputGesture.send = self._original_key
        ctypes.windll.user32.SendInput = self._original_input
        super().terminate()
