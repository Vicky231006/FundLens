"""Render RESULTS.md and the refresh report strictly from computed numbers."""

from __future__ import annotations

from typing import Any

LIMITATIONS = """\
1. **Survivorship bias.** AMFI's historical files list schemes that exist today under their
   current category; funds that were closed or merged away are largely absent or sit under
   legacy headings that FundLens excludes. Funds that did badly are more likely to have been
   merged away, so the peer groups here are better than the true historical peer groups.
   This most likely biases flagged-fund results *towards looking less bad*; the size of the
   bias is unknown and has not been measured.
2. **Look-ahead control.** Flags at month-end t use only NAVs dated <= t. Categories are AMFI's
   *current* labels applied to all history (AMFI re-labels history), so a fund's category at
   time t may differ from its category then. Forward returns are used only for evaluation.
3. **Overlapping windows.** 12-month forward windows overlap for consecutive month-ends, so
   observations are strongly dependent. Confidence intervals use fund-clustered and
   month-block bootstraps; neither fully removes the dependence, and common market shocks
   inside a short evaluation window make the effective sample size much smaller than the
   number of observations.
4. **Short out-of-sample window.** The Direct-plan series only starts in 2013, so its
   out-of-sample period is a few years covering few distinct market regimes.
5. **Plan types are never mixed.** DIRECT and REGULAR plans are screened and evaluated
   separately. The REGULAR run extends the history back to 2006 as a sensitivity analysis;
   it is not the PRD's primary specification (Direct growth plans).
6. **Parameter search.** Parameters are tuned on the training period only, but the grid has
   {n_grid} candidates; some selection optimism remains in the training numbers. Test-period
   numbers are reported for BOTH the default and the tuned parameters.
7. **Not investment advice.** A flag marks a fund for analyst review. It is not a
   recommendation to buy, sell or hold anything. This project has no clients, accounts, AUM
   or users, and is not production-grade or GIPS-compliant.
"""


def _pct(x: float | None, digits: int = 2) -> str:
    return "n/a" if x is None or x != x else f"{x * 100:.{digits}f}%"


def _ci(c: dict[str, float] | None) -> str:
    if not c or c.get("ci_lower") != c.get("ci_lower"):
        return "n/a"
    return f"[{_pct(c['ci_lower'])}, {_pct(c['ci_upper'])}]"


def _plan_section(plan: str, bt: dict[str, Any]) -> str:
    d = bt["dataset"]
    primary = plan == "DIRECT"
    title = f"{plan.title()} plans (Growth)" + (
        " - primary specification" if primary else " - extended-history sensitivity"
    )
    default_p, tuned_p = bt["default_params"], bt["tuned_params"]

    def params_line(p: dict[str, Any]) -> str:
        return (
            f"k={p['k']}, return-rank threshold={p['return_rank_threshold']}, "
            f"drawdown worse than median required={p['require_drawdown_worse_than_median']}, "
            f"min peers={p['min_peers']}"
        )

    out = [f"## {title}\n"]
    out.append(
        f"- **Dataset:** {d['n_schemes_with_metrics']} schemes, {d['n_scheme_month_rows']:,} scheme-month "
        f"rows with metrics, {d['n_categories']} categories.\n"
        f"- **Screenable timeline:** {d['first_screenable_month_end']} to {d['last_screenable_month_end']} "
        f"({d['screenable_month_ends']} month-ends).\n"
        f"- **Split (first {int(bt['config']['train_fraction'] * 100)}% / rest):** {d['train_month_ends']} train "
        f"month-ends, {d['test_month_ends']} test month-ends; test starts {d['test_start']}. Training "
        f"labels whose 12-month window ends on/after that date are purged.\n"
        f"- **Default parameters:** {params_line(default_p)}.\n"
        f"- **Parameters chosen on the training period:** {params_line(tuned_p)}.\n"
    )

    for name in ("default", "tuned"):
        test = bt["periods"][name]["test"]
        if not test.get("n_obs"):
            out.append(f"### Out-of-sample ({name} parameters)\n\nNo evaluable observations.\n")
            continue
        scr, b1 = test["screen"], test["baseline_bottom_quartile_1y"]
        fci, mci = test["ci_fund_cluster_bootstrap"], test["ci_month_block_bootstrap"]
        perm = test["permutation_random_flags_screen"]
        perm_b1 = test["permutation_random_flags_baseline1"]
        out.append(f"### Out-of-sample, {name} parameters\n")
        out.append(
            f"Evaluation period (month-ends): {test['first_month_end']} to {test['last_month_end']}; "
            f"{test['n_obs']:,} eligible fund-month observations from {test['n_funds']} funds over "
            f"{test['n_month_ends']} month-ends. y = fund's forward 12-month return minus the category "
            f"median forward 12-month return; **lower y among flagged funds = flags identified later "
            f"underperformers**.\n"
        )
        out.append(
            "| Method | Flagged obs | Funds | Mean y | 95% CI (fund-cluster bootstrap) | 95% CI (month-block bootstrap) | Share y<0 |\n"
            "|---|---:|---:|---:|---|---|---:|"
        )
        out.append(
            f"| FundLens screen | {scr['n_flag_obs']:,} | {scr['n_funds']} | {_pct(scr['mean_y'])} | "
            f"{_ci(fci['screen'])} | {_ci(mci['screen'])} | {_pct(scr['share_underperforming_peer_median'], 1)} |"
        )
        out.append(
            f"| Baseline 1: bottom-quartile 1-year return | {b1['n_flag_obs']:,} | {b1['n_funds']} | "
            f"{_pct(b1['mean_y'])} | {_ci(fci['baseline_bottom_quartile_1y'])} | "
            f"{_ci(mci['baseline_bottom_quartile_1y'])} | {_pct(b1['share_underperforming_peer_median'], 1)} |"
        )
        if perm:
            out.append(
                f"| Baseline 2: random flags, same per-(month, category) counts ({perm['n_permutations']} permutations) | "
                f"{scr['n_flag_obs']:,} | - | {_pct(perm['random_flags_mean_y'])} | "
                f"[{_pct(perm['random_flags_ci_lower'])}, {_pct(perm['random_flags_ci_upper'])}] (permutation 95% range) | - | - |"
            )
        out.append(
            f"| All eligible observations | {test['n_obs']:,} | {test['n_funds']} | {_pct(test['mean_y_all_eligible'])} | {_ci(fci['all_eligible'])} | {_ci(mci['all_eligible'])} | - |\n"
        )
        diff_key = "screen - baseline_bottom_quartile_1y"
        out.append(
            f"- Screen minus Baseline 1 (mean y): {_pct(fci[diff_key]['estimate'])}, "
            f"fund-cluster 95% CI {_ci(fci[diff_key])}, month-block 95% CI {_ci(mci[diff_key])}."
        )
        if perm:
            out.append(
                f"- Permutation test, screen vs random flags: one-sided p = "
                f"{perm['p_value_flagged_worse_than_random']:.4f} (probability that random flags do at "
                f"least as badly as the screen)."
            )
        if perm_b1:
            out.append(
                f"- Permutation test, Baseline 1 vs random flags: one-sided p = "
                f"{perm_b1['p_value_flagged_worse_than_random']:.4f}."
            )
        out.append(f"\n**Interpretation:** {test['interpretation']}\n")

    tr = bt["periods"]["tuned"]["train"]
    if tr.get("n_obs"):
        out.append(
            f"### Training period (for transparency; selection-optimistic)\n\n"
            f"Tuned parameters on {tr['n_obs']:,} labelled training observations "
            f"({tr['first_month_end']} to {tr['last_month_end']}): flagged mean y = "
            f"{_pct(tr['screen']['mean_y'])} over {tr['screen']['n_flag_obs']:,} flagged observations.\n"
        )
    return "\n".join(out)


def render_results_md(report: dict[str, Any]) -> str:
    snap = report["snapshot"]
    n_grid = len(next(iter(report["backtests"].values()))["tuning_trials"])
    dq_rows = report.get("dq_summary", [])
    open_by_sev: dict[str, int] = {}
    for _cat, sev, status, n in dq_rows:
        if status in ("OPEN", "ACKNOWLEDGED"):
            open_by_sev[sev] = open_by_sev.get(sev, 0) + n

    parts = [
        "# RESULTS\n",
        "> Generated by `make reproduce` (`fundlens pipeline`). Every number below is computed from the "
        "database at generation time; nothing is typed by hand. FundLens is an analyst-support tool: "
        "a flag marks a fund for research review and is **not** an investment recommendation.\n",
        "## Dataset\n",
        f"- Source: AMFI historical NAV download (see `docs/DATA_CARD.md`). Source files registered: "
        f"{snap['source_files']}; SHA-256 fingerprint of the file set: `{snap['source_files_fingerprint_sha256'][:16]}...`.\n"
        f"- NAV rows loaded: {snap['nav_rows']:,}; schemes: {snap['schemes']:,} "
        f"({', '.join(f'{k}: {v}' for k, v in snap['schemes_by_plan'].items())}).\n"
        f"- NAV date range: {snap['first_nav_date']} to {snap['last_nav_date']}.\n"
        f"- Last successful ingestion: {snap['last_successful_ingestion']}.\n"
        f"- Open data-quality issues by severity: {open_by_sev or 'none'}.\n"
        f"- Pipeline runtime (DQ + marts + screening + backtests): {report['pipeline_seconds']} s.\n",
    ]
    for plan in ("DIRECT", "REGULAR"):
        if plan in report["backtests"]:
            parts.append(_plan_section(plan, report["backtests"][plan]))
    parts.append("## Limitations and disclosures\n\n" + LIMITATIONS.format(n_grid=n_grid))
    return "\n".join(parts)


def render_refresh_report(report: dict[str, Any]) -> str:
    snap = report["snapshot"]
    lines = [
        "# FundLens refresh report\n",
        f"- Started: {report['started_at']}",
        f"- Runtime: {report['pipeline_seconds']} s",
        f"- Latest NAV date: {snap['last_nav_date']}",
        f"- NAV rows: {snap['nav_rows']:,}; schemes: {snap['schemes']:,}",
        f"- Source files: {snap['source_files']}",
        "",
        "## Data-quality issues detected this run\n",
        "| Check | Detected |",
        "|---|---:|",
    ]
    lines += [f"| {k} | {v} |" for k, v in report["dq_detected"].items()]
    lines += ["", "## Marts build (seconds)\n", "| File | Seconds |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in report["marts_seconds"].items()]
    lines += [
        "",
        "Critical data-quality gate: **passed** (the pipeline stops before this point otherwise).",
        "",
    ]
    return "\n".join(lines)
