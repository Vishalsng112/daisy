"""LaTeX table generation from verification results.

Adapted from src/analysis/get_tables_results.py with imports updated to use
src.analysis.results_reader and src.config.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import pandas as pd

import src.config as gl
from src.analysis.results_reader import build_analysis_dataframe


def create_table(df: pd.DataFrame, desired_order=None):
    """
    Creates a stacked bar chart per LLM showing:
    - successful pairs (verification succeeded at least once)
    - failed pairs (had something to verify but never succeeded)
    - verification_to_do (no verification existed to perform)
    """
    df = df.assign(
        success=lambda d: d['verif_sucess'] > 0,
        verif_done=lambda d: d['verif_exist'] > 0
    )
    dfgroup = df.groupby(['llm', 'prog', 'group'])

    summary = []
    results_for_benchmarks = {}
    results_for_benchmarks_count = {}
    results_combined = {}
    results_combined_count = {}

    for (llm, prog, group), row in dfgroup:
        success_any = row['success'].any()
        nlen = len(row)

        n_assert = group.count("start") - 1
        if n_assert > 2:
            n_assert = "all"
        if n_assert not in results_for_benchmarks:
            results_for_benchmarks[n_assert] = {}
            results_for_benchmarks_count[n_assert] = {}

        if llm not in results_combined:
            results_combined[llm] = int(success_any)
            results_combined_count[llm] = 1
        else:
            results_combined[llm] += int(success_any)
            results_combined_count[llm] += 1

        if llm not in results_for_benchmarks[n_assert]:
            results_for_benchmarks[n_assert][llm] = {"suc": int(success_any), "tot": 1}
        else:
            prev_suc = results_for_benchmarks[n_assert][llm]["suc"]
            prev_tot = results_for_benchmarks[n_assert][llm]["tot"]
            results_for_benchmarks[n_assert][llm] = {"suc": prev_suc + int(success_any), "tot": prev_tot + 1}

    per_llm = {}
    for assert_numb in results_for_benchmarks.keys():
        prev_max = -1
        llm_list = []
        total_list = []
        suc_list = []
        percentage = []
        for llm in results_for_benchmarks[assert_numb].keys():
            stat = results_for_benchmarks[assert_numb][llm]

            llm_list.append(llm)
            total_list.append(stat["tot"])
            suc_list.append(stat["suc"])
            perc = (stat["suc"] / stat["tot"] * 100)
            percentage.append(f"{perc:.1f}%")
            if llm not in per_llm:
                per_llm[llm] = {}

            per_llm[llm][assert_numb] = (stat["suc"], stat["tot"], f"{perc:.1f}%")

    for llm in per_llm.keys():
        stat = per_llm[llm]
        for assert_n in stat.keys():
            stat_2 = stat[assert_n]
            print(f"{llm}:{assert_n}:{stat_2[0]}:{stat_2[2]}:{stat_2[1]}")


def filter_df(df: pd.DataFrame,
              name_contains: List[str] = [], remove_matches=1
              ) -> pd.DataFrame:
    """
    Return a filtered DataFrame where:
      - llm_names containing `name_contains` are removed (if name_contains != "")
      - if name_contains is empty, returns the original df
    """
    if not name_contains:
        return df

    pattern = "|".join(re.escape(s) for s in name_contains)
    if remove_matches:
        mask = ~df['llm'].str.contains(pattern, regex=True)
    else:
        mask = df['llm'].str.contains(pattern, regex=True)
    return df[mask]


def create_table_cleaned(verif_data_pd, llms_to_plot):
    new_verif_data_pd = filter_df(verif_data_pd, llms_to_plot.keys(), remove_matches=0).copy()
    new_verif_data_pd["llm"] = new_verif_data_pd["llm"].apply(lambda x: llms_to_plot[x])
    create_table(new_verif_data_pd, desired_order=list(llms_to_plot.values()))


def get_pandas_dataset(dataset_dir, result_dir):
    """Convenience wrapper matching old API: returns a pandas DataFrame."""
    rows = build_analysis_dataframe(dataset_dir, result_dir)
    return pd.DataFrame(rows)


if __name__ == '__main__':
    RESULT_DIR = gl.LLM_RESULTS_DIR
    DATASET_DIR = gl.DAFNY_ASSERTION_DATASET
    verif_data_pd = get_pandas_dataset(DATASET_DIR, RESULT_DIR)

    verif_data_pd = verif_data_pd[
        (verif_data_pd['benchmark'] != "w/o-2 one w/o-1")
    ]

    col = list(verif_data_pd.columns)
    plot_data_pd = verif_data_pd
    op = "Table result for:"

    llms_to_plot = {
        "gpt_4.1__nAssertions_ALL_nRounds_1_nRetries_1_addError_1_addExamp_0_ExType_NONE_loc_LLM_EXAMPLE": "LLM_EX_NO_RAG",
        "gpt_4.1__nAssertions_ALL_nRounds_1_nRetries_1_addError_1_addExamp_3_alpha_0.5_ExType_DYNAMIC_loc_LAUREL_BETTER": "STATIC_RAG",
        "gpt_4.1__nAssertions_ALL_nRounds_1_nRetries_1_addError_1_addExamp_3_alpha_0.5_ExType_DYNAMIC_loc_LLM_EXAMPLE": "LLM_EX_RAG",
        "gpt_4.1__nAssertions_ALL_nRounds_1_nRetries_1_addError_1_addExamp_3_alpha_0.5_ExType_DYNAMIC_loc_ORACLE": "ORACLE_RAG",
    }

    title_prefix = op + "_best_overall_"
    print(title_prefix)
    create_table_cleaned(plot_data_pd, llms_to_plot)
