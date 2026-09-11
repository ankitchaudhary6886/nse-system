"""
Simple file + console logger for the NSE system.
Writes to data/logs/nse.log (rotated daily, 14 days kept) and prints to stdout.
"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = os.path.join("data", "logs")
_LOGGERS = {}


def get_logger(name="nse"):
    """Return a configured logger. Safe to call multiple times."""
    if name in _LOGGERS:
        return _LOGGERS[name]
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        _LOGGERS[name] = logger
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

    fh = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, f"{name}.log"),
        when="midnight", backupCount=14, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    _LOGGERS[name] = logger
    return logger