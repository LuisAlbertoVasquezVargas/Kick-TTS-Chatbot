# src/chat_listener.py

import json
import threading
import websockets

class ChatListener:
    def __init__(self, ws_url, chatroom_id, tts_service, logger, tts_enabled_callable):
        self.ws_url = ws_url
        self.chatroom_id = chatroom_id
        self.tts_service = tts_service
        self.logger = logger
        self.tts_enabled = tts_enabled_callable

    @staticmethod
    def parse_message(raw_msg):
        content = raw_msg[1:].strip()
        parts = content.split(maxsplit=1)
        if len(parts) == 2:
            voice, message_text = parts
        else:
            voice = parts[0]
            message_text = ""
        voice = "Mia" if voice.lower() == "m" else voice.lower().capitalize()
        return voice, message_text

    @staticmethod
    def format_tts_text(sender, message_text):
        return f"{sender} dice {message_text}"

    async def listen(self):
        try:
            async with websockets.connect(self.ws_url) as websocket:
                subscribe_msg = {"event": "pusher:subscribe", "data": {"auth": "", "channel": f"chatrooms.{self.chatroom_id}.v2"}}
                await websocket.send(json.dumps(subscribe_msg))
                while True:
                    message = await websocket.recv()
                    try:
                        data = json.loads(message)
                        if data.get("event") == "App\\Events\\ChatMessageEvent":
                            payload = json.loads(data.get("data", "{}"))
                            msg = payload.get("content", "")
                            sender = payload.get("sender", {}).get("username", "???")
                            # Determine TTS state as a string: "on" or "off"
                            status = "on" if self.tts_enabled() else "off"

                            # Use extra to pass tts_state and channel instead of including them manually.
                            if status:
                                self.logger.info("%s: %s", sender, msg, extra={"tts_state": status, "channel": "CHAT"})
                            else:
                                self.logger.warning("%s: %s", sender, msg, extra={"tts_state": status, "channel": "CHAT"})

                            # If TTS is enabled and message starts with "!" then do TTS:
                            if self.tts_enabled() and msg.startswith("!"):
                                voice, message_text = self.parse_message(msg)
                                self.logger.info("Voice = %s", voice, extra={"tts_state": "on", "channel": "CLI"})
                                tts_text = self.format_tts_text(sender, message_text)
                                threading.Thread(target=self.tts_service.play_tts, args=(tts_text, voice), daemon=True).start()
                    except Exception as e_parse:
                        self.logger.error("Failed to parse message: %s", e_parse, extra={"channel": "CHAT"})
        except Exception as e_ws:
            self.logger.error("WebSocket connection failed: %s", e_ws, extra={"channel": "CHAT"})
