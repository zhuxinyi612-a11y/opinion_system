# utils/logger.py
import logging
from pathlib import Path

def setup_logger(log_file: Path, level: str = 'INFO'):
    logger = logging.getLogger('PreprocessLogger')
    logger.setLevel(getattr(logging, level.upper()))
    if logger.handlers:
        return logger
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console)
    return logger