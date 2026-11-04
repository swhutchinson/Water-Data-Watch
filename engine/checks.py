# Runs the rule register: every rule, its planted defect and its "does it change the answer?" test.
# Automation checks and reports here. Nothing in this file changes the source data or decides anything a person should.

# Finds each rule's sections in the SQL files.
import re
# Reads the register.
import yaml
# Reads the shared settings and builds SQL with the project's paths filled in.
from engine import settings
# Reads SQL files with the project's paths filled in.
from engine.layers import read_sql

# The five honest outcomes a rule can have.
PASS, FAIL, REVIEW, NOT_CHECKED, NO_DATA = "Pass", "Fail", "For review", "Not checked", "No data"
# Which source each table in a rule's SQL depends on. A rule reading a failed source says "Not checked".
TABLE_SOURCES = {"silver.results": ["results"], "silver.months": ["results"], "silver.points": ["points"], "silver.bathing": ["bathing"], "bronze.codes": ["codes"], "bronze.source_watch": ["watch"], "bronze.manifest": ["results", "points", "bathing", "codes"]}


# Load the register and attach each rule's SQL.
def load_rules():
    # The register, as a list of rules.
    register = yaml.safe_load((settings.RULES / "register.yaml").read_text(encoding="utf-8"))
    # Each rule's sections, found by ID.
    sections = {}
    # Every SQL file of rules.
    for path in sorted((settings.RULES / "sql").glob("*.sql")):
        # Split the file wherever a new rule starts.
        for block in re.split(r"(?m)^-- @rule ", read_sql(path))[1:]:
            # The first word is the rule's ID.
            rule_id = block.split()[0]
            # Split this rule into its check, plant and impact sections.
            parts = re.split(r"(?m)^-- @(check|plant|impact)\s*$", block)
            # Pair each section name with its SQL.
            sections[rule_id] = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    # Attach the sections to the register's entries.
    for rule in register:
        # A rule with no SQL, such as the check on the checker itself, gets empty sections.
        rule.update(sections.get(rule["id"], {}))
    # Hand back the rules in register order.
    return register


# Say which sources a rule depends on.
def sources_needed(rule):
    # A rule may name its sources directly, which overrides working them out.
    if rule.get("requires"):
        # Use what it says.
        return set(rule["requires"])
    # Otherwise read them from the tables its SQL uses.
    return {source for table, names in TABLE_SOURCES.items() if table in rule.get("check", "") for source in names}


# Decide a rule's outcome from its counts and thresholds.
def outcome(rule, eligible, failed):
    # Nothing to check is never a pass.
    if not eligible:
        # Say so.
        return NO_DATA
    # The failing share of what was checked.
    percent = 100.0 * failed / eligible
    # Above the fail threshold is a Fail.
    if rule.get("fail_above") is not None and percent > rule["fail_above"]:
        # Against a stated threshold.
        return FAIL
    # Above the review threshold needs a person to look.
    if rule.get("review_above") is not None and percent > rule["review_above"]:
        # Merely unusual, so not called a failure.
        return REVIEW
    # Otherwise it passes.
    return PASS


# Run one rule's check into a temporary table, and return its three counts.
def evaluate(con, rule):
    # Run the rule's SQL, keeping every row it returns.
    con.execute(f"CREATE OR REPLACE TEMP TABLE rule_rows AS {rule['check'].rstrip().rstrip(';')}")
    # Count what was checked, what failed and what was excluded.
    return con.execute("SELECT count(*) FILTER (WHERE failed IS NOT NULL), count(*) FILTER (WHERE failed), count(*) FILTER (WHERE failed IS NULL) FROM rule_rows").fetchone()


# Run every rule on the real data.
def run_rules(con, rules, available, run_id):
    # One summary row per rule.
    results = []
    # One row per rule and month, for the grid.
    months = []
    # The failed records, capped per rule.
    exceptions = []
    # Each rule in register order.
    for rule in rules:
        # The summary row, filled in below.
        row = {"run_id": run_id, "rule_id": rule["id"], "rule_version": rule["version"], "eligible": 0, "passed": 0, "failed": 0, "excluded": 0, "failed_pct": None, "status": NOT_CHECKED, "note": "", "exceptions_shown": 0}
        # The check on the checker is worked out later, from the planted results.
        if not rule.get("check"):
            # Keep its place in the list.
            results.append(row)
            # On to the next rule.
            continue
        # The sources this rule can't run without that aren't available tonight.
        missing = sorted(s for s in sources_needed(rule) if not available.get(s, False))
        # A rule whose source failed hasn't been checked. It is never counted as a pass.
        if missing:
            # Say which source.
            row["note"] = "Source not available tonight: " + ", ".join(missing)
            # Keep it in the list.
            results.append(row)
            # On to the next rule.
            continue
        # A rule whose SQL fails hasn't been checked either.
        try:
            # Run it.
            eligible, failed, excluded = evaluate(con, rule)
            # Work out the outcome.
            row.update({"eligible": eligible, "failed": failed, "passed": eligible - failed, "excluded": excluded, "failed_pct": round(100.0 * failed / eligible, 3) if eligible else None, "status": outcome(rule, eligible, failed)})
            # This rule's results by month, for the grid. Rules about a whole list have no month and don't appear in it.
            for month, month_eligible, month_failed in con.execute("SELECT sample_month, count(*) FILTER (WHERE failed IS NOT NULL), count(*) FILTER (WHERE failed) FROM rule_rows WHERE sample_month IS NOT NULL GROUP BY 1 ORDER BY 1").fetchall():
                # One cell of the grid, using the same thresholds as the rule itself.
                months.append({"rule_id": rule["id"], "sample_month": month, "eligible": month_eligible, "failed": month_failed, "status": outcome(rule, month_eligible, month_failed)})
            # The failed records, newest first, up to the cap.
            shown = con.execute(f"SELECT record_ref, point_id, sample_month, detail, source_url FROM rule_rows WHERE failed ORDER BY sample_month DESC NULLS LAST, record_ref LIMIT {settings.EXCEPTION_CAP}").fetchall()
            # Keep each one, naming its rule.
            exceptions += [{"rule_id": rule["id"], "record_ref": s[0], "point_id": s[1], "sample_month": s[2], "detail": s[3], "source_url": s[4]} for s in shown]
            # Note how many are being shown, since the true total can be larger.
            row["exceptions_shown"] = len(shown)
        # Anything that stopped the rule running.
        except Exception as error:
            # Record the reason, and leave the status as Not checked.
            row["note"] = "The check couldn't run: " + str(error)[:180]
        # Keep the row.
        results.append(row)
    # Hand back all three.
    return results, months, exceptions


# Prove each rule still fires: plant its defect in a private copy, check again, then throw the copy away.
def run_planted(con, rules, results):
    # Tonight's real results, by rule.
    clean = {r["rule_id"]: r for r in results}
    # One row per rule.
    tests = []
    # Each rule that has a planted defect.
    for rule in rules:
        # The check on the checker has no defect of its own: a unit test proves it instead.
        if not rule.get("plant"):
            # Move on.
            continue
        # The real result for this rule.
        before = clean[rule["id"]]
        # The test row, filled in below.
        test = {"rule_id": rule["id"], "failed_before": before["failed"], "failed_after": None, "caught": None, "outcome": "Not run", "note": ""}
        # A rule that couldn't run tonight can't be tested tonight.
        if before["status"] == NOT_CHECKED:
            # Say so. It doesn't count as caught.
            test["outcome"] = NOT_CHECKED
            # Keep it.
            tests.append(test)
            # On to the next rule.
            continue
        # Everything planted is rolled back below, so the real tables are never changed.
        con.execute("BEGIN TRANSACTION")
        # Catch any failure, so one bad plant can't stop the others.
        try:
            # Plant the defect.
            con.execute(rule["plant"])
            # Run the same check again.
            _, failed_after, _ = evaluate(con, rule)
            # Record the new count.
            test["failed_after"] = failed_after
            # Caught means the check found more than it did on the real data.
            test["caught"] = failed_after > before["failed"]
            # The plain-English outcome.
            test["outcome"] = "Caught" if test["caught"] else "Missed"
        # The plant or check couldn't run.
        except Exception as error:
            # Record why. A test that didn't run proves nothing, so it isn't counted as caught.
            test["outcome"] = "Not run"
            # Keep the reason.
            test["note"] = str(error)[:180]
        # Whatever happened, undo the plant.
        finally:
            # Throw the private copy away.
            con.execute("ROLLBACK")
        # Keep the result.
        tests.append(test)
    # Hand them back.
    return tests


# Fill in the check on the checker, now the planted results are known.
def finish_checker(rule, row, tests):
    # Tests that ran to a result.
    ran = [t for t in tests if t["outcome"] in ("Caught", "Missed")]
    # Those that missed their defect.
    missed = [t for t in ran if t["outcome"] == "Missed"]
    # Tests that couldn't run for a technical reason, as opposed to a source being down.
    broken = [t for t in tests if t["outcome"] == "Not run"]
    # Nothing ran means nothing has been proved.
    if not ran:
        # Say so.
        row["status"] = NOT_CHECKED
        # Explain.
        row["note"] = "No planted defects could be tested tonight"
        # Finished.
        return row
    # Fill in the counts.
    row.update({"eligible": len(ran) + len(broken), "failed": len(missed) + len(broken), "passed": len(ran) - len(missed), "failed_pct": round(100.0 * (len(missed) + len(broken)) / (len(ran) + len(broken)), 3)})
    # The outcome, using the rule's own threshold.
    row["status"] = outcome(rule, row["eligible"], row["failed"])
    # Name any rule that missed, or couldn't be tested.
    if missed or broken:
        # One short note.
        row["note"] = "Not proved tonight: " + ", ".join(t["rule_id"] for t in missed + broken)
    # Hand back the finished row.
    return row


# Run every "does it change the answer?" test.
def run_impact(con, rules, results):
    # Tonight's results, by rule.
    status = {r["rule_id"]: r["status"] for r in results}
    # One row per rule that has a test.
    rows = []
    # Each rule.
    for rule in rules:
        # Rules with nothing to measure simply have no row.
        if not rule.get("impact"):
            # Move on.
            continue
        # The row, filled in below.
        row = {"rule_id": rule["id"], "figure": "", "careful": None, "careless": None, "unit": "", "effect_pct": None, "measured": False}
        # A rule that wasn't checked can't have its effect measured.
        if status.get(rule["id"]) == NOT_CHECKED:
            # Keep the empty row.
            rows.append(row)
            # On to the next rule.
            continue
        # A test that fails shows as not measured, never as zero.
        try:
            # Run the stated calculation.
            found = con.execute(rule["impact"]).fetchone()
            # A reply with both numbers can be compared.
            if found and found[1] is not None and found[2] is not None:
                # Keep the four parts.
                row.update({"figure": found[0], "careful": round(float(found[1]), 4), "careless": round(float(found[2]), 4), "unit": found[3], "measured": True})
                # How far the careless figure sits from the careful one, as a percentage.
                row["effect_pct"] = round(100.0 * (row["careless"] - row["careful"]) / row["careful"], 1) if row["careful"] else None
        # Anything that stopped the test running.
        except Exception as error:
            # Say why in the log. The page shows "not measured".
            print("impact test", rule["id"], "couldn't run:", str(error)[:180], flush=True)
        # Keep the row.
        rows.append(row)
    # Hand them back.
    return rows


# Put open problems in the order to fix them: gates first, then by how far each moves the answer.
def fix_order(rules, results, impact):
    # Tonight's results, by rule.
    status = {r["rule_id"]: r for r in results}
    # The measured effects, by rule.
    effects = {i["rule_id"]: i for i in impact}
    # The order of severities.
    weight = {"Critical": 0, "Major": 1, "Minor": 2}
    # Only rules needing attention are ranked.
    open_rules = [r for r in rules if status[r["id"]]["status"] in (FAIL, REVIEW)]
    # Sort by severity, then Fail before For review, then the biggest measured effect, with unmeasured last.
    open_rules.sort(key=lambda r: (weight[r["severity"]], status[r["id"]]["status"] != FAIL, -abs(effects.get(r["id"], {}).get("effect_pct") or 0), r["id"]))
    # Number them from 1.
    return [{"rule_id": r["id"], "fix_rank": rank} for rank, r in enumerate(open_rules, start=1)]
