"""RQ1: Best overall — evaluate different localization strategies.

Tests LLM, LAUREL, LAUREL_BETTER, HYBRID, ORACLE, and LLM_EXAMPLE
localization strategies with assertion inference and verification.

Three-phase pattern per (model, strategy) combo:
  1. Localization pass
  2. Assertion inference pass
  3. Verification pass

All results must be pre-cached; raises CacheMissError on miss.
"""

from __future__ import annotations

from pathlib import Path

from src_new.config import (
    DAFNY_ASSERTION_DATASET,
    LLM_RESULTS_DIR,
    ExampleStrategy,
    LocStrategy,
)
from src_new.llm.llm_create import create_llm
from src_new.research_questions.pipeline import run_strategy
from src_new.utils.dataset_class import Dataset

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """RQ1: Evaluate different localization strategies."""
    dataset = Dataset.from_dataset_assertion_groups(DAFNY_ASSERTION_DATASET)
    groups = dataset.get_all_assertion_groups()
    print(f"Loaded {len(groups)} assertion groups")

    results_dir = LLM_RESULTS_DIR
    dataset_path = DAFNY_ASSERTION_DATASET

    # --- Haiku with all localization strategies ---
    name = "claude-haiku-4.5"
    llm = create_llm(name, name)
    print(f"\n=== {name} ===")

    for loc in [
        LocStrategy.LAUREL,
        LocStrategy.LAUREL_BETTER,
        LocStrategy.ORACLE,
        LocStrategy.LLM,
    ]:
        print(f"\n--- {loc.value} ---")
        run_strategy(llm, loc, groups, results_dir, dataset_path,
                     assertion_strategy="LLM_EXAMPLE",
                     example_type=ExampleStrategy.DYNAMIC,
                     num_examples=3,
                     example_weight=0.25)

    # LLM_EXAMPLE with DYNAMIC examples
    print(f"\n--- LLM_EXAMPLE ---")
    run_strategy(
        llm, LocStrategy.LLM_EXAMPLE, groups, results_dir, dataset_path,
        assertion_strategy="LLM_EXAMPLE",
        example_type=ExampleStrategy.DYNAMIC,
        num_examples=3,
        example_weight=0.25,
        example_type_pos=ExampleStrategy.DYNAMIC,
        num_examples_pos=3,
        example_weight_pos=0.25,
    )

    # HYBRID with DYNAMIC examples
    print(f"\n--- HYBRID ---")
    run_strategy(
        llm, LocStrategy.HYBRID, groups, results_dir, dataset_path,
        assertion_strategy="LLM_EXAMPLE",
        example_type=ExampleStrategy.DYNAMIC,
        num_examples=3,
        example_weight=0.25,
        example_type_pos=ExampleStrategy.DYNAMIC,
        num_examples_pos=3,
        example_weight_pos=0.25,
    )

    # --- Opus with selected strategies ---
    name = "claude-opus-4.5"
    llm = create_llm(name, name)
    print(f"\n=== {name} ===")

    for loc in [LocStrategy.LAUREL_BETTER, LocStrategy.ORACLE]:
        print(f"\n--- {loc.value} ---")
        run_strategy(llm, loc, groups, results_dir, dataset_path,
                     assertion_strategy="LLM_EXAMPLE",
                     example_type=ExampleStrategy.DYNAMIC,
                     num_examples=3,
                     example_weight=0.25)

    print(f"\n--- LLM_EXAMPLE ---")
    run_strategy(
        llm, LocStrategy.LLM_EXAMPLE, groups, results_dir, dataset_path,
        assertion_strategy="LLM_EXAMPLE",
        example_type=ExampleStrategy.DYNAMIC,
        num_examples=3,
        example_weight=0.25,
        example_type_pos=ExampleStrategy.DYNAMIC,
        num_examples_pos=3,
        example_weight_pos=0.25,
    )

    print(f"\n--- HYBRID ---")
    run_strategy(
        llm, LocStrategy.HYBRID, groups, results_dir, dataset_path,
        assertion_strategy="LLM_EXAMPLE",
        example_type=ExampleStrategy.DYNAMIC,
        num_examples=3,
        example_weight=0.25,
        example_type_pos=ExampleStrategy.DYNAMIC,
        num_examples_pos=3,
        example_weight_pos=0.25,
    )


if __name__ == "__main__":
    main()
