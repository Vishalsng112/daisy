"""Position evaluation — evaluate position prediction accuracy against oracle.

Rewrites ``src/datasets/dafny_dataset_all_positions_gatherer.py`` using the
new abstractions. Computes oracle positions, valid fix positions, and
syntactically valid positions for assertion groups.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import (
    ASSERTION_PLACEHOLDER,
    DAFNY_ASSERTION_DATASET,
    DAFNY_EXEC,
    TEMP_FOLDER,
)
from src.research_questions import CacheMissError
from src.utils.assertion_method_classes import (
    FileInfo,
    MethodInfo,
    assertionGroup,
    get_assertion_group_string_id,
    get_file_from_assertion_group,
    get_method_from_assertion_group,
)
from src.utils.dataset_class import Dataset
from src.utils.external_cmd import Status, run_external_cmd
from src.utils.parallel_executor import run_parallel_or_seq


# ---------------------------------------------------------------------------
# Position accuracy helpers (pure functions, no I/O)
# ---------------------------------------------------------------------------

def oracle_here_would_fix(
    found_positions: list[int],
    all_options_fixes_positions: list,
) -> bool:
    """Return True if any found position appears in any oracle option.

    ``all_options_fixes_positions`` may be ``list[list[int]]`` or ``list[int]``
    (flat list is auto-wrapped).
    """
    if not all_options_fixes_positions:
        return False
    if isinstance(all_options_fixes_positions[0], int):
        all_options_fixes_positions = [all_options_fixes_positions]
    valid = {pos for option in all_options_fixes_positions for pos in option}
    return any(pos in valid for pos in found_positions)


def assertion_here_syntactic_valid(
    found_positions: list[int],
    syntactic_positions: list[int],
) -> bool:
    """Return True if any found position is syntactically valid."""
    valid = set(syntactic_positions)
    return any(pos in valid for pos in found_positions)


# ---------------------------------------------------------------------------
# Method preparation
# ---------------------------------------------------------------------------

def get_method_for_verification_and_oracle_positions(
    assertion_group: assertionGroup,
    placeholder: str = ASSERTION_PLACEHOLDER,
    remove_empty_lines: bool = True,
) -> tuple[FileInfo, MethodInfo, str, str, list[int]]:
    """Prepare method text and compute oracle positions.

    Returns:
        (file, method, method_without_placeholders, method_with_placeholders,
         oracle_positions)
    """
    file = get_file_from_assertion_group(assertion_group)
    method = get_method_from_assertion_group(assertion_group)

    method_with_placeholders = method.get_method_with_assertion_group_changed(
        assertion_group, remove_empty_lines, placeholder,
    )

    oracle_positions: list[int] = []
    lines_without_placeholder: list[str] = []
    added_lines = 0

    for idx, line in enumerate(method_with_placeholders.splitlines(keepends=True)):
        if placeholder in line:
            added_lines += 1
            oracle_positions.append(idx - added_lines)
        else:
            lines_without_placeholder.append(line)

    method_without_placeholders = "".join(lines_without_placeholder)
    return file, method, method_without_placeholders, method_with_placeholders, oracle_positions


# ---------------------------------------------------------------------------
# Dafny verification helper
# ---------------------------------------------------------------------------

def _run_dafny_verify(
    dafny_exec: Path,
    file_text: str,
    temp_folder: Path,
    option: str = "verify",
) -> tuple[Status, str]:
    """Run Dafny on text, return (status, stdout)."""
    import os
    import tempfile

    temp_file = Path(tempfile.mktemp(suffix=".dfy", dir=str(temp_folder)))
    try:
        temp_file.write_text(file_text, encoding="utf-8")
        cmd = [str(dafny_exec), option, str(temp_file)]
        status, stdout, _stderr = run_external_cmd(cmd, timeout=120)
        return status, stdout
    finally:
        try:
            temp_file.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Dataset expansion: original error + oracle positions
# ---------------------------------------------------------------------------

def _get_original_error_of_group(assertion_group: assertionGroup) -> None:
    """Compute and save original error, oracle positions, oracle assertions."""
    group_name = get_assertion_group_string_id(assertion_group)
    file, method, method_missing, method_with_placeholder, oracle_pos = (
        get_method_for_verification_and_oracle_positions(assertion_group)
    )

    base_path = file.file_path.parent / group_name

    # Skip if already done
    if (base_path / "method_with_assertion_placeholder.dfy").exists():
        return

    # Oracle assertions (sorted by position)
    assertions_list = [
        a.segment_str for a in sorted(assertion_group, key=lambda x: x.start_pos)
    ]

    # Write oracle assertions
    (base_path / "oracle_assertions.json").parent.mkdir(parents=True, exist_ok=True)
    with open(base_path / "oracle_assertions.json", "w", encoding="utf-8") as f:
        json.dump(assertions_list, f, indent=2, ensure_ascii=False)

    # Get original error
    _, full_file_text = file.substitute_method_with_text(method, method_missing)
    _status, stdout = _run_dafny_verify(DAFNY_EXEC, full_file_text, TEMP_FOLDER)

    with open(base_path / "original_error.txt", "w", encoding="utf-8") as f:
        f.write(stdout)

    with open(base_path / "oracle_fix_position.txt", "w", encoding="utf-8") as f:
        f.write(str(oracle_pos))

    with open(base_path / "method_with_assertion_placeholder.dfy", "w", encoding="utf-8") as f:
        f.write(method_with_placeholder)


def expand_assertion_groups_with_original_error_info(
    dataset_dir: Path,
    parallel: bool = True,
) -> list[Any]:
    """Enrich each assertion group with original error and oracle positions."""
    dataset = Dataset.from_dataset_assertion_groups(dataset_dir)
    groups = dataset.get_all_assertion_groups()
    return run_parallel_or_seq(
        groups,
        _get_original_error_of_group,
        "Get Original Error",
        parallel=parallel,
    )


# ---------------------------------------------------------------------------
# Dataset expansion: all valid fix positions
# ---------------------------------------------------------------------------

def _get_all_methods_with_assertion_relocated(
    method_lines: list[str],
    assertions: list[str],
    oracle_lines: list[int],
    ind: int,
) -> list[list[str]]:
    """Generate all methods with assertion ``ind`` relocated to every position.

    Other assertions stay at their oracle positions.
    """
    n_lines = len(method_lines)
    n_assert = len(assertions)
    assert n_lines > 0
    assert n_assert == len(oracle_lines)
    assert 0 <= ind < n_assert

    target = assertions[ind]
    methods: list[list[str]] = []

    for target_pos in range(n_lines):
        method: list[str] = []
        for line_idx in range(n_lines):
            method.append(method_lines[line_idx])
            if target_pos == line_idx:
                method.append(target)
            for a_idx, (assertion, a_line) in enumerate(zip(assertions, oracle_lines)):
                if a_idx == ind:
                    continue
                if a_line == line_idx:
                    method.append(assertion)
        methods.append(method)

    return methods


def _get_all_valid_positions(assertion_group: assertionGroup) -> list[list[int]] | None:
    """Compute all valid positions for each assertion in the group."""
    group_name = get_assertion_group_string_id(assertion_group)
    method = get_method_from_assertion_group(assertion_group)
    file = get_file_from_assertion_group(assertion_group)
    base_path = file.file_path.parent / group_name

    output_file = base_path / "all_lines_that_fix_file.json"
    if output_file.exists():
        return None

    method_file = base_path / "method_without_assertion_group.dfy"
    oracle_assert_file = base_path / "oracle_assertions.json"
    oracle_pos_file = base_path / "oracle_fix_position.txt"

    with open(method_file, "r", encoding="utf-8") as f:
        method_text = f.read()
    with open(oracle_assert_file, "r", encoding="utf-8") as f:
        assertions_list = json.load(f)
    with open(oracle_pos_file, "r", encoding="utf-8") as f:
        oracle_positions = json.load(f)

    method_lines = method_text.splitlines()
    all_valid: list[list[int]] = []

    for ind in range(len(assertions_list)):
        valid_for_assertion: list[int] = []
        methods = _get_all_methods_with_assertion_relocated(
            method_lines, assertions_list, oracle_positions, ind,
        )
        for pos, new_lines in enumerate(methods):
            new_text = "\n".join(new_lines)
            _, full_file_text = file.substitute_method_with_text(method, new_text)
            status, _ = _run_dafny_verify(DAFNY_EXEC, full_file_text, TEMP_FOLDER)
            if status == Status.OK:
                valid_for_assertion.append(pos)
        all_valid.append(valid_for_assertion)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_valid, f, indent=2, ensure_ascii=False)

    return all_valid


def expand_assertion_groups_with_all_fix_positions(
    dataset_dir: Path,
    parallel: bool = True,
) -> list[Any]:
    """Compute all valid fix positions for each assertion group."""
    dataset = Dataset.from_dataset_assertion_groups(dataset_dir)
    groups = dataset.get_all_assertion_groups()
    return run_parallel_or_seq(
        groups,
        _get_all_valid_positions,
        "Get All Valid Positions",
        parallel=parallel,
    )


# ---------------------------------------------------------------------------
# Dataset expansion: syntactically valid positions
# ---------------------------------------------------------------------------

def _get_syntactic_valid_positions(assertion_group: assertionGroup) -> None:
    """Find all syntactically valid positions for assertions in a group."""
    group_name = get_assertion_group_string_id(assertion_group)
    method = get_method_from_assertion_group(assertion_group)
    file = get_file_from_assertion_group(assertion_group)
    base_path = file.file_path.parent / group_name

    output_file = base_path / "all_lines_that_are_syntatic_valid.json"
    if output_file.exists():
        return

    method_file = base_path / "method_without_assertion_group.dfy"
    with open(method_file, "r", encoding="utf-8") as f:
        method_text = f.read()

    test_assertion = "assert 1==1;"
    lines = method_text.splitlines(keepends=True)
    valid_lines: list[int] = []

    for line_idx in range(len(lines)):
        new_lines: list[str] = []
        for idx, line in enumerate(lines):
            new_lines.append(line)
            if idx == line_idx:
                new_lines.append(test_assertion + "\n")
        new_method = "".join(new_lines)
        _, full_file_text = file.substitute_method_with_text(method, new_method)
        _status, stdout = _run_dafny_verify(
            DAFNY_EXEC, full_file_text, TEMP_FOLDER, option="resolve",
        )
        if "parse errors detected" not in stdout:
            valid_lines.append(line_idx)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(valid_lines, f, indent=2, ensure_ascii=False)


def expand_assertion_groups_with_all_syntactic_valid_positions(
    dataset_dir: Path,
    parallel: bool = True,
) -> list[Any]:
    """Compute all syntactically valid assertion positions for each group."""
    dataset = Dataset.from_dataset_assertion_groups(dataset_dir)
    groups = dataset.get_all_assertion_groups()
    return run_parallel_or_seq(
        groups,
        _get_syntactic_valid_positions,
        "Get Syntactic Valid Positions",
        parallel=parallel,
    )
