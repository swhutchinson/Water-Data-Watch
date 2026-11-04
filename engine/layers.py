# Builds the bronze and silver layers in DuckDB from the files the fetch step saved.
# A source that failed still gets its empty tables, so everything downstream runs and says "Not checked" rather than crashing.

# Reads saved reference files and run records.
import csv
# Opens packed files.
import gzip
# Reads each sampling point's record.
import json
# Reads the shared settings.
from engine import settings

# The columns the data contract says each results file must have.
RESULT_COLUMNS = ["id", "samplingPoint.notation", "samplingPoint.prefLabel", "samplingPoint.easting", "samplingPoint.northing", "samplingPoint.region", "samplingPoint.area", "samplingPoint.subArea", "samplingPoint.samplingPointStatus", "samplingPoint.samplingPointType", "phenomenonTime", "samplingPurpose", "sampleMaterialType", "determinand.notation", "determinand.prefLabel", "result", "unit"]


# Turn a path into the form DuckDB expects in SQL.
def sql_path(path):
    # Forward slashes work on every system.
    return str(path).replace("\\", "/")


# Read a sampling point's nested field down to its label.
def label_of(value):
    # Fields come as small records with a label inside.
    if isinstance(value, dict):
        # Hand back the label.
        return value.get("prefLabel")
    # Anything else is passed through unchanged.
    return value


# Create the empty bronze tables, so they exist whatever happens next.
def create_bronze(con, manifest, watch, previous_watch):
    # The three layers, as separate schemas, so the rules read like any warehouse's.
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze; CREATE SCHEMA IF NOT EXISTS silver; CREATE SCHEMA IF NOT EXISTS gold;")
    # The results table starts with the agreed columns, all as text, exactly as served.
    con.execute("CREATE OR REPLACE TABLE bronze.results (" + ", ".join(f'"{name}" VARCHAR' for name in RESULT_COLUMNS) + ", fetch_window VARCHAR)")
    # The register, flattened to the fields the rules use.
    con.execute("CREATE OR REPLACE TABLE bronze.points (notation VARCHAR, prefLabel VARCHAR, status VARCHAR, point_type VARCHAR, area VARCHAR, sub_area VARCHAR, wkt VARCHAR)")
    # The second service's samples.
    con.execute("CREATE OR REPLACE TABLE bronze.bathing (bathing_code VARCHAR, sampled_at VARCHAR, ecoli VARCHAR, ecoli_qualifier VARCHAR)")
    # The official code lists.
    con.execute("CREATE OR REPLACE TABLE bronze.codes (code_list VARCHAR, code VARCHAR, label VARCHAR)")
    # The record of what was asked for and what came back.
    con.execute("CREATE OR REPLACE TABLE bronze.manifest (source VARCHAR, window_start VARCHAR, window_end VARCHAR, api_total BIGINT, rows_received BIGINT, calls BIGINT, seconds DOUBLE, status VARCHAR, error VARCHAR)")
    # The database refuses an empty list, and a night when nothing could be fetched has an empty record.
    if manifest:
        # Fill it from the fetch step's record. Rows received are counted from the files in load_files.
        con.executemany("INSERT INTO bronze.manifest VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)", [[m["source"], m["window_start"], m["window_end"], m["api_total"], m["calls"], m["seconds"], m["status"], m["error"]] for m in manifest])
    # What the publisher says about itself tonight, beside what it said last time.
    con.execute("CREATE OR REPLACE TABLE bronze.source_watch (item VARCHAR, kind VARCHAR, value VARCHAR, fingerprint VARCHAR, status VARCHAR, checked_on VARCHAR, previous_fingerprint VARCHAR)")
    # The same applies to the publisher's statements.
    if watch:
        # Fill it in.
        con.executemany("INSERT INTO bronze.source_watch VALUES (?, ?, ?, ?, ?, ?, ?)", [[w["item"], w["kind"], w["value"], w["fingerprint"], w["status"], w["checked_on"], previous_watch.get(w["item"])] for w in watch])
    # Which columns arrived, compared with the contract. Filled in by load_files.
    con.execute("CREATE OR REPLACE TABLE bronze.columns (column_name VARCHAR, in_source BOOLEAN, in_contract BOOLEAN)")


# Load the saved files into bronze, and say which sources are usable.
def load_files(con, raw_dir, manifest):
    # Every source that reported a failed download is unavailable from the start.
    available = {name: not any(m["status"] != "ok" for m in manifest if m["source"] == name) for name in ("results", "points", "bathing", "codes")}
    # Results come first.
    files = sorted(raw_dir.glob("results_*.csv.gz"))
    # A source with no files at all is unavailable too.
    if not files:
        # Mark it.
        available["results"] = False
    # Only load results that arrived whole.
    if available["results"]:
        # A malformed file makes the source unavailable, not the run crash.
        try:
            # The columns that actually arrived, read from each file's own header line.
            seen = set()
            # The files that hold at least one row.
            with_rows = []
            # Each month's file.
            for path in files:
                # Open the packed file as text.
                with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
                    # The first line holds the column names.
                    seen |= set(next(csv.reader([handle.readline()]), []))
                    # A second line means this month has rows. An empty month is valid, but the database can't read its columns from a header alone.
                    if handle.readline():
                        # Keep it for loading.
                        with_rows.append(path)
            # Every contract column and every arriving column, side by side.
            for name in sorted(seen | set(RESULT_COLUMNS)):
                # Record whether each side has it.
                con.execute("INSERT INTO bronze.columns VALUES (?, ?, ?)", [name, name in seen, name in RESULT_COLUMNS])
            # A missing contract column means the source can't be used until the contract is updated.
            if set(RESULT_COLUMNS) - seen:
                # Mark it, and say why in the log.
                available["results"] = False
                # Name the missing columns.
                print("results: columns missing from the source:", sorted(set(RESULT_COLUMNS) - seen), flush=True)
            # Otherwise load the agreed columns, with the window worked out from the file name.
            elif with_rows:
                # Read every file that has rows as text, with a column naming the file each row came from.
                source = f"read_csv({[sql_path(p) for p in with_rows]!r}, header = true, all_varchar = true, union_by_name = true, filename = 'source_file', quote = '\"', escape = '\"')"
                # Copy across, as text.
                con.execute("INSERT INTO bronze.results SELECT " + ", ".join(f'"{name}"' for name in RESULT_COLUMNS) + f", regexp_extract(source_file, 'results_([0-9]{{4}}-[0-9]{{2}})', 1) || '-01' FROM {source}")
        # Anything that stopped the file being read.
        except Exception as error:
            # The source can't be used tonight.
            available["results"] = False
            # Say why in the log.
            print("results: couldn't read the files:", str(error)[:300], flush=True)
    # The register is next.
    points_file = raw_dir / "points.jsonl.gz"
    # Only read it if the download finished.
    if available["points"] and points_file.exists():
        # Rows to insert.
        rows = []
        # Open the packed file.
        with gzip.open(points_file, "rt", encoding="utf-8") as lines:
            # One sampling point per line.
            for line in lines:
                # Parse it.
                point = json.loads(line)
                # Keep the fields the rules use.
                rows.append([point.get("notation"), point.get("prefLabel"), label_of(point.get("samplingPointStatus")), label_of(point.get("samplingPointType")), label_of(point.get("area")), label_of(point.get("subArea")), (point.get("geometry") or {}).get("asWKT")])
        # Load them.
        con.executemany("INSERT INTO bronze.points VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    # A missing file means the source is unavailable.
    else:
        # Mark it.
        available["points"] = False
    # The bathing water samples are next.
    bathing_file = raw_dir / "bathing.jsonl.gz"
    # Only read them if the download finished.
    if available["bathing"] and bathing_file.exists():
        # Load all four fields as text.
        con.execute(f"INSERT INTO bronze.bathing SELECT * FROM read_json('{sql_path(bathing_file)}', format = 'newline_delimited', columns = {{bathing_code: 'VARCHAR', sampled_at: 'VARCHAR', ecoli: 'VARCHAR', ecoli_qualifier: 'VARCHAR'}})")
    # A missing file means the source is unavailable.
    else:
        # Mark it.
        available["bathing"] = False
    # The official code lists are last.
    codes_file = raw_dir / "codes.jsonl.gz"
    # Only read them if the download finished.
    if available["codes"] and codes_file.exists():
        # Load all three fields as text.
        con.execute(f"INSERT INTO bronze.codes SELECT * FROM read_json('{sql_path(codes_file)}', format = 'newline_delimited', columns = {{code_list: 'VARCHAR', code: 'VARCHAR', label: 'VARCHAR'}})")
    # A missing file means the source is unavailable.
    else:
        # Mark it.
        available["codes"] = False
    # Record how many rows each monthly window really delivered.
    con.execute("UPDATE bronze.manifest m SET rows_received = coalesce((SELECT count(*) FROM bronze.results r WHERE r.fetch_window = m.window_start), 0) WHERE source = 'results'")
    # Record how many points arrived.
    con.execute("UPDATE bronze.manifest SET rows_received = (SELECT count(*) FROM bronze.points) WHERE source = 'points'")
    # Record how many bathing samples arrived.
    con.execute("UPDATE bronze.manifest SET rows_received = (SELECT count(*) FROM bronze.bathing) WHERE source = 'bathing'")
    # Record how many codes arrived.
    con.execute("UPDATE bronze.manifest SET rows_received = (SELECT count(*) FROM bronze.codes) WHERE source = 'codes'")
    # Hand back which sources can be used.
    return available


# Read a SQL file and fill in the project's paths.
def read_sql(path):
    # The text of the file, with the folder of reference lists and the service address filled in.
    return path.read_text(encoding="utf-8").replace("{reference}", sql_path(settings.RULES / "reference")).replace("{wq_base}", settings.WQ_BASE)


# Build the silver layer, given the run's date and the history of earlier runs.
def build_silver(con, as_of, run_id, tracking_since, run_dates, previous_rows=None):
    # The run's date, which every "age" and "stale" check counts from.
    con.execute("CREATE OR REPLACE TABLE silver.run_info AS SELECT CAST(? AS DATE) AS as_of, ? AS run_id", [as_of.isoformat(), run_id])
    # How long the change ledger has been running, counting today.
    days_tracked = (as_of - tracking_since).days + 1
    # One row for the audit trail rule to read.
    con.execute("CREATE OR REPLACE TABLE silver.ledger_info AS SELECT ? AS tracking_since, ? AS days_tracked, CAST(? AS BIGINT) AS previous_rows", [tracking_since.isoformat(), days_tracked, previous_rows])
    # One row per day since tracking began, saying whether the engine ran that day.
    con.execute("CREATE OR REPLACE TABLE silver.run_days (day_checked DATE, had_run BOOLEAN)")
    # Fill it in, oldest first.
    con.executemany("INSERT INTO silver.run_days VALUES (?, ?)", [[(tracking_since.fromordinal(tracking_since.toordinal() + d)).isoformat(), (tracking_since.fromordinal(tracking_since.toordinal() + d)).isoformat() in run_dates] for d in range(days_tracked)])
    # Run the silver SQL.
    con.execute(read_sql(settings.SQL / "silver.sql"))


# Read a CSV the engine published on an earlier run, returning nothing if there isn't one yet.
def read_csv_rows(path):
    # No file yet means no rows.
    if not path.exists():
        # An empty list.
        return []
    # Open it with the settings Python recommends for CSV.
    with open(path, newline="", encoding="utf-8") as handle:
        # Every row as a dictionary.
        return list(csv.DictReader(handle))
