"""RQ3: Example retrieval — evaluate assertion inference with different example strategies.

Uses ORACLE localization (fixed) and varies the example retrieval strategy
for assertion inference: NONE, RANDOM, EMBEDDED, TFIDF, DYNAMIC (multiple weights).

Three-phase pattern per (model, example_strategy) combo:
  1. Localization pass
  2. Assertion inference pass
  3. Verification pass

All results must be pre-cached; raises CacheMissError on miss.
"""

from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import (
    DAFNY_ASSERTION_DATASET,
    LLM_RESULTS_DIR,
    ExampleStrategy,
    LocStrategy,
)
from src.llm.llm_create import create_llm
from src.research_questions.pipeline import run_strategy
from src.utils.dataset_class import Dataset


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """RQ3: Evaluate example retrieval strategies for assertion inference."""
    dataset = Dataset.from_dataset_assertion_groups(DAFNY_ASSERTION_DATASET)
    groups = dataset.get_all_assertion_groups()
    print(f"Loaded {len(groups)} assertion groups")

    results_dir = LLM_RESULTS_DIR
    dataset_path = DAFNY_ASSERTION_DATASET
    loc = LocStrategy.ORACLE

    # --- Haiku ---
    name = "claude-haiku-4.5"
    llm = create_llm(name, name)
    print(f"\n=== {name} ===")

    # NONE
    print("\n--- NONE ---")
    run_strategy(
        llm, loc, groups, results_dir, dataset_path,
        example_type=ExampleStrategy.NONE,
        num_examples=0,
    )

    # RANDOM
    print("\n--- RANDOM ---")
    run_strategy(
        llm, loc, groups, results_dir, dataset_path,
        assertion_strategy="LLM_EXAMPLE",
        example_type=ExampleStrategy.RANDOM,
        num_examples=3,
    )

    # EMBEDDED
    print("\n--- EMBEDDED ---")
    run_strategy(
        llm, loc, groups, results_dir, dataset_path,
        assertion_strategy="LLM_EXAMPLE",
        example_type=ExampleStrategy.EMBEDDED,
        num_examples=3,
    )

    # TFIDF
    print("\n--- TFIDF ---")
    run_strategy(
        llm, loc, groups, results_dir, dataset_path,
        assertion_strategy="LLM_EXAMPLE",
        example_type=ExampleStrategy.TFIDF,
        num_examples=3,
    )

    # DYNAMIC with varying weights
    for weight in [0.25, 0.50, 0.75, 1.00]:
        print(f"\n--- DYNAMIC alpha={weight} ---")
        run_strategy(
            llm, loc, groups, results_dir, dataset_path,
            assertion_strategy="LLM_EXAMPLE",
            example_type=ExampleStrategy.DYNAMIC,
            num_examples=3,
            example_weight=weight,
        )


if __name__ == "__main__":
    main()
