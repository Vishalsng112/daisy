"""Dafny runner — run Dafny verify/resolve/asserttree on code text or files.

Thin wrapper around run_external_cmd with Dafny-specific status parsing.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from enum import Enum
from pathlib import Path

from src.config import DAFNY_EXEC, TEMP_FOLDER, VERIFIER_MAX_MEMORY, VERIFIER_TIME_LIMIT
from src.utils.external_cmd import run_external_cmd

VALID_OPTIONS = ("resolve", "verify", "build", "run", "asserttree")


class DafnyStatus(Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    ERROR = "ERROR"
    MEMORY_ERROR = "MEMORY_ERROR"


def build_dafny_command(
    dafny_exec: Path, dafny_program: Path, option: str = "verify",
) -> list[str]:
    if option not in VALID_OPTIONS:
        raise ValueError(f"Invalid option '{option}'. Must be one of {VALID_OPTIONS}.")

    if option == "verify":
        return [
            str(dafny_exec), option, str(dafny_program),
            "--cores", "1",
            "--verification-time-limit", str(VERIFIER_TIME_LIMIT),
            f"--solver-option:O:memory_max_size={VERIFIER_MAX_MEMORY * 1000}",
        ]
    return [str(dafny_exec), option, str(dafny_program), "--cores", "1"]


def parse_dafny_output(stdout: str, stderr: str) -> DafnyStatus:
    for line in stdout.splitlines():
        if "Dafny program verifier finished" in line:
            if "time out" in line:
                return DafnyStatus.ERROR
            if "0 errors" in line:
                return DafnyStatus.VERIFIED
            return DafnyStatus.NOT_VERIFIED
        if "resolution/type errors detected in" in line:
            return DafnyStatus.ERROR
        if "parse errors detected in" in line:
            return DafnyStatus.ERROR
    return DafnyStatus.MEMORY_ERROR


def run_dafny_from_text(
    dafny_exec: Path,
    dafny_code: str,
    temp_folder: Path = TEMP_FOLDER,
    option: str = "verify",
) -> tuple[DafnyStatus, str, str]:
    """Run Dafny on code text via temp file. Returns (status, stdout, stderr)."""
    thread_dir = Path(tempfile.mkdtemp(prefix=f"dafny_thread_{os.getpid()}_"))
    temp_file = thread_dir / f"temp_{os.getpid()}_{threading.get_ident()}.dfy"

    try:
        temp_file.write_text(dafny_code, encoding="utf-8")
        cmd = build_dafny_command(dafny_exec, temp_file, option)
        _status, stdout, stderr = run_external_cmd(cmd, timeout=180)
        dafny_status = parse_dafny_output(stdout, stderr)
        return dafny_status, stdout, stderr
    finally:
        try:
            temp_file.unlink(missing_ok=True)
            shutil.rmtree(thread_dir, ignore_errors=True)
        except Exception:
            pass
