"""Full dataset creation pipeline.

Runs all three steps:
1. Extract assertions from DafnyBench via asserttree
2. Generate w/o-1, w/o-2, w/o-all assertion-removal datasets
3. Expand with oracle errors, valid positions, syntactic positions

Usage:
    python -m src.datasets.full_dataset_creator
"""

from src.config import DAFNY_ASSERTION_DATASET
from src.datasets.dafny_get_all_assertions import dafny_get_all_assertions
from src.datasets.dafny_dataset_generator import dafny_dataset_generator
from src.analysis.position_evaluation import (
    expand_assertion_groups_with_original_error_info,
    expand_assertion_groups_with_all_fix_positions,
    expand_assertion_groups_with_all_syntactic_valid_positions,
)


def main() -> None:
    print("Step 1: Extracting assertions from DafnyBench")
    dafny_get_all_assertions()

    print("\nStep 2: Generating assertion-removal dataset")
    dafny_dataset_generator()

    print("\nStep 3: Expanding dataset with oracle errors and positions")
    expand_assertion_groups_with_original_error_info(DAFNY_ASSERTION_DATASET, parallel=True)

    print("\nStep 4: Computing syntactically valid positions")
    expand_assertion_groups_with_all_syntactic_valid_positions(DAFNY_ASSERTION_DATASET, parallel=True)

    print("\nStep 5: Computing all valid fix positions")
    expand_assertion_groups_with_all_fix_positions(DAFNY_ASSERTION_DATASET, parallel=True)

    print("\nDone.")


if __name__ == "__main__":
    main()
