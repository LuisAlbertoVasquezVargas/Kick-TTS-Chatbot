# src/tts_service.py

import time
import boto3
from pydub import AudioSegment
from pydub.playback import play
from threading import Lock
from src.config import Config

class TTSService:
    def __init__(self, aws_region, logger, default_voice='Mia'):
        self.logger = logger
        self.default_voice = default_voice
        self.client = boto3.Session(region_name=aws_region).client('polly')
        self.lock = Lock()
        self.last_play_time = 0

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
            self.logger.error("Standard engine failed: %s", e_std)
            try:
                file = self.synthesize_speech(text, voice_id=voice, engine='neural')
            except Exception as e_neural:
                self.logger.error("Neural engine failed: %s", e_neural)
                return

        try:
            audio = AudioSegment.from_mp3(file)
        except Exception as e_audio:
            self.logger.error("Error reading audio file: %s", e_audio)
            return

        with self.lock:
            now = time.time()
            elapsed = now - self.last_play_time
            required_delay = Config.TTS_PLAYBACK_DELAY
            if elapsed < required_delay:
                delay = required_delay - elapsed
                self.logger.debug("Waiting for %.2f seconds before playing audio...", delay)
                time.sleep(delay)
            try:
                play(audio)
            except Exception as e_play:
                self.logger.error("Audio playback error: %s", e_play)
            self.last_play_time = time.time()
