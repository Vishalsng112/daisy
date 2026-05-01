"""Assertion inference strategies."""

from src.daisy.assertion_inference.base import (
    ASSERTION_REGISTRY,
    AssertionInferer,
    register_assertion_strategy,
)

# Import all strategies so their @register decorators execute
from src.daisy.assertion_inference.llm_strategy import (
    AssertionInferenceError,
    LLMAssertionStrategy,
)

from src.daisy.assertion_inference.llm_example_strategy import (
    LLMExampleAssertionStrategy 
)

from src.daisy.assertion_inference.oracle_strategy import OracleAssertionStrategy

__all__ = [
    "ASSERTION_REGISTRY",
    "AssertionInferer",
    "register_assertion_strategy",
    "AssertionInferenceError",
    "LLMAssertionStrategy",
    "OracleAssertionStrategy",
]
