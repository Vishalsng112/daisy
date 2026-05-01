"""Abstract base class for verification strategies.

Simplified interface: works with plain strings (full_file_text,
method_text_with_placeholders, candidates). No FileInfo/MethodInfo dependency.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.config import VerificationConfig


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

VERIFICATION_REGISTRY: dict[str, type["VerificationStrategy"]] = {}


def register_verification_strategy(name: str):
    """Decorator that registers a VerificationStrategy subclass under *name*.

    Usage::

        @register_verification_strategy("MY_VERIFIER")
        class MyVerifier(VerificationStrategy):
            ...
    """
    def decorator(cls: type["VerificationStrategy"]) -> type["VerificationStrategy"]:
        VERIFICATION_REGISTRY[name] = cls
        return cls
    return decorator


@dataclass
class VerificationResult:
    """Result of a verification attempt."""

    verified: bool
    total_tested: int
    verified_count: int
    corrected_method_text: str | None
    corrected_file_text: str | None


class VerificationStrategy(ABC):
    """Base class for all verification strategies.

    Args:
        config: Verification configuration (dafny path, limits, etc.)
    """

    def __init__(self, config: VerificationConfig, **kwargs: Any):
        self.config = config

    @abstractmethod
    def verify_assertions(
        self,
        full_file_text: str,
        method_text_with_placeholders: str,
        candidates: list[list[str]],
    ) -> VerificationResult:
        """Verify assertion candidates against the Dafny verifier.

        Args:
            full_file_text: Complete .dfy file with method still containing placeholders.
            method_text_with_placeholders: Method text containing placeholder strings.
            candidates: One inner list per placeholder position, each with assertion candidates.

        The strategy:
        1. Generates combos from candidates (one assertion per position)
        2. For each combo: replaces placeholders in method_text, replaces method in full_file_text
        3. Writes to temp file, runs Dafny verify
        4. Returns first verified combo (early-stop)
        """
