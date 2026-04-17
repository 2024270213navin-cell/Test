"""
utils/logger.py — Structured logging via loguru.
"""
import sys
from loguru import logger


def setup_logger(log_level: str = "INFO") -> None:
    """Configure loguru with structured console + file output."""
    logger.remove()  # Remove default handler

    # Console — coloured, human-readable
    logger.add(
        sys.stdout,
        level=log_level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File — JSON-structured for production ingestion
    logger.add(
        "logs/app.log",
        level=log_level.upper(),
        rotation="10 MB",
        retention="14 days",
        compression="gz",
        format="{time:YYYY-MM-DDTHH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
        enqueue=True,  # Thread-safe async writes
    )

    logger.info("Logger initialised at level={}", log_level)


def get_logger(name: str):
    """Return a child logger bound to the given module name."""
    return logger.bind(module=name)
