import logging
from typing import Optional


def get_logger(name: str, level: int = logging.INFO, handler: Optional[logging.Handler] = None) -> logging.Logger:
    """Configure and return a logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        stream_handler = handler or logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        )
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger
