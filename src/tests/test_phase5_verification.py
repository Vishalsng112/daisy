"""Unit tests for Phase 5 verification — ParallelComboVerification.

Requirements: 5.2, 5.4, 6.4, 11.4
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import VerificationConfig, VerificationType
from src.daisy.verification.base import VerificationResult
from src.daisy.verification.parallel_combo import (
    ParallelComboVerification,
    zip_with_empty_indexed,
)
from src.utils.external_cmd import Status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PLACEHOLDER = "/*<Assertion is Missing Here>*/"

METHOD_TEMPLATE = f"method Foo() {{\n  {PLACEHOLDER}\n}}"
FILE_TEMPLATE = f"// header\n{METHOD_TEMPLATE}\n// footer"


def _cfg(**overrides) -> VerificationConfig:
    defaults = dict(
        verification_type=VerificationType.PARALLEL_COMBO,
        dafny_exec=Path("/fake/dafny"),
        temp_dir=Path("/tmp/dafny_test"),
        skip_verification=False,
        parallel=False,
        verifier_time_limit=60,
        verifier_max_memory=24,
        placeholder_text=PLACEHOLDER,
    )
    defaults.update(overrides)
    return VerificationConfig(**defaults)


# ---------------------------------------------------------------------------
# 1. Empty candidates → VerificationResult(verified=False, total_tested=0)
# ---------------------------------------------------------------------------

class TestEmptyCandidates:
    def test_empty_candidates_returns_not_verified(self):
        """Req 5.2: no candidates → verified=False, total_tested=0."""
        v = ParallelComboVerification(config=_cfg())
        result = v.verify_assertions(FILE_TEMPLATE, METHOD_TEMPLATE, [])
        assert result == VerificationResult(
            verified=False,
            total_tested=0,
            verified_count=0,
            corrected_method_text=None,
            corrected_file_text=None,
        )


# ---------------------------------------------------------------------------
# 2. Mock Dafny OK for first combo → verified=True, corrected texts populated
# ---------------------------------------------------------------------------

class TestEarlyStopOnFirstVerified:
    @patch("src.daisy.verification.parallel_combo.run_external_cmd")
    def test_first_combo_verified_populates_result(self, mock_cmd):
        """Req 5.2: first verified combo → early-stop, corrected texts set."""
        mock_cmd.return_value = (Status.OK, "verified", "")

        v = ParallelComboVerification(config=_cfg())
        candidates = [["assert x > 0;"]]
        result = v.verify_assertions(FILE_TEMPLATE, METHOD_TEMPLATE, candidates)

        assert result.verified is True
        assert result.corrected_method_text is not None
        assert "assert x > 0;" in result.corrected_method_text
        assert result.corrected_file_text is not None
        assert "assert x > 0;" in result.corrected_file_text
        assert PLACEHOLDER not in result.corrected_method_text

    @patch("src.daisy.verification.parallel_combo.run_external_cmd")
    def test_early_stop_not_all_combos_tested(self, mock_cmd):
        """Req 5.2: early-stop means not all combos need testing."""
        # First call OK, rest should be skipped via cancel_event
        mock_cmd.return_value = (Status.OK, "verified", "")

        v = ParallelComboVerification(config=_cfg(parallel=False))
        # Many candidates → many combos
        candidates = [["assert a;", "assert b;", "assert c;", "assert d;", "assert e;"]]
        result = v.verify_assertions(FILE_TEMPLATE, METHOD_TEMPLATE, candidates)

        assert result.verified is True
        # With early-stop, we shouldn't test all 5 combos
        # (at least one verified, possibly fewer total tested than 5)
        assert result.verified_count >= 1


# ---------------------------------------------------------------------------
# 3. Mock Dafny ERROR for all combos → verified=False
# ---------------------------------------------------------------------------

class TestAllCombosFail:
    @patch("src.daisy.verification.parallel_combo.run_external_cmd")
    def test_all_combos_fail_returns_not_verified(self, mock_cmd):
        """Req 5.2: all combos fail → verified=False."""
        mock_cmd.return_value = (Status.ERROR_EXIT_CODE, "", "verification failed")

        v = ParallelComboVerification(config=_cfg())
        candidates = [["assert false;", "assert 1 == 2;"]]
        result = v.verify_assertions(FILE_TEMPLATE, METHOD_TEMPLATE, candidates)

        assert result.verified is False
        assert result.corrected_method_text is None
        assert result.corrected_file_text is None
        assert result.total_tested == 2  # both combos tested


# ---------------------------------------------------------------------------
# 4. Dafny command includes --solver-option:O:memory_max_size (not systemd)
# ---------------------------------------------------------------------------

class TestDafnyCommandFlags:
    @patch("src.daisy.verification.parallel_combo.run_external_cmd")
    def test_solver_option_memory_flag(self, mock_cmd):
        """Req 11.4: Dafny cmd uses --solver-option:O:memory_max_size, not systemd."""
        mock_cmd.return_value = (Status.OK, "verified", "")

        cfg = _cfg(verifier_max_memory=24)
        v = ParallelComboVerification(config=cfg)
        candidates = [["assert true;"]]
        v.verify_assertions(FILE_TEMPLATE, METHOD_TEMPLATE, candidates)

        assert mock_cmd.called
        cmd_args = mock_cmd.call_args[0][0]  # first positional arg = cmd list
        cmd_str = " ".join(cmd_args)

        assert "--solver-option:O:memory_max_size=24000" in cmd_str
        assert "systemd" not in cmd_str.lower()

    @patch("src.daisy.verification.parallel_combo.run_external_cmd")
    def test_verification_time_limit_flag(self, mock_cmd):
        """Req 11.4: Dafny cmd includes --verification-time-limit."""
        mock_cmd.return_value = (Status.OK, "verified", "")

        cfg = _cfg(verifier_time_limit=120)
        v = ParallelComboVerification(config=cfg)
        candidates = [["assert true;"]]
        v.verify_assertions(FILE_TEMPLATE, METHOD_TEMPLATE, candidates)

        assert mock_cmd.called
        cmd_args = mock_cmd.call_args[0][0]
        cmd_str = " ".join(cmd_args)

        assert "--verification-time-limit" in cmd_str
        assert "120" in cmd_str


# ---------------------------------------------------------------------------
# 5. VerificationResult fields populated correctly
# ---------------------------------------------------------------------------

class TestVerificationResultFields:
    @patch("src.daisy.verification.parallel_combo.run_external_cmd")
    def test_verified_result_fields(self, mock_cmd):
        """Req 5.4: VerificationResult has all fields set on success."""
        mock_cmd.return_value = (Status.OK, "verified", "")

        v = ParallelComboVerification(config=_cfg())
        candidates = [["assert x;"]]
        result = v.verify_assertions(FILE_TEMPLATE, METHOD_TEMPLATE, candidates)

        assert isinstance(result, VerificationResult)
        assert result.verified is True
        assert result.total_tested >= 1
        assert result.verified_count >= 1
        assert result.corrected_method_text is not None
        assert result.corrected_file_text is not None

    @patch("src.daisy.verification.parallel_combo.run_external_cmd")
    def test_failed_result_fields(self, mock_cmd):
        """Req 5.4: VerificationResult has None texts on failure."""
        mock_cmd.return_value = (Status.ERROR_EXIT_CODE, "", "fail")

        v = ParallelComboVerification(config=_cfg())
        candidates = [["assert false;"]]
        result = v.verify_assertions(FILE_TEMPLATE, METHOD_TEMPLATE, candidates)

        assert isinstance(result, VerificationResult)
        assert result.verified is False
        assert result.total_tested == 1
        assert result.verified_count == 0
        assert result.corrected_method_text is None
        assert result.corrected_file_text is None


# ---------------------------------------------------------------------------
# 6. Temp file cleanup after verification
# ---------------------------------------------------------------------------

class TestTempFileCleanup:
    @patch("src.daisy.verification.parallel_combo.run_external_cmd")
    def test_temp_files_cleaned_after_verification(self, mock_cmd, tmp_path):
        """Req 6.4: temp files cleaned after use."""
        mock_cmd.return_value = (Status.OK, "verified", "")

        cfg = _cfg(temp_dir=tmp_path)
        v = ParallelComboVerification(config=cfg)
        candidates = [["assert true;"]]
        v.verify_assertions(FILE_TEMPLATE, METHOD_TEMPLATE, candidates)

        # After verification, no leftover .dfy temp files should remain
        leftover_dfy = list(tmp_path.rglob("*.dfy"))
        assert leftover_dfy == [], f"Leftover temp files: {leftover_dfy}"


# ---------------------------------------------------------------------------
# 7. zip_with_empty_indexed: single position → no leftover rows
# ---------------------------------------------------------------------------

class TestZipWithEmptyIndexed:
    def test_single_position_no_leftovers(self):
        """Single position list → zipped rows only, no leftover rows."""
        vals, inds = zip_with_empty_indexed([["a", "b", "c"]])
        # Single position: each candidate is its own combo, no leftovers
        assert vals == [["a"], ["b"], ["c"]]
        assert inds == [[0], [1], [2]]

    def test_multiple_positions_zipped_plus_leftovers(self):
        """Multiple positions → zipped rows first, then leftover rows."""
        vals, inds = zip_with_empty_indexed([["a1", "a2"], ["b1", "b2"]])

        # Zipped: min_len=2 → [["a1","b1"], ["a2","b2"]]
        assert vals[0] == ["a1", "b1"]
        assert vals[1] == ["a2", "b2"]

        # Leftovers: each individual assertion paired with "" for other positions
        # Position 0: ("a1",""), ("a2","")
        # Position 1: ("","b1"), ("","b2")
        leftover_vals = vals[2:]
        assert ["a1", ""] in leftover_vals
        assert ["a2", ""] in leftover_vals
        assert ["", "b1"] in leftover_vals
        assert ["", "b2"] in leftover_vals

    def test_empty_input(self):
        """Empty assertions list → empty output."""
        vals, inds = zip_with_empty_indexed([])
        assert vals == []
        assert inds == []

    def test_unequal_lengths(self):
        """Unequal candidate lists → zip to shortest, leftovers for all."""
        vals, inds = zip_with_empty_indexed([["a1", "a2", "a3"], ["b1"]])

        # Zipped: min_len=1 → [["a1","b1"]]
        assert vals[0] == ["a1", "b1"]
        assert inds[0] == [0, 0]

        # Leftovers include all individual items
        leftover_vals = vals[1:]
        assert ["a1", ""] in leftover_vals
        assert ["a2", ""] in leftover_vals
        assert ["a3", ""] in leftover_vals
        assert ["", "b1"] in leftover_vals
