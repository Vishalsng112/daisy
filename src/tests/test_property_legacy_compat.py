# Feature: daisy-codebase-rewrite, Property 13: Legacy data structure compatibility
"""Property test: legacy FileInfo/MethodInfo path produces same output as plain-string path.

**Validates: Requirements 13.1, 15.3**

For any Dafny-like file containing a method, substituting the method via
FileInfo.substitute_method_with_text (byte-level) SHALL produce the same
result as plain str.replace() on the file text — proving the new pipeline's
string approach is equivalent to the legacy byte-manipulation approach.

Includes non-ASCII tests: multi-byte UTF-8 chars (ñ, ã, ó, ü, etc.) cause
byte offsets to diverge from char offsets. str.replace() must still match
the legacy byte-level result.
"""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.utils.assertion_method_classes import FileInfo, MethodInfo


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

method_name_st = st.from_regex(r"[a-zA-Z][a-zA-Z0-9]{0,15}", fullmatch=True)

# ASCII-only body lines
ascii_body_line_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Zs"),
        blacklist_characters="\x00\r",
    ),
    min_size=0,
    max_size=40,
)

# Non-ASCII body lines — includes multi-byte UTF-8 chars
non_ascii_body_line_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Zs"),
        blacklist_characters="\x00\r",
    ),
    min_size=1,
    max_size=40,
).filter(lambda s: any(ord(c) > 127 for c in s))

# Mixed body lines — can be ASCII or non-ASCII
body_line_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Zs"),
        blacklist_characters="\x00\r",
    ),
    min_size=0,
    max_size=40,
)

replacement_text_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Zs"),
        blacklist_characters="\x00\r",
    ),
    min_size=1,
    max_size=80,
)

context_lines_st = st.lists(body_line_st, min_size=0, max_size=5)


# ---------------------------------------------------------------------------
# Composite strategy: file with method + byte offsets
# ---------------------------------------------------------------------------

@st.composite
def dafny_file_with_method(draw, body_line_strategy=body_line_st):
    """Generate a file text containing a method, plus the method boundaries."""
    prefix_lines = draw(st.lists(body_line_strategy, min_size=0, max_size=5))
    suffix_lines = draw(st.lists(body_line_strategy, min_size=0, max_size=5))
    mname = draw(method_name_st)
    body_lines = draw(st.lists(body_line_strategy, min_size=1, max_size=5))

    method_text = f"method {mname}()\n{{\n"
    for line in body_lines:
        method_text += f"  {line}\n"
    method_text += "}"

    prefix = "\n".join(prefix_lines)
    if prefix:
        prefix += "\n"
    suffix = "\n".join(suffix_lines)
    if suffix:
        suffix = "\n" + suffix

    file_text = prefix + method_text + suffix

    # Compute BYTE offsets (what the legacy code uses)
    file_bytes = file_text.encode("utf-8")
    method_bytes = method_text.encode("utf-8")
    start_pos = file_bytes.index(method_bytes)
    end_pos = start_pos + len(method_bytes) - 1  # inclusive

    return file_text, method_text, mname, start_pos, end_pos


@st.composite
def dafny_file_with_non_ascii_context(draw):
    """Generate file with non-ASCII chars in prefix/suffix (before/after method).

    This forces byte offsets to diverge from char offsets.
    """
    # At least one non-ASCII line in prefix
    non_ascii_lines = draw(st.lists(non_ascii_body_line_st, min_size=1, max_size=3))
    ascii_lines = draw(st.lists(ascii_body_line_st, min_size=0, max_size=2))
    prefix_lines = non_ascii_lines + ascii_lines

    suffix_lines = draw(st.lists(body_line_st, min_size=0, max_size=3))
    mname = draw(method_name_st)
    body_lines = draw(st.lists(ascii_body_line_st, min_size=1, max_size=3))

    method_text = f"method {mname}()\n{{\n"
    for line in body_lines:
        method_text += f"  {line}\n"
    method_text += "}"

    prefix = "\n".join(prefix_lines)
    if prefix:
        prefix += "\n"
    suffix = "\n".join(suffix_lines)
    if suffix:
        suffix = "\n" + suffix

    file_text = prefix + method_text + suffix

    file_bytes = file_text.encode("utf-8")
    method_bytes = method_text.encode("utf-8")
    start_pos = file_bytes.index(method_bytes)
    end_pos = start_pos + len(method_bytes) - 1

    # Verify byte/char divergence exists
    char_start = file_text.index(method_text)
    assume(start_pos != char_start)  # byte offset != char offset

    return file_text, method_text, mname, start_pos, end_pos


def _run_legacy_and_new(file_text, method_text, mname, start_pos, end_pos, replacement):
    """Run both legacy (byte-level) and new (str.replace) paths, return both results."""
    # New pipeline: plain string replacement
    new_result = file_text.replace(method_text, replacement, 1)

    # Legacy pipeline: FileInfo + MethodInfo byte manipulation
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".dfy", delete=False, encoding="utf-8"
    ) as f:
        f.write(file_text)
        tmp_path = Path(f.name)

    try:
        fi = FileInfo(tmp_path)
        mi = MethodInfo(start_pos, end_pos, mname, fi)
        legacy_bytes, legacy_result = fi.substitute_method_with_text(mi, replacement)
    finally:
        tmp_path.unlink(missing_ok=True)

    return new_result, legacy_result, legacy_bytes


# ---------------------------------------------------------------------------
# Property tests — ASCII (original)
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(data=dafny_file_with_method(), replacement=replacement_text_st)
def test_legacy_substitute_matches_plain_string_replace(
    data: tuple, replacement: str
) -> None:
    """FileInfo.substitute_method_with_text == str.replace() for ASCII content."""
    file_text, method_text, mname, start_pos, end_pos = data
    new_result, legacy_result, _ = _run_legacy_and_new(
        file_text, method_text, mname, start_pos, end_pos, replacement
    )
    assert legacy_result == new_result


@settings(max_examples=100)
@given(data=dafny_file_with_method(), replacement=replacement_text_st)
def test_legacy_substitute_bytes_decode_matches_string(
    data: tuple, replacement: str
) -> None:
    """The bytes returned by substitute_method_with_text decode to the string result."""
    file_text, method_text, mname, start_pos, end_pos = data
    _, legacy_result, legacy_bytes = _run_legacy_and_new(
        file_text, method_text, mname, start_pos, end_pos, replacement
    )
    assert legacy_bytes.decode("utf-8") == legacy_result


# ---------------------------------------------------------------------------
# Property tests — NON-ASCII (new: byte offset != char offset)
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(data=dafny_file_with_non_ascii_context(), replacement=replacement_text_st)
def test_non_ascii_legacy_matches_plain_string_replace(
    data: tuple, replacement: str
) -> None:
    """With non-ASCII prefix (byte offset != char offset), str.replace() still matches legacy."""
    file_text, method_text, mname, start_pos, end_pos = data

    # Confirm byte/char divergence
    char_start = file_text.index(method_text)
    assert start_pos != char_start, "Expected byte/char offset divergence"

    new_result, legacy_result, _ = _run_legacy_and_new(
        file_text, method_text, mname, start_pos, end_pos, replacement
    )
    assert legacy_result == new_result, (
        f"Non-ASCII: legacy and new path differ.\n"
        f"byte_start={start_pos}, char_start={char_start}\n"
        f"Legacy: {legacy_result!r}\n"
        f"New:    {new_result!r}"
    )


@settings(max_examples=100)
@given(
    data=dafny_file_with_method(body_line_strategy=body_line_st),
    replacement=replacement_text_st,
)
def test_mixed_content_legacy_matches_plain_string_replace(
    data: tuple, replacement: str
) -> None:
    """Mixed ASCII/non-ASCII content: str.replace() matches legacy byte-level."""
    file_text, method_text, mname, start_pos, end_pos = data
    new_result, legacy_result, _ = _run_legacy_and_new(
        file_text, method_text, mname, start_pos, end_pos, replacement
    )
    assert legacy_result == new_result


# ---------------------------------------------------------------------------
# Concrete tests — real dataset file with non-ASCII
# ---------------------------------------------------------------------------


import pytest

# Real dataset file with non-ASCII chars (Spanish: ó, í, á, etc.)
# 17 bytes of byte/char offset divergence before the method
_REAL_DATASET_FILE = Path(
    "dataset/extracted/dafny_assertion_dataset/"
    "Formal-methods-of-software-development_tmp_tmppryvbyty_"
    "Examenes_Beni_Heusel-Benedikt-Ass-1_dfy/original_program.dfy"
)
_REAL_METHOD_BYTE_START = 4084
_REAL_METHOD_BYTE_END = 4848  # inclusive
_REAL_METHOD_NAME = "oneIsEven_Lemma"


@pytest.mark.skipif(
    not _REAL_DATASET_FILE.exists(),
    reason="Dataset file not available",
)
def test_real_dataset_non_ascii_file() -> None:
    """Concrete test: real .dfy file with Spanish non-ASCII chars.

    File has ó, í, á etc. in comments before the method, causing
    byte offset 4084 != char offset 4067 (17 bytes divergence).
    str.replace() must still produce identical output to legacy byte-level.
    """
    with open(_REAL_DATASET_FILE, "rb") as f:
        file_bytes = f.read()
    file_text = file_bytes.decode("utf-8")

    method_bytes = file_bytes[_REAL_METHOD_BYTE_START : _REAL_METHOD_BYTE_END + 1]
    method_text = method_bytes.decode("utf-8")

    # Confirm byte/char divergence
    char_start = file_text.index(method_text)
    assert _REAL_METHOD_BYTE_START != char_start, (
        f"Expected divergence: byte={_REAL_METHOD_BYTE_START}, char={char_start}"
    )

    replacement = "lemma oneIsEven_Lemma_FIXED(x:int,y:int,z:int)\n{ /* fixed */ }"

    # New pipeline: str.replace
    new_result = file_text.replace(method_text, replacement, 1)

    # Legacy pipeline: FileInfo byte-level
    fi = FileInfo(_REAL_DATASET_FILE)
    mi = MethodInfo(_REAL_METHOD_BYTE_START, _REAL_METHOD_BYTE_END, _REAL_METHOD_NAME, fi)
    _legacy_bytes, legacy_result = fi.substitute_method_with_text(mi, replacement)

    assert legacy_result == new_result, (
        f"Real non-ASCII file: legacy and new path differ.\n"
        f"byte_start={_REAL_METHOD_BYTE_START}, char_start={char_start}"
    )


@pytest.mark.skipif(
    not _REAL_DATASET_FILE.exists(),
    reason="Dataset file not available",
)
def test_real_dataset_non_ascii_assertion_removal() -> None:
    """Concrete test: remove assertion from method in non-ASCII file.

    Uses get_method_with_assertion_group_changed to remove assertion at
    byte 4259-4288, then verifies str.replace on the result matches.
    """
    from src.utils.assertion_method_classes import AssertionInfo
    from src.config import ASSERTION_PLACEHOLDER

    fi = FileInfo(_REAL_DATASET_FILE)
    mi = MethodInfo(_REAL_METHOD_BYTE_START, _REAL_METHOD_BYTE_END, _REAL_METHOD_NAME, fi)

    # Create assertion info for the assertion at byte 4259-4288
    ai = AssertionInfo(4259, 4288, "assert", mi)
    group = [ai]

    # Legacy: get method with assertion replaced by placeholder
    method_with_placeholder = mi.get_method_with_assertion_group_changed(
        group, remove_empty_lines=True, change_text=ASSERTION_PLACEHOLDER,
    )

    # Verify placeholder is in the result
    assert ASSERTION_PLACEHOLDER in method_with_placeholder

    # Verify the method text is valid UTF-8 (no corruption from byte manipulation)
    method_with_placeholder.encode("utf-8")  # should not raise

    # Now substitute back into file using both paths
    replacement = method_with_placeholder
    file_text = fi.file_text
    method_text = mi.segment_str

    new_result = file_text.replace(method_text, replacement, 1)
    _, legacy_result = fi.substitute_method_with_text(mi, replacement)

    assert legacy_result == new_result
