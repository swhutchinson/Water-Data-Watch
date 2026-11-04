# The nightly run, start to finish: fetch, build the layers, check, plant, measure, record and publish.
# Usage: python -m engine.run              fetch from the live services
#        python -m engine.run --no-fetch   re-use the files already in data/raw
# The run must finish and publish even if a source is down. Its rules then show "Not checked".

# Reads the command line.
import argparse
# Reads and writes the saved fetch record.
import json
# Reads the GitHub Actions run details.
import os
# Times the run.
import time
# Works out the date and the run's name.
from datetime import date, datetime, timezone
# Handles the published folder.
from pathlib import Path
# The in-process database the layers are built in.
import duckdb
# Reads the register's other files.
import yaml
# The engine's own parts.
from engine import points, checks, fetch, issues, layers, ledger, publish, settings, tonight, verdicts

# The columns of each history file, in a fixed order, as the data contract says.
RUN_LOG_COLUMNS = ["run_id", "as_of", "started_utc", "finished_utc", "seconds", "engine_version", "register_rules", "trigger", "results_status", "points_status", "bathing_status", "codes_status", "watch_status", "source_rows", "loaded_rows", "api_calls", "rules_pass", "rules_fail", "rules_review", "rules_not_checked", "rules_no_data", "planted_caught", "planted_tested", "verdict_monthly", "verdict_trend", "verdict_signoff", "verdict_ai", "tracking_since", "github_run"]
# Rule results by run.
RULE_RESULT_COLUMNS = ["run_id", "rule_id", "rule_version", "eligible", "passed", "failed", "excluded", "failed_pct", "status", "note", "exceptions_shown"]
# Verdicts by run.
VERDICT_COLUMNS = ["run_id", "use_id", "dataset_id", "verdict", "gates_failed", "gates_unchecked", "conditions_open", "in_scope", "note"]
# The change ledger, by run.
LEDGER_COLUMNS = ["run_id", "as_of", "is_baseline", "compared", "records_now", "records_new", "records_changed", "records_removed", "lab_status_replaced"]
# The change ledger, by run and month.
LEDGER_MONTH_COLUMNS = ["run_id", "sample_month", "change_kind", "records"]
# The change ledger's record-level detail.
LEDGER_DETAIL_COLUMNS = ["run_id", "as_of", "source_url", "sample_month", "stream", "result_before", "result_now", "change_kind"]
# The publisher's own statements, by run.
WATCH_COLUMNS = ["run_id", "item", "kind", "value", "fingerprint", "previous_fingerprint", "changed", "status", "checked_on"]
# Issues, which are updated rather than only appended.
ISSUE_COLUMNS = ["issue_id", "rule_id", "state", "opened_on", "opened_run", "due_on", "closed_on", "latest_status", "passes_in_a_row", "last_failed_count"]


# Read the run details from the command line.
def read_arguments():
    # A short description for anyone asking for help.
    parser = argparse.ArgumentParser(description="Run the Water Data Watch checks.")
    # Re-use saved files instead of downloading.
    parser.add_argument("--no-fetch", action="store_true", help="re-use the files already in data/raw")
    # Pretend today is another date, for tests and replays.
    parser.add_argument("--as-of", default=None, help="the run's date, as yyyy-mm-dd")
    # Hand back what was given.
    return parser.parse_args()


# Run the whole pipeline. Folders can be overridden, so tests can run it on their own data.
def run(no_fetch=False, as_of=None, raw_dir=settings.RAW, pub_dir=settings.PUB, manifest=None, watch=None):
    # Start the clock.
    began = time.time()
    # The moment the run began, in UTC.
    started = datetime.now(timezone.utc)
    # The run's date.
    as_of = as_of or started.date()
    # The run's name, which appears in every history file.
    run_id = started.strftime("%Y-%m-%dT%H:%MZ")
    # Where history and last night's state live.
    history = pub_dir / "history"
    # How many rows each history file holds now, so a loss can be spotted before publishing.
    history_before = publish.count_history(history)
    # The fingerprints saved by the last run.
    state_file = pub_dir / "state" / "fingerprints.parquet"
    # The fetch step's record is saved beside the raw files.
    record_file = raw_dir / "fetch_record.json"
    # Fetch, unless told to re-use saved files or handed a record directly.
    if manifest is None:
        # Re-use saved files.
        if no_fetch:
            # Read the saved record.
            saved = json.loads(record_file.read_text(encoding="utf-8"))
            # Separate the two parts.
            manifest, watch = saved["manifest"], saved["watch"]
        # Otherwise download everything.
        else:
            # This step never raises for a source being down.
            manifest, watch = fetch.fetch_all(raw_dir, as_of)
            # Save the record, so a later local re-run can use it.
            record_file.write_text(json.dumps({"manifest": manifest, "watch": watch}), encoding="utf-8")
    # An in-memory database: nothing here needs to outlive the run.
    con = duckdb.connect()
    # The run log so far.
    run_log = layers.read_csv_rows(history / "run_log.csv")
    # Tracking began with the first run recorded in the log, or tonight if there isn't one.
    tracking_since = date.fromisoformat(run_log[0]["as_of"]) if run_log else as_of
    # The row count at the last run that read any results, so a sudden fall shows up.
    previous_rows = next((int(row["source_rows"]) for row in reversed(run_log) if int(row["source_rows"] or 0) > 0), None)
    # Every date the engine has run, plus tonight.
    run_dates = {row["as_of"] for row in run_log} | {as_of.isoformat()}
    # The publisher's statements as they stood at the last run.
    previous_watch = {}
    # Later rows overwrite earlier ones, leaving each item's latest fingerprint.
    for row in layers.read_csv_rows(history / "source_watch.csv"):
        # Only a real reading counts.
        if row["fingerprint"]:
            # Keep it.
            previous_watch[row["item"]] = row["fingerprint"]
    # Create empty bronze tables, so everything downstream has something to read.
    layers.create_bronze(con, manifest, watch, previous_watch)
    # Load whatever arrived, and find out which sources are usable.
    available = layers.load_files(con, raw_dir, manifest)
    # The publisher's specification, available if it could be read.
    available["watch_spec"] = any(w["status"] == "ok" for w in watch if w["kind"] == "spec")
    # The licence statements, available if at least one could be read. Those that couldn't are counted as excluded.
    available["watch_licence"] = any(w["status"] == "ok" for w in watch if w["kind"] == "licence")
    # Show which sources are usable.
    print("Sources available:", available, flush=True)
    # Build the silver layer.
    layers.build_silver(con, as_of, run_id, tracking_since, run_dates, previous_rows)
    # The rule register.
    rules = checks.load_rules()
    # Run every rule on the real data.
    results, months, exceptions = checks.run_rules(con, rules, available, run_id)
    # Plant each defect in a private copy, and check that it is caught.
    tests = checks.run_planted(con, rules, results)
    # Find the check on the checker.
    checker = next(r for r in rules if r["id"] == "CHK-01")
    # Fill in its result from the planted tests.
    checks.finish_checker(checker, next(r for r in results if r["rule_id"] == "CHK-01"), tests)
    # Measure how far each problem would move the answer.
    impact = checks.run_impact(con, rules, results)
    # Put open problems in the order to fix them.
    order = checks.fix_order(rules, results, impact)
    # Work out the verdict for each decision.
    uses = verdicts.load_uses()
    # The verdicts and the reasons behind them.
    verdict_rows, reasons = verdicts.compute(uses, rules, results, run_id)
    # Build the gold tables, unless the results are missing, in which case they are simply empty.
    con.execute(layers.read_sql(settings.SQL / "gold.sql"))
    # Compare with the last run's fingerprints.
    ledger_row, ledger_months, ledger_detail = ledger.compare(con, state_file, run_id, as_of, available["results"])
    # Bring the issue list up to date.
    issue_rows = issues.update_issues(layers.read_csv_rows(history / "issues.csv"), rules, results, as_of, run_id)

    # Count the outcomes for the run log.
    counts = {name: sum(r["status"] == name for r in results) for name in (checks.PASS, checks.FAIL, checks.REVIEW, checks.NOT_CHECKED, checks.NO_DATA)}
    # The overall verdict for each use.
    overall = {v["use_id"]: v["verdict"] for v in verdict_rows if v["dataset_id"] == "overall"}
    # The status of each source's download.
    source_status = {name: ("ok" if available.get(name) else "failed") for name in ("results", "points", "bathing", "codes")}
    # A source that stood in with its saved copy says so.
    source_status.update({m["source"]: "copy" for m in manifest if m["status"] == "copy"})
    # The publisher's statements: all read, some read or none read.
    source_status["watch"] = "ok" if watch and all(w["status"] == "ok" for w in watch) else "part" if any(w["status"] == "ok" for w in watch) else "failed"
    # The moment the run finished, in UTC.
    finished = datetime.now(timezone.utc)
    # The run's row in the log.
    log_row = {"run_id": run_id, "as_of": as_of.isoformat(), "started_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"), "finished_utc": finished.strftime("%Y-%m-%dT%H:%M:%SZ"), "seconds": round(time.time() - began), "engine_version": settings.ENGINE_VERSION, "register_rules": len(rules), "trigger": os.environ.get("GITHUB_EVENT_NAME", "local"),
               "results_status": source_status["results"], "points_status": source_status["points"], "bathing_status": source_status["bathing"], "codes_status": source_status["codes"], "watch_status": source_status["watch"],
               "source_rows": sum(m["api_total"] or 0 for m in manifest if m["source"] == "results"), "loaded_rows": con.execute("SELECT count(*) FROM silver.results").fetchone()[0], "api_calls": sum(m["calls"] for m in manifest),
               "rules_pass": counts[checks.PASS], "rules_fail": counts[checks.FAIL], "rules_review": counts[checks.REVIEW], "rules_not_checked": counts[checks.NOT_CHECKED], "rules_no_data": counts[checks.NO_DATA],
               "planted_caught": sum(t["outcome"] == "Caught" for t in tests), "planted_tested": len(tests),
               "verdict_monthly": overall["monthly"], "verdict_trend": overall["trend"], "verdict_signoff": overall["signoff"], "verdict_ai": overall["ai"],
               "tracking_since": tracking_since.isoformat(), "github_run": os.environ.get("GITHUB_RUN_ID", "")}

    # The last run's name, to compare tonight with. Nothing before the first run.
    previous_run = run_log[-1]["run_id"] if run_log else None
    # Last run's rule results, before tonight's are added.
    old_results = layers.read_csv_rows(history / "rule_results.csv")
    # Last run's verdicts, before tonight's are added.
    old_verdicts = layers.read_csv_rows(history / "verdicts.csv")
    # Add tonight to each history file. Each refuses to run if it would lose rows.
    publish.append_history(history / "run_log.csv", [log_row], RUN_LOG_COLUMNS)
    # Rule results by run.
    rule_history = publish.append_history(history / "rule_results.csv", results, RULE_RESULT_COLUMNS)
    # Verdicts by run.
    publish.append_history(history / "verdicts.csv", verdict_rows, VERDICT_COLUMNS)
    # The change ledger, by run.
    publish.append_history(history / "ledger.csv", [ledger_row], LEDGER_COLUMNS)
    # The change ledger, by run and month.
    publish.append_history(history / "ledger_months.csv", ledger_months, LEDGER_MONTH_COLUMNS)
    # The change ledger's record-level detail.
    publish.append_history(history / "ledger_detail.csv", ledger_detail, LEDGER_DETAIL_COLUMNS)
    # What the publisher said about itself tonight, with any change marked.
    watch_rows = [{"run_id": run_id, "item": w["item"], "kind": w["kind"], "value": w["value"], "fingerprint": w["fingerprint"], "previous_fingerprint": previous_watch.get(w["item"], ""), "changed": bool(w["fingerprint"] and previous_watch.get(w["item"]) and w["fingerprint"] != previous_watch[w["item"]]), "status": w["status"], "checked_on": w["checked_on"]} for w in watch]
    # Add them to the history.
    publish.append_history(history / "source_watch.csv", watch_rows, WATCH_COLUMNS)
    # Tonight's copy of the same statements, for the report.
    publish.write_rows(pub_dir / "watch_tonight.csv", watch_rows, WATCH_COLUMNS)
    # Issues are rewritten in full, but their count can only grow.
    issues_before = len(layers.read_csv_rows(history / "issues.csv"))
    # A shrinking issue list means something has gone wrong.
    if len(issue_rows) < issues_before:
        # Stop before anything is lost.
        raise publish.PublishRefused(f"issues.csv would shrink from {issues_before} to {len(issue_rows)} rows")
    # Write the list.
    publish.write_rows(history / "issues.csv", issue_rows, ISSUE_COLUMNS)

    # One flat row per rule, holding all the report shows about it.
    publish.write_rows(pub_dir / "rules_tonight.csv", tonight.flat_rules(rules, results, tests, impact, order, months, rule_history), tonight.RULE_COLUMNS)
    # Tonight's verdicts.
    publish.write_rows(pub_dir / "verdicts_tonight.csv", verdicts.with_names(verdict_rows, uses), verdicts.NAMED_COLUMNS)
    # What changed since the last run.
    publish.write_rows(pub_dir / "changes.csv", tonight.changes_since(previous_run, old_verdicts, verdict_rows, old_results, results, uses, watch_rows), tonight.CHANGE_COLUMNS)
    # The latest rule results' register, with who answers for what. Rule SQL stays in the repository, and the report links to it.
    register_rows = [{key: ", ".join(rule[key]) if key == "fields" else rule.get(key) for key in ("id", "version", "title", "why", "dataset", "fields", "dimension", "severity", "fail_above", "review_above", "owner_role", "steward_role", "action", "root_cause", "condition")} for rule in rules]
    # Write the register.
    publish.write_rows(pub_dir / "rule_register.csv", register_rows, ["id", "version", "title", "why", "dataset", "fields", "dimension", "severity", "fail_above", "review_above", "owner_role", "steward_role", "action", "root_cause", "condition"])
    # The grid of rules by sample month.
    publish.write_rows(pub_dir / "rule_month.csv", months, ["rule_id", "sample_month", "eligible", "failed", "status"])
    # The failed records, with each point's published name and never its raw label.
    names = dict(con.execute("SELECT point_id, display_name FROM gold.points_public").fetchall())
    # Add the name to each record that has a point.
    for row in exceptions:
        # A withheld label shows the point's type and code.
        row["point_name"] = names.get(row["point_id"], "")
        # What the table shows as the record: the point's name, or the rule's own reference unless that is only a web address.
        row["where_label"] = row["point_name"] or ("" if str(row["record_ref"]).startswith("http") else row["record_ref"])
        # The month as the table shows it. A rule about a whole list has no month, and says so.
        row["month_label"] = row["sample_month"] or "Whole list"
    # Write them.
    publish.write_rows(pub_dir / "exceptions.csv", exceptions, ["rule_id", "record_ref", "point_id", "point_name", "where_label", "sample_month", "month_label", "detail", "source_url"])
    # The planted defect results.
    publish.write_rows(pub_dir / "rule_tests.csv", tests, ["rule_id", "failed_before", "failed_after", "caught", "outcome", "note"])
    # The "does it change the answer?" results.
    publish.write_rows(pub_dir / "impact.csv", impact, ["rule_id", "figure", "careful", "careless", "unit", "effect_pct", "measured"])
    # The order to fix things in.
    publish.write_rows(pub_dir / "fix_order.csv", order, ["rule_id", "fix_rank"])
    # The reasons behind each verdict.
    publish.write_rows(pub_dir / "verdict_reasons.csv", reasons, ["use_id", "dataset_id", "rule_id", "role", "status", "matters", "condition"])
    # The decisions on the board.
    publish.write_rows(pub_dir / "uses.csv", [{"use_id": use["id"], "use_order": use["order"], "use_name": use["name"], "question": use["question"], "needs": use["needs"]} for use in uses], ["use_id", "use_order", "use_name", "question", "needs"])
    # The passports of the datasets.
    datasets = yaml.safe_load((settings.RULES / "datasets.yaml").read_text(encoding="utf-8"))
    # Write them, with clear names for the key, order and name columns.
    publish.write_rows(pub_dir / "datasets.csv", [{**d, "dataset_id": d["id"], "dataset_order": d["order"], "dataset_name": d["name"]} for d in datasets], ["dataset_id", "dataset_order", "dataset_name", "source", "address", "licence", "attribution", "owner_role", "steward_role", "refresh", "coverage", "safe_for", "how_to_use", "known_issues"])
    # The decisions people have recorded. These are illustrative, and the page says so.
    publish.write_rows(pub_dir / "decisions.csv", issues.load_decisions(), ["rule", "decided_on", "decision", "decided_by", "accepted", "review_on"])
    # What was asked of each source and what came back.
    publish.write_rows(pub_dir / "manifest.csv", [dict(zip(["source", "window_start", "window_end", "api_total", "rows_received", "calls", "seconds", "status", "error", "taken_on"], row)) for row in con.execute("SELECT * FROM bronze.manifest").fetchall()], ["source", "window_start", "window_end", "api_total", "rows_received", "calls", "seconds", "status", "error", "taken_on"])
    # The gold tables, one file each.
    for table, name, source in [("gold.month_summary", "month_summary", "results"), ("gold.stream_month", "stream_month", "results"), ("gold.months", "months", "results"), ("gold.freshness", "freshness", "results"), ("gold.coverage", "coverage", "results"), ("gold.same_data", "same_data", "results"), ("gold.ai_survival", "ai_survival", "results"), ("gold.points_public", "points", "points"), ("gold.map_cells", "map_cells", "points"), ("gold.result_kinds", "result_kinds", "results"), ("gold.control_totals", "control_totals", "results")]:
        # Tonight's copy of this summary would be empty if its source is down, so last night's stays. The run log shows which night it came from.
        if not available[source] and (pub_dir / f"{name}.csv").exists():
            # Leave the file as it is.
            continue
        # Copy it across.
        publish.copy_table(con, table, pub_dir / f"{name}.csv")
    # The point score needs both the results and the point list. If either is down, last night's files stay.
    if (available["results"] and available["points"]) or not (pub_dir / "point_quality.csv").exists():
        # Work out each point's score, its checks and the map's packed rows.
        point_rows, point_checks, point_packs = points.build(con, rules)
        # One row per point.
        publish.write_rows(pub_dir / "point_quality.csv", point_rows, points.POINT_COLUMNS)
        # One row per check that reached a point.
        publish.write_rows(pub_dir / "point_checks.csv", point_checks, points.CHECK_COLUMNS)
        # The rows the map draws from.
        publish.write_rows(pub_dir / "point_packs.csv", point_packs, points.PACK_COLUMNS)
    # Nothing may leave if any history file has lost rows.
    publish.check_history(history, history_before)
    # The last job before anything leaves: sweep everything for personal data. A hit stops the run.
    swept = publish.privacy_sweep(pub_dir)
    # Save tonight's fingerprints for tomorrow, now that everything else has succeeded.
    ledger.save_fingerprints(con, state_file, available["results"])
    # Report the night in the run's log.
    print(f"Run {run_id}: {counts} | planted {log_row['planted_caught']}/{log_row['planted_tested']} | {overall} | {log_row['seconds']} s | {swept} files swept", flush=True)
    # Close the database.
    con.close()
    # Hand back what tests need to inspect.
    return {"results": results, "tests": tests, "verdicts": verdict_rows, "reasons": reasons, "impact": impact, "available": available, "log": log_row, "issues": issue_rows}


# Run when started from the command line.
if __name__ == "__main__":
    # Read the options.
    arguments = read_arguments()
    # Run it.
    run(no_fetch=arguments.no_fetch, as_of=date.fromisoformat(arguments.as_of) if arguments.as_of else None)
