"""Unit tests for LLMPositionStrategy.

Requirements: 2.1, 2.7
"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import PositionInfererConfig
from src.daisy.position_inference.llm_strategy import (
    LLMPositionStrategy,
    PositionInferenceError,
)
from src.llm.llm_configurations import LLM, ModelInfo, PROVIDER_DEBUG


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

class MockLLM(LLM):
    """LLM stub that returns a canned response."""

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLLMPositionStrategy:
    """Core behaviour of LLMPositionStrategy."""

    def _make_strategy(self, response: str) -> LLMPositionStrategy:
        llm = MockLLM(response)
        config = PositionInfererConfig()
        return LLMPositionStrategy(llm=llm, config=config)

    def test_parses_valid_json_array(self):
        strategy = self._make_strategy("[3, 7, 12]")
        result = strategy._do_infer("line0\nline1\nline2", "some error")
        assert result == [3, 7, 12]

    def test_parses_single_element(self):
        strategy = self._make_strategy("[5]")
        result = strategy._do_infer("a\nb\nc", "err")
        assert result == [5]

    def test_raises_on_malformed_json(self):
        strategy = self._make_strategy("not json at all")
        with pytest.raises(PositionInferenceError) as exc_info:
            strategy._do_infer("a\nb", "err")
        assert exc_info.value.raw_response == "not json at all"

    def test_raises_on_empty_response(self):
        strategy = self._make_strategy("")
        with pytest.raises(PositionInferenceError):
            strategy._do_infer("a", "err")

    def test_prompt_contains_numbered_lines(self):
        """Verify prompt has 0-indexed numbered lines like the original."""
        llm = MockLLM("[1]")
        config = PositionInfererConfig()
        strategy = LLMPositionStrategy(llm=llm, config=config)
        prompt = strategy._build_prompt("alpha\nbeta\ngamma", "timeout error")
        assert "0: alpha" in prompt
        assert "1: beta" in prompt
        assert "2: gamma" in prompt

    def test_prompt_contains_error_output(self):
        llm = MockLLM("[1]")
        config = PositionInfererConfig()
        strategy = LLMPositionStrategy(llm=llm, config=config)
        prompt = strategy._build_prompt("code", "postcondition might not hold")
        assert "postcondition might not hold" in prompt

    def test_prompt_ends_with_output_instruction(self):
        llm = MockLLM("[1]")
        config = PositionInfererConfig()
        strategy = LLMPositionStrategy(llm=llm, config=config)
        prompt = strategy._build_prompt("code", "err")
        assert prompt.endswith(
            "OUTPUT: JSON array of line numbers ONLY, e.g. [2,5] (NO OTHER TEXT OR EXPLANATION)"
        )

    def test_resets_chat_history(self):
        """LLM chat history should be reset before each call."""
        llm = MockLLM("[1]")
        llm.chat_history = ["old stuff"]
        config = PositionInfererConfig()
        strategy = LLMPositionStrategy(llm=llm, config=config)
        strategy._do_infer("code", "err")
        # After reset + one call, history should not contain old stuff
        assert "old stuff" not in llm.chat_history

    def test_caching_integration(self, tmp_path: Path):
        """Verify caching works through the base class."""
        llm = MockLLM("[4, 8]")
        config = PositionInfererConfig()
        strategy = LLMPositionStrategy(llm=llm, config=config, cache_dir=tmp_path)

        # First call — cache miss, calls LLM
        result = strategy.infer_positions("code", "err", cache_key="test_key")
        assert result == [4, 8]

        # Second call — cache hit, should return same result
        llm._response = "[99]"  # change response to prove cache is used
        result2 = strategy.infer_positions("code", "err", cache_key="test_key")
        assert result2 == [4, 8]

    def test_parses_json_in_code_block(self):
        """parse_raw_response handles ```json ... ``` blocks."""
        strategy = self._make_strategy("```json\n[2, 5]\n```")
        result = strategy._do_infer("a\nb\nc", "err")
        assert result == [2, 5]
