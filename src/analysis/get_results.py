"""Bar charts, stats tests, and visualization for verification results.

Adapted from src/analysis/get_results.py with imports updated to use
src.analysis.results_reader and src.config.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import pandas as pd
import numpy as np

from statsmodels.stats.contingency_tables import mcnemar
from scipy.stats import chi2_contingency
from sklearn.metrics import cohen_kappa_score

import src.config as gl
from src.analysis.results_reader import build_analysis_dataframe

green = "#117733"
yellow = "#DDCC77"
red = "#8A1414"

green_darker = "#0d5927"
yellow_darker = "#a39b5b"
red_darker = "#450a0a"

title_prefix = ""


def from_original_dataset_return_verif_stats(df: pd.DataFrame, desired_order) -> tuple:
    df = df.assign(
        success=lambda d: d['verif_sucess'] > 0
    )

    # Success per problem per benchmark
    df_pairs = (
        df.groupby(['llm', 'prog', 'group', 'benchmark'])['success']
          .any()
          .reset_index()
    )

    # --- AGG TOTAL (for the Bar Chart) ---
    total_possible_cases = df_pairs.groupby('llm')['success'].count().max()

    agg_total = (
        df_pairs.groupby(['llm'])['success']
        .agg(
            success='sum',
            fail=lambda x: total_possible_cases - x.sum()
        )
        .reset_index()
    )

    # --- AGG BENCHMARK (for the LaTeX Table) ---
    agg_benchmark = (
        df_pairs.groupby(['llm', 'benchmark'])['success']
        .agg(['sum', 'count'])
        .unstack(fill_value=0)
    )
    agg_benchmark.columns = [f"{col[1]}_{col[0]}" for col in agg_benchmark.columns]
    agg_benchmark = agg_benchmark.reset_index()

    if desired_order:
        existing = set(agg_total['llm'])
        missing = [x for x in desired_order if x not in existing]
        if missing:
            print(f"Warning: Missing from data: {missing}")
        agg_total = agg_total.set_index('llm').reindex(desired_order).reset_index()
        agg_benchmark = agg_benchmark.set_index('llm').reindex(desired_order).reset_index()
        agg_total['llm'] = agg_total['llm'].map(desired_order)
        agg_benchmark['llm'] = agg_benchmark['llm'].map(desired_order)

    return (agg_total, agg_benchmark)


def digit_len(x: int) -> int:
    return len(str(x))


def phantom_pad(value, max_digits: int) -> str:
    s = str(int(value))
    pad = max_digits - len(s)
    return f"{'\\phantom{' + '0' * pad + '}' if pad > 0 else ''}{s}"


def get_latex_table_with_verif_stats(df_verif_stats: pd.DataFrame, caption: str, label: str, desired_order) -> str:
    (_, agg_pairs_benchmarks) = from_original_dataset_return_verif_stats(df_verif_stats, desired_order)

    benchmarks = [c.replace('_sum', '') for c in agg_pairs_benchmarks.columns if c.endswith('_sum')]

    global_totals = {}
    for bench in benchmarks:
        count_col = f"{bench}_count"
        if count_col in agg_pairs_benchmarks.columns:
            global_totals[bench] = int(agg_pairs_benchmarks[count_col].max())
        else:
            global_totals[bench] = 0

    t1 = global_totals.get('w/o-1', 0)
    t2 = global_totals.get('w/o-2', 0)
    ta = global_totals.get('w/o-all', 0)
    combined_total = t1 + t2 + ta
    table_top = f"""
\\begin{{table}}[!t]
\\begin{{center}}
\\small
\\caption{{{caption}}}
\\label{{{label}}}
\\begin{{tabular}}{{|l|c|c|c|c|}}
\\hline
\\multirow{{2}}{{*}}{{Approach}} & \\multicolumn{{4}}{{c|}}{{Benchmarks}} \\\\
\\cline{{2-5}}
 & w/o-1 ({t1}) & w/o-2 ({t2}) & All ({ta}) & Combined ({combined_total}) \\\\
\\hline
"""
    rows = []
    max_sum_digits = 0
    max_pct_digits = 0
    for _, r in agg_pairs_benchmarks.iterrows():
        for bench in ["w/o-1", "w/o-2", "w/o-all"]:
            s = int(r.get(f'{bench}_sum', 0))
            total = global_totals.get(bench, 0)
            pct = (s / total * 100) if total > 0 else 0
            max_sum_digits = max(max_sum_digits, digit_len(s))
            max_pct_digits = max(max_pct_digits, digit_len(int(pct)))

    for _, r in agg_pairs_benchmarks.iterrows():
        def get_total_and_percentage_and_str(bench_name, max_sum_digits, max_pct_digits):
            s = int(r.get(f'{bench_name}_sum', 0))
            total = global_totals.get(bench_name, 0)
            pct = (s / total * 100) if total > 0 else 0
            s_fmt = phantom_pad(s, max_sum_digits)
            pct_fmt = phantom_pad(int(pct), max_pct_digits)
            return s, pct, f"{s_fmt} ({pct_fmt}.0\\%)"

        nw1, _, fw1 = get_total_and_percentage_and_str("w/o-1", max_sum_digits, max_pct_digits)
        nw2, _, fw2 = get_total_and_percentage_and_str("w/o-2", max_sum_digits, max_pct_digits)
        nwall, _, fwall = get_total_and_percentage_and_str("w/o-all", max_sum_digits, max_pct_digits)

        combined = (nw1 + nw2 + nwall)
        combined_pct = ((combined / combined_total) * 100) if combined_total > 0 else 0
        combined_f = f"{combined} ({combined_pct:.1f}\\%)"

        row_str = (
            f"{r['llm']} & "
            f"{fw1} & "
            f"{fw2} & "
            f"{fwall} & "
            f"{combined_f} \\\\"
        )
        rows.append(row_str)

    table_bottom = """
\\hline
\\end{tabular}
\\end{center}
\\end{table}
"""
    return table_top + "\n".join(rows) + table_bottom


def bar_chart_program_method_success_df(df: pd.DataFrame, size="BIG", desired_order=None):
    (agg_pairs, agg_pairs_benchmarks) = from_original_dataset_return_verif_stats(df, desired_order)

    labels = agg_pairs['llm'].tolist()
    success = agg_pairs['success'].tolist()
    fail = agg_pairs['fail'].tolist()

    x = range(len(labels))

    if size == "SINGLE":
        fig, ax = plt.subplots(figsize=(3.5, 3.0), dpi=300)
    elif size == "DOUBLE":
        fig, ax = plt.subplots(figsize=(7, 4), dpi=300)
    elif size == "BIG":
        fig, ax = plt.subplots(figsize=(14, 7))

    ax.bar(x, success, label='Verify', color=green)
    ax.bar(x, fail, bottom=success, label='Fail', color=red)

    for i, (s, f) in enumerate(zip(success, fail)):
        total = s + f
        ax.text(i, total + 0.8, f"{total}", ha='center')

    for i, (s, f) in enumerate(zip(success, fail)):
        total = s + f
        if total == 0:
            continue
        pct_s = s / total * 100
        if s != 0 and pct_s > 5:
            ax.text(i, s / 2, f"{pct_s:.0f}%", ha='center', va='center', color='white')
        pct_f = f / total * 100
        if f != 0 and pct_f > 5:
            ax.text(i, s + f / 2, f"{pct_f:.0f}%", ha='center', va='center', color='white')

    ax.set_ylabel('Program/Assertion Group Pairs')
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=10, ha='right')
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1))

    plt.tight_layout()
    plt.savefig(title_prefix + "bar_chart_program_method_success.pdf", dpi=300, bbox_inches="tight")
    plt.close(fig)


def get_expected_pass_at_k_by_llm(df: pd.DataFrame) -> dict[str, dict[int, int]]:
    df = df.assign(success=lambda d: d['verif_sucess'] > 0)

    grp = (
        df.groupby(['llm', 'prog', 'group'])
          .agg(
              total_assertions=('success', 'size'),
              successes=('success', 'sum')
          )
          .reset_index()
    )
    grp = grp[grp['successes'] > 0]
    grp['k'] = (grp['total_assertions'] / grp['successes']).apply(np.ceil).astype(int)
    histo = {}
    for llm, sub in grp.groupby('llm'):
        counts = sub['k'].value_counts().to_dict()
        histo[llm] = dict(sorted(counts.items()))
    return histo


def line_plot_expected_kpass_df(df: pd.DataFrame, size="BIG"):
    histo = get_expected_pass_at_k_by_llm(df)
    max_k = max((max(d.keys()) for d in histo.values()), default=0)
    if size == "SINGLE":
        fig, ax = plt.subplots(figsize=(3.5, 3.0), dpi=300)
    elif size == "DOUBLE":
        fig, ax = plt.subplots(figsize=(7, 4), dpi=300)
    elif size == "BIG":
        fig, ax = plt.subplots(figsize=(14, 7))

    for llm, bucket in histo.items():
        xs = list(range(1, max_k + 1))
        ys = []
        cum = 0
        for k in xs:
            cum += bucket.get(k, 0)
            ys.append(cum)
        ax.plot(xs, ys, marker='o', label=llm)

    ax.set_xlabel('Expected k (total_assertions / successes)')
    ax.set_ylabel('Program/Assertion Group Pairs')
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1))
    plt.tight_layout()
    plt.savefig(title_prefix + "line_plot_expected_kpass.pdf", dpi=300, bbox_inches="tight")
    plt.close(fig)


def bar_chart_fix_position_analysis_df(df: pd.DataFrame, size="BIG", desired_order=None, localization=""):
    df_pairs = df.groupby(
        ['llm', 'prog', 'group'],
        as_index=False
    ).agg(
        oracle_here_would_fix=('oracle_here_would_fix', lambda x: any(x)),
        assertion_here_syntatic_valid=('assertion_here_syntatic_valid', lambda x: any(x)),
        number_expected_assertions=('number_expected_assertions', lambda x: sum(x)),
    )

    def classify(row):
        if row['number_expected_assertions'] == 0:
            return "No Pos"
        elif row['oracle_here_would_fix']:
            return "Valid"
        elif row['assertion_here_syntatic_valid']:
            return "Partial"
        else:
            return "Invalid"

    df_pairs['category'] = df_pairs.apply(classify, axis=1)

    agg = df_pairs.pivot_table(
        index='llm',
        columns='category',
        aggfunc='size',
        fill_value=0
    )

    cats = ['Valid', 'Partial', 'Invalid', 'No Pos']
    colors = [green, yellow, red, '#777777']

    agg = agg.reindex(columns=cats, fill_value=0)

    if desired_order is not None:
        missing = [x for x in desired_order if x not in agg.index]
        if missing:
            print(f"Warning: these LLMs not found in data and will be skipped: {missing}")
        agg = agg.reindex(desired_order, fill_value=0)

    labels = agg.index.tolist()
    data = [agg[cat].tolist() for cat in cats]

    x = range(len(labels))
    if size == "SINGLE":
        fig, ax = plt.subplots(figsize=(5, 3), dpi=300)
    elif size == "DOUBLE":
        fig, ax = plt.subplots(figsize=(5, 3), dpi=300)
    elif size == "BIG":
        fig, ax = plt.subplots(figsize=(14, 7))

    bottom = [0] * len(labels)
    totals = agg.sum(axis=1).tolist()

    for cat, vals, color in zip(cats, data, colors):
        ax.bar(x, vals, bottom=bottom, label=cat, color=color)
        for i, (b, v, tot) in enumerate(zip(bottom, vals, totals)):
            pct = v / tot * 100
            if v > 0 and pct > 5:
                ax.text(i, b + v / 2, f'{pct:.0f}%', ha='center', va='center', fontsize=10, color='white')
        bottom = [b + v for b, v in zip(bottom, vals)]

    ax.set_ylabel('Testcases')
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha='center')
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1))
    plt.tight_layout()
    plt.savefig(localization, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def filter_df(df: pd.DataFrame,
              name_contains: List[str] = [], remove_matches=1
              ) -> pd.DataFrame:
    if not name_contains:
        return df
    pattern = "|".join(re.escape(s) for s in name_contains)
    if remove_matches:
        mask = ~df['llm'].str.contains(pattern, regex=True)
    else:
        mask = df['llm'].str.contains(pattern, regex=True)
    return df[mask]


def bar_chart_dual_success_fix(df: pd.DataFrame,
                               size: str = "BIG",
                               width: float = 0.35,
                               desired_order: list = None,
                               localization=""):
    df = df.assign(success=lambda d: d['verif_sucess'] > 0)
    agg = (
        df.groupby(['llm', 'prog', 'group'], as_index=False)
          .agg(
            success=('success', 'any'),
            oracle_fix=('oracle_here_would_fix', 'any'),
            synt_valid=('assertion_here_syntatic_valid', 'any'),
            num_expect=('number_expected_assertions', 'sum'),
          )
    )

    def cls(r):
        if r.num_expect == 0:
            return 'No Pos'
        if r.oracle_fix:
            return 'Valid'
        if r.synt_valid:
            return 'Partial'
        return 'Invalid'

    agg['fix_cat'] = agg.apply(cls, axis=1)

    cats = ['Valid', 'Partial', 'Invalid', 'No Pos']
    pivot = (
        agg.pivot_table(
            index='llm',
            columns=['success', 'fix_cat'],
            aggfunc='size',
            fill_value=0
        )
        .reindex(
            pd.MultiIndex.from_product([[True, False], cats],
                                       names=['success', 'fix_cat']),
            axis=1, fill_value=0
        )
    )

    if desired_order is not None:
        missing = [x for x in desired_order if x not in pivot.index]
        if missing:
            print(f"Warning: these LLMs not in data and will be skipped: {missing}")
        pivot = pivot.reindex(desired_order, fill_value=0)

    llms = pivot.index.tolist()
    succ_df = pivot.xs(True, level='success', axis=1)
    fail_df = pivot.xs(False, level='success', axis=1)
    succ_tot = succ_df.sum(axis=1).tolist()
    fail_tot = fail_df.sum(axis=1).tolist()

    if size == "SINGLE":
        fig, ax = plt.subplots(figsize=(5, 3), dpi=300)
    elif size == 'DOUBLE':
        fig, ax = plt.subplots(figsize=(5, 3), dpi=300)
    else:
        fig, ax = plt.subplots(figsize=(14, 7))

    x = range(len(llms))
    lx = [xi - width / 2 for xi in x]
    rx = [xi + width / 2 for xi in x]

    h_s = ax.bar(lx, succ_tot, width, color=green)
    h_f = ax.bar(lx, fail_tot, width, bottom=succ_tot, color=red)

    for xi, s, f in zip(lx, succ_tot, fail_tot):
        tot = s + f
        s1 = s / tot * 100
        f1 = f / tot * 100
        if s and s1 > 5:
            ax.text(xi, s / 2, f"{s1:.0f}%", ha='center', va='center', color='white', fontsize=6)
        if f and f1 > 5:
            ax.text(xi, s + f / 2, f"{f1:.0f}%", ha='center', va='center', color='white', fontsize=6)

    colors_map = {'Valid': green_darker, 'Partial': yellow_darker, 'Invalid': red_darker, 'No Pos': '#777777'}

    bottom = [0] * len(llms)
    fix_handles = {}
    for cat in cats:
        vals = succ_df[cat].tolist()
        bars = ax.bar(rx, vals, width, bottom=bottom, color=colors_map[cat])
        fix_handles[cat] = bars[0]
        for xi, b, v, st in zip(rx, bottom, vals, succ_tot):
            p1 = v / st * 100 if st else 0
            if v and p1 > 5:
                ax.text(xi, b + v / 2, f"{p1:.0f}%", ha='center', va='center', color='white', fontsize=6)
        bottom = [b + v for b, v in zip(bottom, vals)]

    for cat in cats:
        vals = fail_df[cat].tolist()
        bars = ax.bar(rx, vals, width, bottom=bottom, color=colors_map[cat])
        for xi, b, v, ft in zip(rx, bottom, vals, fail_tot):
            p2 = v / ft * 100 if ft else 0
            if v and p2 > 5:
                ax.text(xi, b + v / 2, f"{p2:.0f}%", ha='center', va='center', color='white', fontsize=6)
        bottom = [b + v for b, v in zip(bottom, vals)]

    leg1 = ax.legend(
        handles=[h_s, h_f],
        labels=['Verify', 'Fail'],
        title='Outcome',
        loc='upper left', bbox_to_anchor=(1.01, 1))
    ax.add_artist(leg1)

    leg2 = ax.legend(
        handles=[fix_handles[c] for c in cats],
        labels=cats,
        title='Fix Position',
        loc='lower left', bbox_to_anchor=(1.01, 0))

    ax.set_xticks(x)
    ax.set_xticklabels(llms, rotation=15, ha='center')
    ax.set_ylabel('Testcases')
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.tight_layout()
    plt.savefig(localization, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)


def bar_chart_cleaned(verif_data_pd, size, llms_to_plot):
    new_verif_data_pd = filter_df(verif_data_pd, llms_to_plot.keys(), remove_matches=0).copy()
    new_verif_data_pd["llm"] = new_verif_data_pd["llm"].apply(lambda x: llms_to_plot[x])
    bar_chart_program_method_success_df(new_verif_data_pd, size, desired_order=list(llms_to_plot.values()))


def line_plot_expected_kpass_df_cleaned(verif_data_pd, size, llms_to_plot):
    new_verif_data_pd = filter_df(verif_data_pd, llms_to_plot.keys(), remove_matches=0).copy()
    new_verif_data_pd["llm"] = new_verif_data_pd["llm"].apply(lambda x: llms_to_plot[x])
    line_plot_expected_kpass_df(new_verif_data_pd, size)


def bar_chart_fix_position_cleaned(verif_data_pd, size, llms_to_plot, localization):
    new_verif_data_pd = filter_df(verif_data_pd, llms_to_plot.keys(), remove_matches=0).copy()
    new_verif_data_pd["llm"] = new_verif_data_pd["llm"].apply(lambda x: llms_to_plot[x])
    bar_chart_fix_position_analysis_df(new_verif_data_pd, size, desired_order=list(llms_to_plot.values()), localization=localization)


def sucess_vs_position_cleaned(verif_data_pd, size, llms_to_plot, localization):
    new_verif_data_pd = filter_df(verif_data_pd, llms_to_plot.keys(), remove_matches=0).copy()
    new_verif_data_pd["llm"] = new_verif_data_pd["llm"].apply(lambda x: llms_to_plot[x])
    bar_chart_dual_success_fix(new_verif_data_pd, size, desired_order=list(llms_to_plot.values()), localization=localization)


def compute_stats_tests(LLM1, LLM2, stats_df_pairs, threshold=0.05):
    df_filtered = stats_df_pairs[stats_df_pairs['llm'].isin([LLM1, LLM2])]

    df_comparison = df_filtered.pivot_table(
        index=['prog', 'group'],
        columns='llm',
        values='success',
        aggfunc=any
    ).reset_index()

    df_final = df_comparison[['prog', 'group', LLM1, LLM2]]

    a = df_final[(df_final[LLM1] == True) & (df_final[LLM2] == True)].shape[0]
    b = df_final[(df_final[LLM1] == True) & (df_final[LLM2] == False)].shape[0]
    c = df_final[(df_final[LLM1] == False) & (df_final[LLM2] == True)].shape[0]
    d = df_final[(df_final[LLM1] == False) & (df_final[LLM2] == False)].shape[0]

    mcnemar_matrix = [[d, c], [b, a]]
    print(f"\n--- McNemar Matrix [[d,c],[b,a]]: ---\n{mcnemar_matrix}")

    result = mcnemar(mcnemar_matrix, exact=True)
    print(f"\n--- Results McNemar (is one better than the other) ---")
    print(result)
    print(f"Agreements (d): {LLM1} Failures, {LLM2} Failure: {d}")
    print(f"Agreements (a): {LLM1} Success, {LLM2} Success: {a}")
    print(f"Disagreements (b): {LLM1} Success, {LLM2} Failure: {b}")
    print(f"Disagreements (c): {LLM1} Failure, {LLM2} Success: {c}")
    pval = result.pvalue
    print(f"P-Value: {pval}")
    if pval < threshold:
        print("!!! Models are statistically different (one is better than the other) !!!")
    else:
        print("!!! Models are not statistically different (they are equal in efficacy) !!!")

    print(f"\n--- Results Chi-squared Test of Independence are they independent ---")
    chi2_matrix = [[d, c], [b, a]]
    print(f"--- Chi-Squared Matrix [[d,c],[b,a]]: ---\n{chi2_matrix}")

    chi2, p_value, dof, expected = chi2_contingency(chi2_matrix, correction=True)

    print("--- Chi-Squared Test Results ---")
    print(f"Chi-Squared Statistic: {chi2:.4f}")
    print(f"P-Value: {p_value:.4f}")
    print(f"Degrees of Freedom: {dof}")
    print("Expected Frequencies (if independent):")
    print(expected.round(2))
    if p_value < threshold:
        print("!!! Models are not independent !!!")
    else:
        print("!!! Models are independent!!! ")

    print("Effect Sizes")
    N = d + c + b + a
    chi2_matrix = [[d, c], [b, a]]
    chi2, p, dof, expected = chi2_contingency(chi2_matrix)
    phi = np.sqrt(chi2 / N)

    print(f"Phi (φ) Coefficient: {phi:.3f}")
    jaccard = a / (a + b + c) if (a + b + c) > 0 else 0
    print(f"Jaccard Index (Overlap): {jaccard:.3f}")


def get_pandas_dataset(dataset_dir, result_dir):
    """Convenience wrapper matching old API: returns a pandas DataFrame."""
    rows = build_analysis_dataframe(dataset_dir, result_dir)
    return pd.DataFrame(rows)
