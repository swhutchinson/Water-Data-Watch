# Turns tonight's rule results into a verdict for each decision: Fit, Fit with conditions, Not fit or Not checked.
# There is no average score here. A gate that fails can't be outvoted by the rules that passed.

# Reads the list of uses.
import yaml
# Reads the shared settings and the outcome names.
from engine import settings
# The five outcomes a rule can have.
from engine.checks import FAIL, NO_DATA, NOT_CHECKED, PASS, REVIEW

# The four verdicts.
FIT, CONDITIONS, NOT_FIT, UNCHECKED = "Fit", "Fit with conditions", "Not fit", "Not checked"
# When datasets disagree, the overall verdict is the worst of them, in this order.
WORST_FIRST = [NOT_FIT, UNCHECKED, CONDITIONS, FIT]


# The columns of tonight's verdict file, which carries names so the report needs no lookups.
NAMED_COLUMNS = ["run_id", "use_id", "use_name", "use_phrase", "use_order", "dataset_id", "dataset_name", "dataset_order", "verdict", "gates_failed", "gates_unchecked", "conditions_open", "in_scope", "note"]


# Load the list of uses from the register folder.
def load_uses():
    # The uses, in their stated order.
    return sorted(yaml.safe_load((settings.RULES / "uses.yaml").read_text(encoding="utf-8")), key=lambda use: use["order"])


# Work out one verdict from the rules that apply.
def judge(gates, conditions):
    # Any gate that failed means Not fit, whatever else happened.
    if any(r["status"] == FAIL for r in gates):
        # A failed gate can't be outvoted.
        return NOT_FIT
    # A gate that couldn't be checked means nobody knows, and that is never a Fit.
    if any(r["status"] in (NOT_CHECKED, NO_DATA) for r in gates):
        # Grey, and never mistaken for a pass.
        return UNCHECKED
    # A gate needing review, or any condition that isn't clean, attaches conditions.
    if any(r["status"] == REVIEW for r in gates) or any(r["status"] in (FAIL, REVIEW, NOT_CHECKED) for r in conditions):
        # Usable, if the conditions are met.
        return CONDITIONS
    # Everything that matters passed.
    return FIT


# Work out every verdict, with the reasons that produced it.
def compute(uses, rules, results, run_id):
    # Tonight's result for each rule.
    status = {r["rule_id"]: r for r in results}
    # The register's entry for each rule.
    register = {r["id"]: r for r in rules}
    # The datasets on the board, in order.
    datasets = yaml.safe_load((settings.RULES / "datasets.yaml").read_text(encoding="utf-8"))
    # One row per use and dataset.
    verdicts = []
    # One row per reason.
    reasons = []
    # Each use.
    for use in uses:
        # This use's verdict for each dataset.
        found = []
        # Each dataset.
        for dataset in sorted(datasets, key=lambda d: d["order"]):
            # Some uses have no rules written for some datasets, so nothing has been checked for that pairing.
            if dataset["id"] not in use["datasets"]:
                # Grey, with a stated reason.
                verdicts.append({"run_id": run_id, "use_id": use["id"], "dataset_id": dataset["id"], "verdict": UNCHECKED, "gates_failed": 0, "gates_unchecked": 0, "conditions_open": 0, "in_scope": False, "note": "No readiness rules written for this dataset yet"})
                # On to the next dataset.
                continue
            # This dataset's own rules, plus those about the whole pipeline.
            applies = lambda rule_id: register[rule_id]["dataset"] in (dataset["id"], "pipeline")
            # The gates that apply here.
            gates = [dict(status[g], role="Gate") for g in use["gates"] if applies(g)]
            # The conditions that apply here.
            conditions = [dict(status[c], role="Condition") for c in use["conditions"] if applies(c)]
            # The verdict for this pairing.
            verdict = judge(gates, conditions)
            # Keep it for the overall verdict.
            found.append(verdict)
            # The summary row.
            verdicts.append({"run_id": run_id, "use_id": use["id"], "dataset_id": dataset["id"], "verdict": verdict, "gates_failed": sum(g["status"] == FAIL for g in gates), "gates_unchecked": sum(g["status"] in (NOT_CHECKED, NO_DATA) for g in gates), "conditions_open": sum(c["status"] in (FAIL, REVIEW, NOT_CHECKED) for c in conditions) + sum(g["status"] == REVIEW for g in gates), "in_scope": True, "note": ""})
            # Every rule that applied becomes a line of the reasons, so anyone can reproduce the verdict.
            for row in gates + conditions:
                # The register's entry for this rule.
                rule = register[row["rule_id"]]
                # One line.
                reasons.append({"use_id": use["id"], "dataset_id": dataset["id"], "rule_id": row["rule_id"], "role": row["role"], "status": row["status"], "matters": row["status"] in (FAIL, REVIEW, NOT_CHECKED) or (row["role"] == "Gate" and row["status"] == NO_DATA), "condition": rule["condition"]})
        # The overall verdict is the worst across the datasets in scope.
        overall = next(v for v in WORST_FIRST if v in found) if found else UNCHECKED
        # The overall row.
        verdicts.append({"run_id": run_id, "use_id": use["id"], "dataset_id": "overall", "verdict": overall, "gates_failed": sum(v["gates_failed"] for v in verdicts if v["use_id"] == use["id"] and v["dataset_id"] != "overall"), "gates_unchecked": sum(v["gates_unchecked"] for v in verdicts if v["use_id"] == use["id"] and v["dataset_id"] != "overall"), "conditions_open": sum(v["conditions_open"] for v in verdicts if v["use_id"] == use["id"] and v["dataset_id"] != "overall"), "in_scope": True, "note": ""})
    # Hand back both.
    return verdicts, reasons


# Add each decision's and dataset's name and order to tonight's verdicts.
def with_names(rows, uses):
    # The decisions, by their key.
    use = {u["id"]: u for u in uses}
    # The datasets on the board.
    datasets = {d["id"]: d for d in yaml.safe_load((settings.RULES / "datasets.yaml").read_text(encoding="utf-8"))}
    # The overall column comes first on the board.
    datasets["overall"] = {"name": "Overall", "order": 0}
    # A copy of each row, with the names added.
    return [{**row, "use_name": use[row["use_id"]]["name"], "use_phrase": use[row["use_id"]]["phrase"], "use_order": use[row["use_id"]]["order"], "dataset_name": datasets[row["dataset_id"]]["name"], "dataset_order": datasets[row["dataset_id"]]["order"]} for row in rows]
