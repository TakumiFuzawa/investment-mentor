import os
import sys
from loguru import logger

_configured = False


def setup_logger() -> None:
    global _configured
    if _configured:
        return

    logger.remove()

    log_level = os.getenv("LOG_LEVEL", "INFO")

    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    logger.add(
        "logs/app.log",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
    )

    _configured = True
    logger.info("Logger initialized (level={})", log_level)
