# src/tts_service.py

import time
import boto3
from pydub import AudioSegment
from pydub.playback import play
from threading import Lock
from src.config import Config

class TTSService:
    def __init__(self, aws_region, logger, state, default_voice='Mia'):
        self.logger = logger
        self.default_voice = default_voice
        self.client = boto3.Session(region_name=aws_region).client('polly')
        self.lock = Lock()
        self.last_play_time = 0
        self.state = state

    def synthesize_speech(self, text, voice_id=None, engine='standard', output_format='mp3', output_file='speech.mp3'):
        voice = voice_id or self.default_voice
        response = self.client.synthesize_speech(Text=text, VoiceId=voice, OutputFormat=output_format, Engine=engine)
        with open(output_file, 'wb') as f:
            f.write(response['AudioStream'].read())
        return output_file

    def play_tts(self, text, voice_id=None):
        voice = voice_id or self.default_voice
        try:
            file = self.synthesize_speech(text, voice_id=voice, engine='standard')
        except Exception as e_std:
            self.logger.error(
                f"Standard engine failed: {e_std}", extra={
                    "tts_state": "on" if self.state["tts_enabled"] else "off",
                    "channel": "CLI"
                }
            )
            try:
                file = self.synthesize_speech(text, voice_id=voice, engine='neural')
            except Exception as e_neural:
                self.logger.error(
                    f"Neural engine failed: {e_neural}", extra={
                        "tts_state": "on" if self.state["tts_enabled"] else "off",
                        "channel": "CLI"
                    }
                )
                return

        try:
            audio = AudioSegment.from_mp3(file)
        except Exception as e_audio:
            self.logger.error(f"Error reading audio file: {e_audio}")
            return

        with self.lock:
            now = time.time()
            elapsed = now - self.last_play_time
            if elapsed < Config.TTS_PLAYBACK_DELAY:
                time.sleep(Config.TTS_PLAYBACK_DELAY - elapsed)
            try:
                play(audio)
            except Exception as e_play:
                self.logger.error(f"Audio playback error: {e_play}")
            self.last_play_time = time.time()
