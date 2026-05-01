"""Parallel combo verification strategy.

Generates assertion combinations via zip_with_empty_indexed, tests each
against Dafny in parallel with early-stop on first verified combo.

No FileInfo/MethodInfo dependency — plain strings only.
"""

import os
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from src.config import VerificationConfig
from src.daisy.verification.base import VerificationResult, VerificationStrategy, register_verification_strategy
from src.utils.external_cmd import Status, run_external_cmd


def zip_with_empty_indexed(
    assertions: list[list[str]],
) -> tuple[list[list[str]], list[list[int]]]:
    """Generate assertion combinations from per-position candidate lists.

    Returns two parallel lists:
      1. Values — each row is one combo (one assertion per placeholder position).
         Zipped rows first, then individual leftovers padded with "".
      2. Indices — original index of each value, or -1 for padding.

    Copied from src/llm/llm_pipeline.py for behavioral equivalence.
    """
    n = len(assertions)
    if not assertions:
        return [], []

    min_len = min(map(len, assertions))

    # 1) Standard zip up to shortest list
    zipped_vals = [list(row) for row in zip(*(lst[:min_len] for lst in assertions))]
    zipped_inds = [[i] * n for i in range(min_len)]

    # 2) Leftover: each individual assertion paired with "" for other positions
    leftover_vals: list[list[str]] = []
    leftover_inds: list[list[int]] = []

    if n != 1:
        for list_idx, lst in enumerate(assertions):
            for item_idx, val in enumerate(lst):
                v_row = [val if i == list_idx else "" for i in range(n)]
                i_row = [item_idx if i == list_idx else -1 for i in range(n)]
                leftover_vals.append(v_row)
                leftover_inds.append(i_row)

    return zipped_vals + leftover_vals, zipped_inds + leftover_inds


@register_verification_strategy("PARALLEL_COMBO")
class ParallelComboVerification(VerificationStrategy):
    """Test assertion combos against Dafny in parallel, early-stop on first success.

    Args:
        config: VerificationConfig with dafny_exec, limits, placeholder_text, etc.
    """

    def __init__(self, config: VerificationConfig, **kwargs: Any):
        super().__init__(config, **kwargs)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def verify_assertions(
        self,
        full_file_text: str,
        method_text_with_placeholders: str,
        candidates: list[list[str]],
    ) -> VerificationResult:
        """Verify assertion candidates via parallel Dafny invocations.

        1. Generate combos from candidates
        2. For each combo: substitute placeholders, replace method in file, run Dafny
        3. Return on first verified combo (early-stop)
        """
        if not candidates:
            return VerificationResult(
                verified=False,
                total_tested=0,
                verified_count=0,
                corrected_method_text=None,
                corrected_file_text=None,
            )

        combos, _indices = zip_with_empty_indexed(candidates)

        if not combos:
            return VerificationResult(
                verified=False,
                total_tested=0,
                verified_count=0,
                corrected_method_text=None,
                corrected_file_text=None,
            )

        cancel_event = threading.Event()
        total_tested = 0
        verified_count = 0
        first_corrected_method: str | None = None
        first_corrected_file: str | None = None
        lock = threading.Lock()

        # If parallel is enabled, use ThreadPoolExecutor. Otherwise run sequentially.
        if self.config.parallel:
            with ThreadPoolExecutor() as executor:
                futures = {
                    executor.submit(
                        self._verify_single_combo,
                        full_file_text,
                        method_text_with_placeholders,
                        combo,
                        cancel_event,
                    ): combo
                    for combo in combos
                }

                for future in as_completed(futures):
                    try:
                        verified, method_fixed, file_fixed = future.result()
                    except Exception:
                        continue

                    with lock:
                        total_tested += 1
                        if verified:
                            verified_count += 1
                            if first_corrected_method is None:
                                first_corrected_method = method_fixed
                                first_corrected_file = file_fixed
                                # Only cancel if configured to stop on success
                                if getattr(self.config, "stop_on_success", True):
                                    cancel_event.set()
        else:
            # Sequential execution — iterate combos in order and stop early if configured
            for combo in combos:
                verified, method_fixed, file_fixed = self._verify_single_combo(
                    full_file_text, method_text_with_placeholders, combo, cancel_event
                )
                total_tested += 1
                if verified:
                    verified_count += 1
                    if first_corrected_method is None:
                        first_corrected_method = method_fixed
                        first_corrected_file = file_fixed
                        if getattr(self.config, "stop_on_success", True):
                            break

        return VerificationResult(
            verified=first_corrected_method is not None,
            total_tested=total_tested,
            verified_count=verified_count,
            corrected_method_text=first_corrected_method,
            corrected_file_text=first_corrected_file,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _verify_single_combo(
        self,
        full_file_text: str,
        method_text_with_placeholders: str,
        combo: list[str],
        cancel_event: threading.Event,
    ) -> tuple[bool, str, str]:
        """Verify one combo. Returns (verified, fixed_method, fixed_file).

        Checks cancel_event before expensive work; cleans temp files after.
        """
        if cancel_event.is_set():
            return (False, "", "")

        placeholder = self.config.placeholder_text

        # Substitute each placeholder occurrence with the corresponding assertion
        method_fixed = method_text_with_placeholders
        for assertion_text in combo:
            method_fixed = method_fixed.replace(placeholder, assertion_text, 1)

        # Replace original method in full file text
        file_fixed = full_file_text.replace(
            method_text_with_placeholders, method_fixed, 1
        )

        if cancel_event.is_set():
            return (False, "", "")

        # Write to temp file, run Dafny, clean up
        verified = self._run_dafny_on_text(file_fixed)
        return (verified, method_fixed, file_fixed)

    def _run_dafny_on_text(self, dafny_code: str) -> bool:
        """Write code to temp file, invoke Dafny verify, clean up. Returns True if verified."""
        thread_dir = tempfile.mkdtemp(prefix=f"dafny_combo_{os.getpid()}_")
        temp_file = Path(thread_dir) / f"temp_{os.getpid()}_{threading.get_ident()}.dfy"

        try:
            temp_file.write_text(dafny_code, encoding="utf-8")

            cmd = [
                str(self.config.dafny_exec),
                "verify",
                str(temp_file),
                "--cores",
                "1",
                "--verification-time-limit",
                str(self.config.verifier_time_limit),
                f"--solver-option:O:memory_max_size={self.config.verifier_max_memory * 1000}",
            ]

            timeout = self.config.verifier_time_limit + 30  # buffer beyond Dafny's own limit
            status, _stdout, _stderr = run_external_cmd(cmd, timeout=timeout)
            return status == Status.OK
        finally:
            # Always clean temp files
            try:
                temp_file.unlink(missing_ok=True)
                shutil.rmtree(thread_dir, ignore_errors=True)
            except Exception:
                pass
