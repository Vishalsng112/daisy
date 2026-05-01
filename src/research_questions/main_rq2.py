"""RQ2: Fault localization — evaluate localization strategies with no example retrieval.

Same strategies as RQ1 but with ExampleStrategy.NONE for assertion inference,
focusing on the localization dimension.

Three-phase pattern per (model, strategy) combo:
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
    """RQ2: Evaluate localization strategies (no example retrieval)."""
    dataset = Dataset.from_dataset_assertion_groups(DAFNY_ASSERTION_DATASET)
    groups = dataset.get_all_assertion_groups()
    print(f"Loaded {len(groups)} assertion groups")

    results_dir = LLM_RESULTS_DIR
    dataset_path = DAFNY_ASSERTION_DATASET

    # --- Haiku ---
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
        run_strategy(llm, loc, groups, results_dir, dataset_path)

    # LLM_EXAMPLE with DYNAMIC examples for position
    print(f"\n--- LLM_EXAMPLE ---")
    run_strategy(
        llm, LocStrategy.LLM_EXAMPLE, groups, results_dir, dataset_path,
        example_type_pos=ExampleStrategy.DYNAMIC,
        num_examples_pos=3,
        example_weight_pos=0.25,
    )

    # HYBRID with DYNAMIC examples for position
    print(f"\n--- HYBRID ---")
    run_strategy(
        llm, LocStrategy.HYBRID, groups, results_dir, dataset_path,
        example_type_pos=ExampleStrategy.DYNAMIC,
        num_examples_pos=3,
        example_weight_pos=0.25,
    )


if __name__ == "__main__":
    main()
