"""Unit tests for Phase 3 position inference strategies.

Requirements: 2.2, 2.4, 2.7, 2.8
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import ExampleStrategy, PositionInfererConfig
from src.daisy.position_inference.llm_strategy import (
    LLMPositionStrategy,
    PositionInferenceError,
)
from src.daisy.position_inference.llm_example_strategy import (
    LLMExamplePositionStrategy,
)
from src.daisy.position_inference.laurel_strategy import LAURELPositionStrategy
from src.daisy.position_inference.laurel_better_strategy import (
    LAURELBetterPositionStrategy,
)
from src.daisy.position_inference.oracle_strategy import OraclePositionStrategy
from src.daisy.position_inference.hybrid_strategy import HybridPositionStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_llm(response: str = "[1, 2]") -> MagicMock:
    llm = MagicMock()
    llm.get_response.return_value = response
    llm.reset_chat_history = MagicMock()
    return llm


def _default_config(**overrides: Any) -> PositionInfererConfig:
    return PositionInfererConfig(**overrides)


# ---------------------------------------------------------------------------
# 1. LLM_EXAMPLE: _format_examples produces text with "EXAMPLE" sections
# ---------------------------------------------------------------------------

class TestLLMExampleFormatExamples:
    def test_format_examples_with_examples(self):
        """When given example dicts, output contains EXAMPLE sections."""
        examples = [
            {
                "error_message": "Error: assertion might not hold",
                "method_without_assertion_group": "method Foo()\n{\n  var x := 1;\n}",
                "oracle_pos": "[2]",
            },
            {
                "error_message": "Error: postcondition might not hold",
                "method_without_assertion_group": "method Bar()\n{\n  return;\n}",
                "oracle_pos": "[1]",
            },
        ]
        result = LLMExamplePositionStrategy._format_examples(examples)
        assert "EXAMPLE" in result
        assert result.count("=== EXAMPLE ===") == 2
        assert result.count("=== END ===") == 2
        assert "OUTPUT" in result

    def test_format_examples_empty_returns_empty_string(self):
        """When no examples given, returns empty string."""
        result = LLMExamplePositionStrategy._format_examples([])
        assert result == ""


# ---------------------------------------------------------------------------
# 2. LAUREL_BETTER: correct flag and name
# ---------------------------------------------------------------------------

class TestLaurelBetter:
    def test_use_laurel_better_flag_is_true(self):
        """LAUREL_BETTER sets use_laurel_better=True."""
        cfg = _default_config()
        strategy = LAURELBetterPositionStrategy(config=cfg)
        assert strategy.use_laurel_better is True

    def test_name_is_laurel_better(self):
        """Name attribute is LAUREL_BETTER."""
        cfg = _default_config()
        strategy = LAURELBetterPositionStrategy(config=cfg)
        assert strategy.name == "LAUREL_BETTER"

    def test_binary_path_contains_better(self):
        """Binary path references the better variant."""
        cfg = _default_config()
        strategy = LAURELBetterPositionStrategy(config=cfg)
        assert "better" in str(strategy.binary_path).lower()


# ---------------------------------------------------------------------------
# 3. Error cases: descriptive exceptions
# ---------------------------------------------------------------------------

class TestErrorCases:
    def test_llm_raises_on_malformed_json(self):
        """LLM strategy raises PositionInferenceError on unparseable response."""
        llm = _make_mock_llm(response="not json at all {{{")
        cfg = _default_config()
        strategy = LLMPositionStrategy(llm=llm, config=cfg)

        with pytest.raises(PositionInferenceError) as exc_info:
            strategy._do_infer("method Foo() {}", "Error: something")

        assert exc_info.value.raw_response == "not json at all {{{"

    def test_oracle_raises_file_not_found(self, tmp_path: Path):
        """Oracle strategy raises FileNotFoundError on missing file."""
        strategy = OraclePositionStrategy(dataset_path=tmp_path / "nonexistent")

        with pytest.raises(FileNotFoundError, match="oracle_fix_position"):
            strategy._do_infer("method Foo() {}", "Error: something")


# ---------------------------------------------------------------------------
# 4. All strategies have correct name attribute
# ---------------------------------------------------------------------------

class TestStrategyNames:
    def test_llm_name(self):
        llm = _make_mock_llm()
        cfg = _default_config()
        assert LLMPositionStrategy(llm=llm, config=cfg).name == "LLM"

    def test_llm_example_name(self):
        llm = _make_mock_llm()
        cfg = _default_config()
        assert LLMExamplePositionStrategy(llm=llm, config=cfg).name == "LLM_EXAMPLE"

    def test_laurel_name(self):
        cfg = _default_config()
        assert LAURELPositionStrategy(config=cfg).name == "LAUREL"

    def test_laurel_better_name(self):
        cfg = _default_config()
        assert LAURELBetterPositionStrategy(config=cfg).name == "LAUREL_BETTER"

    def test_oracle_name(self, tmp_path: Path):
        assert OraclePositionStrategy(dataset_path=tmp_path).name == "ORACLE"

    def test_hybrid_name(self):
        stub_a = MagicMock(spec=LAURELBetterPositionStrategy)
        stub_b = MagicMock(spec=LLMPositionStrategy)
        assert HybridPositionStrategy(
            laurel_better_inferer=stub_a, llm_inferer=stub_b
        ).name == "HYBRID"
