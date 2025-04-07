# app.py

import os
import tempfile
temp_dir = r"C:\MyTemp"
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)
tempfile.tempdir = temp_dir
os.environ["TMP"] = temp_dir
os.environ["TEMP"] = temp_dir

import sys
import asyncio
import json
import threading
import time
import argparse
import boto3
from pydub import AudioSegment
from pydub.playback import play
import websockets
from dotenv import load_dotenv
import logging
import colorama

colorama.init()

class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: colorama.Fore.CYAN,
        logging.INFO: colorama.Fore.GREEN,
        logging.WARNING: colorama.Fore.YELLOW,
        logging.ERROR: colorama.Fore.RED,
        logging.CRITICAL: colorama.Fore.RED + colorama.Style.BRIGHT,
    }
    def format(self, record):
        msg = record.getMessage().strip()
        color = self.COLORS.get(record.levelno, '')
        level_tag = f"[{record.levelname}]"
        if msg.lower() == "tts=on":
            colored_status = f"{colorama.Fore.GREEN}{msg}{colorama.Style.RESET_ALL}"
            return f"{color}{level_tag}{colorama.Style.RESET_ALL} {colored_status}"
        elif msg.lower() == "tts=off":
            colored_status = f"{colorama.Fore.YELLOW}{msg}{colorama.Style.RESET_ALL}"
            return f"{color}{level_tag}{colorama.Style.RESET_ALL} {colored_status}"
        if msg.startswith("[CHAT]"):
            prefix = "[CHAT]"
            rest = msg[len(prefix):].lstrip()
            # Check for a tts status at the beginning of the rest
            words = rest.split(maxsplit=1)
            if words:
                tts_status = words[0]
                if tts_status.lower() == "tts=on":
                    colored_status = f"{colorama.Fore.GREEN}{tts_status}{colorama.Style.RESET_ALL}"
                elif tts_status.lower() == "tts=off":
                    colored_status = f"{colorama.Fore.YELLOW}{tts_status}{colorama.Style.RESET_ALL}"
                else:
                    colored_status = tts_status
                new_rest = f"{colored_status} {words[1]}" if len(words) == 2 else colored_status
            else:
                new_rest = rest
            combined_prefix = f"{level_tag} {prefix}"
            return f"{color}{combined_prefix}{colorama.Style.RESET_ALL} {new_rest}"
        return f"{color}{level_tag}{colorama.Style.RESET_ALL} {msg}"

logger = logging.getLogger("TTSChatbot")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter())
logger.addHandler(handler)

load_dotenv(override=True)

parser = argparse.ArgumentParser(description="Kick Chat TTS Webhook")
parser.add_argument('--set', choices=['on', 'off'], default='on', help='Enable or disable TTS')
parser.add_argument('--log-level', default='INFO', help='Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
args = parser.parse_args()
tts_enabled = (args.set == 'on')
logger.info("tts=%s", "on" if tts_enabled else "off")
logger.setLevel(getattr(logging, args.log_level.upper(), logging.INFO))

polly_client = boto3.Session(region_name=os.getenv("AWS_DEFAULT_REGION")).client('polly')

def synthesize_speech(text, voice_id='Mia', engine='standard', output_format='mp3', output_file='speech.mp3'):
    response = polly_client.synthesize_speech(Text=text, VoiceId=voice_id, OutputFormat=output_format, Engine=engine)
    with open(output_file, 'wb') as f:
        f.write(response['AudioStream'].read())
    return output_file

def play_tts(text, voice_id='Mia'):
    try:
        file = synthesize_speech(text, voice_id=voice_id, engine='standard')
    except Exception as e_std:
        logger.error("Standard engine failed: %s", e_std)
        try:
            file = synthesize_speech(text, voice_id=voice_id, engine='neural')
        except Exception as e_neural:
            logger.error("Neural engine failed: %s", e_neural)
            return
    try:
        audio = AudioSegment.from_mp3(file)
        play(audio)
    except Exception as e_play:
        logger.error("Audio playback error: %s", e_play)

def parse_message(raw_msg):
    content = raw_msg[1:].strip()
    parts = content.split(maxsplit=1)
    if len(parts) == 2:
        voice, message_text = parts
    else:
        voice = parts[0]
        message_text = ""
    if voice.lower() == "m":
        voice = "Mia"
    else:
        voice = voice.lower().capitalize()
    return voice, message_text

def format_tts_text(sender, message_text):
    return f"{sender} dice {message_text}"

def command_line_listener():
    logger.info("You can toggle TTS state by typing a command containing 'on' or 'off'")
    while True:
        line = sys.stdin.readline().strip().lower()
        global tts_enabled
        if not line:
            continue
        if "on" in line:
            tts_enabled = True
            logger.info("tts=on")
        else:
            tts_enabled = False
            logger.info("tts=off")

CHATROOM_ID = int(os.getenv("CHATROOM_ID", 34754537))

async def kick_listener(chatroom_id):
    ws_url = "wss://ws-us2.pusher.com/app/32cbd69e4b950bf97679?protocol=7&client=js&version=8.2.0&flash=false"
    try:
        async with websockets.connect(ws_url) as websocket:
            subscribe_msg = {"event": "pusher:subscribe", "data": {"auth": "", "channel": f"chatrooms.{chatroom_id}.v2"}}
            await websocket.send(json.dumps(subscribe_msg))
            while True:
                message = await websocket.recv()
                try:
                    data = json.loads(message)
                    if data.get("event") == "App\\Events\\ChatMessageEvent":
                        payload = json.loads(data.get("data", "{}"))
                        msg = payload.get("content", "")
                        username = payload.get("sender", {}).get("username", "???")
                        status = "on" if tts_enabled else "off"
                        logger.info("[CHAT] tts=%s %s: %s", status, username, msg)
                        if tts_enabled and msg.startswith("!"):
                            voice, message_text = parse_message(msg)
                            logger.info("Voice = %s", voice)
                            tts_text = format_tts_text(username, message_text)
                            threading.Thread(target=play_tts, args=(tts_text, voice), daemon=True).start()
                except Exception as e_parse:
                    logger.error("[ERROR] Failed to parse message: %s", e_parse)
    except Exception as e_ws:
        logger.error("[ERROR] WebSocket connection failed: %s", e_ws)

if __name__ == '__main__':
    threading.Thread(target=command_line_listener, daemon=True).start()
    threading.Thread(target=lambda: asyncio.run(kick_listener(CHATROOM_ID)), daemon=True).start()
    while True:
        time.sleep(1)
