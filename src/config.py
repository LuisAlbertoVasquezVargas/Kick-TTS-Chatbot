# src/config.py

import os
from dotenv import load_dotenv

load_dotenv(override=True)

class Config:
    # Constants that are unlikely to change:
    TEMP_DIR = r"C:\MyTemp"
    WS_URL = "wss://ws-us2.pusher.com/app/32cbd69e4b950bf97679?protocol=7&client=js&version=8.2.0&flash=false"
    TTS_PLAYBACK_DELAY = 2.0

    # Environment-overridable parameters:
    CHATROOM_ID = int(os.getenv("CHATROOM_ID", "34754537"))
    AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
