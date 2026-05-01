"""
Bug condition exploration + preservation tests for cli.py extract_methods() phantom tempfile crash.

Bug: extract_methods() passes Path(tempfile.mktemp(suffix=".dfy")) to extract_assertion().
     mktemp generates a path but never creates the file.
     FileInfo.__init__() does open(file_path, 'rb') → FileNotFoundError → _die → SystemExit.

Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.dafny_read_assertions_xml import extract_assertion
from src.utils.assertion_method_classes import FileInfo

# Valid asserttree XML with one method spanning bytes 0..50
VALID_XML = """\
<program>
  <method>
    <name>TestMethod</name>
    <start_pos>0</start_pos>
    <end_pos>50</end_pos>
  </method>
</program>"""

# Source content — must be >= 51 bytes so byte offsets 0..50 work
SOURCE_CONTENT = "method TestMethod() { assert true; /* padding */ }\n"


## ---------------------------------------------------------------------------
## Task 1: Bug condition exploration test
## ---------------------------------------------------------------------------


def test_bug_condition_extract_methods_crashes_on_phantom_path():
    """
    **Validates: Requirements 2.1, 2.2, 2.3**

    After fix: extract_methods with real source_file path succeeds.
    Mock _run_dafny to return valid XML. Pass real file as source_file.
    Should return FileInfo with methods — no crash.
    """
    with tempfile.TemporaryDirectory() as tmp:
        # Write a real source file
        source_file = Path(tmp) / "test.dfy"
        source_file.write_text(SOURCE_CONTENT, encoding="utf-8")

        mock_return = (None, VALID_XML, "")
        with patch("src.cli._run_dafny", return_value=mock_return):
            from src.cli import extract_methods
            fi = extract_methods(Path("/fake/dafny"), SOURCE_CONTENT, Path(tmp), source_file)
            assert fi is not None
            assert len(fi.methods) == 1
            assert fi.methods[0].method_name == "TestMethod"


## ---------------------------------------------------------------------------
## Task 2: Preservation tests
## ---------------------------------------------------------------------------


def test_preservation_extract_assertion_parses_xml_with_real_file():
    """
    **Validates: Requirements 3.2, 3.3**

    extract_assertion() correctly parses XML into FileInfo when given a REAL file path.
    This works fine on unfixed code — the bug is only in extract_methods' path choice.
    """
    with tempfile.NamedTemporaryFile(suffix=".dfy", mode="w", delete=False) as f:
        f.write(SOURCE_CONTENT)
        real_path = Path(f.name)

    try:
        fi = extract_assertion(VALID_XML, real_path)
        assert isinstance(fi, FileInfo)
        assert len(fi.methods) == 1
        assert fi.methods[0].method_name == "TestMethod"
        assert fi.methods[0].start_pos == 0
        assert fi.methods[0].end_pos == 50
        assert fi.file_bytes == SOURCE_CONTENT.encode("utf-8")
    finally:
        real_path.unlink(missing_ok=True)


def test_preservation_fileinfo_reads_bytes_from_real_file():
    """
    **Validates: Requirements 3.2**

    FileInfo reads bytes correctly from a real file on disk.
    """
    with tempfile.NamedTemporaryFile(suffix=".dfy", mode="w", delete=False) as f:
        f.write(SOURCE_CONTENT)
        real_path = Path(f.name)

    try:
        fi = FileInfo(real_path)
        assert fi.file_bytes == SOURCE_CONTENT.encode("utf-8")
        assert fi.file_text == SOURCE_CONTENT
        assert fi.file_name == real_path.name
    finally:
        real_path.unlink(missing_ok=True)
