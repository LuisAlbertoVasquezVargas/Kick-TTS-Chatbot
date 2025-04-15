# src/main.py

import os
import time
import asyncio
import threading
import argparse

from src.config import Config
from src.logger_setup import setup_logger
from src.tts_service import TTSService
from src.chat_listener import ChatListener
from src.command_listener import CommandListener

def setup_temp_dir():
    if not os.path.exists(Config.TEMP_DIR):
        os.makedirs(Config.TEMP_DIR)
    os.environ["TMP"] = Config.TEMP_DIR
    os.environ["TEMP"] = Config.TEMP_DIR

def parse_args():
    parser = argparse.ArgumentParser(description="Kick Chat TTS Webhook")
    parser.add_argument('--set', choices=['on', 'off'], default='on', help='Enable or disable TTS')
    parser.add_argument('--log-level', default='INFO', help='Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
    return parser.parse_args()

def main():
    setup_temp_dir()
    args = parse_args()

    # CLI commands listener    
    logger = setup_logger(level=getattr(__import__('logging'), args.log_level.upper(), __import__('logging').INFO))
    command_listener = CommandListener(logger, initial_state=(args.set == 'on'))
    
    # Kick's chat listener
    tts_service = TTSService(aws_region=Config.AWS_REGION, logger=logger)
    chat_listener = ChatListener(
        ws_url=Config.WS_URL,
        chatroom_id=Config.CHATROOM_ID,
        tts_service=tts_service,
        logger=logger,
        tts_enabled_callable=command_listener.is_tts_enabled
    )
    
    threading.Thread(target=command_listener.listen, daemon=True).start()
    threading.Thread(target=lambda: asyncio.run(chat_listener.listen()), daemon=True).start()
    
    while True:
        time.sleep(1)

if __name__ == '__main__':
    main()
