# Feature: daisy-codebase-rewrite, Property 3: LLM position response parsing
"""Property test: LLM position response parsing.

**Validates: Requirements 2.1**

For any valid JSON array of non-negative integers returned by the LLM,
the LLM Position Strategy SHALL parse it into the identical list of integers.

Strategy: generate random list[int] (non-negative), convert to JSON string,
mock LLM to return it, call LLMPositionStrategy._do_infer, verify result matches.
"""

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import ExampleStrategy, PositionInfererConfig
from src.daisy.position_inference.llm_strategy import LLMPositionStrategy
from src.llm.llm_configurations import LLM, ModelInfo, PROVIDER_DEBUG


# --- Mock LLM that returns a predetermined response ---

class MockLLM(LLM):
    """LLM stub that returns a fixed response string."""

    def __init__(self, response: str):
        model = ModelInfo(
            provider=PROVIDER_DEBUG,
            model_id="mock",
            max_context=1000,
            cost_1M_in=0.0,
            cost_1M_out=0.0,
        )
        super().__init__(name="mock", model=model)
        self._response = response

    def _get_response(self, prompt: str) -> str:
        return self._response


# --- Minimal config ---

_DEFAULT_CONFIG = PositionInfererConfig(
    localization_base_prompt="Locate assertions.",
    example_retrieval_type=ExampleStrategy.NONE,
    num_examples=0,
    example_weight=0.0,
    placeholder_text="/*<Assertion is Missing Here>*/",
)


# --- Hypothesis strategies ---

positions_st = st.lists(
    st.integers(min_value=0, max_value=10_000),
    min_size=0,
    max_size=30,
)


# --- Property test ---

@settings(max_examples=100)
@given(positions=positions_st)
def test_llm_position_parsing_roundtrip(positions: list[int]) -> None:
    """Mock LLM returns JSON array of ints → parsed positions match original."""
    json_response = json.dumps(positions)
    mock_llm = MockLLM(response=json_response)

    strategy = LLMPositionStrategy(
        llm=mock_llm,
        config=_DEFAULT_CONFIG,
        cache_dir=None,
    )

    result = strategy._do_infer(
        method_text="method Foo() { }",
        error_output="error: assertion might not hold",
    )

    assert result == positions, f"Expected {positions}, got {result}"
