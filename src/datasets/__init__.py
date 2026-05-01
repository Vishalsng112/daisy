"""Dataset creation scripts.

Pipeline:
1. dafny_get_all_assertions  — extract assertions from DafnyBench via asserttree
2. dafny_dataset_generator   — generate w/o-1, w/o-2, w/o-all assertion datasets
3. position_evaluation (in src/analysis/) — expand with oracle errors, valid positions
"""
