# Tests for the nightly engine. The honest states are the point: a broken source says "Not checked", and an empty table says "No data".
# Run with: python -m pytest -q

# Reads the files the engine publishes.
import csv
# Copies the clean files, so each test can break its own copy.
import gzip
# Copies folders.
import shutil
# Reads the fixture's rows.
import json
# Dates for the issue lifecycle.
from datetime import date, timedelta
# The test framework.
import pytest
# The in-process database.
import duckdb
# The engine's parts.
from engine import checks, fetch, issues, layers, points, publish, run, settings, tonight, verdicts
# The made-up clean data.
from tests import fixture

# The rules that have nothing to compare on a first run, and so honestly say No data.
FIRST_RUN_NO_DATA = {"SRC-04", "SRC-05"}


# Read a published CSV into a list of dictionaries.
def read_rows(path):
    # Open it as CSV.
    with open(path, newline="", encoding="utf-8") as handle:
        # Every row.
        return list(csv.DictReader(handle))


# Build the clean raw files once, because every test starts from them.
@pytest.fixture(scope="session")
def clean_raw(tmp_path_factory):
    # A folder for this test session.
    raw_dir = tmp_path_factory.mktemp("raw")
    # Write the files, and keep the record of them.
    return raw_dir, fixture.write_clean_raw(raw_dir)


# Run the engine once on clean data with a long history, because many tests read that one result.
@pytest.fixture(scope="session")
def clean_run(clean_raw, tmp_path_factory):
    # The raw files and their record.
    raw_dir, manifest = clean_raw
    # A folder to publish into.
    pub_dir = tmp_path_factory.mktemp("pub")
    # The rows the results source reports.
    source_rows = sum(m["api_total"] for m in manifest if m["source"] == "results")
    # A history of 40 nights, so rules about history have something to read.
    fixture.write_mature_history(pub_dir, source_rows)
    # Run it.
    output = run.run(as_of=fixture.AS_OF, raw_dir=raw_dir, pub_dir=pub_dir, manifest=manifest, watch=fixture.clean_watch())
    # Hand back the result and where it was published.
    return output, pub_dir


# Every rule passes on clean data. A rule that fires here would raise false alarms.
def test_every_rule_stays_quiet_on_clean_data(clean_run):
    # The run's results.
    output, _ = clean_run
    # Anything that isn't a pass, with its detail.
    noisy = {r["rule_id"]: (r["status"], r["failed"], r["eligible"], r["note"]) for r in output["results"] if r["status"] != checks.PASS}
    # There should be nothing.
    assert noisy == {}


# Every planted defect is caught, on clean data as well as real data.
def test_every_rule_catches_its_planted_defect(clean_run):
    # The run's results.
    output, _ = clean_run
    # Any test that wasn't caught, with its reason.
    missed = {t["rule_id"]: (t["outcome"], t["failed_before"], t["failed_after"], t["note"]) for t in output["tests"] if t["outcome"] != "Caught"}
    # There should be nothing.
    assert missed == {}


# Every rule in the register has a planted defect, apart from the check on the checker itself.
def test_every_rule_has_a_planted_defect():
    # Rules with no defect to plant.
    without = [r["id"] for r in checks.load_rules() if not r.get("plant")]
    # Only the check on the checker, which is proved by its own test below.
    assert without == ["CHK-01"]


# Every rule named by a use is in the register, so a typing slip can't silently weaken a gate.
def test_uses_name_only_real_rules():
    # The IDs in the register.
    known = {r["id"] for r in checks.load_rules()}
    # Each use.
    for use in verdicts.load_uses():
        # Its gates and conditions must all exist.
        assert set(use["gates"]) | set(use["conditions"]) <= known


# Everything is fit when everything passes.
def test_clean_data_is_fit_for_everything_in_scope(clean_run):
    # The run's results.
    output, _ = clean_run
    # The verdicts for pairings in scope.
    found = {v["verdict"] for v in output["verdicts"] if v["in_scope"]}
    # All Fit.
    assert found == {verdicts.FIT}


# The check on the checker fails when a rule misses its defect.
def test_checker_fails_when_a_rule_misses_its_defect():
    # A rule that caught its defect, and one that didn't.
    tests = [{"rule_id": "AAA", "outcome": "Caught"}, {"rule_id": "BBB", "outcome": "Missed"}]
    # The checker's register entry.
    rule = {"fail_above": 0, "review_above": 0}
    # Work out its result.
    row = checks.finish_checker(rule, {"status": checks.NOT_CHECKED, "note": ""}, tests)
    # It fails, and names the rule.
    assert row["status"] == checks.FAIL and "BBB" in row["note"]


# The check on the checker says Not checked when nothing could be tested, and never passes on nothing.
def test_checker_says_not_checked_when_nothing_ran():
    # Every test was blocked by a source being down.
    tests = [{"rule_id": "AAA", "outcome": checks.NOT_CHECKED}]
    # Work out its result.
    row = checks.finish_checker({"fail_above": 0, "review_above": 0}, {"status": checks.PASS, "note": ""}, tests)
    # It says so.
    assert row["status"] == checks.NOT_CHECKED


# A source that is down: every rule that needs it says Not checked, none passes, and the run still publishes.
def test_broken_source_shows_not_checked_and_still_publishes(clean_raw, tmp_path):
    # The record of the clean files.
    raw_dir, manifest = clean_raw
    # A copy of the raw folder, with no results files, as if the service were down.
    broken = tmp_path / "raw"
    # Copy the folder.
    shutil.copytree(raw_dir, broken)
    # Remove the results.
    for path in broken.glob("results_*.csv.gz"):
        # Gone.
        path.unlink()
    # The manifest records one failed window and nothing else from that source, as the fetch step would.
    failed = [m for m in manifest if m["source"] != "results"] + [{"source": "results", "window_start": "2024-12-01", "window_end": "2025-01-01", "api_total": None, "calls": 0, "seconds": 0, "status": "failed", "error": "HTTP 503"}]
    # Run it, into a clean folder.
    output = run.run(as_of=fixture.AS_OF, raw_dir=broken, pub_dir=tmp_path / "pub", manifest=failed, watch=fixture.clean_watch())
    # The rule register, to find the rules that read the results.
    needs_results = [r["id"] for r in checks.load_rules() if "results" in checks.sources_needed(r)]
    # Tonight's results by rule.
    status = {r["rule_id"]: r["status"] for r in output["results"]}
    # At least the core rules read the results.
    assert {"UNI-01", "VAL-02", "TIM-01"} <= set(needs_results)
    # None of them passed.
    assert {status[rule_id] for rule_id in needs_results} == {checks.NOT_CHECKED}
    # No decision is called Fit when its data couldn't be checked.
    assert verdicts.FIT not in {v["verdict"] for v in output["verdicts"]}
    # The run log says what happened.
    assert read_rows(tmp_path / "pub" / "history" / "run_log.csv")[-1]["results_status"] == "failed"
    # And the files Power BI reads are still published.
    assert (tmp_path / "pub" / "rule_month.csv").exists() and (tmp_path / "pub" / "same_data.csv").exists()


# After a good night, a night with a source down keeps the last good summaries, and marks tonight's rules Not checked.
def test_source_down_keeps_last_good_summaries(clean_raw, tmp_path):
    # The record of the clean files.
    raw_dir, manifest = clean_raw
    # A good first night.
    run.run(as_of=fixture.AS_OF, raw_dir=raw_dir, pub_dir=tmp_path / "pub", manifest=manifest, watch=fixture.clean_watch())
    # How many rows the summary holds after it.
    good_rows = len(read_rows(tmp_path / "pub" / "same_data.csv"))
    # The fingerprints saved after it.
    good_state = (tmp_path / "pub" / "state" / "fingerprints.parquet").read_bytes()
    # The second night's raw folder, with no results files.
    broken = tmp_path / "raw"
    # Copy the folder.
    shutil.copytree(raw_dir, broken)
    # Remove the results.
    for path in broken.glob("results_*.csv.gz"):
        # Gone.
        path.unlink()
    # The record shows the failure.
    failed = [m for m in manifest if m["source"] != "results"] + [{"source": "results", "window_start": "2024-12-01", "window_end": "2025-01-01", "api_total": None, "calls": 0, "seconds": 0, "status": "failed", "error": "HTTP 503"}]
    # The second night.
    output = run.run(as_of=fixture.AS_OF + timedelta(days=1), raw_dir=broken, pub_dir=tmp_path / "pub", manifest=failed, watch=fixture.clean_watch())
    # The summary still has its rows, and the fingerprints are untouched.
    assert good_rows > 0 and len(read_rows(tmp_path / "pub" / "same_data.csv")) == good_rows and (tmp_path / "pub" / "state" / "fingerprints.parquet").read_bytes() == good_state
    # Tonight's rule still says it wasn't checked.
    assert next(r["status"] for r in output["results"] if r["rule_id"] == "VAL-02") == checks.NOT_CHECKED


# The changes list names a verdict and a rule that moved between two nights, and nothing on the first night.
def test_changes_list_names_what_moved():
    # A decision, as the list of uses holds it.
    uses = [{"id": "monthly", "name": "Send the monthly report"}]
    # Last night's verdict.
    old_verdicts = [{"run_id": "r1", "use_id": "monthly", "dataset_id": "overall", "verdict": "Fit"}]
    # Tonight's verdict.
    new_verdicts = [{"run_id": "r2", "use_id": "monthly", "dataset_id": "overall", "verdict": "Not fit"}]
    # Last night's rule result.
    old_results = [{"run_id": "r1", "rule_id": "VAL-01", "status": "Pass"}, {"run_id": "r1", "rule_id": "VAL-02", "status": "Pass"}]
    # Tonight's rule results, with one moved.
    new_results = [{"rule_id": "VAL-01", "status": "Fail"}, {"rule_id": "VAL-02", "status": "Pass"}]
    # Compare them.
    rows = tonight.changes_since("r1", old_verdicts, new_verdicts, old_results, new_results, uses, [])
    # The verdict comes first, then the rule, and the unchanged rule isn't listed.
    assert [(r["kind"], r["item"], r["before"], r["after"]) for r in rows] == [("Verdict", "Send the monthly report", "Fit", "Not fit"), ("Rule", "VAL-01", "Pass", "Fail")]
    # The first run has nothing to compare with.
    assert tonight.changes_since(None, [], new_verdicts, [], new_results, uses, []) == []


# A rule's packed history keeps one reading a day, the last of that day, and always reads oldest first.
def test_packed_history_keeps_the_last_run_of_each_day():
    # Two runs on one day, then one on the next, for two rules.
    history = [{"rule_id": "A", "run_id": "2026-01-01T02:00Z", "status": "Pass", "failed": "0"}, {"rule_id": "B", "run_id": "2026-01-01T02:00Z", "status": "Fail", "failed": "9"}, {"rule_id": "A", "run_id": "2026-01-01T09:00Z", "status": "Fail", "failed": "3"}, {"rule_id": "A", "run_id": "2026-01-02T02:00Z", "status": "Pass", "failed": "0"}]
    # Only rule A's, and the morning run is replaced by the later one.
    assert tonight.pack_runs("A", history) == "2026-01-01:F:3;2026-01-02:P:0"


# The flat rule file has one row per rule in the register, and every rule's outcome is one of the five.
def test_flat_rule_file_has_every_rule(clean_run):
    # Where the run published.
    _, pub_dir = clean_run
    # Every row.
    rows = read_rows(pub_dir / "rules_tonight.csv")
    # One row for each rule, and all the outcomes are known ones.
    assert len(rows) == len(checks.load_rules()) and {r["status"] for r in rows} <= {checks.PASS, checks.FAIL, checks.REVIEW, checks.NOT_CHECKED, checks.NO_DATA}


# Write a small saved copy of the bathing season, and point the settings at it.
def use_copy(tmp_path, monkeypatch, taken_on="2026-10-20"):
    # The copy's address.
    path = tmp_path / "bathing_copy.csv"
    # One sample is enough.
    path.write_text(f"season_start,season_end,taken_on,bathing_code,sampled_at,ecoli,ecoli_qualifier\n2026-05-01,2026-10-01,{taken_on},41200,2026-06-01T10:00:00,10,actual\n", encoding="utf-8")
    # The engine reads this one for the length of the test.
    monkeypatch.setattr(settings, "BATHING_COPY", path)


# When the live service refuses, the saved copy stands in, and the record says it is a copy.
def test_bathing_copy_stands_in_when_service_refuses(tmp_path, monkeypatch):
    # Don't wait between retries in a test.
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: None)
    # A saved copy.
    use_copy(tmp_path, monkeypatch)
    # A local address nothing is listening on.
    record = fetch.fetch_bathing(tmp_path, fixture.AS_OF, base="http://127.0.0.1:9")[0]
    # The record is honest about what happened.
    assert record["status"] == "copy" and record["taken_on"] == "2026-10-20" and record["api_total"] == 1 and "copy" in record["error"]
    # The sample is where the layers look for it.
    with gzip.open(tmp_path / "bathing.jsonl.gz", "rt", encoding="utf-8") as lines:
        # One sample, with the expected code.
        assert json.loads(lines.readline())["bathing_code"] == "41200"


# With no copy, the source is simply down.
def test_no_bathing_copy_means_failed(tmp_path, monkeypatch):
    # Don't wait between retries in a test.
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: None)
    # An address with no file.
    monkeypatch.setattr(settings, "BATHING_COPY", tmp_path / "missing.csv")
    # A local address nothing is listening on.
    assert fetch.fetch_bathing(tmp_path, fixture.AS_OF, base="http://127.0.0.1:9")[0]["status"] == "failed"


# A current copy passes the staleness rule, and a stale one fails it. Neither counts as a comparison with the live source.
@pytest.mark.parametrize("window,taken,expected", [(("2026-05-01", "2026-10-01"), "2026-10-20", checks.PASS), (("2026-05-01", "2026-10-01"), "2026-08-01", checks.FAIL), (("2025-05-01", "2025-10-01"), "2025-10-20", checks.FAIL)])
def test_copy_staleness_rule(clean_raw, tmp_path, window, taken, expected):
    # The record of the clean files.
    raw_dir, manifest = clean_raw
    # The bathing source stood in with a copy.
    record = [dict(m, status="copy", window_start=window[0], window_end=window[1], taken_on=taken) if m["source"] == "bathing" else m for m in manifest]
    # Run it, into a clean folder.
    output = run.run(as_of=fixture.AS_OF, raw_dir=raw_dir, pub_dir=tmp_path / "pub", manifest=record, watch=fixture.clean_watch())
    # Tonight's results by rule.
    status = {r["rule_id"]: r["status"] for r in output["results"]}
    # The staleness rule says what's expected, and the rules comparing the two services still ran.
    assert status["SRC-06"] == expected and status["REC-01"] != checks.NOT_CHECKED
    # The run log says a copy was used.
    assert output["log"]["bathing_status"] == "copy"


# One licence page that can't be read leaves the others checked, and is counted as excluded rather than passed.
def test_one_unread_statement_is_excluded_not_passed(clean_raw, tmp_path):
    # The record of the clean files.
    raw_dir, manifest = clean_raw
    # The bathing licence page couldn't be read.
    watch = [dict(w, value="", fingerprint="", status="failed") if w["item"] == "Licence: bathing water service" else w for w in fixture.clean_watch()]
    # Run it, into a clean folder.
    output = run.run(as_of=fixture.AS_OF, raw_dir=raw_dir, pub_dir=tmp_path / "pub", manifest=manifest, watch=watch)
    # The licence rule's result.
    found = next(r for r in output["results"] if r["rule_id"] == "AUD-02")
    # It ran on the other two, and left this one out.
    assert (found["status"], found["eligible"], found["excluded"]) == (checks.PASS, 2, 1)
    # The run log says only some were read.
    assert output["log"]["watch_status"] == "part"


# A really unreachable address: the fetch step records a failure and doesn't crash.
def test_unreachable_service_is_recorded_not_raised(tmp_path, monkeypatch):
    # Don't wait between retries in a test.
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: None)
    # A local address nothing is listening on.
    dead = "http://127.0.0.1:9"
    # Try the register.
    points = fetch.fetch_points(tmp_path, base=dead)
    # Try the results.
    results = fetch.fetch_results(tmp_path, fixture.AS_OF, base=dead)
    # Both say failed, and the results stop after the first window.
    assert points[0]["status"] == "failed" and results[0]["status"] == "failed" and len(results) == 1


# An empty table says No data, and never scores 100%.
def test_empty_results_say_no_data(clean_raw, tmp_path):
    # The record of the clean files.
    raw_dir, manifest = clean_raw
    # A copy of the raw folder.
    empty = tmp_path / "raw"
    # Copy the folder.
    shutil.copytree(raw_dir, empty)
    # Replace every month with a header and no rows.
    for path in empty.glob("results_*.csv.gz"):
        # Rewrite it.
        with gzip.open(path, "wt", encoding="utf-8", newline="") as out:
            # The header only.
            csv.writer(out).writerow(layers.RESULT_COLUMNS)
    # The source says it holds nothing either, so the row counts agree.
    record = [dict(m, api_total=0) if m["source"] == "results" else m for m in manifest]
    # Run it, into a clean folder.
    output = run.run(as_of=fixture.AS_OF, raw_dir=empty, pub_dir=tmp_path / "pub", manifest=record, watch=fixture.clean_watch())
    # Tonight's results by rule.
    status = {r["rule_id"]: r["status"] for r in output["results"]}
    # A selection of rules that read results find nothing to check.
    assert {status[rule_id] for rule_id in ("VAL-02", "VAL-03", "UNI-01", "VAL-07", "ACC-01")} == {checks.NO_DATA}
    # No decision is called Fit on an empty table.
    assert verdicts.FIT not in {v["verdict"] for v in output["verdicts"] if v["in_scope"]}


# A column the contract needs goes missing: the contract rule fails, and the rules that read it say Not checked.
def test_dropped_column_fails_the_contract_rule(clean_raw, tmp_path):
    # The record of the clean files.
    raw_dir, manifest = clean_raw
    # A copy of the raw folder.
    broken = tmp_path / "raw"
    # Copy the folder.
    shutil.copytree(raw_dir, broken)
    # Remove the unit column from every month.
    for path in broken.glob("results_*.csv.gz"):
        # Read the month.
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            # Every row as a dictionary.
            rows = list(csv.DictReader(handle))
        # The columns without the unit.
        kept = [c for c in layers.RESULT_COLUMNS if c != "unit"]
        # Write it back without the column.
        with gzip.open(path, "wt", encoding="utf-8", newline="") as out:
            # A CSV writer that ignores the dropped column.
            writer = csv.DictWriter(out, fieldnames=kept, extrasaction="ignore")
            # The header line.
            writer.writeheader()
            # Every row.
            writer.writerows(rows)
    # Run it, into a clean folder.
    output = run.run(as_of=fixture.AS_OF, raw_dir=broken, pub_dir=tmp_path / "pub", manifest=manifest, watch=fixture.clean_watch())
    # Tonight's results by rule.
    status = {r["rule_id"]: r["status"] for r in output["results"]}
    # The contract rule fails, and rules that read the results don't pass.
    assert status["SRC-03"] == checks.FAIL and status["VAL-02"] == checks.NOT_CHECKED


# The first run sets the baseline, and the rules about change have nothing to compare.
def test_first_run_is_honest_about_history(clean_raw, tmp_path):
    # The record of the clean files.
    raw_dir, manifest = clean_raw
    # Run it with no history at all.
    output = run.run(as_of=fixture.AS_OF, raw_dir=raw_dir, pub_dir=tmp_path / "pub", manifest=manifest, watch=fixture.clean_watch())
    # Tonight's results by rule.
    status = {r["rule_id"]: r["status"] for r in output["results"]}
    # Nothing to compare yet.
    assert {status[rule_id] for rule_id in FIRST_RUN_NO_DATA} == {checks.NO_DATA}
    # The ledger hasn't run long enough to sign anything off.
    assert status["AUD-01"] == checks.FAIL
    # So sign-off is refused, and it clears by itself after 35 days.
    assert next(v["verdict"] for v in output["verdicts"] if v["use_id"] == "signoff" and v["dataset_id"] == "overall") == verdicts.NOT_FIT
    # The ledger row marks this as the baseline.
    assert read_rows(tmp_path / "pub" / "history" / "ledger.csv")[-1]["is_baseline"] == "True"


# The ledger spots a new, a changed and a removed record between two runs, and history only grows.
def test_ledger_finds_new_changed_and_removed(clean_raw, tmp_path):
    # The record of the clean files.
    raw_dir, manifest = clean_raw
    # The first night.
    run.run(as_of=fixture.AS_OF, raw_dir=raw_dir, pub_dir=tmp_path / "pub", manifest=manifest, watch=fixture.clean_watch())
    # A copy of the raw folder for the second night.
    second = tmp_path / "raw2"
    # Copy the folder.
    shutil.copytree(raw_dir, second)
    # The month to change.
    path = second / "results_2026-06.csv.gz"
    # Read it.
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        # Every row.
        rows = list(csv.reader(handle))
    # Where the result column is.
    result_at = rows[0].index("result")
    # Change one record's result.
    rows[1][result_at] = "999"
    # Remove the next record.
    del rows[2]
    # Add one new record, copied from the third with a new address.
    rows.append([rows[2][0] + "9"] + rows[2][1:])
    # Write the month back.
    with gzip.open(path, "wt", encoding="utf-8", newline="") as out:
        # Every row.
        csv.writer(out).writerows(rows)
    # The source's totals match what is now there.
    record = [dict(m, api_total=len(rows) - 1) if m["window_start"] == "2026-06-01" else m for m in manifest]
    # The second night.
    run.run(as_of=fixture.AS_OF + timedelta(days=1), raw_dir=second, pub_dir=tmp_path / "pub", manifest=record, watch=fixture.clean_watch())
    # The ledger's two rows.
    ledger_rows = read_rows(tmp_path / "pub" / "history" / "ledger.csv")
    # One row was added per night, and the counts are exactly right.
    assert len(ledger_rows) == 2 and (ledger_rows[1]["records_new"], ledger_rows[1]["records_changed"], ledger_rows[1]["records_removed"]) == ("1", "1", "1")
    # The record-level detail shows the old and new values of the changed record.
    assert "999" in {row["result_now"] for row in read_rows(tmp_path / "pub" / "history" / "ledger_detail.csv")}


# Reading the result column: each kind of text, and what it must become.
@pytest.mark.parametrize("text,kind,value,limit", [("12.5", "number", 12.5, None), ("<0.03", "below", None, 0.03), ("< 5", "below", None, 5.0), (">110", "above", None, 110.0), (">9999999", "above", None, 9999999.0), ("-3.2", "number", -3.2, None), ("Not found", "text", None, None), ("", "empty", None, None), ("<abc", "text", None, None)])
def test_result_text_is_parsed_correctly(text, kind, value, limit):
    # An in-memory database.
    con = duckdb.connect()
    # Empty bronze tables.
    layers.create_bronze(con, [], [], {})
    # One result with this text.
    row = fixture.result_row("https://x/sample/1/observation/0001", "NW-1", "2026-01-05T09:30:00", fixture.PURPOSES[0], "0111", "Ammonia", "MILLIGRAM PER LITRE", text, fixture.RIVER_TYPE, "A")
    # Load it.
    con.execute("INSERT INTO bronze.results VALUES (" + ",".join("?" * 17) + ", '2026-01-01')", row)
    # Build silver.
    layers.build_silver(con, fixture.AS_OF, "test", fixture.AS_OF, {fixture.AS_OF.isoformat()})
    # Read it back.
    found = con.execute("SELECT result_kind, result_value, limit_value FROM silver.results").fetchone()
    # It matches what's expected.
    assert found == (kind, value, limit)


# Labels: only clean labels on natural waters are published. Everything flagged is withheld, and coordinates are classified.
@pytest.mark.parametrize("label,point_type,east,north,published,location", [
    ("RIVER TEST AT BRIDGE", fixture.RIVER_TYPE, 350000, 420000, True, "Inside the North West"),
    ("RIVER TEST AT M1 1AA", fixture.RIVER_TYPE, 350000, 420000, False, "Inside the North West"),
    ("RIVER TEST AT 12 HIGH STREET", fixture.RIVER_TYPE, 350000, 420000, False, "Inside the North West"),
    ("RIVER TEST AT MR SMITH", fixture.RIVER_TYPE, 350000, 420000, False, "Inside the North West"),
    ("RIVER TEST AT ROSE COTTAGE", fixture.RIVER_TYPE, 350000, 420000, False, "Inside the North West"),
    ("RIVER TEST AT ACME LTD", fixture.RIVER_TYPE, 350000, 420000, False, "Inside the North West"),
    ("OUTFALL AT BRIDGE", fixture.DISCHARGE_TYPE, 350000, 420000, False, "Inside the North West"),
    ("BOREHOLE AT BRIDGE", "GROUNDWATER - BOREHOLE", 350000, 420000, False, "Inside the North West"),
    ("MISC RIVER SAMPLE", fixture.RIVER_TYPE, 500000, 4, True, "Stand-in location"),
    ("RIVER FAR AWAY", fixture.RIVER_TYPE, 100000, 100000, True, "Outside the North West")])
def test_labels_and_locations(label, point_type, east, north, published, location):
    # An in-memory database.
    con = duckdb.connect()
    # Empty bronze tables.
    layers.create_bronze(con, [], [], {})
    # One point with this label.
    con.execute("INSERT INTO bronze.points VALUES ('NW-1', ?, 'OPEN', ?, 'A', 'B', ?)", [label, point_type, f"POINT({east} {north}) <x>"])
    # Build silver.
    layers.build_silver(con, fixture.AS_OF, "test", fixture.AS_OF, {fixture.AS_OF.isoformat()})
    # Read it back.
    label_public, location_kind = con.execute("SELECT label_public, location_kind FROM silver.points").fetchone()
    # The label is published or withheld, as expected.
    assert (label_public is not None) == published and location_kind == location


# The final sweep refuses to publish a file holding a postcode or a title with a name, and names only the file.
@pytest.mark.parametrize("line", ["point at M1 1AA", "the home of MR SMITH"])
def test_privacy_sweep_stops_the_run(tmp_path, line):
    # A file about to be published.
    (tmp_path / "points.csv").write_text("label\n" + line + "\n", encoding="utf-8")
    # The sweep stops the run.
    with pytest.raises(publish.PublishRefused):
        # Try it.
        publish.privacy_sweep(tmp_path)


# Nothing the clean run published contains a raw label from a withheld point.
def test_withheld_labels_never_reach_published_files(clean_run):
    # Where the run published.
    _, pub_dir = clean_run
    # Every published CSV.
    for path in pub_dir.rglob("*.csv"):
        # The discharge point's raw label must not appear anywhere.
        assert "TESTFORD OUTFALL" not in path.read_text(encoding="utf-8"), path.name


# Control totals all agree on clean data, which is what the page's strip shows. The plausibility check on ranges belongs here too.
def test_control_totals_agree_and_values_are_plausible(clean_run):
    # Where the run published.
    _, pub_dir = clean_run
    # The row count at each stage.
    totals = {row["row_count"] for row in read_rows(pub_dir / "control_totals.csv")}
    # One number at every stage.
    assert len(totals) == 1
    # Every figure in the same-data table is a sensible size for the made-up data.
    figures = [float(row["figure"]) for row in read_rows(pub_dir / "same_data.csv") if row["figure"]]
    # No negatives, and nothing wildly out of range.
    assert figures and min(figures) >= 0 and max(figures) < 100


# Medians and ranks in the same-data table are worked out per scenario, and no scenario is double-counted.
def test_same_data_has_one_row_per_scenario_and_area(clean_run):
    # Where the run published.
    _, pub_dir = clean_run
    # Every row.
    rows = read_rows(pub_dir / "same_data.csv")
    # The key of each row.
    keys = [(r["scenario_key"], r["sub_area"]) for r in rows]
    # No repeats.
    assert len(keys) == len(set(keys))


# Date windows: no overlap, no gap, and exactly 24 of them. The service's end date excludes the day it names.
def test_month_windows_join_up():
    # The windows.
    windows = fetch.month_windows(date(2026, 1, 15))
    # 24 of them, ending with the current month.
    assert len(windows) == 24 and windows[-1] == ("2026-01-01", "2026-02-01") and windows[0] == ("2024-02-01", "2024-03-01")
    # Each starts where the last one ended.
    assert all(windows[i][1] == windows[i + 1][0] for i in range(len(windows) - 1))


# The bathing season is the latest that has begun.
def test_bathing_season_rolls_over_in_may():
    # April looks back to last year.
    assert fetch.bathing_season(date(2026, 4, 30)) == ("2025-05-01", "2025-10-01")
    # May looks at this year.
    assert fetch.bathing_season(date(2026, 5, 1)) == ("2026-05-01", "2026-10-01")


# Verdict logic, one case per row. A failed gate can't be outvoted, and grey is never green.
@pytest.mark.parametrize("gate,condition,expected", [(checks.PASS, checks.PASS, verdicts.FIT), (checks.PASS, checks.FAIL, verdicts.CONDITIONS), (checks.PASS, checks.REVIEW, verdicts.CONDITIONS), (checks.REVIEW, checks.PASS, verdicts.CONDITIONS), (checks.FAIL, checks.PASS, verdicts.NOT_FIT), (checks.NOT_CHECKED, checks.PASS, verdicts.UNCHECKED), (checks.NO_DATA, checks.PASS, verdicts.UNCHECKED), (checks.FAIL, checks.NOT_CHECKED, verdicts.NOT_FIT), (checks.PASS, checks.NOT_CHECKED, verdicts.CONDITIONS), (checks.PASS, checks.NO_DATA, verdicts.FIT)])
def test_verdict_logic(gate, condition, expected):
    # Judge one gate and one condition.
    assert verdicts.judge([{"status": gate}], [{"status": condition}]) == expected


# An issue's life: it opens on a problem, survives a night that couldn't be checked, and closes after enough passes.
def test_issue_lifecycle():
    # A rule, as the register holds it.
    rules = [{"id": "VAL-99", "severity": "Major"}]
    # One night's result with a given status.
    night = lambda status: [{"rule_id": "VAL-99", "status": status, "failed": 5 if status == checks.FAIL else 0}]
    # The first failure opens an issue, due in 30 days.
    state = issues.update_issues([], rules, night(checks.FAIL), date(2026, 1, 1), "run1")
    # One open issue with the right date.
    assert state[0]["state"] == "Open" and state[0]["due_on"] == "2026-01-31"
    # A night that couldn't be checked changes nothing.
    state = issues.update_issues(state, rules, night(checks.NOT_CHECKED), date(2026, 1, 2), "run2")
    # Still open, with no passes counted.
    assert state[0]["state"] == "Open" and state[0]["passes_in_a_row"] == 0
    # Two passes aren't enough.
    for day in (3, 4):
        # Another pass.
        state = issues.update_issues(state, rules, night(checks.PASS), date(2026, 1, day), "run")
    # Still open.
    assert state[0]["state"] == "Open"
    # The third pass closes it.
    state = issues.update_issues(state, rules, night(checks.PASS), date(2026, 1, 5), "run")
    # Closed, with the date.
    assert state[0]["state"] == "Closed" and state[0]["closed_on"] == "2026-01-05"
    # A new failure opens a second issue, and the first stays in the record.
    state = issues.update_issues(state, rules, night(checks.FAIL), date(2026, 2, 1), "run")
    # Two issues, one open and one closed.
    assert [i["state"] for i in state] == ["Closed", "Open"]


# History files keep every row from earlier nights.
def test_history_keeps_every_row(tmp_path):
    # A history file's path.
    path = tmp_path / "history.csv"
    # The first night.
    publish.append_history(path, [{"a": 1}], ["a"])
    # The second night.
    rows = publish.append_history(path, [{"a": 2}], ["a"])
    # Both rows are there, in order.
    assert [r["a"] for r in rows] == ["1", "2"]


# Any history file losing rows, or vanishing, stops the run before anything can be published.
def test_lost_history_stops_the_run(tmp_path):
    # Two history files.
    publish.write_rows(tmp_path / "run_log.csv", [{"a": 1}, {"a": 2}], ["a"])
    # The second file.
    publish.write_rows(tmp_path / "issues.csv", [{"a": 1}], ["a"])
    # How many rows they hold.
    before = publish.count_history(tmp_path)
    # Nothing has changed, so all is well.
    publish.check_history(tmp_path, before)
    # One file loses a row.
    publish.write_rows(tmp_path / "run_log.csv", [{"a": 1}], ["a"])
    # The run stops.
    with pytest.raises(publish.PublishRefused):
        # Try it.
        publish.check_history(tmp_path, before)
    # Put the row back.
    publish.write_rows(tmp_path / "run_log.csv", [{"a": 1}, {"a": 2}], ["a"])
    # The other file vanishes.
    (tmp_path / "issues.csv").unlink()
    # The run stops again.
    with pytest.raises(publish.PublishRefused):
        # Try it.
        publish.check_history(tmp_path, before)


# The issue list can't shrink: the engine refuses to publish rather than lose an issue.
def test_shrinking_issue_list_is_refused(clean_run, tmp_path, monkeypatch, clean_raw):
    # The record of the clean files.
    raw_dir, manifest = clean_raw
    # A first night that opens some issues.
    pub_dir = tmp_path / "pub"
    # Run it.
    run.run(as_of=fixture.AS_OF, raw_dir=raw_dir, pub_dir=pub_dir, manifest=manifest, watch=fixture.clean_watch())
    # Pretend a bug loses every issue on the second night.
    monkeypatch.setattr(issues, "update_issues", lambda *args, **kwargs: [])
    # The run refuses to publish.
    with pytest.raises(publish.PublishRefused):
        # Try it.
        run.run(as_of=fixture.AS_OF + timedelta(days=1), raw_dir=raw_dir, pub_dir=pub_dir, manifest=manifest, watch=fixture.clean_watch())


# A point's score weights each rule by severity, and a rule that didn't reach the point doesn't count either way.
def test_point_score_weights_rules_by_severity():
    # A critical rule passing everything and a minor rule failing half.
    assert points.score_from([(3, 10, 0), (1, 10, 5)]) == pytest.approx(87.5)
    # A rule with nothing to check makes no difference.
    assert points.score_from([(3, 10, 0), (2, 0, 0)]) == 100.0
    # No rule reaching a point means no score, never a perfect one.
    assert points.score_from([]) is None


# A flagged point can never read as a perfect 100, and no results is grey rather than a pass.
def test_point_bands_stay_honest():
    # Rounding down keeps a flagged point below 100.
    assert points.shown_score(99.99, 1) == 99.9
    # Nothing flagged is exactly 100.
    assert points.shown_score(100.0, 0) == 100.0
    # No results is its own band, whatever else is true.
    assert points.band_for(0, 0, None) == settings.POINT_BANDS[3]
    # Nothing flagged.
    assert points.band_for(10, 0, 100.0) == settings.POINT_BANDS[0]
    # A few flags, at the threshold.
    assert points.band_for(10, 2, settings.POINT_LOOK_CLOSER_BELOW) == settings.POINT_BANDS[1]
    # Below the threshold.
    assert points.band_for(10, 2, settings.POINT_LOOK_CLOSER_BELOW - 0.1) == settings.POINT_BANDS[2]


# Below-limit results and clock times are shown on a point but never counted against it.
def test_point_score_leaves_out_normal_reporting_and_open_questions():
    # Neither rule is in the score.
    assert not set(settings.POINT_INFO_RULES) & set(settings.POINT_SCORE_RULES)
    # Every rule named really exists.
    assert set(settings.POINT_SCORE_RULES + settings.POINT_INFO_RULES) <= {r["id"] for r in checks.load_rules()}


# Each point is published once, every drawn point is in a pack, and a point with no results has no score.
def test_point_files_agree(clean_run):
    # Where the run published.
    _, pub_dir = clean_run
    # The points.
    rows = read_rows(pub_dir / "point_quality.csv")
    # The packs.
    packs = read_rows(pub_dir / "point_packs.csv")
    # No point appears twice.
    assert len({r["point_id"] for r in rows}) == len(rows) > 0
    # Names are unique, because the report drills through by name, and the engine ignores case when it compares them.
    assert len({r["point_label"].lower() for r in rows}) == len({r["point_id"].lower() for r in rows}) == len(rows)
    # The packs hold every point exactly once.
    assert sum(int(p["points_in_pack"]) for p in packs) == len(rows)
    # Every point names a row that exists, and that row says the same about it.
    by_pack = {p["pack_id"]: p for p in packs}
    assert all(by_pack[r["pack_id"]]["band"] == r["band"] and by_pack[r["pack_id"]]["point_group"] == r["point_group"] for r in rows)
    # A flagged point has a row of its own, so a click can find it.
    assert all(p["points_in_pack"] == "1" for p in packs if p["band"] in settings.POINT_BANDS[1:3])
    # A row's points are all drawn or all parked, and the ones with no location are the parked ones.
    assert all((r["map_e"] != "") == (by_pack[r["pack_id"]]["located"] == "True") for r in rows)
    # Points with no results have no score, and points with results have one.
    assert all(bool(r["score"]) == (int(r["results"]) > 0) for r in rows)


# When the results can't be read, last night's point files stay rather than turning every point grey.
def test_source_down_keeps_last_point_files(clean_raw, tmp_path):
    # The saved folders.
    raw_dir, manifest = clean_raw
    # A first good night.
    run.run(as_of=fixture.AS_OF, raw_dir=raw_dir, pub_dir=tmp_path / "pub", manifest=manifest, watch=fixture.clean_watch())
    # What it published.
    before = (tmp_path / "pub" / "point_quality.csv").read_bytes()
    # A copy of the downloads with the results removed.
    broken = tmp_path / "raw"
    # Copy the folder.
    shutil.copytree(raw_dir, broken)
    # Remove the results.
    for path in broken.glob("results_*.csv.gz"):
        # Gone.
        path.unlink()
    # The record shows the results failed.
    failed = [m for m in manifest if m["source"] != "results"] + [{"source": "results", "window_start": "2024-12-01", "window_end": "2025-01-01", "api_total": None, "calls": 0, "seconds": 0, "status": "failed", "error": "HTTP 503"}]
    # A second night, with the results down.
    run.run(as_of=fixture.AS_OF, raw_dir=broken, pub_dir=tmp_path / "pub", manifest=failed, watch=fixture.clean_watch())
    # The file is unchanged.
    assert (tmp_path / "pub" / "point_quality.csv").read_bytes() == before
