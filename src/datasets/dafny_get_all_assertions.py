"""Step 1: Extract assertions from DafnyBench programs via asserttree.

For each .dfy file in the DafnyBench ground_truth folder, runs the custom
Dafny fork's ``asserttree`` command to extract an XML description of all
methods and assertions. Saves ``assert.xml`` + ``program.dfy`` per file
into ``dataset/dafny_assertion_all/``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from src.config import (
    DAFNY_BASE_ASSERTION_DATASET,
    DAFNY_DATASET,
    DAFNY_MODIFIED_EXEC_FOR_ASSERTIONS,
    TEMP_FOLDER,
)
from src.utils.dafny_runner import run_dafny_from_text
from src.utils.parallel_executor import run_parallel_or_seq


def extract_assertions_from_file(
    dafny_exec: Path,
    dafny_program: Path,
    destination_path: Path,
    temp_folder: Path,
) -> None:
    """Run asserttree on one .dfy file, save assert.xml + program.dfy."""
    if not dafny_program.is_file():
        raise FileNotFoundError(f"File not found: {dafny_program}")

    code = dafny_program.read_text(encoding="utf-8")
    program_name = dafny_program.stem + "_dfy"

    _, stdout, _ = run_dafny_from_text(dafny_exec, code, temp_folder, option="asserttree")

    program_folder = destination_path / program_name
    program_folder.mkdir(parents=True, exist_ok=True)

    # Extract <program>...</program> block from asserttree output
    match = re.search(r"<program>(.*?)</program>", stdout, re.DOTALL)
    parsed_output = match.group(0) if match else ""
    if not parsed_output:
        print(f"ERROR PROCESSING {dafny_program}")

    (program_folder / "assert.xml").write_text(parsed_output, encoding="utf-8")
    (program_folder / "program.dfy").write_text(code, encoding="utf-8")


def dafny_get_all_assertions(
    dataset_path: Path = DAFNY_DATASET,
    dafny_exec: Path = DAFNY_MODIFIED_EXEC_FOR_ASSERTIONS,
    destination: Path = DAFNY_BASE_ASSERTION_DATASET,
    temp_folder: Path = TEMP_FOLDER,
    parallel: bool = True,
) -> list:
    """Extract assertions from all DafnyBench files.

    Args:
        dataset_path: Path to DafnyBench ground_truth folder.
        dafny_exec: Path to custom Dafny fork binary.
        destination: Output path for assertion XMLs.
        temp_folder: Temp folder for Dafny runs.
        parallel: Run in parallel.
    """
    files = [
        Path(os.path.join(dataset_path, f))
        for f in os.listdir(dataset_path)
        if os.path.isfile(os.path.join(dataset_path, f))
    ]

    print(f"Gathering assertions from {len(files)} DafnyBench files")

    def process_file(file_path: Path) -> None:
        extract_assertions_from_file(dafny_exec, file_path, destination, temp_folder)

    return run_parallel_or_seq(files, process_file, "Extracting assertions", parallel=parallel)
