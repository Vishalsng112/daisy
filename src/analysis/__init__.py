"""Analysis modules for reading cached results and evaluating position accuracy.

Provides:
- ResultsReader: reads cached localization/assertion/verification results
- PositionEvaluator: evaluates position prediction accuracy against oracle
- dataset_graphs: plotting functions for dataset visualization
- get_tables_results: LaTeX table generation
- get_results: bar charts, stats tests, and visualization
"""

from src.analysis.results_reader import (
    ResultsReader,
    parse_verification_output,
    retrieve_results_rows,
    retrieve_dataset_rows,
    merge_dataset_and_results,
    build_analysis_dataframe,
)
from src.analysis.position_evaluation import (
    oracle_here_would_fix,
    assertion_here_syntactic_valid,
    get_method_for_verification_and_oracle_positions,
    expand_assertion_groups_with_original_error_info,
    expand_assertion_groups_with_all_fix_positions,
    expand_assertion_groups_with_all_syntactic_valid_positions,
)

__all__ = [
    "ResultsReader",
    "parse_verification_output",
    "retrieve_results_rows",
    "retrieve_dataset_rows",
    "merge_dataset_and_results",
    "build_analysis_dataframe",
    "oracle_here_would_fix",
    "assertion_here_syntactic_valid",
    "get_method_for_verification_and_oracle_positions",
    "expand_assertion_groups_with_original_error_info",
    "expand_assertion_groups_with_all_fix_positions",
    "expand_assertion_groups_with_all_syntactic_valid_positions",
]
