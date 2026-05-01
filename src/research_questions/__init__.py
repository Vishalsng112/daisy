"""Research question evaluation scripts.

Provides CacheMissError and shared helpers for RQ1–RQ3 scripts.
"""

from __future__ import annotations


class CacheMissError(Exception):
    """Raised when research scripts detect missing cache entries.

    Attributes:
        missing_entries: list of group IDs that have no cached results.
    """

    def __init__(self, message: str, missing_entries: list[str] | None = None):
        super().__init__(message)
        self.missing_entries: list[str] = missing_entries or []


__all__ = ["CacheMissError"]
