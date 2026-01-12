"""Structured logging configuration."""

import logging
import sys
from typing import Any

# Configure logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Setup a logger with consistent formatting.
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Formatter
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    return logger


def log_job_event(logger: logging.Logger, job_id: str, event: str, **kwargs: Any) -> None:
    """
    Log a structured job event.
    
    Args:
        logger: Logger instance
        job_id: Job UUID
        event: Event description
        **kwargs: Additional context
    """
    context = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"[JOB:{job_id}] {event} {context}".strip())


# Default application logger
app_logger = setup_logger("contract_analyzer")
