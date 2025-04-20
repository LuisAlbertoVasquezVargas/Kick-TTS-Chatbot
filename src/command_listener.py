# src/command_listener.py

import sys

class CommandListener:
    def __init__(self, logger, state):
        self.logger = logger
        self.state = state

    def set_tts(self, status):
        self.state["tts_enabled"] = status
        level = "info" if status else "warning"
        msg = f"tts={'on' if status else 'off'}"
        getattr(self.logger, level)(msg, extra={"tts_state": "on" if status else "off", "channel": "CLI"})

    def listen(self):
        self.logger.info(
            "Initialized program. Toggle TTS state by typing a command containing 'on' or 'off'",
            extra={
                "tts_state": "on" if self.state["tts_enabled"] else "off",
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
