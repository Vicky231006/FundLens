# FundLens - User Stories

These stories describe planned behaviour for three roles: **Research Analyst**, **Desk Lead**
and **Data Operations**. They trace to the functional requirements FR-A1 to FR-A9 in
`docs/BRD.md`. The roles frame requirements only; FundLens makes no claim of real users.

**Status of the stories.** None of these stories is accepted yet. Only parts of FR-A1
(ingestion) are partly implemented, and these stories include one that depends on it
(US-DO-06). Delivery status per story is tracked in `docs/JIRA_BACKLOG.md`.

**Important framing.** A FundLens flag means "flagged for further research review". It is not
a recommendation to buy, sell or switch any fund.

**Priority** uses MoSCoW: Must, Should, Could, Won't (this release).

## Index

| ID | Role | Title | FR | Priority |
|---|---|---|---|---|
| US-RA-01 | Research Analyst | Review flagged funds with filters | FR-A5, FR-A7 | Must |
| US-RA-02 | Research Analyst | Export the flagged-fund list to CSV | FR-A7 | Must |
| US-RA-03 | Research Analyst | See why a fund was flagged | FR-A5, FR-A7 | Must |
| US-RA-04 | Research Analyst | Drill down into a single fund | FR-A4, FR-A7 | Must |
| US-RA-05 | Research Analyst | Compare a fund with its category | FR-A4, FR-A7 | Should |
| US-RA-06 | Research Analyst | See when the data was last refreshed | FR-A7, FR-A8 | Must |
| US-RA-07 | Research Analyst | See a disclosure that flags are not advice | FR-A5, FR-A7 | Must |
| US-RA-08 | Research Analyst | Use a library of ad-hoc SQL queries | FR-A9 | Should |
| US-DL-01 | Desk Lead | Configure k and thresholds | FR-A5 | Must |
| US-DL-02 | Desk Lead | See backtest results against baselines with CIs | FR-A6, FR-A7 | Must |
| US-DL-03 | Desk Lead | See backtest limitations next to results | FR-A6, FR-A7 | Must |
| US-DL-04 | Desk Lead | Confirm flags use no future information | FR-A5, FR-A6 | Must |
| US-DL-05 | Desk Lead | See refresh status and data freshness | FR-A7, FR-A8 | Should |
| US-DL-06 | Desk Lead | See flag counts by category and month-end | FR-A5, FR-A7 | Could |
| US-DO-01 | Data Operations | View a data-quality dashboard | FR-A3, FR-A7 | Must |
| US-DO-02 | Data Operations | Resolve data issues through a workflow | FR-A3 | Must |
| US-DO-03 | Data Operations | Have critical DQ failures block the pipeline | FR-A3, FR-A8 | Must |
| US-DO-04 | Data Operations | Run a monthly refresh that fails visibly | FR-A8 | Must |
| US-DO-05 | Data Operations | Review scheme rename/merge mappings | FR-A2 | Must |
| US-DO-06 | Data Operations | Re-run ingestion without duplicates | FR-A1 | Must |
| US-DO-07 | Data Operations | Receive a refresh report | FR-A8 | Should |
| US-DO-08 | Data Operations | Keep questionable observations rather than deleting them | FR-A3 | Should |

---

## Research Analyst

### US-RA-01 - Review flagged funds with filters

- **User role:** Research Analyst
- **Capability:** As a research analyst, I want to see the list of funds flagged at a chosen
  month-end and filter it by category (and plan type) so that I can focus my review on the
  peer group I cover.
- **Business value:** Gives every analyst the same starting list produced by the same rule,
  replacing individually built spreadsheet screens.
- **Acceptance criteria:**
  1. Given a refreshed dataset, when I open the fund review screen, then I see the funds
     flagged at the latest available month-end, each with category, 3-year return, drawdown and
     number of consecutive flagged month-ends.
  2. Given the review screen, when I select a category filter, then only funds in that
     category are listed and the displayed count matches the filtered rows.
  3. Given the review screen, when I select an earlier month-end, then the list shows the flags
     as they were computed for that month-end only (using data available up to it).
  4. Given a category and month-end with no flagged funds, then the screen shows an explicit
     "no funds flagged" message instead of an empty or broken table.
- **Linked FR:** FR-A5, FR-A7
- **Priority:** Must

### US-RA-02 - Export the flagged-fund list to CSV

- **User role:** Research Analyst
- **Capability:** As a research analyst, I want to export the currently filtered review list to
  CSV so that I can use it in my own write-ups and share it with colleagues.
- **Business value:** Fits the output into existing analyst documents without retyping, and
  keeps the exported numbers identical to the dashboard.
- **Acceptance criteria:**
  1. Given a filtered review list, when I click export, then a CSV downloads containing exactly
     the rows and columns shown on screen.
  2. The CSV includes the month-end, the trigger reasons, and the dataset's last-refresh date.
  3. The CSV includes the research-review disclosure (as a header row or a companion line).
  4. Given a list with funds whose names contain commas or quotes, then the CSV opens correctly
     with each fund in one row (proper quoting).
- **Linked FR:** FR-A7
- **Priority:** Must

### US-RA-03 - See why a fund was flagged

- **User role:** Research Analyst
- **Capability:** As a research analyst, I want each flag to list the conditions that
  triggered it, with the actual values, so that I can judge whether the flag deserves a
  closer look and explain it to others.
- **Business value:** Explainability: no flag exists without a recorded reason, which supports
  review by desk leads and audit.
- **Acceptance criteria:**
  1. Given a flagged fund, then the review screen shows the trigger reasons: the 3-year return
     and its category quartile, the drawdown versus the category median, and the number of
     consecutive month-ends (k) satisfied.
  2. Given two flagged funds with different triggers (for example different persistence
     length), then each shows its own distinct reason text.
  3. Given any flag in the database, then its explanation field is non-empty (checked by an
     automated test).
  4. Reason values shown on screen equal those in the underlying SQL output for the same
     fund and month-end.
- **Linked FR:** FR-A5, FR-A7
- **Priority:** Must

### US-RA-04 - Drill down into a single fund

- **User role:** Research Analyst
- **Capability:** As a research analyst, I want a fund drilldown showing NAV history, rolling
  returns, volatility, drawdown and a timeline of past flags so that I can see how the fund
  reached its current position.
- **Business value:** Lets the analyst move from "flagged" to an evidence-based view of the
  fund's behaviour in one place.
- **Acceptance criteria:**
  1. Given a fund selection, then charts show historical NAV, rolling 1/3/5-year CAGR,
     annualised volatility and drawdown over time.
  2. Given a fund with fewer than 3 years of history, then the 3-year chart shows "insufficient
     history" for the missing period rather than a plotted value.
  3. Given a fund that has been flagged in the past, then a flag timeline shows each month-end
     where it was flagged.
  4. Sampled values on the drilldown equal the corresponding SQL view output.
- **Linked FR:** FR-A4, FR-A7
- **Priority:** Must

### US-RA-05 - Compare a fund with its category

- **User role:** Research Analyst
- **Capability:** As a research analyst, I want to compare a fund's metrics and percentile
  rank against its category (median and quartiles) over time so that I can judge relative
  performance rather than absolute performance.
- **Business value:** Relative-to-peer context is the basis of the review rule, so analysts
  need to see it directly.
- **Acceptance criteria:**
  1. Given a fund, then the drilldown shows the fund's 3-year return alongside the category
     median and quartile bounds at each month-end.
  2. Given a fund, then its category percentile rank at each month-end is displayed.
  3. Comparisons only include funds in the same category and the same plan type.
  4. The number of peer funds used at the selected month-end is displayed.
- **Linked FR:** FR-A4, FR-A7
- **Priority:** Should

### US-RA-06 - See when the data was last refreshed

- **User role:** Research Analyst
- **Capability:** As a research analyst, I want the last successful refresh date shown on
  every dashboard page so that I know how current the information is before relying on it.
- **Business value:** Prevents decisions based on stale data and makes the output's age explicit.
- **Acceptance criteria:**
  1. Given any dashboard page, then the last successful refresh date is visible without
     scrolling or clicking.
  2. Given a failed refresh after a successful one, then the page still shows the date of the
     last *successful* refresh (not the failed attempt).
  3. Given a data-quality page, then it additionally shows the most recent NAV date loaded.
- **Linked FR:** FR-A7, FR-A8
- **Priority:** Must

### US-RA-07 - See a disclosure that flags are not advice

- **User role:** Research Analyst
- **Capability:** As a research analyst, I want a clear disclosure on the dashboard and in
  exports stating that flags are research-review indicators, not investment advice, and
  listing the data limitations, so that results are not misread.
- **Business value:** Reduces the risk of misuse of flags as buy/sell signals and states
  data limitations (survivorship, data gaps) alongside the results.
- **Acceptance criteria:**
  1. Given any dashboard page, then the disclosure is visible and states that a flag means
     "flagged for further research review" and is not a recommendation.
  2. The disclosure lists the main data limitations (source, survivorship bias, data gaps).
  3. No dashboard text uses the words "buy", "sell" or "recommended" to describe a flagged fund
     (checked by an automated text scan of dashboard strings).
- **Linked FR:** FR-A5, FR-A7
- **Priority:** Must

### US-RA-08 - Use a library of ad-hoc SQL queries

- **User role:** Research Analyst
- **Capability:** As a research analyst, I want a library of documented SQL queries for common
  questions so that I can investigate funds and data beyond what the dashboard shows.
- **Business value:** Supports exploratory analysis and demonstrates SQL skills (CTEs, window
  functions, ranking, time series, DQ investigation) on the real schema.
- **Acceptance criteria:**
  1. Given the repository, then `sql/adhoc/` contains at least ten `.sql` files.
  2. Each file begins with a comment stating the business question it answers.
  3. Each file executes without error against the actual schema (automated check).
  4. Between them, the files use CTEs, window functions, aggregations, joins and ranking, and
     include at least one data-quality investigation and one performance comparison.
- **Linked FR:** FR-A9
- **Priority:** Should

---

## Desk Lead

### US-DL-01 - Configure k and thresholds

- **User role:** Desk Lead
- **Capability:** As a desk lead, I want to change the persistence length k and the screening
  thresholds in configuration so that I can adjust how sensitive the review flags are.
- **Business value:** Lets the desk set review workload and sensitivity deliberately, with
  recorded parameters rather than ad-hoc spreadsheet edits.
- **Acceptance criteria:**
  1. Given a configuration file, then k, the return-quartile cut-off and the drawdown
     comparison threshold are settable without code changes.
  2. Given k is increased, then the set of flagged funds at a month-end is a subset of the
     set flagged with the smaller k (automated test).
  3. Each flag output records the parameter values used to produce it.
  4. Invalid values (for example k < 1 or a quartile outside 0-1) are rejected with a clear
     error message.
  5. Parameter tuning uses only the training period (see US-DL-04).
- **Linked FR:** FR-A5
- **Priority:** Must

### US-DL-02 - See backtest results against baselines with confidence intervals

- **User role:** Desk Lead
- **Capability:** As a desk lead, I want to see out-of-sample backtest results for the flag
  rule next to the two baselines, with 95% confidence intervals, dataset size and evaluation
  period, so that I can judge whether the rule has shown any value.
- **Business value:** Replaces unverified belief in a screening rule with evidence, including
  an honest "inconclusive" or "negative" result if that is what the data shows.
- **Acceptance criteria:**
  1. Given the backtesting page, then it shows the mean excess forward 12-month return
     (fund minus category median) for flagged funds, for Baseline 1 (bottom-quartile 1-year
     return) and for Baseline 2 (random flags at the same rate, permutation-based).
  2. Each result shows a 95% confidence interval from the fund-clustered block bootstrap.
  3. Each result shows dataset size (funds and fund-month observations) and the out-of-sample
     evaluation period.
  4. Given results whose confidence interval includes zero or overlaps a baseline, then the
     page labels them inconclusive rather than describing them as predictive.
- **Linked FR:** FR-A6, FR-A7
- **Priority:** Must

### US-DL-03 - See backtest limitations next to results

- **User role:** Desk Lead
- **Capability:** As a desk lead, I want the backtesting page to state its limitations
  (survivorship bias, missing closed or merged schemes, overlapping windows, data gaps) next to
  the numbers so that I do not over-interpret them.
- **Business value:** Honest reporting protects the desk from presenting a biased evaluation
  as proof.
- **Acceptance criteria:**
  1. Given the backtesting page, then a limitations section is visible on the same page as the
     results.
  2. The section names survivorship bias and the exclusion of closed or merged schemes.
  3. The section explains how overlapping forward-return windows are handled (block bootstrap
     clustered by fund) and states that results do not demonstrate predictive ability on
     their own.
  4. The section states the train/test split (about 60% / 40%) and the dates it produced.
- **Linked FR:** FR-A6, FR-A7
- **Priority:** Must

### US-DL-04 - Confirm flags use no future information

- **User role:** Desk Lead
- **Capability:** As a desk lead, I want assurance that historical flags and parameter tuning
  use only information available at each month-end so that backtest results are not
  contaminated by look-ahead bias.
- **Business value:** Credibility of the evaluation depends on avoiding look-ahead bias.
- **Acceptance criteria:**
  1. Given a month-end t, when NAV data after t is altered in a test database, then flags and
     metrics for t are unchanged (automated test).
  2. Given the tuning process, then only observations in the training period (about the first
     60% of the timeline) are used, and the split date is recorded in the results.
  3. The methodology section of the backtesting page describes the as-of rule in plain
     language.
- **Linked FR:** FR-A5, FR-A6
- **Priority:** Must

### US-DL-05 - See refresh status and data freshness

- **User role:** Desk Lead
- **Capability:** As a desk lead, I want to see the last successful refresh date and whether
  the latest scheduled refresh succeeded so that I know whether the information in front of me
  is current.
- **Business value:** Gives oversight of data currency without asking the developer.
- **Acceptance criteria:**
  1. Given the dashboard, then the last successful refresh date is visible on every page.
  2. Given a failed latest refresh, then the dashboard shows a visible warning that the
     displayed data is from an earlier refresh.
  3. The warning gives the date of the last successful refresh.
- **Linked FR:** FR-A7, FR-A8
- **Priority:** Should

### US-DL-06 - See flag counts by category and month-end

- **User role:** Desk Lead
- **Capability:** As a desk lead, I want a summary of how many funds are flagged in each
  category per month-end so that I can see review workload and unusual spikes.
- **Business value:** Supports workload planning and helps spot when a rule becomes too loose
  or too tight.
- **Acceptance criteria:**
  1. Given the review screen, then a summary shows flagged count and eligible-fund count per
     category for the selected month-end.
  2. Counts reconcile with the detailed list (sum of flagged rows equals the summary count).
  3. Categories with too few funds to form quartiles show "insufficient peers" rather than
     flags.
- **Linked FR:** FR-A5, FR-A7
- **Priority:** Could

---

## Data Operations

### US-DO-01 - View a data-quality dashboard

- **User role:** Data Operations
- **Capability:** As a data operations user, I want a data-quality page showing issue counts
  by category, severity, resolution status and affected schemes, plus the last successful
  ingestion, so that I can see where data needs attention.
- **Business value:** Makes the state of the data visible and helps prioritise work.
- **Acceptance criteria:**
  1. Given the data-quality page, then I can see issue counts broken down by issue category,
     severity and resolution status.
  2. Given an issue category, when I select it, then the affected schemes are listed.
  3. The page shows the last successful ingestion time and the latest NAV date loaded.
  4. Totals on the page equal a `COUNT(*)` on `dq_issue` for the same filters (automated
     check).
- **Linked FR:** FR-A3, FR-A7
- **Priority:** Must

### US-DO-02 - Resolve data issues through a workflow

- **User role:** Data Operations
- **Capability:** As a data operations user, I want to move each data issue through resolution
  states (for example open, investigating, resolved, accepted-as-is) with a note so that
  there is a record of how each was handled.
- **Business value:** Gives an audit trail of data decisions instead of untracked spreadsheet
  fixes.
- **Acceptance criteria:**
  1. Given an open issue, when I change its status and add a note, then the `dq_issue` row
     records the new status, note, and timestamp.
  2. Given an issue marked resolved or accepted, then the original observation and
     explanation remain stored and unchanged.
  3. Given an invalid status value, then the change is rejected.
  4. Given a re-run of DQ checks that detects the same underlying problem, then no duplicate
     open issue is created.
  5. Each persisted issue contains the issue id, scheme id (where applicable), category,
     detection timestamp, severity, relevant observation, explanation and resolution status.
- **Linked FR:** FR-A3
- **Priority:** Must

### US-DO-03 - Have critical DQ failures block the pipeline

- **User role:** Data Operations
- **Capability:** As a data operations user, I want critical data-quality issues to stop the
  analytics pipeline so that flags and metrics are never published from data known to be
  unreliable.
- **Business value:** Avoids silently wrong results reaching analysts.
- **Acceptance criteria:**
  1. Given the DQ checks find at least one critical issue (for example a non-positive NAV or a
     duplicate scheme-date pair), when the pipeline runs, then it exits with a non-zero status
     before metrics are refreshed.
  2. Given a blocked run, then the critical issues are listed in the log and the refresh
     report.
  3. Given only non-critical issues, then the pipeline continues and reports the issue counts.
  4. The severity classification of each check is documented.
- **Linked FR:** FR-A3, FR-A8
- **Priority:** Must

### US-DO-04 - Run a monthly refresh that fails visibly

- **User role:** Data Operations
- **Capability:** As a data operations user, I want the refresh to run automatically each
  month on GitHub Actions and to fail visibly when something is wrong so that I do not have to
  run it by hand or discover problems later.
- **Business value:** Removes repeated manual effort and ensures failures are noticed.
- **Acceptance criteria:**
  1. Given the repository, then a workflow `monthly_refresh.yml` runs on a monthly schedule and
     can also be triggered manually.
  2. The workflow retrieves the latest NAV, validates, loads, runs DQ checks, refreshes the
     analytical outputs and generates a refresh report.
  3. Given a critical DQ failure or a download failure, then the workflow run ends in a failed
     state (red), not a silent success.
  4. Database credentials come from repository secrets; none appear in the repository or logs.
  5. The hosting strategy for the remote PostgreSQL database is documented.
- **Linked FR:** FR-A8
- **Priority:** Must

### US-DO-05 - Review scheme rename/merge mappings

- **User role:** Data Operations
- **Capability:** As a data operations user, I want to review and approve proposed scheme
  rename and merger mappings so that a fund's history is continuous only when a human has
  confirmed it is the same scheme.
- **Business value:** Prevents false continuity (merging different funds that look alike) and
  broken history (treating a renamed fund as a new fund).
- **Acceptance criteria:**
  1. Given a scheme whose name changes between files but whose AMFI scheme code is the same,
     then the change is recorded in the name history for that single scheme.
  2. Given two schemes with similar names but different identifiers, then they are not merged
     automatically (automated test).
  3. Given a merger, then the mapping is stored as an explicit `scheme_mapping` row linking the
     source and target schemes, with an effective date and a status (proposed, approved,
     rejected).
  4. Only approved mappings are used when building continuous histories.
  5. Given the mapping review, then each mapping shows the evidence recorded for it.
- **Linked FR:** FR-A2
- **Priority:** Must

### US-DO-06 - Re-run ingestion without duplicates

- **User role:** Data Operations
- **Capability:** As a data operations user, I want to be able to re-run the same ingestion
  safely so that retries and overlapping date ranges never create duplicate NAV records or lose
  provenance.
- **Business value:** Makes recovery from failed or repeated runs routine and safe.
- **Acceptance criteria:**
  1. Given a completed ingestion, when the same date range is ingested again, then the
     `fact_nav` row count is unchanged.
  2. Each loaded observation traces to an ingestion run and a stored source file (with file
     hash).
  3. The original downloaded files are retained unmodified in the raw data layer.
  4. Given a re-run in which the source reports a different NAV for an existing scheme-date
     pair, then the conflict is recorded (not silently overwritten) and surfaced as a data issue.
- **Linked FR:** FR-A1
- **Priority:** Must

### US-DO-07 - Receive a refresh report

- **User role:** Data Operations
- **Capability:** As a data operations user, I want each refresh to produce a short report
  (rows downloaded, rows loaded, rows rejected, DQ issues by severity, duration, final status)
  so that I can check the run without reading logs.
- **Business value:** Quick operational oversight and an audit trail of each refresh.
- **Acceptance criteria:**
  1. Given a refresh run, then a report file is produced and attached to the workflow run as an
     artefact.
  2. The report includes row counts for downloaded, loaded and rejected records, issue counts
     by severity, the elapsed time, and the final status.
  3. Given a failed run, then the report is still produced and states the failure reason.
- **Linked FR:** FR-A8
- **Priority:** Should

### US-DO-08 - Keep questionable observations rather than deleting them

- **User role:** Data Operations
- **Capability:** As a data operations user, I want DQ checks to flag suspicious observations
  without deleting or altering them so that the original data remains available for
  investigation.
- **Business value:** Preserves auditability and avoids hidden data edits.
- **Acceptance criteria:**
  1. Given an abnormal day-over-day NAV movement, then a `dq_issue` is created and the
     observation remains in the data unchanged.
  2. Given any DQ run, then the row counts of the raw and `fact_nav` tables are unchanged by
     the DQ step (automated test).
  3. Given a flagged observation, then metrics that depend on it are either computed with the
     observation included or marked as affected; they are never silently computed from
     discarded data.
- **Linked FR:** FR-A3
- **Priority:** Should
