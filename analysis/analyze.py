"""Planned analysis for Objectives 2 and 3 (Section 7 of the report).

Input: participant-level CSV from export.py. Output: printed report.
  - completeness, exclusions, descriptives per condition
  - Cronbach's alpha per 3-item scale; AUTH-TRUST correlation
  - per outcome: mean difference with Welch 95% CI, Welch t-test, Hedges' g with 95% CI
  - Holm adjustment across the two outcomes
  - robustness: Mann-Whitney U; sensitivity excluding label-condition non-noticers
  - label recall per condition
Usage: python analysis/analyze.py data/export.csv [--pipeline-check]"""
import argparse
import math

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.power import TTestIndPower


def cronbach_alpha(df):
    df = df.dropna()
    k = df.shape[1]
    item_var = df.var(axis=0, ddof=1).sum()
    total_var = df.sum(axis=1).var(ddof=1)
    return (k / (k - 1)) * (1 - item_var / total_var)


def hedges_g(x, y):
    nx, ny = len(x), len(y)
    sp = math.sqrt(((nx - 1) * x.var(ddof=1) + (ny - 1) * y.var(ddof=1)) / (nx + ny - 2))
    d = (x.mean() - y.mean()) / sp
    j = 1 - 3 / (4 * (nx + ny) - 9)
    g = j * d
    se = math.sqrt((nx + ny) / (nx * ny) + g ** 2 / (2 * (nx + ny)))
    return g, g - 1.96 * se, g + 1.96 * se


def welch(x, y):
    t = stats.ttest_ind(x, y, equal_var=False)
    ci = t.confidence_interval(0.95)
    return x.mean() - y.mean(), ci.low, ci.high, t.statistic, t.df, t.pvalue


def compare(df, label):
    print(f"\n--- Group comparison: {label} (label=1 minus no-label=0) ---")
    pvals, rows = [], []
    for out in ("auth_score", "trust_score"):
        x = df.loc[df.condition == 1, out]; y = df.loc[df.condition == 0, out]
        diff, lo, hi, t, dof, p = welch(x, y)
        g, glo, ghi = hedges_g(x, y)
        u = stats.mannwhitneyu(x, y, alternative="two-sided")
        pvals.append(p)
        rows.append((out, len(x), len(y), diff, lo, hi, t, dof, p, g, glo, ghi, u.pvalue))
    holm = multipletests(pvals, method="holm")[1]
    for r, ph in zip(rows, holm):
        out, nx, ny, diff, lo, hi, t, dof, p, g, glo, ghi, pu = r
        print(f"{out:12s} n={nx}/{ny}  diff={diff:+.2f} [95% CI {lo:+.2f}, {hi:+.2f}]  "
              f"Welch t({dof:.1f})={t:.2f} p={p:.3f} p_Holm={ph:.3f}  "
              f"Hedges g={g:+.2f} [{glo:+.2f}, {ghi:+.2f}]  Mann-Whitney p={pu:.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--pipeline-check", action="store_true",
                    help="input is simulated test sessions; numbers are NOT study results")
    a = ap.parse_args()
    if a.pipeline_check:
        print("=" * 78)
        print("PIPELINE CHECK ON SIMULATED TEST SESSIONS - THESE NUMBERS ARE NOT STUDY RESULTS")
        print("=" * 78)

    power = TTestIndPower().solve_power(nobs1=30, alpha=0.05, power=0.80, ratio=1.0, alternative="two-sided")
    print(f"Sensitivity (n=30/group, alpha=.05 two-sided, power=.80): minimum detectable d = {power:.3f}")

    raw = pd.read_csv(a.csv)
    print(f"\nRows: {len(raw)}; excluded: {int(raw.exclude.sum())} "
          f"({raw.loc[raw.exclude == 1, 'exclude_reason'].value_counts().to_dict()})")
    df = raw[raw.exclude == 0].copy()
    print("\nDescriptives (participant-level scale means, 1-7):")
    print(df.groupby("condition")[["auth_score", "trust_score"]].agg(["count", "mean", "std"]).round(2).to_string())

    a_auth = cronbach_alpha(df[["item1", "item2", "item3"]])
    a_trust = cronbach_alpha(df[["item4", "item5", "item6"]])
    r = stats.pearsonr(df.auth_score, df.trust_score)
    print(f"\nCronbach's alpha: authenticity={a_auth:.2f}, trust={a_trust:.2f}; "
          f"AUTH-TRUST r={r.statistic:.2f} (p={r.pvalue:.3f})")

    compare(df, "all included participants")
    print("\nLabel recall by condition (manipulation check):")
    print(pd.crosstab(df.condition, df.label_recall).to_string())
    sens = df[~((df.condition == 1) & (df.label_recall != "yes"))]
    compare(sens, "sensitivity: label-condition participants who did not report noticing the label removed")


if __name__ == "__main__":
    main()
