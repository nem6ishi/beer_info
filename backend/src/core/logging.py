import logging
import sys
import os
from typing import Optional

def setup_logging(name: str, level: Optional[int] = None) -> logging.Logger:
    """Configures and returns a logger with standard formatting."""
    if level is None:
        env_level = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)

    # Configure basic config for root logger if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S', stream=sys.stdout
        )
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger
