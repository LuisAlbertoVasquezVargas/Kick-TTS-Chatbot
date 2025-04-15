# src/logger_setup.py

import sys
import logging
import colorama

class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: colorama.Fore.CYAN,
        logging.INFO: colorama.Fore.GREEN,
        logging.WARNING: colorama.Fore.YELLOW,
        logging.ERROR: colorama.Fore.RED,
        logging.CRITICAL: colorama.Fore.RED + colorama.Style.BRIGHT,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, '')
        level_tag = f"{color}[{record.levelname}]{colorama.Style.RESET_ALL}"
        
        tts_tag = ""
        if hasattr(record, 'tts_state'):
            tts_tag = f" {color}[tts={record.tts_state}]{colorama.Style.RESET_ALL}"
        
        channel_tag = ""
        if hasattr(record, 'channel'):
            channel_tag = f" {color}[{record.channel}]{colorama.Style.RESET_ALL}"
        
        message = record.getMessage()
        return f"{level_tag}{tts_tag}{channel_tag} {message}"

def setup_logger(name="TTSChatbot", level=logging.DEBUG):
    colorama.init()
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter())
    logger.addHandler(handler)
    return logger
