#!/usr/bin/env python3
"""Single-file Dafny assertion repair CLI.

Usage:
    python -m src_new.cli <path_to_code.dfy> --model <model> --localization LLM
"""

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from src_new.config import (
    ASSERTION_PLACEHOLDER,
    BASE_PATH,
    DAFNY_EXEC,
    ExampleStrategy,
    AssertionInfererConfig,
    PositionInfererConfig,
    VerificationConfig,
)
from src_new.llm.llm_configurations import MODEL_REGISTRY
from src_new.llm.llm_create import create_llm
from src_new.llm.extract_error_blocks import extract_error_blocks
from src_new.utils.external_cmd import Status, run_external_cmd

# Import packages to trigger @register decorators, then grab registries
from src_new.daisy import position_inference as _pos_mod  # noqa: F401
from src_new.daisy import assertion_inference as _assert_mod  # noqa: F401
from src_new.daisy import verification as _verif_mod  # noqa: F401

from src_new.daisy.position_inference.base import POSITION_REGISTRY
from src_new.daisy.assertion_inference.base import ASSERTION_REGISTRY
from src_new.daisy.verification.base import VERIFICATION_REGISTRY

# CLI-available localization choices: everything registered except ORACLE + add NONE
LOCALIZATION_CHOICES = [k for k in POSITION_REGISTRY if k != "ORACLE"] + ["NONE"]
ASSERTION_CHOICES = [k for k in ASSERTION_REGISTRY if k != "ORACLE"]
VERIFICATION_CHOICES = list(VERIFICATION_REGISTRY.keys())

EXAMPLE_STRATEGY = [ k.value for k in ExampleStrategy]

CLI_RESULTS_DIR: Path = BASE_PATH / "results" / "cli_runs"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
#   example_retrieval_type:
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Dafny assertion-repair pipeline.")
    p.add_argument("file", help="Path to .dfy file.")
    p.add_argument("--localization", choices=LOCALIZATION_CHOICES, default="LLM")
    p.add_argument("--assertion", choices=ASSERTION_CHOICES, default="LLM")
    p.add_argument("--model", default="openrouter-free")
    p.add_argument("--num-assertions", type=int, default=10)
    p.add_argument("--n-examples-pos", type=int, default=0)
    p.add_argument("--n-examples-inf", type=int, default=0)
    p.add_argument("--s-examples-pos", choices=EXAMPLE_STRATEGY, default="NONE")
    p.add_argument("--s-examples-inf", choices=EXAMPLE_STRATEGY, default="NONE")
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--no-color", action="store_true", default=False)
    return p


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_USE_COLOR: bool = True

def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

def _ok(t: str) -> str: return _c(t, "32")
def _err(t: str) -> str: return _c(t, "31")
def _warn(t: str) -> str: return _c(t, "33")
def _hdr(t: str) -> str: return _c(t, "1;36")
def _dim(t: str) -> str: return _c(t, "2")
def _sec(t: str) -> str: return _hdr(f"── {t} ──")

def _die(msg: str, code: int = 1) -> None:
    print(_err(msg))
    sys.exit(code)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_file(path: str) -> None:
    if not Path(path).is_file():
        _die(f"Error: file not found: {path}")


def validate_model(model_name: str) -> None:
    if model_name not in MODEL_REGISTRY:
        print(_err(f"Error: unknown model '{model_name}'."))
        print("Valid models:")
        for n in sorted(MODEL_REGISTRY):
            i = MODEL_REGISTRY[n]
            print(f"  {n:<30s} provider={i.provider.name}  model_id={i.model_id}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Cache dir helpers
# ---------------------------------------------------------------------------

def _create_run_cache_dir(source_file: str, model: str) -> Path:
    """Create a fresh cache dir for this CLI run under results/cli_runs/.

    Structure: results/cli_runs/<timestamp>_<filename>_<model>/
    Cleans any previous run with the same file+model combo.
    """
    file_stem = Path(source_file).stem
    if CLI_RESULTS_DIR.exists():
        for d in CLI_RESULTS_DIR.iterdir():
            if d.is_dir() and d.name.endswith(f"_{file_stem}_{model}"):
                shutil.rmtree(d, ignore_errors=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = CLI_RESULTS_DIR / f"{timestamp}_{file_stem}_{model}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _save_artifact(run_dir: Path, name: str, content: str) -> None:
    """Save a text artifact to the run cache dir."""
    path = run_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Dafny helpers
# ---------------------------------------------------------------------------

def _run_dafny(dafny_exec: Path, code: str, temp_dir: Path, option: str = "verify"):
    """Write code to temp, run dafny <option>, return (status, stdout, stderr)."""
    tmp = Path(tempfile.mktemp(suffix=".dfy", dir=str(temp_dir)))
    tmp.write_text(code, encoding="utf-8")
    try:
        cmd = [str(dafny_exec), option, str(tmp), "--cores", "1"]
        if option == "verify":
            cmd += ["--verification-time-limit", "60",
                     "--solver-option:O:memory_max_size=24000"]
        return run_external_cmd(cmd, timeout=120)
    finally:
        tmp.unlink(missing_ok=True)


def _parse_dafny_status(stdout: str, stderr: str) -> str:
    for line in stdout.splitlines():
        if "Dafny program verifier finished" in line:
            if "time out" in line: return "ERROR"
            if "0 errors" in line: return "VERIFIED"
            return "NOT_VERIFIED"
        if "resolution/type errors detected in" in line: return "ERROR"
        if "parse errors detected in" in line: return "ERROR"
    return "MEMORY_ERROR"


def extract_methods(dafny_exec: Path, code: str, temp_dir: Path, source_file: Path):
    from src_new.utils.dafny_read_assertions_xml import extract_assertion
    status, stdout, stderr = _run_dafny(dafny_exec, code, temp_dir, "asserttree")
    if not stdout.strip():
        _die(f"Error: asserttree produced no output.\n{stderr.strip()}")
    try:
        fi = extract_assertion(stdout.strip(), source_file)
    except Exception as e:
        _die(f"Error: failed to parse asserttree XML: {e}")
    if not fi.methods:
        _die("Error: no methods found in the file.")
    return fi


def run_initial_verification(dafny_exec: Path, code: str, temp_dir: Path) -> tuple[str, str]:
    status, stdout, stderr = _run_dafny(dafny_exec, code, temp_dir)
    combined = stdout + ("\n" + stderr if stderr.strip() else "")
    ds = _parse_dafny_status(stdout, stderr)
    if ds == "VERIFIED":
        print(_ok("Program already verified — nothing to fix."))
        sys.exit(0)
    if ds in ("ERROR", "MEMORY_ERROR"):
        _die(f"Verifier error (status={ds}):\n{combined.strip()}")
    return ds, combined


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def select_method(file_info, error_output: str):
    for line in error_output.splitlines():
        for m in file_info.methods:
            if m.method_name and m.method_name in line:
                return m
    if file_info.methods:
        return file_info.methods[0]
    _die("Error: could not determine a failing method.")


def insert_placeholders(method_text: str, positions: list[int], placeholder: str) -> str:
    lines = method_text.splitlines()
    result: list[str] = []
    for idx, line in enumerate(lines):
        result.append(line)
        if idx in positions:
            result.append(placeholder)
    return "\n".join(result)


def create_position_inferer(strategy: str, llm, pos_config: PositionInfererConfig, cache_dir: Path | None = None):
    """Create a position inferer from the registry.

    HYBRID is special-cased because it composes two sub-inferers.
    All other strategies are instantiated directly from the registry.
    """
    cls = POSITION_REGISTRY.get(strategy)
    if cls is None:
        return None

    # HYBRID needs two sub-inferers composed together
    if strategy == "HYBRID":
        laurel_cls = POSITION_REGISTRY["LAUREL_BETTER"]
        llm_cls = POSITION_REGISTRY["LLM"]
        return cls(
            laurel_better_inferer=laurel_cls(config=pos_config, cache_dir=cache_dir),
            llm_inferer=llm_cls(llm=llm, config=pos_config, cache_dir=cache_dir),
            cache_dir=cache_dir,
        )

    # Strategies that need an LLM
    if strategy in ("LLM", "LLM_EXAMPLE"):
        return cls(llm=llm, config=pos_config, cache_dir=cache_dir)

    # LAUREL / LAUREL_BETTER — no LLM needed
    return cls(config=pos_config, cache_dir=cache_dir)


def create_assertion_inferer(strategy: str, llm, assertion_config: AssertionInfererConfig, cache_dir: Path | None = None):
    """Create a assertion inferer from the registry.
    """
    cls = ASSERTION_REGISTRY.get(strategy)
    if cls is None:
        return None

    if strategy in ("LLM", "LLM_EXAMPLE"):
        return cls(llm=llm, config=assertion_config, cache_dir=cache_dir)

    return None

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _display_candidates(candidates: list[list[str]]) -> None:
    """Print assertion candidates summary."""
    if not candidates:
        print("  No assertion candidates received.")
        return
    num_positions = len(candidates)
    per_pos = max(len(pos) for pos in candidates)
    print(f"  Candidates: {per_pos} per position, {num_positions} position(s)")
    for i, pos_assertions in enumerate(candidates):
        preview = pos_assertions[:3]
        preview_strs = [repr(a) for a in preview]
        suffix = f" ... ({len(pos_assertions)} total)" if len(pos_assertions) > 3 else ""
        print(f"    Position {i + 1}: [{', '.join(preview_strs)}{suffix}]")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    global _USE_COLOR
    args = build_parser().parse_args(argv)
    _USE_COLOR = not args.no_color

    validate_file(args.file)
    validate_model(args.model)

    model_info = MODEL_REGISTRY[args.model]
    code = Path(args.file).read_text(encoding="utf-8")
    llm = create_llm("llm", args.model)
    temp_dir = Path(tempfile.mkdtemp(prefix="dafny_repair_"))
    placeholder = ASSERTION_PLACEHOLDER

    # Create run cache dir (clean previous runs for same file+model)
    run_dir = _create_run_cache_dir(args.file, args.model)

    # ── Banner ──
    print(_hdr("═══ Dafny Assertion Repair ═══"))
    print(f"  File:          {args.file}")
    print(f"  Model:         {args.model} ({model_info.model_id})")
    print(f"  Localization:  {args.localization}")
    print(f"  Assert Infer:  {args.assertion}")
    print(f"  Assertions:    {args.num_assertions} per position, {args.rounds} round(s)")
    print(f"  N Example (Pos, Inf): ({args.n_examples_pos}, {args.n_examples_inf})")

    print()

    try:
        # ── Extract methods ──
        file_info = extract_methods(DAFNY_EXEC, code, temp_dir, Path(args.file))
        try:
            _save_artifact(run_dir, "methods.txt",
                           "\n".join(str(m.method_name) for m in file_info.methods))
        except Exception:
            pass  # non-critical artifact save

        # ── Initial verification ──
        status_str, error_output = run_initial_verification(DAFNY_EXEC, code, temp_dir)

        print(_sec("Verification"))
        print(f"  Status: {_warn(status_str)}")
        filtered_errors = extract_error_blocks(error_output)
        if filtered_errors.strip():
            print("  Errors:")
            for line in filtered_errors.strip().splitlines():
                print(f"    {line}")
        print()

        _save_artifact(run_dir, "verification_errors.txt", error_output)

        # ── Method selection ──
        method = select_method(file_info, error_output)
        method_text = method.segment_str

        print(f"  Selected method: {_hdr(method.method_name)}")
        print()

        _save_artifact(run_dir, "selected_method.txt", method_text)

        # ── Position inference (localization) ──
        print(_sec("Localization"))
        print(f"  Strategy: {args.localization}")

        if args.localization == "NONE":
            if placeholder not in method_text:
                _die("Error: --localization NONE requires existing placeholders.")
            localized_text = method_text
            positions: list[int] = []
        else:
            pos_inferer = create_position_inferer(
                args.localization, llm, 
                    PositionInfererConfig(
                        num_examples=args.n_examples_pos,
                        example_retrieval_type=args.s_examples_pos
                    ), 
                    cache_dir=run_dir)
            if pos_inferer is None:
                _die(f"Error: unsupported localization '{args.localization}'.")
            extra = {}
            if args.localization in ("LAUREL", "LAUREL_BETTER", "HYBRID"):
                extra = {"method_name": method.method_name.split(".")[-1], "program_text": code}
            positions = pos_inferer.infer_positions(method_text, error_output, **extra)
            localized_text = insert_placeholders(method_text, positions, placeholder)

        print(f"  Predicted lines: {positions}")
        print()

        _save_artifact(run_dir, "localization_positions.json", json.dumps(positions))
        _save_artifact(run_dir, "method_with_placeholders.txt", localized_text)

        if placeholder not in localized_text:
            _die("No assertion placeholders after localization — no fix found.")

        # ── Assertion inference ──
        print(_sec("Assertion Inference"))
        print(f"  Strategy: {args.assertion}")


        assert_inferer = create_assertion_inferer(args.assertion, llm, 
                                                AssertionInfererConfig(
                                                    num_assertions_to_test=args.num_assertions, 
                                                    num_rounds=args.rounds,
                                                    num_examples=args.n_examples_inf,
                                                    example_retrieval_type=args.s_examples_inf
                                                ), 
                                                cache_dir = run_dir)
        if assert_inferer is None:
            _die(f"Error: unsupported assertion '{args.assertion}'.")

        candidates = assert_inferer.infer_assertions(localized_text, error_output)

        _display_candidates(candidates)
        print()

        if not candidates:
            _die("No assertion candidates — no fix found.")

        # ── Verification ──
        print(_sec("Verification"))

        verif_cls = VERIFICATION_REGISTRY["PARALLEL_COMBO"]
        verifier = verif_cls(config=VerificationConfig())
        full_file = code.replace(method_text, localized_text, 1)
        result = verifier.verify_assertions(full_file, localized_text, candidates)

        if result.verified:
            print(_ok(f"  Tested {result.total_tested} combinations, "
                       f"{result.verified_count} verified ✓"))
            print()
            print(_sec("Corrected Method"))
            print(result.corrected_method_text)

            _save_artifact(run_dir, "corrected_method.txt", result.corrected_method_text or "")
            if result.corrected_file_text:
                _save_artifact(run_dir, "corrected_file.dfy", result.corrected_file_text)

            print()
            print(_dim(f"Full artifacts saved at: {run_dir}"))
            sys.exit(0)
        else:
            print(f"  Tested {result.total_tested} combinations, 0 verified")
            print()
            print(_dim(f"Full artifacts saved at: {run_dir}"))
            _die("No fix found.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
