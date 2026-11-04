# Data contract

What each layer holds, what the report may rely on, and what happens when something is missing.

## Rules that apply everywhere

- **Missing is never zero.** A gap is counted and shown, never filled silently.
- **Five outcomes for a rule:** Pass, Fail, For review, Not checked, No data. Not checked means the source or the check failed. No data means there was nothing to check. Neither ever counts as a pass.
- **Nothing changes the source data.** The engine reads, checks and reports.
- **Times are clock times as served.** The source states no time zone, so none is assumed and none is converted.
- **Run dates are UTC.** The report's "now" is the refresh time captured once by Power Query, in `RefreshInfo`.
- **Keys are codes, never names.** One name can cover two codes, as rule CON-02 shows.

## Layers

| Layer | Where | Holds |
|---|---|---|
| Raw | `data/raw` on the runner, thrown away after each run | Files exactly as served |
| Bronze | DuckDB, in memory | Everything as text, plus the request record and the publisher's statements |
| Silver | DuckDB, in memory | Parsed results and points, with a stated reading of the result column |
| Gold | DuckDB, then CSV | Small summaries for the report |
| Published | `powerbi-data` branch, one commit, overwritten nightly | The CSV files below |

### The columns the source must provide

`id`, `samplingPoint.notation`, `samplingPoint.prefLabel`, `samplingPoint.easting`, `samplingPoint.northing`, `samplingPoint.region`, `samplingPoint.area`, `samplingPoint.subArea`, `samplingPoint.samplingPointStatus`, `samplingPoint.samplingPointType`, `phenomenonTime`, `samplingPurpose`, `sampleMaterialType`, `determinand.notation`, `determinand.prefLabel`, `result`, `unit`.

A column going missing fails rule SRC-03, and every rule that reads results says Not checked. A new column fails SRC-03 too, until the contract has been updated.

### How the result column is read

| `result_kind` | Example | `result_value` | `limit_value` |
|---|---|---|---|
| `number` | `12.5` | 12.5 | blank |
| `below` | `<0.03` | blank | 0.03 |
| `above` | `>110` | blank | 110 |
| `text` | `Not found` | blank | blank |
| `empty` | | blank | blank |

A below-limit result is a real measurement meaning "less than this". Its value is left blank in silver, and every figure built from it states one of four methods: dropped, zero, half the limit, or the limit.

## Privacy

- **Sampling point labels leave the engine only as `display_name`.** A label is published only for a river, bathing water, lake or other fresh water, or coast or estuary, and only when it contains no postcode, house number, personal title, domestic word or business word. Otherwise `display_name` is the point's group and code, with a link to the source record.
- **Discharge and site labels are always withheld.**
- **Coordinates are published only for points inside the North West.** Stand-in locations and points outside the region are counted, not drawn.
- **A final sweep reads every published CSV** for postcode and personal title patterns. A match stops the run, and the log names only the file.

## Published files

### History files: these can't be recreated

These only ever grow. If any of them loses rows, or goes missing, the run stops before anything is published. If the branch exists but its run log doesn't, the workflow stops too.

| File | One row per | Columns |
|---|---|---|
| `history/run_log.csv` | run | `run_id, as_of, started_utc, finished_utc, seconds, engine_version, register_rules, trigger, results_status, points_status, bathing_status, codes_status, watch_status, source_rows, loaded_rows, api_calls, rules_pass, rules_fail, rules_review, rules_not_checked, rules_no_data, planted_caught, planted_tested, verdict_monthly, verdict_trend, verdict_signoff, verdict_ai, tracking_since, github_run` |
| `history/rule_results.csv` | rule, run | `run_id, rule_id, rule_version, eligible, passed, failed, excluded, failed_pct, status, note, exceptions_shown` |
| `history/verdicts.csv` | use, dataset, run | `run_id, use_id, dataset_id, verdict, gates_failed, gates_unchecked, conditions_open, in_scope, note` |
| `history/ledger.csv` | run | `run_id, as_of, is_baseline, compared, records_now, records_new, records_changed, records_removed, lab_status_replaced` |
| `history/ledger_months.csv` | run, sample month, kind of change | `run_id, sample_month, change_kind, records` |
| `history/ledger_detail.csv` | changed or removed record, up to 200 a run | `run_id, as_of, source_url, sample_month, stream, result_before, result_now, change_kind` |
| `history/source_watch.csv` | statement, run | `run_id, item, kind, value, fingerprint, previous_fingerprint, changed, status, checked_on` |
| `history/issues.csv` | issue, ever | `issue_id, rule_id, state, opened_on, opened_run, due_on, closed_on, latest_status, passes_in_a_row, last_failed_count` |
| `state/fingerprints.parquet` | record in the window | Not read by the report. Tomorrow's comparison starts from it |

### Tonight's results

| File | One row per | Columns |
|---|---|---|
| `rules_tonight.csv` | rule | Every register column, tonight's result, the planted result, the measured effect, `fix_rank`, and two packed fields: `months_packed` (`month:status:failed:checked`) and `runs_packed` (`day:status:failed`), so a chart reads one row per rule. Status letters: P, F, R, N, D |
| `verdicts_tonight.csv` | use, dataset | `run_id, use_id, use_name, use_phrase, use_order, dataset_id, dataset_name, dataset_order, verdict, gates_failed, gates_unchecked, conditions_open, in_scope, note` |
| `watch_tonight.csv` | statement | The same columns as `history/source_watch.csv`, tonight only |
| `changes.csv` | thing that moved since the last run | `change_order, kind, item, before, after, previous_run` |
| `rule_register.csv` | rule | `id, version, title, why, dataset, fields, dimension, severity, fail_above, review_above, owner_role, steward_role, action, root_cause, condition` |
| `rule_month.csv` | rule, sample month | `rule_id, sample_month, eligible, failed, status` |
| `exceptions.csv` | failed record, up to 500 per rule | `rule_id, record_ref, point_id, point_name, where_label, sample_month, month_label, detail, source_url` |
| `rule_tests.csv` | planted defect | `rule_id, failed_before, failed_after, caught, outcome, note` |
| `impact.csv` | rule with an effect test | `rule_id, figure, careful, careless, unit, effect_pct, measured` |
| `fix_order.csv` | open rule | `rule_id, fix_rank` |
| `verdict_reasons.csv` | rule, use, dataset | `use_id, dataset_id, rule_id, role, status, matters, condition` |
| `uses.csv` | decision | `use_id, use_order, use_name, question, needs` |
| `datasets.csv` | dataset | `dataset_id, dataset_order, dataset_name, source, address, licence, attribution, owner_role, steward_role, refresh, coverage, safe_for, how_to_use, known_issues` |
| `decisions.csv` | recorded decision (illustrative) | `rule, decided_on, decision, decided_by, accepted, review_on` |
| `manifest.csv` | request window | `source, window_start, window_end, api_total, rows_received, calls, seconds, status, error, taken_on`. Status is `ok`, `copy` or `failed` |

### Summaries of the data

When a source is down, these keep their last good contents, and the run log shows which night they came from.

| File | One row per | Columns |
|---|---|---|
| `month_summary.csv` | month, stream, group, kind of result | `sample_month, stream, purpose_group, point_group, result_kind, row_count, samples` |
| `stream_month.csv` | stream, month | `stream, sample_month, samples, row_count, month_part_complete` |
| `months.csv` | month | `sample_month, samples, samples_year_before, is_current_month, is_part_complete` |
| `freshness.csv` | stream | `stream, is_seasonal, sample_dates, newest_date, days_silent, longest_normal_silence, allowed_silence, freshness_status` |
| `coverage.csv` | scope, weekday, hour | `scope, weekday_no, hour_of_day, samples` |
| `same_data.csv` | scenario, area | `det_code, det_name, plain_name, sub_area, method, sample_set, month_set, statistic, figure, rows_used, rows_in_scope, is_ranked_area, area_rank, scenario_key, unit_label` |
| `ai_survival.csv` | step | `step_no, step_name, rows_left, step_note` |
| `points.csv` | sampling point | `point_id, display_name, label_withheld, point_status, point_group, area, sub_area, location_kind, easting, northing, results_in_window, samples_in_window, newest_date` |
| `point_quality.csv` | sampling point that is open or has results | `point_id, point_label, display_name, label_withheld, point_group, area_name, point_status, location_kind, map_e, map_n, results, samples, newest_date, score, band, band_order, flags, rules_flagged, source_url, pack_id`. The score describes the records, never the water. It is illustrative and feeds no verdict |
| `point_checks.csv` | check reaching a point | `point_id, rule_id, checked, flagged, counts_in_score`. Below-limit results (VAL-07) and clock times (AI-04) are listed but never scored |
| `point_packs.csv` | row of the map's data | `pack_id, point_group, area_name, band, band_order, located, points_in_pack, packed`. Each point in `packed` is `east~north~score~results~name`, separated by `\|`, on the National Grid in units of 100 m. A flagged point has a row of its own |
| `map_cells.csv` | 5 km square | `cell_e, cell_n, points_total, points_open, points_open_silent, results_in_window` |
| `result_kinds.csv` | kind of result | `result_kind, row_count, share_pct` |
| `control_totals.csv` | stage | `stage_no, stage_name, row_count` |

## Part-complete months

A month is part-complete while it holds under 70% of the samples of the same month a year earlier, or if it is the current month. That threshold is a choice, stated here and on the page. Results arrive in batches, so the newest months often fill in later.

## Trends

Anything measured by the engine, as opposed to read from the source, can only go back to the first run. The report states "tracking since" that date wherever it appears.
