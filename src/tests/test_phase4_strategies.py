"""Unit tests for Phase 4 assertion inference strategies.

Requirements: 4.1, 4.3, 4.4
"""

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import AssertionInfererConfig, ExampleStrategy
from src.daisy.assertion_inference.llm_strategy import LLMAssertionStrategy
from src.daisy.assertion_inference.oracle_strategy import OracleAssertionStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_llm(response: str = '[["assert x;"], ["assert y;"]]') -> MagicMock:
    llm = MagicMock()
    llm.get_response.return_value = response
    llm.reset_chat_history = MagicMock()
    return llm


def _default_config(**overrides: Any) -> AssertionInfererConfig:
    defaults = dict(
        add_error_message=True,
        filter_warnings=False,
        example_retrieval_type=ExampleStrategy.NONE,
        num_examples=0,
        num_rounds=1,
    )
    defaults.update(overrides)
    return AssertionInfererConfig(**defaults)


# ---------------------------------------------------------------------------
# 1. Malformed JSON → returns empty list (warning logged, not exception)
# ---------------------------------------------------------------------------

class TestMalformedJSON:
    def test_malformed_json_returns_empty_list(self):
        """Req 4.3: malformed JSON → empty list with warning, not exception."""
        llm = _make_mock_llm(response="not json at all {{{")
        cfg = _default_config()
        strategy = LLMAssertionStrategy(llm=llm, config=cfg)

        result = strategy._do_infer("method Foo() {}", "Error: something")
        assert result == []

    def test_completely_empty_response_returns_empty_list(self):
        """Empty string from LLM → empty list."""
        llm = _make_mock_llm(response="")
        cfg = _default_config()
        strategy = LLMAssertionStrategy(llm=llm, config=cfg)

        result = strategy._do_infer("method Foo() {}", "Error: something")
        assert result == []


# ---------------------------------------------------------------------------
# 2. Prompt construction
# ---------------------------------------------------------------------------

class TestPromptConstruction:
    def test_prompt_contains_error_message_when_enabled(self):
        """Req 4.1: prompt includes ERROR section when add_error_message=True."""
        llm = _make_mock_llm()
        cfg = _default_config(add_error_message=True)
        strategy = LLMAssertionStrategy(llm=llm, config=cfg)

        prompt = strategy._build_prompt(
            "method Foo() { /*<Assertion>*/ }",
            "Error: postcondition might not hold",
        )
        assert "ERROR" in prompt
        assert "postcondition might not hold" in prompt

    def test_prompt_contains_code_with_placeholders(self):
        """Req 4.1: prompt includes CODE section with method text."""
        llm = _make_mock_llm()
        cfg = _default_config()
        strategy = LLMAssertionStrategy(llm=llm, config=cfg)

        method_text = "method Foo() {\n  /*<Assertion is Missing Here>*/\n}"
        prompt = strategy._build_prompt(method_text, "Error: something")
        assert "CODE" in prompt
        assert "/*<Assertion is Missing Here>*/" in prompt

    def test_prompt_ends_with_output_instruction(self):
        """Req 4.1: prompt ends with OUTPUT instruction for JSON array of arrays."""
        llm = _make_mock_llm()
        cfg = _default_config()
        strategy = LLMAssertionStrategy(llm=llm, config=cfg)

        prompt = strategy._build_prompt("method Foo() {}", "Error: something")
        assert "OUTPUT" in prompt
        assert "JSON array of arrays" in prompt


# ---------------------------------------------------------------------------
# 3. Multi-round merges candidates correctly
# ---------------------------------------------------------------------------

class TestMultiRoundMerge:
    def test_multi_round_merges_candidates(self):
        """Multiple rounds extend candidates per position."""
        llm = MagicMock()
        llm.reset_chat_history = MagicMock()
        # Round 1 returns one candidate per position, round 2 returns another
        llm.get_response.side_effect = [
            '[["assert a;"], ["assert b;"]]',
            '[["assert c;"], ["assert d;"]]',
        ]
        cfg = _default_config(num_rounds=2)
        strategy = LLMAssertionStrategy(llm=llm, config=cfg)

        result = strategy._do_infer("method Foo() {}", "Error: something")
        # Position 0 should have candidates from both rounds
        assert "assert a;" in result[0]
        assert "assert c;" in result[0]
        # Position 1 should have candidates from both rounds
        assert "assert b;" in result[1]
        assert "assert d;" in result[1]


# ---------------------------------------------------------------------------
# 4. Oracle strategy: FileNotFoundError on missing file
# ---------------------------------------------------------------------------

class TestOracleStrategy:
    def test_raises_file_not_found_on_missing_file(self, tmp_path: Path):
        """Req 4.2: Oracle raises FileNotFoundError when oracle file missing."""
        strategy = OracleAssertionStrategy(dataset_path=tmp_path / "nonexistent")

        with pytest.raises(FileNotFoundError, match="oracle_assertions"):
            strategy._do_infer("method Foo() {}", "Error: something")

    def test_correct_name_attribute(self, tmp_path: Path):
        """Oracle strategy has name='ORACLE'."""
        strategy = OracleAssertionStrategy(dataset_path=tmp_path)
        assert strategy.name == "ORACLE"


# ---------------------------------------------------------------------------
# 5. LLM strategy: correct name attribute
# ---------------------------------------------------------------------------

class TestLLMStrategyName:
    def test_correct_name_attribute(self):
        """LLM assertion strategy has name='LLM'."""
        llm = _make_mock_llm()
        cfg = _default_config()
        strategy = LLMAssertionStrategy(llm=llm, config=cfg)
        assert strategy.name == "LLM"
