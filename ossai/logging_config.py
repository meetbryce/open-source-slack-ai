import logging
import sys
import os


def setup_logger(name: str = __name__) -> logging.Logger:
    env_level = os.getenv("LOG_LEVEL", "").upper()
    level = (
        logging._nameToLevel[env_level]
        if env_level in logging._nameToLevel
        else logging.INFO
    )

    logger = logging.getLogger(name)
    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger("ossai")
