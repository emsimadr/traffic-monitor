"""
Storage adapter.

For now, this wraps the existing Database implementation.
"""

from __future__ import annotations

from storage.database import Database

__all__ = ["Database"]


