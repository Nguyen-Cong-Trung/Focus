"""Small rotating logs for launches through pythonw/shortcuts."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def setup_logging(directory):
    folder = Path(directory) / 'logs'
    folder.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(folder / 'deep-focus.log', maxBytes=524288, backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    sys.excepthook = lambda *error: logging.getLogger('uncaught').error('Unhandled error', exc_info=error)
