#!/usr/bin/env python3
"""Single-file Dafny assertion repair CLI.

Usage:
    PYTHONPATH=src python src/single_file_run.py <path_to_code> [options]
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from llm.llm_configurations import MODEL_REGISTRY
from llm.extract_error_blocks import extract_error_blocks
from dafny.dafny_runner import run_dafny_from_text, Status


# ---------------------------------------------------------------------------
# Localization / example strategy choices (CLI-level, not enum)
# ---------------------------------------------------------------------------
# ORACLE is excluded: requires ground-truth positions from the dataset.
LOCALIZATION_CHOICES = ["LLM", "LLM_EXAMPLE", "LAUREL", "LAUREL_BETTER", "HYBRID", "NONE"]
EXAMPLE_CHOICES = ["NONE", "RANDOM", "TFIDF", "EMBEDDED", "DYNAMIC"]


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Dafny assertion-repair pipeline on a single .dfy file.",
    )

    parser.add_argument(
        "path_to_code",
        help="Path to the .dfy file to analyze.",
    )
    parser.add_argument(
        "--method",
        default=None,
        help="Method name to analyze. If omitted, the first failing method is selected.",
    )
    parser.add_argument(
        "--error-file",
        default=None,
        help="Pre-computed verifier error file. Skips initial verification when provided.",
    )
    parser.add_argument(
        "--localization",
        choices=LOCALIZATION_CHOICES,
        default="LLM",
        help="Localization strategy (default: LLM). ORACLE is not available in single-file mode.",
    )
    parser.add_argument(
        "--examples",
        choices=EXAMPLE_CHOICES,
        default="NONE",
        help="Example retrieval strategy (default: NONE).",
    )
    parser.add_argument(
        "--model",
        default="openrouter-free",
        help="Model name from MODEL_REGISTRY (default: openrouter-free).",
    )
    parser.add_argument(
        "--num-assertions",
        type=int,
        default=10,
        help="Number of assertion candidates per position (default: 10).",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Number of independent inference rounds (default: 1).",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Disable colored terminal output.",
    )

    return parser


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_model(model_name: str) -> None:
    """Exit with code 1 if *model_name* is not in MODEL_REGISTRY."""
    if model_name not in MODEL_REGISTRY:
        print(f"Error: unknown model '{model_name}'.")
        print("Valid model names:")
        for name in sorted(MODEL_REGISTRY):
            info = MODEL_REGISTRY[name]
            print(f"  {name:<30s} provider={info.provider}  model_id={info.model_id}")
        sys.exit(1)


def validate_file(path: str) -> None:
    """Exit with code 1 if *path* does not exist or is not readable."""
    if not os.path.isfile(path):
        print(f"Error: file not found: {path}")
        sys.exit(1)
    if not os.access(path, os.R_OK):
        print(f"Error: file is not readable: {path}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Color output helpers (Req 7.1–7.7)
# ---------------------------------------------------------------------------

_USE_COLOR: bool = True


def color(text: str, code: str) -> str:
    """Wrap *text* in ANSI escape *code* if color is enabled."""
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def header(text: str) -> str:
    """Bold cyan text for top-level headers."""
    return color(text, "1;36")


def success(text: str) -> str:
    """Green text for success messages."""
    return color(text, "32")


def error(text: str) -> str:
    """Red text for error messages."""
    return color(text, "31")


def warning(text: str) -> str:
    """Yellow text for warning messages."""
    return color(text, "33")


def section_header(title: str) -> str:
    """Return a formatted section divider like ``── Title ──``."""
    return header(f"── {title} ──")


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

# 3.3  Method extraction via asserttree

def extract_methods(dafny_exec: Path, code: str, temp_dir: Path) -> "FileInfo":
    """Run asserttree on *code* and return a populated FileInfo.

    Exits with code 1 on any failure (no XML output, unparseable XML,
    no methods found).
    """
    from dafny.dafny_runner import run_dafny_from_text
    from utils.dafny_read_assertions_xml import extract_assertion

    status, stdout, stderr = run_dafny_from_text(
        dafny_exec, code, temp_dir, option="asserttree",
    )

    # --- no XML produced ---
    xml_output = stdout.strip()
    if not xml_output:
        print(error("Error: asserttree produced no XML output."))
        if stderr.strip():
            print(stderr.strip())
        sys.exit(1)

    # --- write code to a temp file so FileSegment can read byte ranges ---
    tmp_file = Path(tempfile.mktemp(suffix=".dfy", dir=temp_dir))
    try:
        tmp_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file.write_text(code, encoding="utf-8")

        # --- parse XML ---
        try:
            file_info = extract_assertion(xml_output, tmp_file)
        except Exception as exc:
            print(error(f"Error: failed to parse asserttree XML: {exc}"))
            print("Raw output:")
            print(stdout)
            sys.exit(1)
    finally:
        tmp_file.unlink(missing_ok=True)

    # --- no methods ---
    if not file_info.methods:
        print(error("Error: no methods found in the file."))
        sys.exit(1)

    return file_info


# 3.4  Initial verification and method selection

def run_initial_verification(
    dafny_exec: Path,
    code: str,
    temp_dir: Path,
    error_file: str | None,
) -> tuple[str, str]:
    """Return (status_string, error_output).

    If *error_file* is provided the errors are read from disk and
    verification is skipped.  Otherwise Dafny is invoked with
    ``option="verify"``.

    Exits the process when:
    * the program already verifies  → exit 0
    * the verifier crashes / OOMs   → exit 1
    """
    if error_file is not None:
        # --error-file supplied: read pre-computed errors, skip verification
        try:
            with open(error_file, "r", encoding="utf-8") as fh:
                error_output = fh.read()
        except OSError as exc:
            print(error(f"Error: cannot read error file: {exc}"))
            sys.exit(1)
        return ("NOT_VERIFIED", error_output)

    status, stdout, stderr = run_dafny_from_text(
        dafny_exec, code, temp_dir, option="verify",
    )

    combined_output = stdout
    if stderr.strip():
        combined_output += "\n" + stderr

    if status == Status.VERIFIED:
        print(success("Program already verified — nothing to fix."))
        sys.exit(0)

    if status in (Status.ERROR, Status.MEMORY_ERROR):
        print(error(f"Verifier error (status={status.value}):"))
        print(combined_output.strip())
        sys.exit(1)

    # NOT_VERIFIED — the normal case: there are verification errors to fix
    return (status.value, combined_output)


def select_method(
    file_info: "FileInfo",
    method_name: str | None,
    error_output: str,
) -> "MethodInfo":
    """Pick the method to repair.

    If *method_name* is given, match by ``MethodInfo.method_name``.
    Otherwise parse *error_output* to find the first failing method.

    Exits with code 1 when no match is found.
    """
    methods = file_info.methods

    # --- explicit --method flag ---
    if method_name is not None:
        for m in methods:
            if m.method_name == method_name:
                return m
        print(error(f"Error: method '{method_name}' not found."))
        print("Available methods:")
        for m in methods:
            print(f"  {m.method_name}")
        sys.exit(1)

    # --- heuristic: first method name that appears in an error line ---
    method_names = {m.method_name: m for m in methods}
    for line in error_output.splitlines():
        for name, m in method_names.items():
            if name and name in line:
                return m

    # Fallback: just pick the first method
    if methods:
        return methods[0]

    print(error("Error: could not determine a failing method from verifier output."))
    sys.exit(1)


# 3.5  Localization dispatch

def _run_laurel_localization(
    method_text: str,
    method_name: str,
    error_output: str,
    code: str,
    temp_dir: Path,
    use_laurel_better: bool,
) -> str:
    """Call the LAUREL/LAUREL_BETTER C# placeholder finder and return
    method text with ``/*<Assertion is Missing Here>*/`` placeholders.
    """
    import sys
    import utils.global_variables as gl

    sys.path.append(str(gl.PATH_TO_LAUREL))
    from placeholder_wrapper import call_placeholder_finder

    # Write the full program to a temp file (placeholder_finder needs a file path)
    tmp_file = Path(tempfile.mktemp(suffix=".dfy", dir=temp_dir))
    try:
        tmp_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file.write_text(code, encoding="utf-8")

        # LAUREL expects the short method name (e.g. "BinarySearch"),
        # not the fully qualified "_module._default.BinarySearch".
        short_name = method_name.split(".")[-1]

        result, err = call_placeholder_finder(
            error_output,
            str(tmp_file),
            short_name,
            use_laurel_better=use_laurel_better,
        )
    finally:
        tmp_file.unlink(missing_ok=True)

    if err:
        print(warning(f"LAUREL error: {err}"))

    if not result:
        print(error("Error: LAUREL produced no output."))
        sys.exit(1)

    # Replace LAUREL's XML placeholders with the codebase placeholder string
    laurel_placeholder = "<assertion> Insert assertion here </assertion>"
    assertion_placeholder = "/*<Assertion is Missing Here>*/"
    localized = result.replace(laurel_placeholder, assertion_placeholder)
    return localized


def _extract_placeholder_line_numbers(method_text: str) -> list[int]:
    """Return 0-based line numbers where the assertion placeholder appears."""
    placeholder = "/*<Assertion is Missing Here>*/"
    return [
        i for i, line in enumerate(method_text.splitlines())
        if placeholder in line
    ]


def run_localization(
    strategy: str,
    method_text: str,
    method_name: str,
    error_output: str,
    llm,
    run_options,
    dafny_exec: Path,
    code: str,
    temp_dir: Path,
) -> str:
    """Dispatch localization and return method text with placeholders inserted.

    Exits with code 1 for unsupported strategies or when NONE has no
    pre-existing placeholders.
    """
    from llm.llm_pipeline import run_llm_get_localization, get_method_with_assertions_placeholder

    assertion_placeholder = "/*<Assertion is Missing Here>*/"

    if strategy in ("LLM", "LLM_EXAMPLE"):
        # LLM-based localization
        _prompt, _raw, localized_text = run_llm_get_localization(
            method_text, error_output, llm, run_options, "", "",
        )

    elif strategy in ("LAUREL", "LAUREL_BETTER"):
        use_better = (strategy == "LAUREL_BETTER")
        localized_text = _run_laurel_localization(
            method_text, method_name, error_output, code, temp_dir, use_better,
        )

    elif strategy == "HYBRID":
        # Static (LAUREL_BETTER) first
        laurel_text = _run_laurel_localization(
            method_text, method_name, error_output, code, temp_dir,
            use_laurel_better=True,
        )
        laurel_positions = _extract_placeholder_line_numbers(laurel_text)

        # LLM localization on the *original* method text (no placeholders yet)
        _prompt, _raw, llm_text = run_llm_get_localization(
            method_text, error_output, llm, run_options, "", "",
        )
        llm_positions = _extract_placeholder_line_numbers(llm_text)

        # Merge: LAUREL_BETTER first, then LLM positions not already present
        merged = laurel_positions + [p for p in llm_positions if p not in laurel_positions]

        # Re-insert placeholders at merged positions on the original method text
        localized_text = get_method_with_assertions_placeholder(
            method_text, merged, assertion_placeholder,
        )

    elif strategy == "NONE":
        if assertion_placeholder in method_text:
            localized_text = method_text
        else:
            print(error(
                "Error: --localization NONE requires the method to already contain "
                "'/*<Assertion is Missing Here>*/' placeholders."
            ))
            print("Place the placeholder manually or choose a localization strategy.")
            sys.exit(1)

    elif strategy == "ORACLE":
        print(error(
            "Error: ORACLE localization is not supported in single-file mode "
            "(requires ground-truth positions from dataset)."
        ))
        sys.exit(1)

    else:
        print(error(f"Error: unknown localization strategy '{strategy}'."))
        sys.exit(1)

    # Display predicted line numbers
    positions = _extract_placeholder_line_numbers(localized_text)
    print(section_header("Localization"))
    print(f"Strategy: {strategy}")
    print(f"Predicted lines: {positions}")

    return localized_text


# 3.6  Assertion inference and verification loop


def build_run_options(args) -> "RunOptions":
    """Create a RunOptions from CLI args with sensible defaults."""
    from llm.llm_pipeline import RunOptions, LocStrategies, ExampleStrategies
    import utils.global_variables as gl

    loc_map = {name: member for name, member in LocStrategies.__members__.items()}
    ex_map = {name: member for name, member in ExampleStrategies.__members__.items()}

    # Map CLI string to enum; NONE localization is CLI-only, default to LLM for RunOptions
    loc_strategy = loc_map.get(args.localization, LocStrategies.LLM)
    ex_strategy = ex_map.get(args.examples, ExampleStrategies.NONE)

    return RunOptions(
        number_assertions_to_test=args.num_assertions,
        number_rounds=args.rounds,
        number_retries_chain=0,
        add_error_message=True,
        skip_verification=False,
        remove_empty_lines=True,
        change_assertion_per_text=gl.ASSERTION_PLACEHOLDER,
        base_prompt=gl.BASE_PROMPT,
        localization_base_prompt=gl.LOCALIZATION_BASE_PROMPT,
        examples_to_augment_prompt_type=ex_strategy,
        number_examples_to_add=0,
        limit_example_length_bytes=4096,
        verifier_output_filter_warnings=True,
        system_prompt=gl.SYSTEM_PROMPT,
        localization=loc_strategy,
        only_verify=False,
        only_get_location=False,
        only_get_assert_candidate=False,
        skip_original_verification=False,
        examples_weight_of_error_message=0.5,
        examples_to_augment_prompt_type_pos=ex_strategy,
        examples_weight_of_error_message_pos=0.5,
        number_examples_to_add_pos=0,
    )


def verify_single_combo(
    localized_method_text: str,
    combo: list[str],
    placeholder: str,
    file_info: "FileInfo",
    method: "MethodInfo",
    dafny_exec: Path,
    temp_dir: Path,
    cancel_event: threading.Event | None = None,
) -> tuple[bool, str]:
    """Verify one assertion combo. Returns (verified, fixed_method_text).

    If cancel_event is set before Dafny runs, returns (False, "") early.
    """
    if cancel_event and cancel_event.is_set():
        return (False, "")

    method_fixed = localized_method_text
    for assertion_text in combo:
        method_fixed = method_fixed.replace(placeholder, assertion_text, 1)

    _, fixed_file = file_info.substitute_method_with_text(method, method_fixed)

    if cancel_event and cancel_event.is_set():
        return (False, "")

    status, _, _ = run_dafny_from_text(dafny_exec, fixed_file, temp_dir)
    verified = (status == Status.VERIFIED)
    return (verified, method_fixed)


def run_inference_and_verify(
    localized_method_text: str,
    file_info: "FileInfo",
    method: "MethodInfo",
    error_output: str,
    llm,
    run_options: "RunOptions",
    dafny_exec: Path,
    code: str,
    temp_dir: Path,
) -> tuple[int, int, str | None]:
    """Run assertion inference then verify each candidate combination.

    Returns (total_tested, verified_count, corrected_method_text_or_None).
    """
    from llm.llm_pipeline import (
        get_base_prompt,
        run_llm_get_assertions,
        zip_with_empty_indexed,
    )
    from llm.parse_raw_response import parse_raw_response

    placeholder = "/*<Assertion is Missing Here>*/"

    # --- Early exit if no placeholders to fill ---
    if placeholder not in localized_method_text:
        print(section_header("Assertion Inference"))
        print(warning("No assertion placeholders found after localization — nothing to infer."))
        print(warning("No fix found."))
        return (0, 0, None)

    # --- Build prompt and get assertion candidates ---
    system_prompt = run_options.base_prompt
    prompt = get_base_prompt(
        system_prompt, localized_method_text, error_output,
        run_options, "", "",
    )

    raw_response, response_assertions, _chat = run_llm_get_assertions(prompt, llm)

    # --- Graceful JSON fallback (Req 9.2) ---
    # run_llm_get_assertions already catches parse errors internally,
    # but it falls back to [["FAILED_RECEIVING_JSON_BAD_FORMATTED_JSON"]].
    # We re-parse here to give a cleaner fallback with a warning.
    bad_marker = "FAILED_RECEIVING_JSON_BAD_FORMATTED_JSON"
    if (
        len(response_assertions) == 1
        and len(response_assertions[0]) == 1
        and response_assertions[0][0] == bad_marker
    ):
        print(warning("Warning: LLM returned malformed JSON. Raw response:"))
        print(raw_response[:500])
        response_assertions = []

    # --- Display candidates (Req 7.4) ---
    num_positions = len(response_assertions)
    print(section_header("Assertion Inference"))
    if not response_assertions:
        print("No assertion candidates received.")
    else:
        per_pos = max(len(pos) for pos in response_assertions) if response_assertions else 0
        print(f"Candidates ({per_pos} per position, {num_positions} positions):")
        for i, pos_assertions in enumerate(response_assertions):
            display = pos_assertions[:5]
            suffix = f", ... ({len(pos_assertions)} total)" if len(pos_assertions) > 5 else ""
            print(f"  Position {i + 1}: {display}{suffix}")

    # --- Verification loop (Req 7.5) ---
    if not response_assertions:
        print(section_header("Verification"))
        print("Tested 0 combinations, 0 verified")
        print(warning("No fix found."))
        return (0, 0, None)

    combos, _indices = zip_with_empty_indexed(response_assertions)

    cancel_event = threading.Event()
    total_tested = 0
    verified_count = 0
    first_corrected_text = None

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(
                verify_single_combo,
                localized_method_text, combo, placeholder,
                file_info, method, dafny_exec, temp_dir, cancel_event,
            ): combo
            for combo in combos
        }

        for future in as_completed(futures):
            try:
                verified, method_fixed = future.result()
            except Exception as exc:
                print(warning(f"Verification error: {exc}"))
                continue

            total_tested += 1
            if verified:
                verified_count += 1
                if first_corrected_text is None:
                    first_corrected_text = method_fixed
                    cancel_event.set()  # signal others to stop

    # --- Display results (Req 7.5, 7.6, 7.7) ---
    print(section_header("Verification"))
    if verified_count > 0:
        print(success(f"Tested {total_tested} combinations, {verified_count} verified ✓"))
    else:
        print(f"Tested {total_tested} combinations, {verified_count} verified")

    if first_corrected_text is not None:
        print(section_header("Corrected Method"))
        print(first_corrected_text)
    else:
        print(warning("No fix found."))

    return (total_tested, verified_count, first_corrected_text)


# ---------------------------------------------------------------------------
# Main — wires all stages together (3.7)
# ---------------------------------------------------------------------------

def main() -> None:
    global _USE_COLOR
    parser = build_parser()
    args = parser.parse_args()

    _USE_COLOR = not args.no_color

    # --- Validations (Req 4.6, 5.5) ---
    validate_model(args.model)
    validate_file(args.path_to_code)

    # --- Banner (Req 7.1) ---
    model_info = MODEL_REGISTRY[args.model]
    print(header("═══ Dafny Assertion Repair ═══"))
    print(f"File:  {args.path_to_code}")
    print(f"Model: {args.model} ({model_info.model_id})")
    print()

    # --- Read source code ---
    code = Path(args.path_to_code).read_text(encoding="utf-8")

    # --- Create LLM ---
    from llm.llm_create import create_llm
    llm = create_llm("llm", args.model)

    # --- Temp dir ---
    temp_dir = Path(tempfile.mkdtemp(prefix="dafny_repair_"))

    # --- Dafny executable ---
    import utils.global_variables as gl
    dafny_exec = gl.DAFNY_EXEC

    # --- Extract methods via asserttree (Req 4.3, 4.5) ---
    file_info = extract_methods(dafny_exec, code, temp_dir)

    # --- Initial verification (Req 4.2, 4.7, 4.8) ---
    status_str, error_output = run_initial_verification(
        dafny_exec, code, temp_dir, args.error_file,
    )

    # --- Display verification errors (Req 7.1) ---
    print(section_header("Verification"))
    print(f"Status: {status_str}")
    filtered = extract_error_blocks(error_output)
    if filtered.strip():
        print("Errors:")
        for line in filtered.strip().splitlines():
            print(f"  {line}")
    print()

    # --- Select method (Req 4.4) ---
    method = select_method(file_info, args.method, error_output)
    method_text = method.segment_str
    print(f"Selected method: {method.method_name}")
    print()

    # --- Build run options ---
    run_options = build_run_options(args)

    # --- Localization (Req 5.1) ---
    localized_text = run_localization(
        args.localization,
        method_text,
        method.method_name,
        error_output,
        llm,
        run_options,
        dafny_exec,
        code,
        temp_dir,
    )
    print()

    # --- Assertion inference and verification loop (Req 7.3-7.7) ---
    _total, _verified, _corrected = run_inference_and_verify(
        localized_text,
        file_info,
        method,
        error_output,
        llm,
        run_options,
        dafny_exec,
        code,
        temp_dir,
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
