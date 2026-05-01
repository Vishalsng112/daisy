"""Dataset visualization — plotting functions for position analysis.

Adapted from src/analysis/dataset_graphs.py with imports updated to use
src.analysis.results_reader instead of analysis.get_dataframe_from_results.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


# This only works for 1 assertion benchmarks
def plot_graphs_of_dataset_loc(df: pd.DataFrame, images_path: Path):
    df["n_assertions_fix_posiiton"] = df["all_lines_where_oracle_fixes_file"].apply(
        lambda x: 0 if not x else (1 if isinstance(x[0], int) else len(x))
    )
    df["n_assertions"] = df["group"].apply(lambda x: x.count("start") - 1)
    df_1 = df[df["n_assertions"] == 1].copy()

    df_1["min_pos"] = df_1["all_lines_where_oracle_fixes_file"].apply(lambda x: -1 if not x[0] else min(x[0]))
    df_1["max_pos"] = df_1["all_lines_where_oracle_fixes_file"].apply(lambda x: -1 if not x[0] else max(x[0]))
    df_1["pos"] = df_1["all_lines_where_oracle_fixes_file"].apply(lambda x: len(x[0]))
    # compute diff only if poss > 0, else np.nan
    df_1["diff"] = df_1.apply(
        lambda row: (row["max_pos"] - row["min_pos"]) if row["pos"] > 0 else np.nan,
        axis=1,
    )

    green = "#117733"
    # Histogram for 'diff'
    plt.figure(figsize=(4.0, 2.5), dpi=300)
    plt.hist(df_1["diff"].dropna(), bins=range(50), color=green, edgecolor='black')
    plt.xlabel("Maximum difference between positions")
    plt.ylabel("Frequency")
    plt.savefig(images_path / "valid_positions_difference.pdf", dpi=300, bbox_inches="tight")
    plt.show()
    plt.close()

    # Histogram for 'poss'
    plt.figure(figsize=(4.0, 2.5), dpi=300)
    plt.hist(df_1["pos"], bins=range(30), color=green, edgecolor='black')
    plt.xlabel("Number  of valid positions")
    plt.ylabel("Frequency")
    plt.savefig(images_path / "valid_positions_number.pdf", dpi=300, bbox_inches="tight")
    plt.show()
    plt.close()
