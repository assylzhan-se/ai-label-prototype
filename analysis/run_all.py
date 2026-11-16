"""Assignment 4: one command from the study database to every table, figure and statistic.

Usage:
    python analysis/run_all.py --db data/study.db --out results
    python analysis/run_all.py --db data/pipeline_check/pipeline_check.db --out results_check --include-test --pipeline-check

Outputs (in --out):
    results.txt                      all numbers, in report order
    tab1_flow.csv                    enrolment -> exclusions -> analysed, per condition
    tab2_sample.csv                  sample description per condition
    tab3_items.csv                   item descriptives, Cronbach's alpha
    tab4_main.csv                    main comparison (Welch CI, Hedges g, Holm, Mann-Whitney, Bayes)
    tab5_robustness.csv              same effect under alternative reasonable choices
    tab6_manipulation.csv            label recall by condition
    fig1_distributions.png           participant scores by condition
    fig2_profiles.png                profile-level means by condition (exploratory)
    fig3_robustness.png              effect estimates across robustness checks
    fig4_timeline.png                completed sessions over time (collection log)
    data_participant_level.csv       anonymised analysis-ready dataset (study codes only)
    data_profile_level.csv           anonymised profile-level extract
    open_text_for_coding.csv         optional open answers, for thematic coding
"""
import argparse
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402
from statsmodels.stats.multitest import multipletests  # noqa: E402
from statsmodels.stats.power import TTestIndPower  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import db  # noqa: E402
import export  # noqa: E402

COND = {0: "No label", 1: "AI label"}
COL = {0: "#7a8794", 1: "#2f6fde"}
OUT_LABEL = {"auth_score": "Perceived authenticity", "trust_score": "Perceived trustworthiness"}
PRIOR_SD = 1.0   # weakly informative prior on the mean difference: Normal(0, 1) scale points

LINES = []


def say(s=""):
    print(s)
    LINES.append(s)


# ---------------- statistics ----------------
def cronbach_alpha(df):
    df = df.dropna()
    k = df.shape[1]
    if len(df) < 3:
        return float("nan")
    return (k / (k - 1)) * (1 - df.var(ddof=1).sum() / df.sum(axis=1).var(ddof=1))


def hedges_g(x, y):
    nx, ny = len(x), len(y)
    sp = math.sqrt(((nx - 1) * x.var(ddof=1) + (ny - 1) * y.var(ddof=1)) / (nx + ny - 2))
    g = (1 - 3 / (4 * (nx + ny) - 9)) * (x.mean() - y.mean()) / sp
    se = math.sqrt((nx + ny) / (nx * ny) + g ** 2 / (2 * (nx + ny)))
    return g, g - 1.96 * se, g + 1.96 * se


def compare(df, out):
    """label (1) minus no label (0)."""
    x = df.loc[df.condition == 1, out].dropna()
    y = df.loc[df.condition == 0, out].dropna()
    t = stats.ttest_ind(x, y, equal_var=False)
    ci = t.confidence_interval(0.95)
    diff = x.mean() - y.mean()
    g, glo, ghi = hedges_g(x, y)
    mw = stats.mannwhitneyu(x, y, alternative="two-sided")
    # Bayesian estimate (normal approximation): prior N(0, PRIOR_SD^2) x likelihood N(diff, se^2)
    se = math.sqrt(x.var(ddof=1) / len(x) + y.var(ddof=1) / len(y))
    post_var = 1 / (1 / PRIOR_SD ** 2 + 1 / se ** 2)
    post_mean = post_var * diff / se ** 2
    post_sd = math.sqrt(post_var)
    p_neg = stats.norm.cdf(0, post_mean, post_sd)
    return dict(outcome=out, n_label=len(x), n_nolabel=len(y), mean_label=x.mean(), sd_label=x.std(ddof=1),
                mean_nolabel=y.mean(), sd_nolabel=y.std(ddof=1), diff=diff, ci_low=ci.low, ci_high=ci.high,
                t=t.statistic, df=t.df, p=t.pvalue, g=g, g_low=glo, g_high=ghi,
                mw_U=mw.statistic, mw_p=mw.pvalue, bayes_mean=post_mean,
                bayes_low=post_mean - 1.96 * post_sd, bayes_high=post_mean + 1.96 * post_sd,
                p_diff_below_0=p_neg)


def comparison_table(df):
    rows = [compare(df, o) for o in ("auth_score", "trust_score")]
    holm = multipletests([r["p"] for r in rows], method="holm")[1]
    for r, h in zip(rows, holm):
        r["p_holm"] = h
    return pd.DataFrame(rows)


# ---------------- figures ----------------
def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e6e6", lw=0.8)
    ax.set_axisbelow(True)


def fig_distributions(df, path):
    fig, axes = plt.subplots(1, 2, figsize=(8, 4), sharey=True)
    rng = np.random.default_rng(1)
    for ax, out in zip(axes, ("auth_score", "trust_score")):
        for i, c in enumerate((0, 1)):
            v = df.loc[df.condition == c, out].dropna().values
            ax.boxplot(v, positions=[i], widths=0.45, showfliers=False,
                       medianprops=dict(color="#1d2329"), boxprops=dict(color="#9aa3ab"),
                       whiskerprops=dict(color="#9aa3ab"), capprops=dict(color="#9aa3ab"))
            ax.scatter(i + rng.uniform(-0.12, 0.12, len(v)), v, s=18, color=COL[c], alpha=0.75, zorder=3)
            ax.plot([i - 0.25, i + 0.25], [v.mean()] * 2, color=COL[c], lw=2.5, zorder=4)
        ax.set_xticks([0, 1], [f"{COND[c]}\n(n={int((df.condition == c).sum())})" for c in (0, 1)])
        ax.set_title(OUT_LABEL[out], fontsize=11)
        ax.set_ylim(1, 7)
        style(ax)
    axes[0].set_ylabel("Participant mean score (1-7)")
    fig.text(0.5, -0.02, "Dots = participants; box = median and IQR; thick line = group mean",
             ha="center", fontsize=8, color="#555")
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_profiles(long, path):
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.8), sharey=True)
    pids = sorted(long.profile_id.unique())
    for ax, out in zip(axes, ("auth", "trust")):
        for c, dx in ((0, -0.12), (1, 0.12)):
            g = long[long.condition == c].groupby("profile_id")[out]
            m = g.mean().reindex(pids)
            se = (g.std(ddof=1) / np.sqrt(g.count())).reindex(pids)
            xs = np.arange(len(pids)) + dx
            ax.errorbar(xs, m, yerr=1.96 * se, fmt="o", color=COL[c], ms=5, capsize=2, lw=1, label=COND[c])
        ax.set_xticks(range(len(pids)), pids)
        ax.set_title(OUT_LABEL[out + "_score"], fontsize=11)
        ax.set_ylim(1, 7)
        style(ax)
    axes[0].set_ylabel("Mean rating (1-7), 95% CI")
    axes[1].legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_robustness(rob, path):
    fig, axes = plt.subplots(1, 2, figsize=(9, 0.45 * len(rob) / 2 + 1.6), sharey=True)
    for ax, out in zip(axes, ("auth_score", "trust_score")):
        r = rob[rob.outcome == out].reset_index(drop=True)
        ys = np.arange(len(r))[::-1]
        ax.axvline(0, color="#999", lw=0.8)
        ax.errorbar(r["diff"], ys, xerr=[r["diff"] - r.ci_low, r.ci_high - r["diff"]], fmt="o",
                    color="#2f6fde", ms=5, capsize=2, lw=1)
        ax.set_yticks(ys, [f"{c} (n={a}+{b})" for c, a, b in zip(r.check, r.n_label, r.n_nolabel)], fontsize=8)
        ax.set_title(OUT_LABEL[out], fontsize=11)
        ax.set_xlabel("Label minus no label, scale points (95% CI)")
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_timeline(raw, path):
    t = pd.to_datetime(raw["completed_at"].dropna(), utc=True).dt.tz_convert("Asia/Almaty").sort_values()
    fig, ax = plt.subplots(figsize=(8, 3))
    if len(t):
        ax.step(t, np.arange(1, len(t) + 1), where="post", color="#2f6fde")
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %H:%M", tz=t.dt.tz if len(t) else None))
    ax.set_ylabel("Completed sessions (cumulative)")
    ax.set_xlabel("Time (Asia/Almaty)")
    style(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "study.db"))
    ap.add_argument("--out", default=os.path.join(ROOT, "results"))
    ap.add_argument("--include-test", action="store_true", help="only for pipeline checks")
    ap.add_argument("--pipeline-check", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    P = lambda f: os.path.join(a.out, f)  # noqa: E731

    if a.pipeline_check:
        say("=" * 78)
        say("PIPELINE CHECK ON SIMULATED TEST SESSIONS - THESE NUMBERS ARE NOT STUDY RESULTS")
        say("=" * 78)
    con = db.connect(a.db)
    raw = pd.DataFrame(export.build_rows(con, a.include_test))
    long_all = pd.DataFrame(export.build_rating_rows(con, a.include_test))
    long = long_all[~long_all.profile_id.str.startswith("R")].copy()      # main analysis: six AI profiles only
    if raw.empty:
        sys.exit("No participants in the database.")
    n_test = con.execute("SELECT COUNT(*) FROM participants WHERE is_test=1").fetchone()[0]

    # ---- 1. collection and cleaning log ----
    say("1. DATA COLLECTION AND CLEANING")
    times = pd.to_datetime(raw.created_at, utc=True).dt.tz_convert("Asia/Almaty")
    say(f"Collection window: {times.min():%Y-%m-%d %H:%M} to {times.max():%Y-%m-%d %H:%M} (Asia/Almaty)")
    say(f"Team test sessions in database (never analysed): {n_test}")
    say(f"Enrolled (consented + eligible){' incl. test' if a.include_test else ''}: {len(raw)}")
    flow = []
    for c in (0, 1):
        d = raw[raw.condition == c]
        reasons = d.exclude_reason.str.split(";").explode()
        flow.append({"condition": COND[c], "enrolled": len(d),
                     "incomplete": int((reasons == "incomplete").sum()),
                     "missing_ratings": int((reasons == "missing_ratings").sum()),
                     "too_fast": int((reasons == "too_fast").sum()),
                     "attention_fail": int((reasons == "attention_fail").sum()),
                     "repeat_device": int((reasons == "repeat_device").sum()),
                     "excluded_total": int(d.exclude.sum()), "analysed": int((d.exclude == 0).sum()),
                     "straightlining_flag": int(d.straightlining.sum())})
    flow = pd.DataFrame(flow)
    tot = flow.drop(columns="condition").sum()
    flow = pd.concat([flow, pd.DataFrame([{"condition": "Total", **tot.to_dict()}])], ignore_index=True)
    flow.to_csv(P("tab1_flow.csv"), index=False)
    say(flow.to_string(index=False))
    say("Duplicates: study codes are unique by construction (primary key); "
        f"duplicate (code, profile, item) rating rows: "
        f"{con.execute('SELECT COUNT(*) - COUNT(DISTINCT study_code||profile_id||item_no) FROM ratings').fetchone()[0]}")
    say(f"Out-of-range rating values (outside 1-7): "
        f"{con.execute('SELECT COUNT(*) FROM ratings WHERE value NOT BETWEEN 1 AND 7').fetchone()[0]}")
    say(f"Sessions without timing events (speed rule not applicable): {int(raw.mean_view_ms.isna().sum())}")

    df = raw[raw.exclude == 0].copy()
    lng = long[long.study_code.isin(df.study_code)].copy()
    for col in ("label_text", "mc_correct", "source", "attention_value", "wave"):
        if col not in raw:
            raw[col] = None
    for col in ("real_auth", "real_trust"):
        if col not in raw:
            raw[col] = None
    keep = ["study_code", "condition", "condition_name", "auth_score", "trust_score", "real_auth", "real_trust",
            "label_text", "mc_correct",
            "source", "attention_value", "wave"] + \
           [f"item{i}" for i in range(1, 7)] + ["likes", "mean_view_ms", "label_recall", "label_hovers",
                                                 "gender", "study_year", "app_use_freq", "straightlining",
                                                 "exclude", "exclude_reason"]
    raw[keep].to_csv(P("data_participant_level.csv"), index=False)
    long.to_csv(P("data_profile_level.csv"), index=False)
    ot = pd.read_sql_query("SELECT ps.study_code, p.condition, ps.open_text FROM post_survey ps "
                           "JOIN participants p USING(study_code) WHERE ps.open_text IS NOT NULL"
                           + ("" if a.include_test else " AND p.is_test=0"), con)
    ot.to_csv(P("open_text_for_coding.csv"), index=False)
    fig_timeline(raw, P("fig4_timeline.png"))

    # ---- 2. descriptive / exploratory ----
    say("\n2. SAMPLE DESCRIPTION (analysed participants)")
    rows = []
    for var in ("gender", "study_year", "app_use_freq", "label_recall"):
        for lvl, sub in df.fillna({var: "Not reported"}).groupby(var):
            r = {"variable": var, "level": lvl}
            for c in (0, 1):
                n = int((sub.condition == c).sum()); N = int((df.condition == c).sum())
                r[COND[c]] = f"{n} ({100 * n / N:.0f}%)" if N else "0"
            rows.append(r)
    samp = pd.DataFrame(rows)
    samp.to_csv(P("tab2_sample.csv"), index=False)
    say(samp.to_string(index=False))
    say("\nScale scores by condition (mean, SD, median, min-max):")
    say(df.groupby("condition_name")[["auth_score", "trust_score"]]
        .agg(["count", "mean", "std", "median", "min", "max"]).round(2).to_string())
    for out in ("auth_score", "trust_score"):
        for c in (0, 1):
            v = df.loc[df.condition == c, out]
            if len(v) >= 3:
                sw = stats.shapiro(v)
                say(f"  {out} {COND[c]}: skew={stats.skew(v):.2f}, Shapiro-Wilk p={sw.pvalue:.3f}")
    fig_distributions(df, P("fig1_distributions.png"))
    fig_profiles(lng, P("fig2_profiles.png"))
    say("\nExploratory behaviour logs by condition (mean, SD):")
    say(df.groupby("condition_name")[["likes", "mean_view_ms"]].agg(["mean", "std"]).round(1).to_string())

    # ---- 3. Objective 2: reliability and construct separation ----
    say("\n3. OBJECTIVE 2 - MEASUREMENT")
    items = []
    for i in range(1, 7):
        v = df[f"item{i}"]
        items.append({"item": i, "construct": "AUTH" if i <= 3 else "TRUST", "mean": v.mean(), "sd": v.std(ddof=1)})
    items = pd.DataFrame(items)
    a_auth = cronbach_alpha(df[["item1", "item2", "item3"]])
    a_trust = cronbach_alpha(df[["item4", "item5", "item6"]])
    # alpha at the rating level (participant x profile), a stricter view of the item set
    r_items = pd.read_sql_query("SELECT study_code, profile_id, item_no, value FROM ratings WHERE profile_id NOT LIKE 'R%'", con)
    r_items = r_items[r_items.study_code.isin(df.study_code)].pivot_table(
        index=["study_code", "profile_id"], columns="item_no", values="value")
    a_auth_r = cronbach_alpha(r_items[[1, 2, 3]]); a_trust_r = cronbach_alpha(r_items[[4, 5, 6]])
    items["alpha_participant_level"] = [a_auth] * 3 + [a_trust] * 3
    items["alpha_rating_level"] = [a_auth_r] * 3 + [a_trust_r] * 3
    items.round(3).to_csv(P("tab3_items.csv"), index=False)
    say(items.round(2).to_string(index=False))
    r = stats.pearsonr(df.auth_score, df.trust_score)
    say(f"Authenticity-trust correlation: r = {r.statistic:.2f} [p = {r.pvalue:.3f}], n = {len(df)}")
    say(f"Interpretation guide: alpha >= .70 acceptable; r > .85 would suggest the two scales overlap strongly.")

    # ---- 4. Objective 3: main analysis ----
    say("\n4. OBJECTIVE 3 - MAIN COMPARISON (AI label minus no label)")
    mde = TTestIndPower().solve_power(nobs1=max(2, int((df.condition == 1).sum())), alpha=0.05, power=0.8,
                                      ratio=max(1, int((df.condition == 0).sum())) / max(1, int((df.condition == 1).sum())))
    say(f"Minimum detectable effect with the achieved n (80% power, two-sided .05): d = {mde:.2f}")
    main_tab = comparison_table(df)
    main_tab.round(4).to_csv(P("tab4_main.csv"), index=False)
    for _, m in main_tab.iterrows():
        say(f"{OUT_LABEL[m.outcome]}: label M={m.mean_label:.2f} (SD {m.sd_label:.2f}, n={m.n_label}) vs "
            f"no label M={m.mean_nolabel:.2f} (SD {m.sd_nolabel:.2f}, n={m.n_nolabel})")
        say(f"   diff = {m['diff']:+.2f} [95% CI {m.ci_low:+.2f}, {m.ci_high:+.2f}], Welch t({m.df:.1f}) = {m.t:.2f}, "
            f"p = {m.p:.3f}, Holm p = {m.p_holm:.3f}")
        say(f"   Hedges g = {m.g:+.2f} [{m.g_low:+.2f}, {m.g_high:+.2f}]; Mann-Whitney U = {m.mw_U:.0f}, p = {m.mw_p:.3f}")
        say(f"   Bayesian (prior N(0,1)): {m.bayes_mean:+.2f} [95% CrI {m.bayes_low:+.2f}, {m.bayes_high:+.2f}], "
            f"P(label lowers score) = {m.p_diff_below_0:.2f}")

    # ---- 5. robustness ----
    say("\n5. ROBUSTNESS / SENSITIVITY")
    checks = [("Main analysis", df)]
    if df.mc_correct.notna().any():                                   # v4 two-part check
        checks.append(("Passed manipulation check", df[df.mc_correct == 1]))
    else:
        checks.append(("Label group: only those who noticed label",
                       df[~((df.condition == 1) & (df.label_recall != "yes"))]))
    for src_, sub_ in df.groupby("source"):
        if src_ and len(sub_) >= 4:
            checks.append((f"Source = {src_}", sub_))
    checks.append(("No speed exclusion", raw[~raw.exclude_reason.str.contains("incomplete|missing", na=False)]))
    for thr in (3, 8):
        alt = raw[~raw.exclude_reason.str.contains("incomplete|missing", na=False)]
        alt = alt[~(alt.mean_view_ms < thr * 1000)]
        checks.append((f"Speed threshold {thr} s", alt))
    checks.append(("Straight-liners removed", df[df.straightlining == 0]))
    for pid in sorted(lng.profile_id.unique()):
        sub = lng[lng.profile_id != pid].groupby(["study_code", "condition"])[["auth", "trust"]].mean().reset_index()
        sub = sub.rename(columns={"auth": "auth_score", "trust": "trust_score"})
        checks.append((f"Without profile {pid}", sub))
    rob = []
    for name, d in checks:
        if (d.condition == 0).sum() < 2 or (d.condition == 1).sum() < 2:
            continue
        for out in ("auth_score", "trust_score"):
            c = compare(d, out)
            rob.append({"check": name, **{k: c[k] for k in ("outcome", "n_label", "n_nolabel", "diff",
                                                             "ci_low", "ci_high", "g", "p", "mw_p")}})
    rob = pd.DataFrame(rob)
    rob.round(4).to_csv(P("tab5_robustness.csv"), index=False)
    say(rob.round(2).to_string(index=False))
    # comparable method: mixed model on profile-level data (random intercept per participant, profile fixed)
    try:
        import statsmodels.formula.api as smf
        for out in ("auth", "trust"):
            mm = smf.mixedlm(f"{out} ~ condition + C(profile_id)", lng, groups=lng["study_code"]).fit(reml=True)
            lo, hi = mm.conf_int().loc["condition"]
            say(f"Mixed model ({out}, profile-level, random intercept per participant): "
                f"condition = {mm.params['condition']:+.2f} [{lo:+.2f}, {hi:+.2f}], p = {mm.pvalues['condition']:.3f}")
    except Exception as e:  # small or degenerate samples
        say(f"Mixed model not estimable: {e}")
    fig_robustness(rob, P("fig3_robustness.png"))

    # ---- 5b. exploratory: real stock photos (v4) ----
    if "real_auth_score" not in df and "real_auth" in df and df.real_auth.notna().any():
        say("\n5b. EXPLORATORY: TWO REAL STOCK PHOTOS (shown after the six AI profiles)")
        rr = []
        for out in ("real_auth", "real_trust"):
            c_ = compare(df.dropna(subset=[out]), out)
            rr.append(c_)
            say(f"{out}: label M={c_['mean_label']:.2f} vs no label M={c_['mean_nolabel']:.2f}; "
                f"diff = {c_['diff']:+.2f} [{c_['ci_low']:+.2f}, {c_['ci_high']:+.2f}], p = {c_['p']:.3f}, g = {c_['g']:+.2f}")
        pd.DataFrame(rr).round(4).to_csv(P("tab7_real_photos.csv"), index=False)
        for c in (0, 1):
            sub = df[df.condition == c].dropna(subset=["real_trust"])
            if len(sub) >= 3:
                t_ = stats.ttest_rel(sub.real_trust, sub.trust_score)
                say(f"  {COND[c]}: trust real minus AI photos = {(sub.real_trust - sub.trust_score).mean():+.2f}, "
                    f"paired p = {t_.pvalue:.3f} (n = {len(sub)})")

    # ---- 6. manipulation check ----
    say("\n6. MANIPULATION CHECK (label recall)")
    mc = pd.crosstab(df.condition.map(COND), df.label_recall.fillna("missing"))
    mc.to_csv(P("tab6_manipulation.csv"))
    say(mc.to_string())
    if {"yes"} <= set(df.label_recall.dropna()) and df.condition.nunique() == 2:
        t2 = pd.crosstab(df.condition, df.label_recall == "yes")
        if t2.shape == (2, 2):
            fe = stats.fisher_exact(t2.values)
            say(f"Fisher exact test (said 'yes' by condition): p = {fe.pvalue:.4f}")
    if df.mc_correct.notna().any():
        say("\nTwo-part manipulation check (v4): what did the label say?")
        say(pd.crosstab(df.condition.map(COND), df.label_text.fillna("missing")).to_string())
        acc = df.groupby(df.condition.map(COND)).mc_correct.mean()
        say(f"Correct identification: {acc.round(2).to_dict()}")
        t3 = pd.crosstab(df.condition, df.label_text == "ai")
        if t3.shape == (2, 2):
            say(f"Fisher exact test ('AI-generated image' chosen, by condition): p = {stats.fisher_exact(t3.values).pvalue:.4f}")
    say(f"Label hover/click events in label condition: mean {df.loc[df.condition == 1, 'label_hovers'].mean():.2f} per participant")
    say(f"\nOpen answers available for thematic coding: {len(ot)}")

    with open(P("results.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LINES) + "\n")
    print(f"\nAll outputs written to {a.out}")


if __name__ == "__main__":
    main()
