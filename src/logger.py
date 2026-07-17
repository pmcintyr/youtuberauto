from loguru import logger
import sys
from pathlib import Path
from datetime import datetime

# Create logs directory if it doesn't exist
logs_dir = Path(__file__).parent.parent / 'logs'
logs_dir.mkdir(exist_ok=True)

# Configure loguru
logger.remove()  # Remove default handler

# Add console handler with custom format
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# Add file handler with rotation
logger.add(
    logs_dir / f"youtube_automation_{datetime.now().strftime('%Y%m%d')}.log",
    rotation="1 day",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG"
)

# Add error file handler
logger.add(
    logs_dir / "errors.log",
    rotation="1 week",
    retention="3 months",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR"
)

# Export logger instance
log = logger
