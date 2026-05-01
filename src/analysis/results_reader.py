"""Read cached localization, assertion, and verification results.

Mirrors the functionality of ``src/analysis/get_dataframe_from_results.py``
but uses the new abstractions and raises CacheMissError on missing entries.

Directory structure read:
    results/{model_name}/{prog_folder}/{group_id}/
        localization/localization_raw_response.txt
        assertions_list/assertions_parsed.json
        verification/Assertion_id_{id}/verif_stdout.txt
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from src.llm.parse_raw_response import parse_raw_response
from src.research_questions import CacheMissError


# ---------------------------------------------------------------------------
# Low-level file helpers
# ---------------------------------------------------------------------------

def _read_file(path: Path) -> Optional[str]:
    """Read text file, return None if missing."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _parse_localization(localization_file: Path) -> list[int]:
    """Parse cached localization response into list of ints."""
    raw = _read_file(localization_file)
    if raw is None:
        return []
    try:
        return parse_raw_response(raw)
    except Exception:
        return []


def parse_verification_output(verif_stdout_path: Path) -> dict[str, Any]:
    """Parse a single verification stdout file into a result dict.

    Returns dict with keys: verified, verification_errors, resolution_errors,
    parse_errors, time_out_errors, did_not_finish, verif_sucess.
    """
    text = _read_file(verif_stdout_path)
    if text is None:
        return {}

    result: dict[str, Any] = {
        "verified": 0,
        "verification_errors": 0,
        "resolution_errors": 0,
        "parse_errors": 0,
        "time_out_errors": 0,
        "did_not_finish": 1,
    }

    try:
        lines = text.splitlines()
    except Exception:
        return result

    for line in lines[-3:]:
        if "ERROR SKIPPED VERIFICATION" in line:
            result.update({"verification_errors": 1, "did_not_finish": 0})
            break
        if m := re.search(r"(\d+) verified, (\d+) errors, (\d+) time out", line):
            result.update({
                "verified": int(m.group(1)),
                "verification_errors": int(m.group(2)),
                "time_out_errors": int(m.group(3)),
                "did_not_finish": 0,
            })
            break
        if m := re.search(r"(\d+) verified, (\d+) error", line):
            result.update({
                "verified": int(m.group(1)),
                "verification_errors": int(m.group(2)),
                "did_not_finish": 0,
            })
            break
        if m := re.search(r"(\d+) resolution/type errors detected", line):
            result.update({"resolution_errors": int(m.group(1)), "did_not_finish": 0})
            break
        if m := re.search(r"(\d+) parse errors detected", line):
            result.update({"parse_errors": int(m.group(1)), "did_not_finish": 0})
            break

    result["verif_sucess"] = not any([
        result["verification_errors"],
        result["resolution_errors"],
        result["parse_errors"],
        result["time_out_errors"],
        result["did_not_finish"],
    ])
    return result


# ---------------------------------------------------------------------------
# ResultsReader — reads from the standard cache directory structure
# ---------------------------------------------------------------------------

class ResultsReader:
    """Read cached results from ``results/{model_name}/{prog_folder}/{group_id}/``.

    Raises CacheMissError when requested results are not cached.
    """

    def __init__(self, results_dir: Path):
        self.results_dir = results_dir

    def read_localization(self, model_name: str, prog_folder: str, group_id: str) -> list[int]:
        """Read cached localization positions.

        Raises CacheMissError if the localization file is missing.
        """
        loc_file = (
            self.results_dir / model_name / prog_folder / group_id
            / "localization" / "localization_raw_response.txt"
        )
        if not loc_file.exists():
            cache_key = f"{model_name}/{prog_folder}/{group_id}"
            raise CacheMissError(
                f"Missing localization cache for {cache_key}",
                missing_entries=[cache_key],
            )
        return _parse_localization(loc_file)

    def read_assertions(self, model_name: str, prog_folder: str, group_id: str) -> list[list[str]]:
        """Read cached assertion candidates.

        Raises CacheMissError if the assertions file is missing.
        """
        assert_file = (
            self.results_dir / model_name / prog_folder / group_id
            / "assertions_list" / "assertions_parsed.json"
        )
        if not assert_file.exists():
            cache_key = f"{model_name}/{prog_folder}/{group_id}"
            raise CacheMissError(
                f"Missing assertion cache for {cache_key}",
                missing_entries=[cache_key],
            )
        return json.loads(assert_file.read_text(encoding="utf-8"))

    def read_verification(
        self, model_name: str, prog_folder: str, group_id: str,
    ) -> list[dict[str, Any]]:
        """Read all verification results for a group.

        Returns list of parsed verification dicts (one per Assertion_id_* subdir).
        Raises CacheMissError if the verification directory is missing.
        """
        verif_dir = (
            self.results_dir / model_name / prog_folder / group_id / "verification"
        )
        if not verif_dir.exists():
            cache_key = f"{model_name}/{prog_folder}/{group_id}"
            raise CacheMissError(
                f"Missing verification cache for {cache_key}",
                missing_entries=[cache_key],
            )

        results: list[dict[str, Any]] = []
        for sub in sorted(verif_dir.iterdir()):
            if not sub.is_dir():
                continue
            stdout_file = sub / "verif_stdout.txt"
            parsed = parse_verification_output(stdout_file)
            if parsed:
                parsed["assertion_dir"] = sub.name
                results.append(parsed)
        return results

    def check_cache(
        self, model_name: str, prog_folder: str, group_id: str,
    ) -> dict[str, bool]:
        """Check which cache entries exist for a group."""
        base = self.results_dir / model_name / prog_folder / group_id
        return {
            "localization": (base / "localization" / "localization_raw_response.txt").exists(),
            "assertions": (base / "assertions_list" / "assertions_parsed.json").exists(),
            "verification": (base / "verification").exists(),
        }

    def check_all_cached(
        self,
        model_name: str,
        groups: list[tuple[str, str]],
    ) -> list[str]:
        """Return list of cache keys missing localization results.

        Args:
            model_name: The model directory name.
            groups: List of (prog_folder, group_id) tuples.

        Returns:
            List of ``prog_folder/group_id`` strings that lack cached localization.
        """
        missing: list[str] = []
        for prog_folder, group_id in groups:
            loc_file = (
                self.results_dir / model_name / prog_folder / group_id
                / "localization" / "localization_raw_response.txt"
            )
            if not loc_file.exists():
                missing.append(f"{prog_folder}/{group_id}")
        return missing


# ---------------------------------------------------------------------------
# DataFrame construction — mirrors get_dataframe_from_results.py
# ---------------------------------------------------------------------------

def retrieve_dataset_rows(dataset_dir: Path) -> list[dict[str, Any]]:
    """Read dataset metadata (oracle positions, syntactic valid lines, etc.).

    Walks ``dataset_dir/{prog_folder}/{group_id}/`` reading JSON metadata files.
    """
    rows: list[dict[str, Any]] = []
    pat1 = re.compile(r"method_start_(\d+)_as_start_(\d+)_end_(\d+)")
    pat2 = re.compile(
        r"method_start_(\d+)_as_start_(\d+)_end_(\d+)_as_start_(\d+)_end_(\d+)"
    )

    for prog_dir in sorted(dataset_dir.iterdir()):
        if not prog_dir.is_dir():
            continue

        # Identify w/o-1 groups
        wo1_names: dict[str, str] = {}
        wo1_methods: dict[int, list[tuple[int, int]]] = {}
        for grp_dir in prog_dir.iterdir():
            if not grp_dir.is_dir() or grp_dir.name in ("bin", "obj"):
                continue
            m = pat1.fullmatch(grp_dir.name)
            if m:
                ms, a_s, a_e = map(int, m.groups())
                wo1_names[grp_dir.name] = "w/o-1"
                wo1_methods.setdefault(ms, []).append((a_s, a_e))

        # Identify w/o-2 groups
        wo2_names: dict[str, str] = {}
        for grp_dir in prog_dir.iterdir():
            if not grp_dir.is_dir() or grp_dir.name in ("bin", "obj"):
                continue
            m = pat2.fullmatch(grp_dir.name)
            if m:
                wo2_names[grp_dir.name] = "w/o-2"

        # Build rows
        for grp_dir in sorted(prog_dir.iterdir()):
            if not grp_dir.is_dir() or grp_dir.name in ("bin", "obj"):
                continue
            row: dict[str, Any] = {"prog": prog_dir.name, "group": grp_dir.name}

            for fname, key in [
                ("all_lines_that_are_syntatic_valid.json", "all_syntatic_valid_lines"),
                ("all_lines_that_fix_file.json", "all_lines_where_oracle_fixes_file"),
                ("manual_assertions_type.json", "assertion_type"),
            ]:
                try:
                    with open(grp_dir / fname, "r", encoding="utf-8") as f:
                        row[key] = json.load(f)
                except Exception:
                    row[key] = []

            for fname, key in [
                ("laurel_LAURELassertion_position.txt", "laurel_pos"),
                ("laurel_LAUREL_BETTERassertion_position.txt", "laurel_better_pos"),
            ]:
                try:
                    with open(grp_dir / fname, "r", encoding="utf-8") as f:
                        row[key] = json.load(f)
                except Exception:
                    row[key] = []

            if grp_dir.name in wo1_names:
                row["benchmark"] = "w/o-1"
            elif grp_dir.name in wo2_names:
                row["benchmark"] = "w/o-2"
            else:
                row["benchmark"] = "w/o-all"

            rows.append(row)
    return rows


def retrieve_results_rows(results_dir: Path) -> list[dict[str, Any]]:
    """Walk ``results/{model}/{prog}/{group}/`` and collect all result rows.

    Each row contains: llm, prog, group, verif_exist, local_exist, localization,
    plus per-assertion verification stats.
    """
    rows: list[dict[str, Any]] = []

    for llm_dir in sorted(results_dir.iterdir()):
        if not llm_dir.is_dir():
            continue
        llm_name = llm_dir.name

        for prog_dir in sorted(llm_dir.iterdir()):
            if not prog_dir.is_dir():
                continue
            prog_name = prog_dir.name

            for grp_dir in sorted(prog_dir.iterdir()):
                if not grp_dir.is_dir():
                    continue
                group_name = grp_dir.name

                verif_root = grp_dir / "verification"
                loc_root = grp_dir / "localization"

                localization = _parse_localization(
                    loc_root / "localization_raw_response.txt"
                )

                base_row: dict[str, Any] = {
                    "llm": llm_name,
                    "prog": prog_name,
                    "group": group_name,
                    "verif_exist": verif_root.exists(),
                    "local_exist": loc_root.exists(),
                    "localization": localization,
                }

                if not verif_root.exists() or not localization:
                    rows.append(base_row.copy())
                    continue

                assertion_dirs = [
                    d for d in verif_root.iterdir() if d.is_dir()
                ]
                if not assertion_dirs:
                    rows.append(base_row.copy())
                    continue

                for adir in sorted(assertion_dirs):
                    parsed = parse_verification_output(adir / "verif_stdout.txt")
                    if parsed:
                        row = base_row.copy()
                        row.update(parsed)
                        rows.append(row)
                    else:
                        rows.append(base_row.copy())

    return rows


def merge_dataset_and_results(
    dataset_rows: list[dict[str, Any]],
    results_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join dataset and results rows on (prog, group)."""
    lookup = {(r["prog"], r["group"]): r for r in dataset_rows}
    merged: list[dict[str, Any]] = []
    for res in results_rows:
        key = (res["prog"], res["group"])
        if key in lookup:
            merged.append({**lookup[key], **res})
    return merged


def _oracle_here_would_fix(
    found_positions: list[int],
    all_options: list,
) -> bool:
    """Check if any found position appears in any oracle option."""
    # Normalize: if all_options is a flat list of ints, wrap it
    if all_options and isinstance(all_options[0], int):
        all_options = [all_options]
    valid = {pos for option in all_options for pos in option}
    return any(pos in valid for pos in found_positions)


def _assertion_here_syntactic_valid(
    found_positions: list[int],
    syntactic_positions: list[int],
) -> bool:
    """Check if any found position is syntactically valid."""
    valid = set(syntactic_positions)
    return any(pos in valid for pos in found_positions)


def build_analysis_dataframe(
    dataset_dir: Path,
    results_dir: Path,
) -> list[dict[str, Any]]:
    """Build expanded analysis rows from dataset + results.

    Mirrors ``get_pandas_dataset`` from the old codebase. Returns list of dicts
    ready for ``pd.DataFrame()``.
    """
    dataset_rows = retrieve_dataset_rows(dataset_dir)
    results_rows = retrieve_results_rows(results_dir)
    merged = merge_dataset_and_results(dataset_rows, results_rows)

    expanded: list[dict[str, Any]] = []
    for row in merged:
        all_options = row.get("all_lines_where_oracle_fixes_file", [])
        localization = row.get("localization", [])
        syntactic = row.get("all_syntatic_valid_lines", [])
        n_oracle = row.get("group", "").count("start") - 1
        n_found = len(localization)

        oracle_fix = _oracle_here_would_fix(localization, all_options)
        synt_valid = _assertion_here_syntactic_valid(localization, syntactic)

        new_row = dict(row)
        new_row.update({
            "number_oracle_assertions": n_oracle,
            "number_expected_assertions": n_found,
            "oracle_here_would_fix": oracle_fix,
            "assertion_here_syntatic_valid": synt_valid,
            "position_valid": oracle_fix,
            "position_partial": synt_valid and not oracle_fix,
            "position_invalid": not synt_valid,
            "position_no_pos": n_found == 0,
        })
        expanded.append(new_row)

    return expanded
