"""Tests for LAURELPositionStrategy — parsing logic and error handling."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import PositionInfererConfig
from src.daisy.position_inference.laurel_strategy import (
    LAUREL_ASSERTION_TAG,
    LAURELPositionStrategy,
)
from src.daisy.position_inference.llm_strategy import PositionInferenceError
from src.utils.external_cmd import Status


# ---------------------------------------------------------------------------
# _parse_output unit tests
# ---------------------------------------------------------------------------


class TestParseOutput:
    def test_single_tag(self):
        output = "line0\n<assertion> Insert assertion here </assertion>\nline2"
        assert LAURELPositionStrategy._parse_output(output) == [0]

    def test_multiple_tags(self):
        output = (
            "method Foo() {\n"
            "  a := b;\n"
            "<assertion> Insert assertion here </assertion>\n"
            "  c := d;\n"
            "  e := f;\n"
            "<assertion> Insert assertion here </assertion>\n"
            "}"
        )
        # Tag at idx 2 → original 2-1=1; tag at idx 5 → original 5-2=3
        assert LAURELPositionStrategy._parse_output(output) == [1, 3]

    def test_no_tags(self):
        output = "line0\nline1\nline2"
        assert LAURELPositionStrategy._parse_output(output) == []

    def test_empty_output(self):
        assert LAURELPositionStrategy._parse_output("") == []

    def test_tag_on_first_line(self):
        output = "<assertion> Insert assertion here </assertion>\nline1"
        # idx 0, added_lines becomes 1 → position = 0-1 = -1
        # This matches the existing src/ behavior (idx - added_lines)
        assert LAURELPositionStrategy._parse_output(output) == [-1]

    def test_consecutive_tags(self):
        output = (
            "line0\n"
            "<assertion> Insert assertion here </assertion>\n"
            "<assertion> Insert assertion here </assertion>\n"
            "line3"
        )
        # First tag: idx=1, added=1 → 0
        # Second tag: idx=2, added=2 → 0
        assert LAURELPositionStrategy._parse_output(output) == [0, 0]


# ---------------------------------------------------------------------------
# _do_infer tests (mocking run_external_cmd)
# ---------------------------------------------------------------------------


class TestDoInfer:
    def _make_strategy(self, binary_path: Path | None = None) -> LAURELPositionStrategy:
        config = PositionInfererConfig()
        return LAURELPositionStrategy(
            config=config,
            laurel_binary_path=binary_path or Path("/fake/binary"),
        )

    @patch("src.daisy.position_inference.laurel_strategy.run_external_cmd")
    def test_success(self, mock_cmd):
        output = (
            "method Foo() {\n"
            "  a := b;\n"
            "<assertion> Insert assertion here </assertion>\n"
            "  c := d;\n"
            "}"
        )
        mock_cmd.return_value = (Status.OK, output, "")
        strategy = self._make_strategy()
        result = strategy._do_infer("method text", "error", method_name="Foo")
        assert result == [1]

    @patch("src.daisy.position_inference.laurel_strategy.run_external_cmd")
    def test_raises_on_non_ok_status(self, mock_cmd):
        mock_cmd.return_value = (Status.ERROR_EXIT_CODE, "", "binary crashed")
        strategy = self._make_strategy()
        with pytest.raises(PositionInferenceError, match="LAUREL binary failed"):
            strategy._do_infer("text", "err", method_name="Foo")

    @patch("src.daisy.position_inference.laurel_strategy.run_external_cmd")
    def test_raises_on_empty_output(self, mock_cmd):
        mock_cmd.return_value = (Status.OK, "", "")
        strategy = self._make_strategy()
        with pytest.raises(PositionInferenceError, match="no output"):
            strategy._do_infer("text", "err", method_name="Foo")

    @patch("src.daisy.position_inference.laurel_strategy.run_external_cmd")
    def test_raises_on_timeout(self, mock_cmd):
        mock_cmd.return_value = (Status.TIMEOUT, "", "timed out")
        strategy = self._make_strategy()
        with pytest.raises(PositionInferenceError):
            strategy._do_infer("text", "err", method_name="Foo")

    @patch("src.daisy.position_inference.laurel_strategy.run_external_cmd")
    def test_cmd_receives_correct_args(self, mock_cmd):
        mock_cmd.return_value = (Status.OK, "line0\n", "")
        binary = Path("/my/binary")
        strategy = self._make_strategy(binary_path=binary)
        # Returns [] since no tags — that's fine, we're checking the cmd
        strategy._do_infer(
            "method text", "error",
            method_name="MyMethod",
            program_text="full program",
        )
        args, kwargs = mock_cmd.call_args
        cmd = args[0]
        assert cmd[0] == str(binary)
        # cmd[1] is the temp file path
        assert cmd[2] == "MyMethod"
        assert cmd[3] == "False"
