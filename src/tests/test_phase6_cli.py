"""Unit tests for Phase 6 CLI — src/cli.py.

Requirements: 8.1-8.11
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.cli import (
    build_parser,
    validate_file,
    validate_model,
    insert_placeholders,
    create_position_inferer,
    create_assertion_inferer,
    _parse_dafny_status,
    LOCALIZATION_CHOICES,
)
from src.config import (
    ASSERTION_PLACEHOLDER,
    PositionInfererConfig,
    AssertionInfererConfig,
)
from src.llm.llm_configurations import (
    MODEL_REGISTRY,
    LLM_COST_STUB_RESPONSE_IS_PROMPT,
    LLM_EMPTY_RESPONSE_STUB,
)


# ---------------------------------------------------------------------------
# 1. build_parser: all args present with correct defaults
# ---------------------------------------------------------------------------

class TestBuildParser:
    """Req 8.1-8.5: CLI accepts file, --localization, --model, --num-assertions, --rounds, --no-color."""

    def test_positional_file_required(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["test.dfy"])
        assert args.file == "test.dfy"
        assert args.localization == "LLM"
        assert args.model == "openrouter-free"
        assert args.num_assertions == 10
        assert args.rounds == 1
        assert args.no_color is False

    def test_all_flags(self):
        parser = build_parser()
        args = parser.parse_args([
            "foo.dfy",
            "--localization", "LAUREL",
            "--model", "claude-opus-4.5",
            "--num-assertions", "5",
            "--rounds", "3",
            "--no-color",
        ])
        assert args.file == "foo.dfy"
        assert args.localization == "LAUREL"
        assert args.model == "claude-opus-4.5"
        assert args.num_assertions == 5
        assert args.rounds == 3
        assert args.no_color is True

    def test_localization_choices(self):
        parser = build_parser()
        for choice in LOCALIZATION_CHOICES:
            args = parser.parse_args(["x.dfy", "--localization", choice])
            assert args.localization == choice

    def test_invalid_localization_rejected(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["x.dfy", "--localization", "BOGUS"])


# ---------------------------------------------------------------------------
# 2. validate_file: nonexistent → SystemExit
# ---------------------------------------------------------------------------

class TestValidateFile:
    """Req 8.11: missing file → exit 1 with error."""

    def test_nonexistent_file_exits(self):
        with pytest.raises(SystemExit):
            validate_file("/no/such/file_abc123.dfy")

    def test_existing_file_ok(self, tmp_path):
        f = tmp_path / "ok.dfy"
        f.write_text("method M() {}")
        validate_file(str(f))  # should not raise


# ---------------------------------------------------------------------------
# 3. validate_model: unknown model → SystemExit with model list
# ---------------------------------------------------------------------------

class TestValidateModel:
    """Req 8.10: invalid model → exit 1 with available models."""

    def test_unknown_model_exits(self, capsys):
        with pytest.raises(SystemExit):
            validate_model("totally-fake-model-xyz")
        captured = capsys.readouterr()
        assert "unknown model" in captured.out.lower() or "error" in captured.out.lower()

    def test_valid_model_ok(self):
        # claude-opus-4.5 exists in MODEL_REGISTRY
        validate_model("claude-opus-4.5")  # should not raise


# ---------------------------------------------------------------------------
# 4. insert_placeholders: correct placeholder insertion
# ---------------------------------------------------------------------------

class TestInsertPlaceholders:
    """Req 8.7: placeholders inserted at predicted positions."""

    def test_single_position(self):
        text = "line0\nline1\nline2"
        result = insert_placeholders(text, [1], "PH")
        assert result == "line0\nline1\nPH\nline2"

    def test_multiple_positions(self):
        text = "a\nb\nc\nd"
        result = insert_placeholders(text, [0, 2], "PH")
        assert result == "a\nPH\nb\nc\nPH\nd"

    def test_no_positions(self):
        text = "a\nb\nc"
        result = insert_placeholders(text, [], "PH")
        assert result == "a\nb\nc"

    def test_last_line(self):
        text = "a\nb"
        result = insert_placeholders(text, [1], "PH")
        assert result == "a\nb\nPH"

    def test_uses_actual_placeholder(self):
        text = "line0\nline1"
        result = insert_placeholders(text, [0], ASSERTION_PLACEHOLDER)
        assert ASSERTION_PLACEHOLDER in result


# ---------------------------------------------------------------------------
# 5. create_position_inferer: each strategy → correct class
# ---------------------------------------------------------------------------

class TestCreatePositionInferer:
    """Req 8.3, 8.9: correct inferer class, cache_dir=None."""

    def setup_method(self):
        self.llm = MagicMock()
        self.cfg = PositionInfererConfig()

    def test_llm_returns_correct_type(self):
        from src.daisy.position_inference import LLMPositionStrategy
        result = create_position_inferer("LLM", self.llm, self.cfg)
        assert isinstance(result, LLMPositionStrategy)
        assert result.cache_dir is None

    def test_llm_example_returns_correct_type(self):
        from src.daisy.position_inference import LLMExamplePositionStrategy
        result = create_position_inferer("LLM_EXAMPLE", self.llm, self.cfg)
        assert isinstance(result, LLMExamplePositionStrategy)
        assert result.cache_dir is None

    def test_laurel_returns_correct_type(self):
        from src.daisy.position_inference import LAURELPositionStrategy
        result = create_position_inferer("LAUREL", self.llm, self.cfg)
        assert isinstance(result, LAURELPositionStrategy)
        assert result.cache_dir is None

    def test_laurel_better_returns_correct_type(self):
        from src.daisy.position_inference import LAURELBetterPositionStrategy
        result = create_position_inferer("LAUREL_BETTER", self.llm, self.cfg)
        assert isinstance(result, LAURELBetterPositionStrategy)
        assert result.cache_dir is None

    def test_hybrid_returns_correct_type(self):
        from src.daisy.position_inference import HybridPositionStrategy
        result = create_position_inferer("HYBRID", self.llm, self.cfg)
        assert isinstance(result, HybridPositionStrategy)
        assert result.cache_dir is None

    def test_none_returns_none(self):
        result = create_position_inferer("NONE", self.llm, self.cfg)
        assert result is None


# ---------------------------------------------------------------------------
# 6. create_assertion_inferer: each strategy → correct class
# ---------------------------------------------------------------------------

class TestCreateAssertionInferer:
    """Req 8.3, 8.9: correct inferer class, cache_dir=None."""

    def setup_method(self):
        self.llm = MagicMock()
        self.cfg = AssertionInfererConfig()

    def test_llm_returns_correct_type(self):
        from src.daisy.assertion_inference import LLMAssertionStrategy
        result = create_assertion_inferer("LLM", self.llm, self.cfg)
        assert isinstance(result, LLMAssertionStrategy)
        assert result.cache_dir is None

    def test_llm_example_returns_correct_type(self):
        from src.daisy.assertion_inference import LLMExampleAssertionStrategy
        result = create_assertion_inferer("LLM_EXAMPLE", self.llm, self.cfg)
        assert isinstance(result, LLMExampleAssertionStrategy)
        assert result.cache_dir is None

    def test_none_returns_none(self):
        result = create_assertion_inferer("NONE", self.llm, self.cfg)
        assert result is None


# ---------------------------------------------------------------------------
# 6. _parse_dafny_status: various Dafny outputs → correct status strings
# ---------------------------------------------------------------------------

class TestParseDafnyStatus:
    """Req 8.6-8.8: parse Dafny output to VERIFIED/NOT_VERIFIED/ERROR/MEMORY_ERROR."""

    def test_verified(self):
        stdout = "Dafny program verifier finished with 3 verified, 0 errors\n"
        assert _parse_dafny_status(stdout, "") == "VERIFIED"

    def test_not_verified(self):
        stdout = "Dafny program verifier finished with 1 verified, 2 errors\n"
        assert _parse_dafny_status(stdout, "") == "NOT_VERIFIED"

    def test_timeout(self):
        stdout = "Dafny program verifier finished with 0 verified, 1 errors, 1 time out\n"
        assert _parse_dafny_status(stdout, "") == "ERROR"

    def test_resolution_error(self):
        stdout = "2 resolution/type errors detected in foo.dfy\n"
        assert _parse_dafny_status(stdout, "") == "ERROR"

    def test_parse_error(self):
        stdout = "1 parse errors detected in foo.dfy\n"
        assert _parse_dafny_status(stdout, "") == "ERROR"

    def test_no_recognizable_output(self):
        assert _parse_dafny_status("", "") == "MEMORY_ERROR"

    def test_garbage_output(self):
        assert _parse_dafny_status("some random text\n", "") == "MEMORY_ERROR"


# ---------------------------------------------------------------------------
# 7. Full pipeline mock: verify wiring and exit codes
# ---------------------------------------------------------------------------

class TestMainAlreadyVerified:
    """Req 8.6: file already verifies → exit 0."""

    @patch("src.cli.shutil.rmtree")
    @patch("src.cli.run_external_cmd")
    @patch("src.cli.create_llm")
    @patch("src.cli.extract_methods")
    def test_already_verified_exits_0(
        self, mock_extract, mock_create_llm, mock_cmd, mock_rmtree, tmp_path
    ):
        dfy = tmp_path / "test.dfy"
        dfy.write_text("method M() {}")

        # run_initial_verification calls run_external_cmd → return VERIFIED output
        mock_cmd.return_value = (
            MagicMock(),  # Status
            "Dafny program verifier finished with 1 verified, 0 errors\n",
            "",
        )
        mock_create_llm.return_value = MagicMock()
        mock_extract.return_value = MagicMock(methods=[MagicMock()])

        with pytest.raises(SystemExit) as exc_info:
            from src.cli import main
            main([str(dfy), "--model", "claude-opus-4.5"])

        assert exc_info.value.code == 0


class TestMainMissingFile:
    """Req 8.11: missing file → exit 1."""

    def test_missing_file_exits_1(self):
        with pytest.raises(SystemExit) as exc_info:
            from src.cli import main
            main(["/no/such/file_xyz.dfy", "--model", "claude-opus-4.5"])
        assert exc_info.value.code == 1


class TestMainInvalidModel:
    """Req 8.10: invalid model → exit 1."""

    def test_invalid_model_exits_1(self, tmp_path):
        dfy = tmp_path / "test.dfy"
        dfy.write_text("method M() {}")

        with pytest.raises(SystemExit) as exc_info:
            from src.cli import main
            main([str(dfy), "--model", "nonexistent-model-xyz"])
        assert exc_info.value.code == 1


class TestMainFullPipelineVerified:
    """Req 8.7: full pipeline mock → verified fix → exit 0."""

    @patch("src.cli.shutil.rmtree")
    @patch("src.daisy.verification.ParallelComboVerification")
    @patch("src.cli.run_initial_verification")
    @patch("src.cli.extract_methods")
    @patch("src.cli.create_llm")
    def test_verified_fix_exits_0(
        self,
        mock_create_llm,
        mock_extract,
        mock_init_verif,
        mock_verifier_cls,
        mock_rmtree,
        tmp_path,
    ):
        dfy = tmp_path / "test.dfy"
        dfy.write_text("method M() {\n  var x := 1;\n}")

        mock_create_llm.return_value = LLM_COST_STUB_RESPONSE_IS_PROMPT(
            "test",
            MODEL_REGISTRY["cost_stub_almost_real"],
        )

        # extract_methods returns a FileInfo with one method
        mock_method = MagicMock()
        mock_method.method_name = "M"
        mock_method.segment_str = "method M() {\n  var x := 1;\n}"
        mock_file_info = MagicMock()
        mock_file_info.methods = [mock_method]
        mock_extract.return_value = mock_file_info

        # initial verification → NOT_VERIFIED
        mock_init_verif.return_value = ("NOT_VERIFIED", "error on line 2\n")

        # position inferer → returns positions
        mock_pos_inferer = MagicMock()
        mock_pos_inferer.infer_positions.return_value = [1]
        with patch("src.cli.create_position_inferer", return_value=mock_pos_inferer):
            # verifier → verified
            from src.daisy.verification.base import VerificationResult
            mock_verifier = MagicMock()
            mock_verifier.verify_assertions.return_value = VerificationResult(
                verified=True,
                total_tested=1,
                verified_count=1,
                corrected_method_text="method M() {\n  var x := 1;\n  assert x > 0;\n}",
                corrected_file_text="method M() {\n  var x := 1;\n  assert x > 0;\n}",
            )
            mock_verifier_cls.return_value = mock_verifier

            with pytest.raises(SystemExit) as exc_info:
                from src.cli import main
                main([str(dfy), "--model", "claude-opus-4.5", "--localization", "LLM"])

            assert exc_info.value.code == 0


class TestMainFullPipelineNoFix:
    """Req 8.8: no fix found → exit 1."""

    @patch("src.cli.shutil.rmtree")
    @patch("src.daisy.verification.ParallelComboVerification")
    @patch("src.cli.create_position_inferer")
    @patch("src.cli.run_initial_verification")
    @patch("src.cli.extract_methods")
    @patch("src.cli.create_llm")
    def test_no_fix_exits_1(
        self,
        mock_create_llm,
        mock_extract,
        mock_init_verif,
        mock_create_pos,
        mock_verifier_cls,
        mock_rmtree,
        tmp_path,
    ):
        dfy = tmp_path / "test.dfy"
        dfy.write_text("method M() {\n  var x := 1;\n}")

        mock_create_llm.return_value = LLM_EMPTY_RESPONSE_STUB(
            "test",
            MODEL_REGISTRY["cost_stub_almost_real"],
        )

        mock_method = MagicMock()
        mock_method.method_name = "M"
        mock_method.segment_str = "method M() {\n  var x := 1;\n}"
        mock_file_info = MagicMock()
        mock_file_info.methods = [mock_method]
        mock_extract.return_value = mock_file_info

        mock_init_verif.return_value = ("NOT_VERIFIED", "error on line 2\n")

        mock_pos_inferer = MagicMock()
        mock_pos_inferer.infer_positions.return_value = [1]
        mock_create_pos.return_value = mock_pos_inferer

        with pytest.raises(SystemExit) as exc_info:
            from src.cli import main
            main([str(dfy), "--model", "claude-opus-4.5", "--localization", "LLM"])

        assert exc_info.value.code == 1
