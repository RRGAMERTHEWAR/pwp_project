"""Application Logging Configuration.

All system activity, database events, and uncaught exceptions are recorded to
`app.log` in the project root directory.

HOW TO USE IN ANY FILE:
    from core.logger import logger
    logger.info("Something good happened")
    logger.error("Something went wrong", exc_info=True)
"""

import logging
from logging.handlers import RotatingFileHandler
import os

# Full path to the log file in the project root folder
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.log")


def setup_logger():
    """Configure the application logger with a rotating file handler.
    
    Rotates the log when it reaches 5 MB to prevent unbounded disk growth.
    """
    logger = logging.getLogger("billing_system")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate log outputs if setup is imported multiple times
    if not logger.handlers:
        # Rotate when file reaches 5MB; retain up to 5 historical log files
        handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Shared global logger instance used across the app
logger = setup_logger()
