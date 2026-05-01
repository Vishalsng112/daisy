"""
Shared configuration for the Daisy codebase rewrite.

Contains:
- Shared paths (DAFNY_EXEC, dataset paths, results dirs)
- Shared prompts (BASE_PROMPT, LOCALIZATION_BASE_PROMPT, SYSTEM_PROMPT)
- Shared constants (ASSERTION_PLACEHOLDER, VERIFIER defaults)
- Enums for type-safe strategy selection (LocStrategy, ExampleStrategy, VerificationType)
- Per-concern config dataclasses (PositionInfererConfig, AssertionInfererConfig, VerificationConfig)
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import os


# ---------------------------------------------------------------------------
# Repo root discovery (same logic as src/utils/global_variables.py)
# ---------------------------------------------------------------------------

def find_repo_root(marker: str = ".repo_multi_assertions_marker") -> Path:
    """Find repo root by walking up from this file looking for marker."""
    current = Path(__file__).resolve().parent
    while str(current) != current.root:
        if (current / marker).exists():
            return current
        current = current.parent
    raise FileNotFoundError(
        "Could not find repository root. Make sure you're running inside a valid repo."
    )


BASE_PATH: Path = find_repo_root()

# ---------------------------------------------------------------------------
# Shared paths
# ---------------------------------------------------------------------------

TEMP_FOLDER: Path = BASE_PATH / "temp"
DAFNY_EXEC: Path = BASE_PATH / "external/dafny_fork/Binaries/Dafny"
DAFNY_MODIFIED_EXEC_FOR_ASSERTIONS: Path = DAFNY_EXEC

UNIT_TESTS_DIR: Path = BASE_PATH / "src/tests"
DAFNY_DATASET: Path = BASE_PATH / "external/DafnyBenchFork/DafnyBench/dataset/ground_truth"

DAFNY_BASE_ASSERTION_DATASET: Path = BASE_PATH / "dataset/dafny_assertion_all"
DAFNY_ASSERTION_DATASET: Path = BASE_PATH / "dataset/dafny_assertion_dataset"
DAFNY_ASSERTION_DATASET_TEST: Path = BASE_PATH / "dataset/dafny_assertion_dataset_test"

LLM_RESULTS_DIR: Path = BASE_PATH / "results/dafny_llm_results"
LLM_COSTS_DIR: Path = BASE_PATH / "results/costs"
LLM_RESULTS_DIR_TEST: Path = BASE_PATH / "results/dafny_llm_results_test"

PATH_TO_LAUREL: Path = BASE_PATH / "external/dafny_laurel_repair/laurel"

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

ASSERTION_PLACEHOLDER: str = "/*<Assertion is Missing Here>*/"

VERIFIER_TIME_LIMIT: int = 60  # seconds
VERIFIER_MAX_MEMORY: int = 24  # gigabytes

# ---------------------------------------------------------------------------
# Shared prompts (carried over verbatim from src/utils/global_variables.py)
# ---------------------------------------------------------------------------

BASE_PROMPT: str = """
Task:
For each location marked as needing assertions, return exactly 10 valid Dafny assertions that could fix the error at that point. 

Output:
- A JSON array of arrays, one inner array per missing assertion location.
- Each inner array must have exactly 10 strings, each string a valid Dafny assertion ending with a semicolon.
- Escape double quotes as \\".
- Do NOT output explanations, markdown, or any other text.

Examples:
# One missing position
[
  ["assert C;", "assert D;", "...", "assert J;"]
]

# Two missing positions
[
  ["assert A;", "assert B;", "...", "assert J;"],
  ["assert C;", "assert D;", "...", "assert L;"]
]
"""

LOCALIZATION_BASE_PROMPT: str = """
You are given a Dafny method with line numbers.
Return the line numbers AFTER which helper assertions should be inserted to fix verification errors.

FORMAT:
- JSON list only (e.g., [3], [5,7]).
- At least one number.
- Do NOT output any explanations.

RULES:
- Line numbers refer to the original program before insertions.
- Assertions are inserted independently after each listed line.
- Only insert inside the method body (between { and }).
- Never insert in signatures, requires, ensures or loop invariants
- The CODE section is your only source for line numbering. Disregard line numbers in the Error logs, as they do not match the local snippet.

INSERT EXAMPLE:

Original:
5: {
6: a := b;
7: c := d;
8: e := f;
9: }

Answer: [6,8]

Becomes:
5: {
6: a := b;
7: <assertion>
8: c := d;
9: e := f;
10: <assertion>
11: }

HEURISTICS (guidance, not mandatory):
These heuristics guide typical proof-repair behavior, but you may choose other valid placements 
- Failing assert → insert just before it.
- Postcondition/forall → near end of block.
- Loop invariant failures → end of loop body.
- Timeout/subset/domain → right before problematic stmt.
- Prefer after assignments, calls, swaps, updates.

Return ONLY the JSON list of line numbers.
"""

SYSTEM_PROMPT: str = """You are a dafny developer code expert"""

# ---------------------------------------------------------------------------
# Enums — type-safe strategy selection
# ---------------------------------------------------------------------------


class LocStrategy(Enum):
    """Position inference strategy."""
    ORACLE = "ORACLE"
    LLM = "LLM"
    LLM_EXAMPLE = "LLM_EXAMPLE"
    LAUREL = "LAUREL"
    LAUREL_BETTER = "LAUREL_BETTER"
    HYBRID = "HYBRID"


class ExampleStrategy(Enum):
    """Example retrieval strategy for prompt augmentation."""
    NONE = "NONE"
    RANDOM = "RANDOM"
    TFIDF = "TFIDF"
    EMBEDDED = "EMBEDDED"
    DYNAMIC = "DYNAMIC"


class VerificationType(Enum):
    """Verification strategy type."""
    PARALLEL_COMBO = "PARALLEL_COMBO"


# ---------------------------------------------------------------------------
# Per-concern config dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PositionInfererConfig:
    """Config for position inference stage."""
    system_prompt : str = SYSTEM_PROMPT
    localization_base_prompt: str = LOCALIZATION_BASE_PROMPT
    example_retrieval_type: ExampleStrategy = ExampleStrategy.NONE
    num_examples: int = 0
    example_weight: float = 0.5
    placeholder_text: str = ASSERTION_PLACEHOLDER


@dataclass
class AssertionInfererConfig:
    """Config for assertion inference stage."""
    base_prompt: str = BASE_PROMPT
    system_prompt: str = SYSTEM_PROMPT
    num_assertions_to_test: int = 10
    num_rounds: int = 1
    example_retrieval_type: ExampleStrategy = ExampleStrategy.NONE
    num_examples: int = 0
    example_weight: float = 0.5
    add_error_message: bool = True
    remove_empty_lines: bool = True
    filter_warnings: bool = True


@dataclass
class VerificationConfig:
    """Config for verification stage."""
    verification_type: VerificationType = VerificationType.PARALLEL_COMBO
    dafny_exec: Path = DAFNY_EXEC
    temp_dir: Path = TEMP_FOLDER
    skip_verification: bool = False
    parallel: bool = True
    stop_on_success: bool = True
    verifier_time_limit: int = VERIFIER_TIME_LIMIT
    verifier_max_memory: int = VERIFIER_MAX_MEMORY
    placeholder_text: str = ASSERTION_PLACEHOLDER


# ---------------------------------------------------------------------------
# Ensure temp folder exists
# ---------------------------------------------------------------------------

if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER, exist_ok=True)
