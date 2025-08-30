# file: app/logging_utils.py
import logging
from datetime import datetime
from rich.logging import RichHandler

def setup_logging(level=logging.INFO):
    """Configure rich logging"""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )

def log_event(agent: str, message: str, type: str = "agent_log", payload: dict = None) -> dict:
    """Create a pipeline event for streaming"""
    return {
        "ts": datetime.utcnow().isoformat(),
        "type": type,
        "agent": agent,
        "message": message,
        "payload": payload or {}
    }

logger = logging.getLogger(__name__)