# Opens and closes issues automatically from each night's results. People's decisions come from rules/decisions.yaml, and the engine never writes to it.

# Works out due dates.
from datetime import timedelta
# Reads the decisions file.
import yaml
# Reads the shared settings.
from engine import settings
# The outcomes a rule can have.
from engine.checks import FAIL, NOT_CHECKED, PASS, REVIEW


# Bring the issue list up to date with tonight's results.
def update_issues(previous, rules, results, as_of, run_id):
    # Tonight's result for each rule.
    status = {r["rule_id"]: r for r in results}
    # The register's entry for each rule.
    register = {r["id"]: r for r in rules}
    # Start from every issue already known, including closed ones, so history is kept.
    issues = [dict(i) for i in previous]
    # The issue currently open for each rule.
    open_now = {i["rule_id"]: i for i in issues if i["state"] == "Open"}
    # Each rule.
    for rule_id, row in status.items():
        # The issue open for this rule, if any.
        current = open_now.get(rule_id)
        # A rule that couldn't run tells us nothing, so its issue stays exactly as it is.
        if row["status"] == NOT_CHECKED:
            # On to the next rule.
            continue
        # A failure or a review item.
        if row["status"] in (FAIL, REVIEW):
            # No open issue yet means this is the first night of the problem.
            if current is None:
                # This rule's register entry.
                rule = register[rule_id]
                # How long is allowed for a response, by severity. These days are illustrative.
                allowed = settings.RESPONSE_DAYS[rule["severity"]]
                # Open a new issue.
                issues.append({"issue_id": f"{rule_id}-{as_of.isoformat()}", "rule_id": rule_id, "state": "Open", "opened_on": as_of.isoformat(), "opened_run": run_id, "due_on": (as_of + timedelta(days=allowed)).isoformat(), "closed_on": "", "latest_status": row["status"], "passes_in_a_row": 0, "last_failed_count": row["failed"]})
            # It was already open.
            else:
                # Record tonight's status and how many records it affects.
                current.update({"latest_status": row["status"], "passes_in_a_row": 0, "last_failed_count": row["failed"]})
        # A pass moves an open issue towards closing.
        elif row["status"] == PASS and current is not None:
            # One more pass in a row.
            current["passes_in_a_row"] = int(current["passes_in_a_row"]) + 1
            # Record tonight's status.
            current.update({"latest_status": row["status"], "last_failed_count": row["failed"]})
            # Enough passes in a row closes it.
            if current["passes_in_a_row"] >= settings.PASSES_TO_CLOSE:
                # Close it, with the date.
                current.update({"state": "Closed", "closed_on": as_of.isoformat()})
    # Hand back the full list.
    return issues


# Read the decisions people have recorded.
def load_decisions():
    # The file may be empty.
    return yaml.safe_load((settings.RULES / "decisions.yaml").read_text(encoding="utf-8")) or []
