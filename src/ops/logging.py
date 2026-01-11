"""
Logging setup.
"""

from __future__ import annotations

import logging
import os


def setup_logging(log_path: str, log_level: str) -> None:
    log_dir = os.path.dirname(log_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Use force=True to override any handlers that were auto-created
    # by early logging calls (e.g., during config validation)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(),
        ],
        force=True,
    )


