import logging
from config.settings import settings

def get_logger(name: str) -> logging.Logger:
    """Create a logger with the specified name."""
    logger = logging.getLogger(name)
    logger.setLevel(settings.LOG_LEVEL)
    
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(handler)
    
    return logger
