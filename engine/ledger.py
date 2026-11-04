# The change ledger: fingerprint every record each run, compare with the last run, and record what changed.
# Nobody can buy this history later, because it only starts when the first run does. A changed record isn't automatically an error: the publisher says records can change as quality assurance continues.

# Forms file paths for SQL.
from engine.layers import sql_path

# How many changed records are kept per run for people to look at. The true totals are always recorded.
DETAIL_CAP = 200


# Build tonight's fingerprints: a stable hash of each record's address and contents.
def build_fingerprints(con):
    # MD5 is used because, unlike the database's own hash, it gives the same answer on every version.
    con.execute("""
        CREATE OR REPLACE TEMP TABLE fingerprints_now AS
        SELECT
            md5_number_lower(obs_id) AS obs_key,
            md5_number_lower(coalesce(raw_result, '') || '|' || coalesce(unit, '') || '|' || coalesce(det_code, '') || '|' || coalesce(raw_time, '') || '|' || coalesce(purpose, '') || '|' || coalesce(point_id, '')) AS content_key,
            sample_month,
            stream,
            raw_result
        FROM silver.results
    """)


# Compare tonight's fingerprints with the last run's, and return the summary and the detail.
def compare(con, state_file, run_id, as_of, results_available):
    # A night with no results can't be compared, and mustn't replace the good fingerprints.
    if not results_available:
        # Say that nothing was compared.
        return {"run_id": run_id, "as_of": as_of.isoformat(), "is_baseline": False, "compared": False, "records_now": 0, "records_new": 0, "records_changed": 0, "records_removed": 0, "lab_status_replaced": 0}, [], []
    # Fingerprint tonight's records.
    build_fingerprints(con)
    # The very first run has nothing to compare with, so it sets the baseline.
    if not state_file.exists():
        # Tonight's row count is all there is to record.
        count = con.execute("SELECT count(*) FROM fingerprints_now").fetchone()[0]
        # Mark this run as the start of tracking.
        return {"run_id": run_id, "as_of": as_of.isoformat(), "is_baseline": True, "compared": True, "records_now": count, "records_new": 0, "records_changed": 0, "records_removed": 0, "lab_status_replaced": 0}, [], []
    # Load last time's fingerprints.
    con.execute(f"CREATE OR REPLACE TEMP TABLE fingerprints_before AS SELECT * FROM read_parquet('{sql_path(state_file)}')")
    # Compare only months both runs cover, because the oldest month drops out of the rolling window and that isn't a removal.
    con.execute("""
        CREATE OR REPLACE TEMP TABLE changes AS
        WITH shared_months AS (
            SELECT DISTINCT fetch_window AS m FROM (SELECT substr(fetch_window, 1, 7) AS fetch_window FROM silver.results)
            INTERSECT SELECT DISTINCT sample_month FROM fingerprints_before
        )
        SELECT
            s.obs_id AS source_url,
            coalesce(n.sample_month, b.sample_month) AS sample_month,
            coalesce(n.stream, b.stream) AS stream,
            b.raw_result AS result_before,
            n.raw_result AS result_now,
            CASE WHEN b.obs_key IS NULL THEN 'New' WHEN n.obs_key IS NULL THEN 'Removed' ELSE 'Changed' END AS change_kind
        FROM fingerprints_now n
        FULL OUTER JOIN fingerprints_before b ON n.obs_key = b.obs_key
        LEFT JOIN (SELECT obs_id, md5_number_lower(obs_id) AS obs_key FROM silver.results) s ON s.obs_key = n.obs_key
        WHERE (b.obs_key IS NULL)
           OR (n.obs_key IS NULL AND b.sample_month IN (SELECT m FROM shared_months))
           OR (n.obs_key IS NOT NULL AND b.obs_key IS NOT NULL AND n.content_key <> b.content_key)
    """)
    # Count each kind of change, and how many lab status rows have since gained a real value.
    new, changed, removed, replaced = con.execute("""
        SELECT count(*) FILTER (WHERE change_kind = 'New'), count(*) FILTER (WHERE change_kind = 'Changed'), count(*) FILTER (WHERE change_kind = 'Removed'),
               count(*) FILTER (WHERE change_kind = 'Changed' AND result_before = 'Sample sent to sub contract lab')
        FROM changes
    """).fetchone()
    # The summary for tonight.
    summary = {"run_id": run_id, "as_of": as_of.isoformat(), "is_baseline": False, "compared": True, "records_now": con.execute("SELECT count(*) FROM fingerprints_now").fetchone()[0], "records_new": new, "records_changed": changed, "records_removed": removed, "lab_status_replaced": replaced}
    # Changes by month, so the page can show where they fall. Sample months only: a trend by run date builds up from the first run.
    by_month = [{"run_id": run_id, "sample_month": m, "change_kind": k, "records": c} for m, k, c in con.execute("SELECT sample_month, change_kind, count(*) FROM changes GROUP BY 1, 2 ORDER BY 1, 2").fetchall()]
    # The changed and removed records people will want to look at, up to the cap. New records are normal and not listed.
    detail = [{"run_id": run_id, "as_of": as_of.isoformat(), "source_url": u, "sample_month": m, "stream": s, "result_before": b, "result_now": n, "change_kind": k} for u, m, s, b, n, k in con.execute(f"SELECT source_url, sample_month, stream, result_before, result_now, change_kind FROM changes WHERE change_kind <> 'New' ORDER BY sample_month DESC, source_url LIMIT {DETAIL_CAP}").fetchall()]
    # Hand back all three.
    return summary, by_month, detail


# Save tonight's fingerprints for tomorrow's comparison.
def save_fingerprints(con, state_file, results_available):
    # A night with no results keeps the last good fingerprints.
    if not results_available:
        # Nothing to save.
        return
    # Make the folder if it's missing.
    state_file.parent.mkdir(parents=True, exist_ok=True)
    # Write a packed file. The hashes and result text are all it holds, and no labels.
    con.execute(f"COPY fingerprints_now TO '{sql_path(state_file)}' (FORMAT PARQUET, COMPRESSION ZSTD)")
