# Water Data Watch - writes the Power Query parts of the TMDL model from the column lists below and build/m/*.pq.
# Owns: the DataRepoPath parameter, the helper functions (expressions.tmdl) and the imported tables listed in TABLES.
# It never touches other tables (calculated tables and the Report Measures table are made through the MCP),
# keeps every lineageTag Desktop has written, and keeps relationships it does not own.
# Run with Power BI Desktop CLOSED:  python build/model.py
# Then reopen Desktop and refresh; if a column's type changed, refresh that table and press Ctrl+S.

# Import re to find existing lineage tags and relationship blocks
import re
# Import uuid to make lineage tags for new objects
import uuid
# Import path handling
from pathlib import Path

# The project folder (this script lives in build/)
ROOT = Path(__file__).resolve().parent.parent
# The model definition folder
DEF = ROOT / "Water Data Watch.SemanticModel" / "definition"
# The folder of readable Power Query sources
M = ROOT / "build" / "m"

# The parameter: owner/repo/branch on raw.githubusercontent.com where the nightly engine publishes its files
PARAMETER = ("DataRepoPath", '"swhutchinson/Water-Data-Watch/powerbi-data"', "Text",
             # Its description
             "Path inside raw.githubusercontent.com to this project's powerbi-data branch, where the nightly engine publishes its CSV files.")
# Helper functions: name and description (the code is build/m/<name>.pq)
FUNCTIONS = [
    # GitHub reader
    ("fnRepoCsv", "Reads one CSV from this project's powerbi-data branch on raw.githubusercontent.com (empty fields become null)."),
]
# Staging queries (not loaded): none, because every table reads one file through fnRepoCsv
STAGING = []
# Short aliases for column types: TMDL data type, format string, summarise-by, Power Query type
T = {"text": ("string", None, "none", "type text"), "int": ("int64", "#,0", "none", "Int64.Type"), "num": ("double", None, "none", "type number"),
     # Dates, date-times, and true or false values
     "date": ("dateTime", "yyyy-mm-dd", "none", "type date"), "dtz": ("dateTime", "General Date", "none", "type datetime"), "bool": ("boolean", None, "none", "type logical")}
# Imported tables: name, source file (None when build/m/<name>.pq is written by hand), description, columns (name, type alias, hidden?, description)
TABLES = [
    # The run log
    ("RunLog", None, "One row per nightly run: what it read, what it found, and the verdict for each decision. It can't be recreated later.", [
        ("run_id", "text", True, "The run's name: its start time in UTC."), ("as_of", "date", False, "The run's date."), ("started_utc", "text", True, None), ("finished_utc", "text", True, None),
        ("seconds", "int", False, "How long the run took."), ("engine_version", "text", True, None), ("register_rules", "int", False, "Rules in the register."), ("trigger", "text", True, "What started it: schedule, push or a manual run."),
        ("results_status", "text", False, None), ("points_status", "text", False, None), ("bathing_status", "text", False, None), ("codes_status", "text", False, None), ("watch_status", "text", False, None),
        ("source_rows", "int", False, "What the source said it held."), ("loaded_rows", "int", False, "What was checked."), ("api_calls", "int", False, None),
        ("rules_pass", "int", False, None), ("rules_fail", "int", False, None), ("rules_review", "int", False, None), ("rules_not_checked", "int", False, None), ("rules_no_data", "int", False, None),
        ("planted_caught", "int", False, "Planted defects the rules caught."), ("planted_tested", "int", False, "Planted defects tried."),
        ("verdict_monthly", "text", False, None), ("verdict_trend", "text", False, None), ("verdict_signoff", "text", False, None), ("verdict_ai", "text", False, None),
        ("tracking_since", "date", False, "The first run's date. Anything the engine measures goes back no further than this."), ("github_run", "text", True, None),
        ("RunNo", "int", True, "1 for the first run."), ("IsLatest", "int", True, "1 for the newest run."), ("RunUTC", "dtz", True, "When the run finished, as a date and time in UTC."), ("RunUKText", "text", True, "When the run finished in UK time, e.g. 4 Nov 02:40.")]),
    # Each rule, flat
    ("Rules", "rules_tonight.csv", "One row per rule: the register's entry with tonight's result, the planted defect result and the measured effect. Filters the exceptions and reasons.", [
        ("rule_order", "int", True, "The rule's place in the register."), ("id", "text", False, "The rule's reference."), ("rule_label", "text", False, "Reference and title, for the picker."), ("version", "int", False, None),
        ("title", "text", False, None), ("why", "text", False, None), ("dataset", "text", False, None), ("fields", "text", False, None), ("dimension", "text", False, None), ("severity", "text", False, None),
        ("fail_above", "num", False, "Fails above this percentage. Illustrative."), ("review_above", "num", False, "Needs review above this percentage. Illustrative."), ("owner_role", "text", False, "Illustrative role."), ("steward_role", "text", False, "Illustrative role."),
        ("action", "text", False, None), ("root_cause", "text", False, None), ("condition", "text", False, None), ("eligible", "int", False, "Records the rule could check."), ("failed", "int", False, "True number of failed records."), ("excluded", "int", False, "Records the rule doesn't apply to."),
        ("failed_pct", "num", False, None), ("status", "text", False, "Pass, Fail, For review, Not checked or No data."), ("note", "text", False, None), ("exceptions_shown", "int", False, None), ("exceptions_hidden", "int", False, "Failed records beyond the listing cap."),
        ("test_outcome", "text", False, "Whether the rule caught its planted defect."), ("test_failed_before", "int", True, None), ("test_failed_after", "int", True, None), ("figure", "text", False, "What the effect test measures."),
        ("careful", "num", False, None), ("careless", "num", False, None), ("unit", "text", False, None), ("effect_pct", "num", False, "How far the careless figure sits from the careful one."), ("measured", "bool", False, None), ("fix_rank", "int", False, "Order to fix things in."),
        ("months_packed", "text", True, None), ("runs_packed", "text", True, None)]),
    # The same rules, unrelated to anything, so the rule picker can highlight a row without filtering the chart
    ("RuleGrid", None, "The rule-by-month chart's data, deliberately unrelated to any table, so picking a rule highlights its row instead of removing the others.", [
        ("rule_order", "int", False, None), ("id", "text", False, None), ("title", "text", False, None), ("dimension", "text", False, None), ("severity", "text", False, None), ("status", "text", False, None),
        ("failed", "int", False, None), ("eligible", "int", False, None), ("failed_pct", "num", False, None), ("test_outcome", "text", False, None), ("effect_pct", "num", False, None), ("fix_rank", "int", False, None),
        ("owner_role", "text", False, None), ("why", "text", False, None), ("months_packed", "text", False, None), ("runs_packed", "text", False, None)]),
    # Failed records
    ("Exceptions", "exceptions.csv", "The failed records, up to 500 per rule. The true total is on Rules. Withheld labels show the point's type and code.", [
        ("rule_id", "text", True, None), ("record_ref", "text", False, None), ("point_id", "text", False, None), ("point_name", "text", False, None), ("where_label", "text", False, "The point's published name, or the rule's own reference."), ("sample_month", "text", False, None), ("month_label", "text", False, "The sample month, or Whole list for a rule that has no months."), ("detail", "text", False, None), ("source_url", "text", False, "A link to the source record, where there is one.")]),
    # Verdicts tonight
    ("Verdicts", "verdicts_tonight.csv", "Tonight's verdict for each decision and dataset, plus each decision overall. Deliberately unrelated to Uses, so the board shows every decision whatever is picked.", [
        ("run_id", "text", True, None), ("use_id", "text", False, None), ("use_name", "text", False, None), ("use_phrase", "text", False, "The decision, as worded inside a sentence."), ("use_order", "int", False, None), ("dataset_id", "text", False, None), ("dataset_name", "text", False, None), ("dataset_order", "int", False, None),
        ("verdict", "text", False, None), ("gates_failed", "int", False, None), ("gates_unchecked", "int", False, None), ("conditions_open", "int", False, None), ("in_scope", "bool", False, None), ("note", "text", False, None)]),
    # Reasons behind each verdict
    ("VerdictReasons", "verdict_reasons.csv", "Every rule behind each verdict, as a gate or a condition, so anyone can reproduce it.", [
        ("use_id", "text", True, None), ("dataset_id", "text", True, None), ("rule_id", "text", True, None), ("role", "text", False, "Gate or Condition."), ("status", "text", False, None), ("matters", "bool", False, "True when this rule is holding the decision back."), ("condition", "text", False, None)]),
    # The decisions
    ("Uses", "uses.csv", "The decisions the data might feed.", [
        ("use_id", "text", True, None), ("use_order", "int", True, None), ("use_name", "text", False, None), ("question", "text", False, None), ("needs", "text", False, None)]),
    # Dataset passports
    ("Datasets", "datasets.csv", "A passport for each dataset. Owner and steward roles are illustrative.", [
        ("dataset_id", "text", True, None), ("dataset_order", "int", True, None), ("dataset_name", "text", False, None), ("source", "text", False, None), ("address", "text", False, None), ("licence", "text", False, None), ("attribution", "text", False, None),
        ("owner_role", "text", False, None), ("steward_role", "text", False, None), ("refresh", "text", False, None), ("coverage", "text", False, None), ("safe_for", "text", False, None), ("how_to_use", "text", False, None), ("known_issues", "text", False, None)]),
    # Same data, different answer
    ("SameData", None, "River figures worked out every way a person might, so the report can switch between them. Medians can't be added up, so each row is one finished figure.", [
        ("det_code", "text", True, None), ("det_name", "text", False, None), ("plain_name", "text", False, "What was measured, in plain words."), ("sub_area", "text", True, None), ("area_name", "text", False, "The sub-area, in normal capitals."), ("method", "text", False, "How below-limit results are counted."),
        ("sample_set", "text", False, None), ("month_set", "text", False, None), ("statistic", "text", False, None), ("figure", "num", False, None), ("rows_used", "int", False, None), ("rows_in_scope", "int", False, None), ("is_ranked_area", "bool", False, None), ("area_rank", "int", False, "1 is the highest figure. It describes the calculation, and says nothing about whose water is better."), ("scenario_key", "text", True, None), ("unit_label", "text", False, None)]),
    # Months
    ("Months", "months.csv", "Samples in each month, against the same month a year earlier.", [
        ("sample_month", "text", False, None), ("samples", "int", False, None), ("samples_year_before", "int", False, None), ("is_current_month", "bool", False, None), ("is_part_complete", "bool", False, None)]),
    # Freshness
    ("Freshness", "freshness.csv", "Each stream's newest result, against its own normal silence.", [
        ("stream", "text", False, None), ("is_seasonal", "bool", False, None), ("sample_dates", "int", False, None), ("newest_date", "date", False, None), ("days_silent", "int", False, None), ("longest_normal_silence", "int", False, None), ("allowed_silence", "int", False, None), ("freshness_status", "text", False, None)]),
    # Control totals
    ("ControlTotals", "control_totals.csv", "The row count at each stage, so a loss anywhere shows up.", [
        ("stage_no", "int", False, None), ("stage_name", "text", False, None), ("row_count", "int", False, None)]),
    # Requests
    ("Manifest", "manifest.csv", "What was asked of each source, and what came back.", [
        ("source", "text", False, None), ("window_start", "text", False, None), ("window_end", "text", False, None), ("api_total", "int", False, None), ("rows_received", "int", False, None), ("calls", "int", False, None), ("seconds", "num", False, None), ("status", "text", False, None), ("error", "text", False, None), ("taken_on", "date", False, "When a saved copy was taken.")]),
    # Change ledger
    ("Ledger", "history/ledger.csv", "How many records were new, changed or removed at each run. The first run sets the baseline.", [
        ("run_id", "text", True, None), ("as_of", "date", False, None), ("is_baseline", "bool", False, None), ("compared", "bool", False, None), ("records_now", "int", False, None), ("records_new", "int", False, None), ("records_changed", "int", False, None), ("records_removed", "int", False, None), ("lab_status_replaced", "int", False, None)]),
    # Publisher's statements
    ("SourceWatch", "watch_tonight.csv", "What the publisher says about itself tonight, and whether that changed.", [
        ("run_id", "text", True, None), ("item", "text", False, None), ("kind", "text", False, None), ("value", "text", False, None), ("fingerprint", "text", True, None), ("previous_fingerprint", "text", True, None), ("changed", "bool", False, None), ("status", "text", False, None), ("checked_on", "date", False, None)]),
    # Changes
    ("Changes", "changes.csv", "What moved since the last run: verdicts, rules and the publisher's statements.", [
        ("change_order", "int", False, None), ("kind", "text", False, None), ("item", "text", False, None), ("before", "text", False, None), ("after", "text", False, None), ("previous_run", "text", True, None)]),
    # Issues
    ("Issues", "history/issues.csv", "Every issue ever opened. The engine opens and closes them; due dates are illustrative.", [
        ("issue_id", "text", False, None), ("rule_id", "text", True, None), ("state", "text", False, None), ("opened_on", "date", False, None), ("opened_run", "text", True, None), ("due_on", "date", False, None), ("closed_on", "date", False, None), ("latest_status", "text", False, None), ("passes_in_a_row", "int", False, None), ("last_failed_count", "int", False, None)]),
    # Decisions
    ("Decisions", "decisions.csv", "Illustrative decisions recorded by people. The engine never writes these.", [
        ("rule", "text", True, None), ("decided_on", "date", False, None), ("decision", "text", False, None), ("decided_by", "text", False, None), ("accepted", "text", False, None), ("review_on", "date", False, None)]),
    # Coverage
    ("Coverage", "coverage.csv", "Samples in each hour of the week.", [
        ("scope", "text", False, None), ("weekday_no", "int", False, "1 is Monday."), ("hour_of_day", "int", False, None), ("samples", "int", False, None)]),
    # Map squares
    ("MapCells", "map_cells.csv", "Sampling points counted into 5 km squares. Stand-in locations stay out.", [
        ("cell_e", "int", False, None), ("cell_n", "int", False, None), ("points_total", "int", False, None), ("points_open", "int", False, None), ("points_open_silent", "int", False, None), ("results_in_window", "int", False, None)]),
    # AI survival
    ("AiSurvival", "ai_survival.csv", "How many results stay usable at each step for a model of river conditions.", [
        ("step_no", "int", False, None), ("step_name", "text", False, None), ("rows_left", "int", False, None), ("step_note", "text", False, None)]),
    # Result kinds
    ("ResultKinds", "result_kinds.csv", "How the result column splits by kind.", [
        ("result_kind", "text", False, None), ("row_count", "int", False, None), ("share_pct", "num", False, None)]),
    # One row per sampling point
    ("PointQuality", "point_quality.csv", "Each sampling point's record quality score, describing its records and never the water. Illustrative. It feeds no verdict. Withheld labels show the point's type and code.", [
        ("point_id", "text", True, "The point's reference at source."), ("point_label", "text", False, "The name shown, always unique."), ("display_name", "text", True, None), ("label_withheld", "text", True, None),
        ("point_group", "text", False, "A broad grouping of the source's point types."), ("area_name", "text", False, None), ("point_status", "text", False, None), ("location_kind", "text", False, None),
        ("map_e", "int", True, "East on the National Grid, in units of 100 m. Blank with no real location."), ("map_n", "int", True, "North on the National Grid, in units of 100 m."), ("results", "int", False, None), ("samples", "int", False, None), ("newest_date", "date", False, None),
        ("score", "num", False, "Out of 100, weighted by each check's severity. Blank with no results."), ("band", "text", False, "No flags, A few flags, Look closer or No results to check."), ("band_order", "int", True, None), ("flags", "int", False, "Records flagged by the checks in the score."), ("rules_flagged", "int", False, None),
        ("source_url", "text", False, "The point's page at source."), ("pack_id", "int", True, "The row of PointPacks holding this point.")]),
    # One row per check at a point
    ("PointChecks", "point_checks.csv", "Every check that reached each sampling point, and what it found, whether or not it counts towards the score.", [
        ("point_id", "text", True, None), ("rule_id", "text", True, None), ("checked", "int", False, "Records this check looked at here."), ("flagged", "int", False, "Records it flagged here."), ("counts_in_score", "text", False, "True if it counts towards the score.")]),
    # The map's rows
    ("PointPacks", "point_packs.csv", "The points packed into short text rows for the map, because a chart's cost grows with rows. The pickers filter this table, and it filters the points. A flagged point has a row of its own.", [
        ("pack_id", "int", True, None), ("point_group", "text", False, None), ("area_name", "text", False, None), ("band", "text", False, None), ("band_order", "int", True, None), ("located", "text", True, "False if these points have no real location."), ("points_in_pack", "int", True, None), ("packed", "text", True, "Each point as east~north~score~results~name, separated by |.")]),
    # Refresh time
    ("RefreshInfo", None, "When the data was last refreshed (UTC), captured once per refresh. The report's only \"now\".", [
        ("RefreshedUTC", "dtz", True, None), ("RefreshedUKDate", "date", True, "UK local date of the refresh."), ("RefreshedUKText", "text", True, "UK local time of the refresh, e.g. 26 Oct 18:42.")]),
]
# Relationships this script owns: name, from table.column (many side), to table.column (one side)
RELATIONSHIPS = [
    # A rule has many failed records
    ("Exceptions_Rules", "Exceptions.rule_id", "Rules.id"),
    # A rule sits behind many verdicts
    ("VerdictReasons_Rules", "VerdictReasons.rule_id", "Rules.id"),
    # A decision has many reasons
    ("VerdictReasons_Uses", "VerdictReasons.use_id", "Uses.use_id"),
    # A rule can have had many issues
    ("Issues_Rules", "Issues.rule_id", "Rules.id"),
    # A rule can have recorded decisions
    ("Decisions_Rules", "Decisions.rule", "Rules.id"),
    # A map row holds many points, so a picker or a click on the map reaches the points
    ("PointQuality_PointPacks", "PointQuality.pack_id", "PointPacks.pack_id"),
    # A point has many checks
    ("PointChecks_PointQuality", "PointChecks.point_id", "PointQuality.point_id"),
    # A rule reaches many points
    ("PointChecks_Rules", "PointChecks.rule_id", "Rules.id"),
    # A point can have many flagged records
    ("Exceptions_PointQuality", "Exceptions.point_id", "PointQuality.point_id"),
]


# Read the lineage tags already in a file: object kind + name -> tag
def existing_tags(path):
    # No file yet means no tags
    if not path.exists():
        # Empty lookup
        return {}
    # The file's text
    text = path.read_text(encoding="utf-8")
    # Tags found so far
    tags = {}
    # Each object header followed (within a few lines) by its lineageTag
    for m in re.finditer(r"^\t*(table|column|expression|measure) ('[^']+'|[^\s=]+)[^\n]*\n(?:\t+[^\n]*\n){0,8}?\t+lineageTag: ([0-9a-f-]+)", text, re.M):
        # Remember the tag under kind and unquoted name
        tags[(m.group(1), m.group(2).strip("'"))] = m.group(3)
    # Hand back the lookup
    return tags


# Indent every line of a block of M code
def indent(code, tabs):
    # Prefix each line with the tabs (blank lines stay blank)
    return "\n".join(("\t" * tabs + line) if line.strip() else "" for line in code.strip("\n").splitlines())


# Read the readable M source for a query
def source(name):
    # The .pq file's text with Windows line endings removed
    return (M / f"{name}.pq").read_text(encoding="utf-8").replace("\r\n", "\n")


# The M for a table that simply reads one file and types its columns, with a comment on each step
def plain_source(desc, path, columns):
    # Each column with its Power Query type
    typed = ", ".join(f'{{"{col}", {T[alias][3]}}}' for col, alias, _, _ in columns)
    # The whole query
    return f"""// {desc}
let
    // Read the file from the data branch
    Source = fnRepoCsv("{path}"),
    // Give every column its type. en-US means numbers use a dot, and dates are read as written, year first
    Typed = Table.TransformColumnTypes(Source, {{{typed}}}, "en-US")
in
    Typed"""


# The tag for an object: the existing one, or a new one
def tag(tags, kind, name):
    # Re-use Desktop's tag when there is one
    return tags.get((kind, name)) or str(uuid.uuid4())


# Write expressions.tmdl: the parameter, functions and staging queries
def write_expressions():
    # The file
    path = DEF / "expressions.tmdl"
    # Its current tags
    tags = existing_tags(path)
    # Output blocks
    out = []
    # The parameter's parts
    name, value, ptype, desc = PARAMETER
    # The parameter block
    out.append(f"/// {desc}\nexpression {name} = {value} meta [IsParameterQuery = true, Type = \"{ptype}\", IsParameterQueryRequired = true]\n\tlineageTag: {tag(tags, 'expression', name)}\n\tqueryGroup: Parameters\n\n\tannotation PBI_ResultType = Text\n")
    # Each function
    for name, desc in FUNCTIONS:
        # Function block, code indented two tabs
        out.append(f"/// {desc}\nexpression {name} =\n{indent(source(name), 2)}\n\tlineageTag: {tag(tags, 'expression', name)}\n\tqueryGroup: Functions\n\n\tannotation PBI_ResultType = Function\n")
    # Each staging query
    for name, desc in STAGING:
        # Staging block (not loaded: expressions are never loaded)
        out.append(f"/// {desc}\nexpression {name} =\n{indent(source(name), 2)}\n\tlineageTag: {tag(tags, 'expression', name)}\n\tqueryGroup: Staging\n\n\tannotation PBI_ResultType = Table\n")
    # Write it (text mode on Windows writes Windows line endings, as Desktop does)
    path.write_text("\n".join(out), encoding="utf-8")


# Find the DAX calculated columns already in a table's TMDL file, so a rewrite keeps them
def calculated_columns(path):
    # Nothing to keep on the first run
    if not path.exists():
        # No blocks
        return []
    # The file's text
    text = path.read_text(encoding="utf-8")
    # Each calculated column: optional /// lines, the "column X =" header, then its indented body (blank lines inside allowed)
    pattern = r"^(?:\t///[^\n]*\n)*\tcolumn [^\n]*=[^\n]*\n(?:(?:\t\t[^\n]*|[ \t]*)\n)*"
    # The blocks, without trailing blank lines
    return [m.group(0).rstrip() for m in re.finditer(pattern, text, re.M)]


# Write one imported table's TMDL file from its column spec and its .pq source
def write_table(name, path_in_repo, desc, columns):
    # The file
    path = DEF / "tables" / f"{name}.tmdl"
    # Its current tags
    tags = existing_tags(path)
    # The table header
    lines = [f"/// {desc}", f"table {name}", f"\tlineageTag: {tag(tags, 'table', name)}", ""]
    # Each column
    for col, alias, hidden, cdesc in columns:
        # Its TMDL type, format and summarise-by
        dtype, fmt, summ, _ = T[alias]
        # Description first, if any
        if cdesc:
            # Doc comment above the column
            lines.append(f"\t/// {cdesc}")
        # The column header
        lines.append(f"\tcolumn {col}")
        # Its data type
        lines.append(f"\t\tdataType: {dtype}")
        # Its format, if any
        if fmt:
            # Format string line
            lines.append(f"\t\tformatString: {fmt}")
        # Hidden columns stay out of the field list
        if hidden:
            # Hidden flag
            lines.append("\t\tisHidden")
        # Its lineage tag
        lines.append(f"\t\tlineageTag: {tag(tags, 'column', col)}")
        # How it adds up by default
        lines.append(f"\t\tsummarizeBy: {summ}")
        # The query column it comes from
        lines.append(f"\t\tsourceColumn: {col}")
        # A link to the source record shows as a link in tables
        if col == "source_url":
            # Mark it as a web address
            lines.append("\t\tdataCategory: WebUrl")
        # Blank line between columns
        lines.append("")
    # Keep DAX calculated columns added through the MCP (header "column Name =", with any /// description above it)
    for block in calculated_columns(path):
        # The block as it was, then a blank line
        lines += [block, ""]
    # The partition (the Power Query source)
    lines += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tqueryGroup: Model", "\t\tsource =", indent(plain_source(desc, path_in_repo, columns) if path_in_repo else source(name), 4), "", "\tannotation PBI_ResultType = Table", ""]
    # Write it (text mode on Windows writes Windows line endings)
    path.write_text("\n".join(lines), encoding="utf-8")


# Write relationships.tmdl, keeping relationships this script does not own
def write_relationships():
    # The file
    path = DEF / "relationships.tmdl"
    # Its current text, if any
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""
    # Existing relationship blocks: name -> block text
    blocks = {m.group(1): m.group(0).rstrip("\n") for m in re.finditer(r"^relationship (\S+)\n(?:\t[^\n]*\n?)*", text, re.M)}
    # Blocks to write
    out = []
    # The ones this script owns, re-using any existing block (Desktop may have renamed it to a GUID; then it is kept below)
    owned = set()
    # Each owned relationship
    for name, frm, to in RELATIONSHIPS:
        # Mark the name as owned
        owned.add(name)
        # Its block
        out.append(f"relationship {name}\n\tfromColumn: {frm}\n\ttoColumn: {to}")
    # Every other relationship already in the file, unless it duplicates an owned one by its columns
    for name, block in blocks.items():
        # Skip owned names
        if name in owned:
            # Already written
            continue
        # Skip a Desktop-renamed copy of an owned relationship (same from and to columns)
        if any(f"fromColumn: {frm}" in block and f"toColumn: {to}" in block for _, frm, to in RELATIONSHIPS):
            # Already written under our name
            continue
        # Keep it as it is
        out.append(block)
    # Write it (text mode on Windows writes Windows line endings)
    path.write_text("\n\n".join(out) + "\n", encoding="utf-8")


# Update model.tmdl's query order and query groups
def write_model():
    # The file
    path = DEF / "model.tmdl"
    # Its text
    text = path.read_text(encoding="utf-8")
    # Every query in display order
    order = [PARAMETER[0]] + [f for f, _ in FUNCTIONS] + [s for s, _ in STAGING] + [t[0] for t in TABLES]
    # Replace the query-order annotation
    text = re.sub(r'annotation PBI_QueryOrder = \[[^\]]*\]', "annotation PBI_QueryOrder = [" + ",".join(f'"{q}"' for q in order) + "]", text)
    # The query groups that must exist, with their descriptions
    groups = {"Functions": "Reusable helper functions (the GitHub CSV reader).", "Model": "Tables loaded into the data model."}
    # Add any missing group after the Parameters group
    for i, (g, d) in enumerate(groups.items(), start=1):
        # Only when it is not there yet
        if f"queryGroup {g}" not in text:
            # Insert it before the time-intelligence annotation
            text = text.replace("annotation __PBI_TimeIntelligenceEnabled", f"/// {d}\nqueryGroup {g}\n\n\tannotation PBI_QueryGroupOrder = {i}\n\nannotation __PBI_TimeIntelligenceEnabled", 1)
    # Write it back
    path.write_text(text, encoding="utf-8")


# Make the tables folder if this is the first run
(DEF / "tables").mkdir(exist_ok=True)
# Write the expressions
write_expressions()
# Write each imported table
for t in TABLES:
    # One file per table
    write_table(*t)
# Write the relationships
write_relationships()
# Update the model file
write_model()
# Report
print(f"Wrote {len(FUNCTIONS)} functions, {len(STAGING)} staging queries, {len(TABLES)} tables, {len(RELATIONSHIPS)} relationships")
