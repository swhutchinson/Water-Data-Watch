# Shapes tonight's results for the report: one flat row per rule, and a list of what changed since the last run.
# Deneb's cost grows with rows, so a rule's history by month and by day is packed into one text field per rule.

# The five outcomes a rule can have.
from engine.checks import FAIL, NO_DATA, NOT_CHECKED, PASS, REVIEW

# One letter for each outcome, to keep the packed fields short.
LETTER = {PASS: "P", FAIL: "F", REVIEW: "R", NOT_CHECKED: "N", NO_DATA: "D"}
# How many days of history the rule-by-day strip carries.
STRIP_DAYS = 90
# The columns of the flat rule file, in a fixed order.
RULE_COLUMNS = ["rule_order", "id", "rule_label", "version", "title", "why", "dataset", "fields", "dimension", "severity", "fail_above", "review_above", "owner_role", "steward_role", "action", "root_cause", "condition", "eligible", "failed", "excluded", "failed_pct", "status", "note", "exceptions_shown", "exceptions_hidden", "test_outcome", "test_failed_before", "test_failed_after", "figure", "careful", "careless", "unit", "effect_pct", "measured", "fix_rank", "months_packed", "runs_packed"]
# The columns of the changes file.
CHANGE_COLUMNS = ["change_order", "kind", "item", "before", "after", "previous_run"]


# Pack a rule's results by month: month, status letter, failed, checked.
def pack_months(rule_id, months):
    # One short piece per month, oldest first, because the engine produces them in month order.
    return ";".join(f'{m["sample_month"]}:{LETTER[m["status"]]}:{m["failed"]}:{m["eligible"]}' for m in months if m["rule_id"] == rule_id)


# Pack a rule's history by day: the last run of each day, with its status letter and failed count.
def pack_runs(rule_id, history):
    # A day's later runs overwrite its earlier ones, because history is in run order.
    by_day = {}
    # Each past result of this rule.
    for row in history:
        # Only this rule.
        if row["rule_id"] == rule_id:
            # The day is the start of the run's name.
            by_day[row["run_id"][:10]] = f'{row["run_id"][:10]}:{LETTER[row["status"]]}:{row["failed"]}'
    # The latest days, oldest first.
    return ";".join(by_day[day] for day in sorted(by_day)[-STRIP_DAYS:])


# Build one flat row per rule, holding everything the report shows about it.
def flat_rules(rules, results, tests, impact, order, months, history):
    # Tonight's result for each rule.
    result = {r["rule_id"]: r for r in results}
    # The planted defect result for each rule.
    test = {t["rule_id"]: t for t in tests}
    # The measured effect for each rule.
    effect = {i["rule_id"]: i for i in impact}
    # Each rule's place in the order to fix things.
    rank = {o["rule_id"]: o["fix_rank"] for o in order}
    # The finished rows.
    rows = []
    # Each rule, in register order.
    for number, rule in enumerate(rules, start=1):
        # Tonight's result for this rule.
        found = result[rule["id"]]
        # The planted result, which the check on the checker doesn't have.
        planted = test.get(rule["id"], {})
        # The measured effect, which many rules don't have.
        measured = effect.get(rule["id"], {})
        # Put the row together.
        rows.append({"rule_order": number, "id": rule["id"], "rule_label": f'{rule["id"]} · {rule["title"]}', "version": rule["version"], "title": rule["title"], "why": rule["why"], "dataset": rule["dataset"], "fields": ", ".join(rule["fields"]), "dimension": rule["dimension"], "severity": rule["severity"], "fail_above": rule.get("fail_above"), "review_above": rule.get("review_above"), "owner_role": rule["owner_role"], "steward_role": rule["steward_role"], "action": rule["action"], "root_cause": rule["root_cause"], "condition": rule["condition"], "eligible": found["eligible"], "failed": found["failed"], "excluded": found["excluded"], "failed_pct": found["failed_pct"], "status": found["status"], "note": found["note"], "exceptions_shown": found["exceptions_shown"], "exceptions_hidden": max(found["failed"] - found["exceptions_shown"], 0), "test_outcome": planted.get("outcome", "Proved by its own test"), "test_failed_before": planted.get("failed_before"), "test_failed_after": planted.get("failed_after"), "figure": measured.get("figure", ""), "careful": measured.get("careful"), "careless": measured.get("careless"), "unit": measured.get("unit", ""), "effect_pct": measured.get("effect_pct"), "measured": measured.get("measured", False), "fix_rank": rank.get(rule["id"]), "months_packed": pack_months(rule["id"], months), "runs_packed": pack_runs(rule["id"], history)})
    # Hand them back.
    return rows


# List what changed since the last run: verdicts first, then rules, then what the publisher says about itself.
def changes_since(previous_run, old_verdicts, new_verdicts, old_results, new_results, uses, watch_rows):
    # The very first run has nothing to compare with.
    if previous_run is None:
        # No rows, and the report says this is the first run.
        return []
    # The name of each decision.
    use_names = {use["id"]: use["name"] for use in uses}
    # The finished rows.
    rows = []
    # Last run's overall verdict for each decision.
    before = {v["use_id"]: v["verdict"] for v in old_verdicts if v["run_id"] == previous_run and v["dataset_id"] == "overall"}
    # Each overall verdict tonight.
    for verdict in new_verdicts:
        # Only those that moved, and only overall.
        if verdict["dataset_id"] == "overall" and before.get(verdict["use_id"]) not in (None, verdict["verdict"]):
            # One row.
            rows.append({"kind": "Verdict", "item": use_names[verdict["use_id"]], "before": before[verdict["use_id"]], "after": verdict["verdict"], "previous_run": previous_run})
    # Last run's outcome for each rule.
    before = {r["rule_id"]: r["status"] for r in old_results if r["run_id"] == previous_run}
    # Each rule tonight.
    for result in new_results:
        # Only those that moved.
        if before.get(result["rule_id"]) not in (None, result["status"]):
            # One row.
            rows.append({"kind": "Rule", "item": result["rule_id"], "before": before[result["rule_id"]], "after": result["status"], "previous_run": previous_run})
    # Anything the publisher says about itself that changed tonight.
    for row in watch_rows:
        # Only those marked as changed.
        if row["changed"]:
            # One row, without the wording, which the Source Watch table holds.
            rows.append({"kind": "Publisher", "item": row["item"], "before": "An earlier wording", "after": row["value"], "previous_run": previous_run})
    # Number them, so the report can keep this order.
    for number, row in enumerate(rows, start=1):
        # Verdicts come first, as built above.
        row["change_order"] = number
    # Hand them back.
    return rows
