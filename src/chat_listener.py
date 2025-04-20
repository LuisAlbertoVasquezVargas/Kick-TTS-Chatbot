# src/chat_listener.py

import json
import threading
import websockets

class ChatListener:
    def __init__(self, ws_url, chatroom_id, tts_service, logger, state):
        self.ws_url = ws_url
        self.chatroom_id = chatroom_id
        self.tts_service = tts_service
        self.logger = logger
        self.state = state

    @staticmethod
    def parse_message(raw_msg):
        content = raw_msg[1:].strip()
        parts = content.split(maxsplit=1)
        voice, message_text = (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "")
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

                            if self.state["tts_enabled"]:
                                self.logger.info(f"{sender}: {msg}", extra={"tts_state": "on", "channel": "CHAT"})
                            else:
                                self.logger.warning(f"{sender}: {msg}", extra={"tts_state": "off", "channel": "CHAT"})

                            if self.state["tts_enabled"] and msg.startswith("!"):
                                voice, message_text = self.parse_message(msg)
                                self.logger.info(f"Voice = {voice}", extra={"tts_state": "on", "channel": "CLI"})
                                tts_text = self.format_tts_text(sender, message_text)
                                threading.Thread(target=self.tts_service.play_tts, args=(tts_text, voice), daemon=True).start()
                    except Exception as e_parse:
                        self.logger.error(f"Failed to parse message: {e_parse}", extra={"channel": "CHAT"})
        except Exception as e_ws:
            self.logger.error(f"WebSocket connection failed: {e_ws}", extra={"channel": "CHAT"})
