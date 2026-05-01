"""Unit tests for Phase 7 — Research Scripts & Analysis.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 12.1, 12.2
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.research_questions import CacheMissError
from src.analysis.results_reader import (
    ResultsReader,
    parse_verification_output,
)
from src.analysis.position_evaluation import (
    oracle_here_would_fix,
    assertion_here_syntactic_valid,
)


# ---------------------------------------------------------------------------
# 1. CacheMissError: has missing_entries attribute, message contains count
# ---------------------------------------------------------------------------

class TestCacheMissError:
    def test_missing_entries_attribute(self):
        """CacheMissError stores missing_entries list."""
        entries = ["prog1/g1", "prog2/g2", "prog3/g3"]
        err = CacheMissError(f"Missing cache for {len(entries)} groups", missing_entries=entries)
        assert err.missing_entries == entries

    def test_message_contains_count(self):
        """CacheMissError message includes count of missing entries."""
        entries = ["a/b", "c/d"]
        err = CacheMissError(f"Missing cache for {len(entries)} groups", missing_entries=entries)
        assert "2" in str(err)

    def test_default_missing_entries_empty(self):
        """CacheMissError with no missing_entries defaults to empty list."""
        err = CacheMissError("some error")
        assert err.missing_entries == []

    def test_is_exception(self):
        """CacheMissError is an Exception subclass."""
        err = CacheMissError("boom")
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# 2. ResultsReader: read_localization raises CacheMissError on missing file
# ---------------------------------------------------------------------------

class TestResultsReaderLocalizationMiss:
    def test_raises_on_missing_localization(self, tmp_path):
        """Req 12.2: read_localization raises CacheMissError when file absent."""
        reader = ResultsReader(tmp_path)
        with pytest.raises(CacheMissError) as exc_info:
            reader.read_localization("model_x", "prog_a", "group_1")
        assert "model_x/prog_a/group_1" in exc_info.value.missing_entries


# ---------------------------------------------------------------------------
# 3. ResultsReader: read_assertions raises CacheMissError on missing file
# ---------------------------------------------------------------------------

class TestResultsReaderAssertionMiss:
    def test_raises_on_missing_assertions(self, tmp_path):
        """Req 12.2: read_assertions raises CacheMissError when file absent."""
        reader = ResultsReader(tmp_path)
        with pytest.raises(CacheMissError) as exc_info:
            reader.read_assertions("model_x", "prog_a", "group_1")
        assert "model_x/prog_a/group_1" in exc_info.value.missing_entries


# ---------------------------------------------------------------------------
# 4. ResultsReader: read_verification raises CacheMissError on missing dir
# ---------------------------------------------------------------------------

class TestResultsReaderVerificationMiss:
    def test_raises_on_missing_verification_dir(self, tmp_path):
        """Req 12.2: read_verification raises CacheMissError when dir absent."""
        reader = ResultsReader(tmp_path)
        with pytest.raises(CacheMissError) as exc_info:
            reader.read_verification("model_x", "prog_a", "group_1")
        assert "model_x/prog_a/group_1" in exc_info.value.missing_entries


# ---------------------------------------------------------------------------
# 5. ResultsReader: read_localization returns correct data when cached
# ---------------------------------------------------------------------------

class TestResultsReaderLocalizationHit:
    def test_returns_parsed_positions(self, tmp_path):
        """Req 12.1: read_localization returns parsed ints from cached file."""
        loc_dir = tmp_path / "m" / "p" / "g" / "localization"
        loc_dir.mkdir(parents=True)
        (loc_dir / "localization_raw_response.txt").write_text("[3, 7, 12]")

        reader = ResultsReader(tmp_path)
        result = reader.read_localization("m", "p", "g")
        assert result == ["3", "7", "12"] or result == [3, 7, 12]


# ---------------------------------------------------------------------------
# 6. ResultsReader: read_assertions returns correct data when cached
# ---------------------------------------------------------------------------

class TestResultsReaderAssertionHit:
    def test_returns_parsed_assertions(self, tmp_path):
        """Req 12.1: read_assertions returns parsed JSON from cached file."""
        assert_dir = tmp_path / "m" / "p" / "g" / "assertions_list"
        assert_dir.mkdir(parents=True)
        data = [["assert x > 0;"], ["assert y < 10;", "assert z;"]]
        (assert_dir / "assertions_parsed.json").write_text(json.dumps(data))

        reader = ResultsReader(tmp_path)
        result = reader.read_assertions("m", "p", "g")
        assert result == data


# ---------------------------------------------------------------------------
# 7. ResultsReader: check_all_cached returns correct missing list
# ---------------------------------------------------------------------------

class TestResultsReaderCheckAllCached:
    def test_returns_missing_groups(self, tmp_path):
        """Req 9.3: check_all_cached lists exactly the missing groups."""
        # Create cache for group g1 only
        loc_dir = tmp_path / "model" / "prog" / "g1" / "localization"
        loc_dir.mkdir(parents=True)
        (loc_dir / "localization_raw_response.txt").write_text("[1]")

        reader = ResultsReader(tmp_path)
        groups = [("prog", "g1"), ("prog", "g2"), ("prog", "g3")]
        missing = reader.check_all_cached("model", groups)

        assert "prog/g1" not in missing
        assert "prog/g2" in missing
        assert "prog/g3" in missing
        assert len(missing) == 2

    def test_all_cached_returns_empty(self, tmp_path):
        """Req 9.3: all cached → empty missing list."""
        for gid in ["g1", "g2"]:
            loc_dir = tmp_path / "model" / "prog" / gid / "localization"
            loc_dir.mkdir(parents=True)
            (loc_dir / "localization_raw_response.txt").write_text("[1]")

        reader = ResultsReader(tmp_path)
        missing = reader.check_all_cached("model", [("prog", "g1"), ("prog", "g2")])
        assert missing == []


# ---------------------------------------------------------------------------
# 8. parse_verification_output: parses verified output correctly
# ---------------------------------------------------------------------------

class TestParseVerificationOutputVerified:
    def test_parses_verified_line(self, tmp_path):
        """Req 12.1: parse verified Dafny output."""
        f = tmp_path / "verif_stdout.txt"
        f.write_text("Dafny program verifier finished\n2 verified, 0 errors, 0 time out\n")

        result = parse_verification_output(f)
        assert result["verified"] == 2
        assert result["verification_errors"] == 0
        assert result["time_out_errors"] == 0
        assert result["did_not_finish"] == 0
        assert result["verif_sucess"] is True


# ---------------------------------------------------------------------------
# 9. parse_verification_output: parses error output correctly
# ---------------------------------------------------------------------------

class TestParseVerificationOutputError:
    def test_parses_error_line(self, tmp_path):
        """Req 12.1: parse Dafny output with errors."""
        f = tmp_path / "verif_stdout.txt"
        f.write_text("Dafny program verifier finished\n0 verified, 3 errors, 1 time out\n")

        result = parse_verification_output(f)
        assert result["verified"] == 0
        assert result["verification_errors"] == 3
        assert result["time_out_errors"] == 1
        assert result["did_not_finish"] == 0
        assert result["verif_sucess"] is False

    def test_parses_resolution_errors(self, tmp_path):
        """Req 12.1: parse resolution error output."""
        f = tmp_path / "verif_stdout.txt"
        f.write_text("5 resolution/type errors detected in foo.dfy\n")

        result = parse_verification_output(f)
        assert result["resolution_errors"] == 5
        assert result["verif_sucess"] is False

    def test_parses_parse_errors(self, tmp_path):
        """Req 12.1: parse parse-error output."""
        f = tmp_path / "verif_stdout.txt"
        f.write_text("2 parse errors detected in foo.dfy\n")

        result = parse_verification_output(f)
        assert result["parse_errors"] == 2
        assert result["verif_sucess"] is False

    def test_missing_file_returns_empty(self, tmp_path):
        """parse_verification_output returns {} for missing file."""
        result = parse_verification_output(tmp_path / "nonexistent.txt")
        assert result == {}

    def test_error_skipped_verification(self, tmp_path):
        """parse_verification_output handles ERROR SKIPPED VERIFICATION."""
        f = tmp_path / "verif_stdout.txt"
        f.write_text("ERROR SKIPPED VERIFICATION\n")

        result = parse_verification_output(f)
        assert result["verification_errors"] == 1
        assert result["did_not_finish"] == 0


# ---------------------------------------------------------------------------
# 10. oracle_here_would_fix: returns True when position matches
# ---------------------------------------------------------------------------

class TestOracleHereWouldFix:
    def test_returns_true_on_match(self):
        """Req 12.1: True when found position in oracle options."""
        assert oracle_here_would_fix([3, 7], [[3, 5], [7, 9]]) is True

    def test_returns_true_flat_list(self):
        """Handles flat list of ints (auto-wrapped)."""
        assert oracle_here_would_fix([5], [5, 10]) is True

    def test_returns_true_nested_match(self):
        """Match in second option list."""
        assert oracle_here_would_fix([9], [[1, 2], [9, 10]]) is True


# ---------------------------------------------------------------------------
# 11. oracle_here_would_fix: returns False when no match
# ---------------------------------------------------------------------------

class TestOracleHereWouldFixFalse:
    def test_returns_false_no_match(self):
        """Req 12.1: False when no found position in oracle options."""
        assert oracle_here_would_fix([99], [[1, 2], [3, 4]]) is False

    def test_returns_false_empty_found(self):
        """False when found_positions is empty."""
        assert oracle_here_would_fix([], [[1, 2]]) is False

    def test_returns_false_empty_options(self):
        """False when oracle options is empty."""
        assert oracle_here_would_fix([1], []) is False


# ---------------------------------------------------------------------------
# 12. assertion_here_syntactic_valid: returns True when position valid
# ---------------------------------------------------------------------------

class TestAssertionHereSyntacticValid:
    def test_returns_true_on_match(self):
        """Req 12.1: True when found position in syntactic valid set."""
        assert assertion_here_syntactic_valid([3, 7], [1, 3, 5, 7, 9]) is True

    def test_returns_false_no_match(self):
        """False when no found position is syntactically valid."""
        assert assertion_here_syntactic_valid([2, 4], [1, 3, 5]) is False

    def test_returns_false_empty_found(self):
        """False when found_positions is empty."""
        assert assertion_here_syntactic_valid([], [1, 2, 3]) is False
