"""Abstract base class for assertion inference strategies.

Provides transparent caching: when cache_dir is set, results are read/written
automatically around the concrete _do_infer implementation.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import json


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

ASSERTION_REGISTRY: dict[str, type["AssertionInferer"]] = {}


def register_assertion_strategy(name: str):
    """Decorator that registers an AssertionInferer subclass under *name*.

    Usage::

        @register_assertion_strategy("MY_STRATEGY")
        class MyStrategy(AssertionInferer):
            ...
    """
    def decorator(cls: type["AssertionInferer"]) -> type["AssertionInferer"]:
        ASSERTION_REGISTRY[name] = cls
        return cls
    return decorator


class AssertionInferer(ABC):
    """Base class for all assertion inference strategies.

    Cache pattern:
        - cache_dir is None  → no I/O, call _do_infer directly
        - cache_dir set + cache file exists → return cached, skip _do_infer
        - cache_dir set + cache miss → call _do_infer, write result, return
    """

    def __init__(self, name: str, cache_dir: Path | None = None, **kwargs: Any):
        self.name = name
        self.cache_dir = cache_dir

    @abstractmethod
    def _do_infer(
        self, method_text_with_placeholders: str, error_output: str, **kwargs: Any
    ) -> list[list[str]]:
        """Concrete inference logic. Subclasses implement this."""

    def infer_assertions(
        self,
        method_text_with_placeholders: str,
        error_output: str,
        cache_key: str = "",
        **kwargs: Any,
    ) -> list[list[str]]:
        """Public method with transparent caching."""
        if self.cache_dir is not None:
            cache_file = self._cache_path(cache_key)
            if cache_file.exists():
                return json.loads(cache_file.read_text())

        result = self._do_infer(method_text_with_placeholders, error_output, **kwargs)

        if self.cache_dir is not None:
            cache_file = self._cache_path(cache_key)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(result))

        return result

    def check_cache(self, cache_key: str = "") -> bool:
        """Return True if cached results exist for the given key."""
        if self.cache_dir is None:
            return False
        return self._cache_path(cache_key).exists()

    def _cache_path(self, cache_key: str) -> Path:
        """Cache file path: {cache_dir}/{cache_key}/assertions_list/assertions_parsed.json"""
        return self.cache_dir / cache_key / "assertions_list" / "assertions_parsed.json"
