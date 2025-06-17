# utils/helpers.py

"""
helpers.py

General helper utilities for logging, instrument querying, and formatting.
"""

import logging


# -----------------------------------------------------------------------------
# Logger setup
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
_ch = logging.StreamHandler()
_ch.setLevel(logging.DEBUG)
_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
_ch.setFormatter(_formatter)
logger.addHandler(_ch)


def safe_query(inst, command: str, default=None):
    """
    Send a SCPI query to the instrument and return the response.
    If an error occurs, log it and return the default value.
    """
    try:
        return inst.query(command)
    except Exception as e:
        logger.error(f"Error querying '{command}': {e}")
        return default


def format_record_length(count: int) -> str:
    """
    Format a record length integer as k or M suffix.
    E.g. 200000 -> "200k", 2000000 -> "2M", 500 -> "500"
    """
    if count >= 1_000_000:
        return f"{count // 1_000_000}M"
    elif count >= 1_000:
        return f"{count // 1_000}k"
    else:
        return str(count)
