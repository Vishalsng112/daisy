# Feature: daisy-codebase-rewrite, Property 7: LLM assertion response parsing
"""Property test: LLM assertion response parsing.

**Validates: Requirements 4.1**

For any valid JSON array of arrays of strings returned by the LLM,
the LLM Assertion Strategy SHALL parse it into the identical
list[list[str]] structure.

Strategy: generate random list[list[str]], convert to JSON, mock LLM
to return it, call LLMAssertionStrategy._do_infer, verify result matches.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import AssertionInfererConfig, ExampleStrategy
from src.daisy.assertion_inference.llm_strategy import LLMAssertionStrategy
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


# --- Minimal config (single round, no examples, no error append) ---

_DEFAULT_CONFIG = AssertionInfererConfig(
    base_prompt="Generate assertions.",
    system_prompt="You are a Dafny expert.",
    num_assertions_to_test=10,
    num_rounds=1,
    example_retrieval_type=ExampleStrategy.NONE,
    num_examples=0,
    example_weight=0.0,
    add_error_message=False,
    remove_empty_lines=True,
    filter_warnings=True,
)


# --- Hypothesis strategies ---
# Generate nested form: list[list[str]] with printable assertion-like strings.

assertion_str_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=60,
)

assertion_candidates_st = st.lists(
    st.lists(assertion_str_st, min_size=1, max_size=10),
    min_size=1,
    max_size=10,
)


# --- Property test ---

@settings(max_examples=100)
@given(candidates=assertion_candidates_st)
def test_llm_assertion_parsing_roundtrip(candidates: list[list[str]]) -> None:
    """Mock LLM returns JSON array of arrays → parsed output matches original."""
    json_response = json.dumps(candidates)
    mock_llm = MockLLM(response=json_response)

    strategy = LLMAssertionStrategy(
        llm=mock_llm,
        config=_DEFAULT_CONFIG,
        cache_dir=None,
    )

    result = strategy._do_infer(
        method_text_with_placeholders="method Foo() { /*<Assertion is Missing Here>*/ }",
        error_output="error: assertion might not hold",
    )

    assert result == candidates, f"Expected {candidates}, got {result}"
