"""Verification strategies."""

from src.daisy.verification.base import (
    VERIFICATION_REGISTRY,
    VerificationResult,
    VerificationStrategy,
    register_verification_strategy,
)

# Import all strategies so their @register decorators execute
from src.daisy.verification.parallel_combo import (
    ParallelComboVerification,
    zip_with_empty_indexed,
)

__all__ = [
    "VERIFICATION_REGISTRY",
    "ParallelComboVerification",
    "VerificationResult",
    "VerificationStrategy",
    "register_verification_strategy",
    "zip_with_empty_indexed",
]
