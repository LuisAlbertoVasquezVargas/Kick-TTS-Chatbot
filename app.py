# app.py

import os
import tempfile

temp_dir = r"C:\MyTemp"
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)
tempfile.tempdir = temp_dir
os.environ["TMP"] = temp_dir
os.environ["TEMP"] = temp_dir

import asyncio
import json
import threading
import sys
import time
import argparse
import boto3
from pydub import AudioSegment
from pydub.playback import play
import websockets
from dotenv import load_dotenv

load_dotenv(override=True)

parser = argparse.ArgumentParser(description="Kick Chat TTS Webhook")
parser.add_argument('--set', choices=['on', 'off'], default='on', help='Enable or disable TTS')
args = parser.parse_args()
tts_enabled = (args.set == 'on')
print(f"Initial TTS is {'enabled' if tts_enabled else 'disabled'}")

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
        print("Standard engine failed:", e_std)
        try:
            file = synthesize_speech(text, voice_id=voice_id, engine='neural')
        except Exception as e_neural:
            print("Neural engine failed:", e_neural)
            return
    try:
        audio = AudioSegment.from_mp3(file)
        play(audio)
    except Exception as e_play:
        print("Audio playback error:", e_play)

def command_line_listener():
    print("You can toggle TTS state by typing a command containing 'on' or 'off'")
    while True:
        line = sys.stdin.readline().strip().lower()
        global tts_enabled
        if line == "":
            pass
        elif "on" in line:
            tts_enabled = True
            print("TTS is enabled")
        else:
            tts_enabled = False
            print("TTS is disabled")

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
                        username = payload.get("sender", {}).get("username", "Desconocido")
                        print(f"[CHAT] {'TTS_ENABLED' if tts_enabled else 'TTS_DISABLED'} {username}: {msg}")
                        if tts_enabled and msg.startswith("!m "):
                            content = msg[3:].strip()
                            parts = content.split(maxsplit=1)
                            if parts and parts[0].startswith("!"):
                                voice = parts[0][1:]
                                voice = voice.lower().capitalize()
                                message_text = parts[1] if len(parts) > 1 else ""
                            else:
                                voice = "Mia"
                                message_text = content
                            print(f"Voice = {voice}")
                            # Now pass "sender dice message" to TTS
                            tts_text = f"{username} dice {message_text}"
                            threading.Thread(target=play_tts, args=(tts_text, voice), daemon=True).start()
                except Exception as e_parse:
                    print("[ERROR] Failed to parse message:", e_parse)
    except Exception as e_ws:
        print("[ERROR] WebSocket connection failed:", e_ws)

if __name__ == '__main__':
    threading.Thread(target=command_line_listener, daemon=True).start()
    threading.Thread(target=lambda: asyncio.run(kick_listener(CHATROOM_ID)), daemon=True).start()
    while True:
        time.sleep(1)
