"""Step 2: Generate assertion-removal dataset from extracted assertions.

For each program in ``dafny_assertion_all/``, reads the assert.xml,
verifies the original program, then systematically removes assertion
combinations (w/o-1, w/o-2, w/o-all) and saves failing cases.
"""

from __future__ import annotations

import os
from pathlib import Path

from src.config import (
    DAFNY_ASSERTION_DATASET,
    DAFNY_BASE_ASSERTION_DATASET,
    DAFNY_EXEC,
    TEMP_FOLDER,
)
from src.datasets.assertion_test_generator import process_assertions_method
from src.utils.assertion_method_classes import FileInfo
from src.utils.dafny_read_assertions_xml import extract_assertion
from src.utils.dafny_runner import DafnyStatus, run_dafny_from_text
from src.utils.parallel_executor import run_parallel_or_seq


def generate_dataset_for_program(
    dafny_exec: Path,
    assertion_folder: Path,
    destination: Path,
    temp_folder: Path,
    max_assertions_to_remove: int,
) -> None:
    """Generate assertion-removal test cases for one program folder.

    Args:
        dafny_exec: Dafny binary.
        assertion_folder: Folder with assert.xml + program.dfy.
        destination: Output dataset folder.
        temp_folder: Temp folder for Dafny runs.
        max_assertions_to_remove: Max assertions per combo (-1 = all).
    """
    assert_xml = assertion_folder / "assert.xml"
    program_file = assertion_folder / "program.dfy"

    if not assert_xml.is_file() or not program_file.is_file():
        return

    xml_text = assert_xml.read_text(encoding="utf-8")
    file_info = extract_assertion(xml_text, program_file)
    code = program_file.read_text(encoding="utf-8")

    # Verify original program first — skip if it doesn't verify
    status, _, _ = run_dafny_from_text(dafny_exec, code, temp_folder)
    if status != DafnyStatus.VERIFIED:
        return

    folder_name = assertion_folder.name
    dst = destination / folder_name
    dst.mkdir(parents=True, exist_ok=True)

    (dst / "original_program.dfy").write_text(code, encoding="utf-8")

    for method in file_info.methods:
        process_assertions_method(dafny_exec, dst, program_file, method, max_assertions_to_remove)


def run_dataset_generation(
    max_to_remove: int,
    base_dir: Path = DAFNY_BASE_ASSERTION_DATASET,
    dafny_exec: Path = DAFNY_EXEC,
    destination: Path = DAFNY_ASSERTION_DATASET,
    temp_folder: Path = TEMP_FOLDER,
    parallel: bool = True,
) -> list:
    """Generate dataset for all programs in base_dir."""
    dirs = [
        base_dir / name
        for name in os.listdir(base_dir)
        if (base_dir / name).is_dir() and not name.startswith(".")
    ]

    def process_dir(d: Path) -> None:
        generate_dataset_for_program(dafny_exec, d, destination, temp_folder, max_to_remove)

    return run_parallel_or_seq(dirs, process_dir, "Generating dataset", parallel=parallel)


def dafny_dataset_generator(parallel: bool = True) -> None:
    """Full dataset generation: w/o-1, w/o-2, then w/o-all."""
    print("Creating w/o-1 and w/o-2 test cases")
    run_dataset_generation(2, parallel=parallel)
    print("Creating w/o-all test cases")
    run_dataset_generation(-1, parallel=parallel)
