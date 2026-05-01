"""Tests for dataset creation scripts.

Tests the pure/unit-testable parts of:
- dafny_get_all_assertions (XML extraction regex)
- dafny_dataset_generator (folder structure, skip logic)
- assertion_test_generator (combination generation, XML creation)
- dafny_runner (command building, status parsing)
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.dafny_runner import (
    DafnyStatus,
    build_dafny_command,
    parse_dafny_output,
)
from src.datasets.assertion_test_generator import (
    _create_assertion_xml,
    _process_assertion_combinations,
)


# ---------------------------------------------------------------------------
# dafny_runner: build_dafny_command
# ---------------------------------------------------------------------------

class TestBuildDafnyCommand:
    def test_verify_includes_solver_option(self):
        cmd = build_dafny_command(Path("/dafny"), Path("/test.dfy"), "verify")
        cmd_str = " ".join(cmd)
        assert "--solver-option:O:memory_max_size=" in cmd_str
        assert "--verification-time-limit" in cmd_str
        assert "--cores" in cmd_str

    def test_asserttree_no_solver_option(self):
        cmd = build_dafny_command(Path("/dafny"), Path("/test.dfy"), "asserttree")
        cmd_str = " ".join(cmd)
        assert "--solver-option" not in cmd_str
        assert "asserttree" in cmd_str

    def test_resolve_no_solver_option(self):
        cmd = build_dafny_command(Path("/dafny"), Path("/test.dfy"), "resolve")
        cmd_str = " ".join(cmd)
        assert "--solver-option" not in cmd_str
        assert "resolve" in cmd_str

    def test_invalid_option_raises(self):
        with pytest.raises(ValueError, match="Invalid option"):
            build_dafny_command(Path("/dafny"), Path("/test.dfy"), "bogus")


# ---------------------------------------------------------------------------
# dafny_runner: parse_dafny_output
# ---------------------------------------------------------------------------

class TestParseDafnyOutput:
    def test_verified(self):
        assert parse_dafny_output(
            "Dafny program verifier finished with 3 verified, 0 errors\n", ""
        ) == DafnyStatus.VERIFIED

    def test_not_verified(self):
        assert parse_dafny_output(
            "Dafny program verifier finished with 1 verified, 2 errors\n", ""
        ) == DafnyStatus.NOT_VERIFIED

    def test_timeout(self):
        assert parse_dafny_output(
            "Dafny program verifier finished with 0 verified, 1 errors, 1 time out\n", ""
        ) == DafnyStatus.ERROR

    def test_resolution_error(self):
        assert parse_dafny_output(
            "2 resolution/type errors detected in foo.dfy\n", ""
        ) == DafnyStatus.ERROR

    def test_parse_error(self):
        assert parse_dafny_output(
            "1 parse errors detected in foo.dfy\n", ""
        ) == DafnyStatus.ERROR

    def test_empty_output_memory_error(self):
        assert parse_dafny_output("", "") == DafnyStatus.MEMORY_ERROR


# ---------------------------------------------------------------------------
# assertion_test_generator: _process_assertion_combinations
# ---------------------------------------------------------------------------

class TestProcessAssertionCombinations:
    def test_remove_one(self):
        combos = _process_assertion_combinations(
            [MagicMock(), MagicMock(), MagicMock()], 1,
        )
        assert len(combos) == 3
        assert all(len(c) == 1 for c in combos)

    def test_remove_two(self):
        combos = _process_assertion_combinations(
            [MagicMock(), MagicMock(), MagicMock()], 2,
        )
        assert len(combos) == 3  # C(3,2) = 3
        assert all(len(c) == 2 for c in combos)

    def test_remove_all(self):
        assertions = [MagicMock() for _ in range(4)]
        combos = _process_assertion_combinations(assertions, -1)
        assert len(combos) == 1
        assert combos[0] == {0, 1, 2, 3}

    def test_remove_zero_returns_empty_combo(self):
        combos = _process_assertion_combinations([MagicMock()], 0)
        # C(1,0) = 1 combo of size 0
        assert len(combos) == 1
        assert combos[0] == set()


# ---------------------------------------------------------------------------
# assertion_test_generator: _create_assertion_xml
# ---------------------------------------------------------------------------

class TestCreateAssertionXml:
    def test_creates_valid_xml(self, tmp_path):
        a1 = MagicMock()
        a1.type = "Regular_assertion"
        a1.start_pos = 100
        a1.end_pos = 150

        a2 = MagicMock()
        a2.type = "By_assertion"
        a2.start_pos = 200
        a2.end_pos = 250

        mi = MagicMock()
        mi.method_name = "TestMethod"
        mi.start_pos = 50
        mi.end_pos = 300

        out = tmp_path / "info.xml"
        _create_assertion_xml(2, [a1, a2], mi, out, group_id=7)

        assert out.exists()
        tree = ET.parse(out)
        root = tree.getroot()
        assert root.tag == "method"
        assert root.find("name").text == "TestMethod"
        assert root.find("start_pos").text == "50"
        assert root.find("end_pos").text == "300"

        ag = root.find("assertion_group")
        assert ag.find("id").text == "7"
        assert ag.find("number_assertions").text == "2"

        assertions = ag.findall("assertion")
        assert len(assertions) == 2
        assert assertions[0].find("type").text == "Regular_assertion"
        assert assertions[1].find("type").text == "By_assertion"

    def test_creates_parent_dirs(self, tmp_path):
        a = MagicMock()
        a.type = "assert"
        a.start_pos = 10
        a.end_pos = 20

        mi = MagicMock()
        mi.method_name = "M"
        mi.start_pos = 0
        mi.end_pos = 50

        out = tmp_path / "deep" / "nested" / "info.xml"
        _create_assertion_xml(1, [a], mi, out, group_id=0)
        assert out.exists()


# ---------------------------------------------------------------------------
# dafny_get_all_assertions: XML extraction regex
# ---------------------------------------------------------------------------

class TestAssertionXmlExtraction:
    def test_regex_extracts_program_block(self):
        stdout = "some preamble\n<program><method>foo</method></program>\nsome trailer"
        match = re.search(r"<program>(.*?)</program>", stdout, re.DOTALL)
        assert match is not None
        assert match.group(0) == "<program><method>foo</method></program>"

    def test_regex_no_match_returns_none(self):
        stdout = "no xml here"
        match = re.search(r"<program>(.*?)</program>", stdout, re.DOTALL)
        assert match is None


# ---------------------------------------------------------------------------
# dafny_dataset_generator: generate_dataset_for_program (mocked Dafny)
# ---------------------------------------------------------------------------

class TestGenerateDatasetForProgram:
    @patch("src.datasets.dafny_dataset_generator.run_dafny_from_text")
    @patch("src.datasets.dafny_dataset_generator.extract_assertion")
    @patch("src.datasets.dafny_dataset_generator.process_assertions_method")
    def test_skips_non_verified_program(self, mock_process, mock_extract, mock_run, tmp_path):
        """Programs that don't verify should be skipped entirely."""
        from src.datasets.dafny_dataset_generator import generate_dataset_for_program

        # Setup: assertion folder with assert.xml + program.dfy
        src = tmp_path / "src_prog"
        src.mkdir()
        (src / "assert.xml").write_text("<program></program>")
        (src / "program.dfy").write_text("method M() {}")

        mock_extract.return_value = MagicMock(methods=[])
        mock_run.return_value = (DafnyStatus.NOT_VERIFIED, "errors", "")

        dst = tmp_path / "dst"
        generate_dataset_for_program(Path("/dafny"), src, dst, tmp_path, 2)

        # Should not create output folder or call process_assertions
        mock_process.assert_not_called()

    @patch("src.datasets.dafny_dataset_generator.run_dafny_from_text")
    @patch("src.datasets.dafny_dataset_generator.extract_assertion")
    @patch("src.datasets.dafny_dataset_generator.process_assertions_method")
    def test_verified_program_creates_output(self, mock_process, mock_extract, mock_run, tmp_path):
        """Verified programs should create output folder + original_program.dfy."""
        from src.datasets.dafny_dataset_generator import generate_dataset_for_program

        src = tmp_path / "src_prog"
        src.mkdir()
        (src / "assert.xml").write_text("<program></program>")
        (src / "program.dfy").write_text("method M() { assert true; }")

        mock_method = MagicMock()
        mock_extract.return_value = MagicMock(methods=[mock_method])
        mock_run.return_value = (DafnyStatus.VERIFIED, "verified", "")

        dst = tmp_path / "dst"
        generate_dataset_for_program(Path("/dafny"), src, dst, tmp_path, 2)

        assert (dst / "src_prog" / "original_program.dfy").exists()
        mock_process.assert_called_once()

    def test_missing_files_skips(self, tmp_path):
        """Folders without assert.xml or program.dfy should be skipped."""
        from src.datasets.dafny_dataset_generator import generate_dataset_for_program

        src = tmp_path / "empty_prog"
        src.mkdir()

        dst = tmp_path / "dst"
        # Should not raise
        generate_dataset_for_program(Path("/dafny"), src, dst, tmp_path, 2)
        assert not dst.exists()


# ---------------------------------------------------------------------------
# full_dataset_creator: import check
# ---------------------------------------------------------------------------

class TestFullDatasetCreatorImport:
    def test_importable(self):
        """full_dataset_creator module should be importable."""
        from src.datasets import full_dataset_creator
        assert hasattr(full_dataset_creator, "main")
