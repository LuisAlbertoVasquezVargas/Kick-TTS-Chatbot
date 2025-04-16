# src/command_listener.py

import sys

class CommandListener:
    def __init__(self, logger, initial_state=True):
        self.logger = logger
        self._tts_enabled = initial_state

    def set_tts(self, status):
        self._tts_enabled = status
        if self._tts_enabled:
            self.logger.info("tts=%s", "on" if self._tts_enabled else "off", extra={"tts_state": "on", "channel": "CLI"})
        else:
            self.logger.warning("tts=%s", "on" if self._tts_enabled else "off", extra={"tts_state": "off", "channel": "CLI"})

    def is_tts_enabled(self):
        return self._tts_enabled

    def listen(self):
        if self._tts_enabled:
            self.logger.info(
                "Initialized program. Toggle TTS state by typing a command containing 'on' or 'off'",
                extra={
                    "tts_state": "on",
                    "channel": "CLI"
                }
            )
        else:
            self.logger.warning(
                "Initialized program. Toggle TTS state by typing a command containing 'on' or 'off'",
                extra={
                    "tts_state": "off",
                    "channel": "CLI"
                }
            )
        while True:
            line = sys.stdin.readline().strip().lower()
            if not line:
                continue
            if "on" in line:
                self.set_tts(True)
            elif "off" in line:
                self.set_tts(False)
