# src: https://docs.python.org/3/howto/logging.html
"""
Custom log
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:

    logger = logging.getLogger(name)
    # console handler and level
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    # formatter
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
