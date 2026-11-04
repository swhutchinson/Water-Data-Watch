-- Rules for reconciliation, completeness and timeliness.
-- Every check returns one row per thing checked, with the same six columns:
--   record_ref   what was checked
--   point_id     its sampling point, if it has one
--   sample_month its month as yyyy-MM, if it has one (this drives the rule-by-month grid)
--   failed       TRUE when it breaks the rule, FALSE when it passes, NULL when it is excluded
--   detail       one plain sentence about this record
--   source_url   a link to the source record, if there is one
-- Under @plant is the defect the engine puts into a private copy to prove the check fires.
-- Under @impact is the "does it change the answer?" test: a stated figure worked out carefully and carelessly.

-- @rule SRC-01
-- @check
SELECT source || ' ' || window_start AS record_ref, NULL AS point_id, nullif(substr(window_start, 1, 7), '') AS sample_month,
       -- A source that couldn't be read has nothing to compare, and a saved copy can only be compared with itself. Neither counts as a pass.
       CASE WHEN status = 'ok' THEN rows_received IS DISTINCT FROM api_total END AS failed,
       CASE WHEN status = 'ok' THEN 'The source says ' || coalesce(CAST(api_total AS VARCHAR), 'nothing') || '; ' || rows_received || ' rows loaded'
            WHEN status = 'copy' THEN 'Not compared: this used a saved copy, with ' || rows_received || ' rows'
            ELSE 'Not compared: this source could not be read at this check' END AS detail,
       NULL AS source_url
FROM bronze.manifest WHERE source IN ('results', 'points', 'bathing', 'codes');
-- @plant
UPDATE bronze.manifest SET rows_received = rows_received - 5 WHERE source = 'points';

-- @rule SRC-02
-- @check
WITH w AS (
    SELECT window_start, window_end, lag(window_end) OVER (ORDER BY window_start) AS previous_end
    FROM bronze.manifest WHERE source = 'results'
), outside AS (
    SELECT fetch_window, count(*) FILTER (WHERE strftime(sampled_at, '%Y-%m') <> substr(fetch_window, 1, 7)) AS strays
    FROM silver.results GROUP BY 1
)
SELECT w.window_start AS record_ref, NULL AS point_id, substr(w.window_start, 1, 7) AS sample_month,
       (w.previous_end IS NOT NULL AND w.previous_end <> w.window_start) OR coalesce(o.strays, 0) > 0 AS failed,
       'Starts ' || w.window_start || ', the last window ended ' || coalesce(w.previous_end, 'nowhere (the first)') || '; ' || coalesce(o.strays, 0) || ' records outside their window' AS detail,
       NULL AS source_url
FROM w LEFT JOIN outside o ON o.fetch_window = w.window_start;
-- @plant
UPDATE bronze.manifest SET window_start = strftime(CAST(window_start AS DATE) + INTERVAL 1 DAY, '%Y-%m-%d') WHERE source = 'results' AND window_start = (SELECT max(window_start) FROM bronze.manifest WHERE source = 'results');
-- @impact
SELECT 'Rows counted for last calendar year, if the end date is set to 31 December rather than 1 January' AS figure,
       count(*) AS careful,
       count(*) FILTER (WHERE strftime(sample_date, '%m-%d') <> '12-31') AS careless,
       'rows' AS unit
FROM silver.results WHERE year(sample_date) = year((SELECT as_of FROM silver.run_info)) - 1;

-- @rule SRC-03
-- @check
SELECT column_name AS record_ref, NULL AS point_id, NULL AS sample_month,
       NOT (in_source AND in_contract) AS failed,
       CASE WHEN in_source AND in_contract THEN 'As agreed'
            WHEN in_source THEN 'The source has added this column'
            ELSE 'The source has dropped this column' END AS detail,
       NULL AS source_url
FROM bronze.columns;
-- @plant
UPDATE bronze.columns SET in_source = FALSE WHERE column_name = 'unit';

-- @rule SRC-04
-- @check
SELECT item AS record_ref, NULL AS point_id, NULL AS sample_month,
       CASE WHEN previous_fingerprint IS NULL THEN NULL ELSE fingerprint <> previous_fingerprint END AS failed,
       CASE WHEN previous_fingerprint IS NULL THEN 'First reading: nothing to compare with yet'
            WHEN fingerprint <> previous_fingerprint THEN 'Changed since the last run: now ' || value
            ELSE 'Unchanged: ' || value END AS detail,
       NULL AS source_url
FROM bronze.source_watch WHERE kind = 'spec' AND status = 'ok';
-- @plant
UPDATE bronze.source_watch SET previous_fingerprint = 'planted', fingerprint = 'changed' WHERE kind = 'spec';

-- @rule SRC-06
-- @check
WITH today AS (
    -- The bathing season runs from May to September, and the latest one that has begun is the one to hold.
    SELECT as_of, make_date(year(as_of) - CASE WHEN month(as_of) < 5 THEN 1 ELSE 0 END, 5, 1) AS season_start FROM silver.run_info
), sources AS (
    SELECT source, min(status) AS status, min(window_start) AS window_start, max(window_end) AS window_end, max(taken_on) AS taken_on
    FROM bronze.manifest WHERE source <> 'results' GROUP BY 1
)
SELECT source AS record_ref, NULL AS point_id, NULL AS sample_month,
       CASE WHEN status = 'failed' THEN NULL
            WHEN status <> 'copy' THEN FALSE
            -- A copy of a past season no longer holds what is needed.
            WHEN CAST(window_start AS DATE) <> season_start THEN TRUE
            -- During the season and a fortnight after it, a copy over two weeks old is out of date.
            WHEN as_of < CAST(window_end AS DATE) + 14 AND CAST(taken_on AS DATE) < as_of - 14 THEN TRUE
            -- After the season, a copy taken before the season ended is missing its end.
            WHEN as_of >= CAST(window_end AS DATE) + 14 AND CAST(taken_on AS DATE) < CAST(window_end AS DATE) THEN TRUE
            ELSE FALSE END AS failed,
       CASE WHEN status = 'failed' THEN 'Could not be read at this check, and there is no copy'
            WHEN status <> 'copy' THEN 'Read live at this check'
            ELSE 'A saved copy, taken on ' || taken_on || ', of the season from ' || window_start END AS detail,
       NULL AS source_url
FROM sources, today;
-- @plant
UPDATE bronze.manifest SET status = 'copy', window_start = '2000-05-01', window_end = '2000-10-01', taken_on = '2000-10-02' WHERE source = 'bathing';

-- @rule SRC-05
-- @check
SELECT 'Rows at this check against the last run' AS record_ref, NULL AS point_id, NULL AS sample_month,
       CASE WHEN previous_rows IS NULL THEN NULL ELSE (SELECT count(*) FROM silver.results) < 0.9 * previous_rows END AS failed,
       (SELECT count(*) FROM silver.results) || ' rows at this check, ' || coalesce(CAST(previous_rows AS VARCHAR), 'none recorded') || ' at the last run' AS detail,
       NULL AS source_url
FROM silver.ledger_info;
-- @plant
UPDATE silver.ledger_info SET previous_rows = 100 * (SELECT count(*) FROM silver.results) + 100;

-- @rule COM-01
-- @check
SELECT p.point_id AS record_ref, p.point_id, NULL AS sample_month,
       r.point_id IS NULL AS failed,
       'Open in the register, with ' || CASE WHEN r.point_id IS NULL THEN 'no result in the window' ELSE 'results' END AS detail,
       '{wq_base}/sampling-point/' || p.point_id AS source_url
FROM silver.points p
LEFT JOIN (SELECT DISTINCT point_id FROM silver.results) r ON r.point_id = p.point_id
WHERE p.point_status = 'OPEN';
-- @plant
UPDATE silver.points SET point_status = 'OPEN', point_id = 'PLANTED-' || point_id WHERE point_id IN (SELECT point_id FROM silver.points ORDER BY point_id LIMIT 3);

-- @rule COM-02
-- @check
WITH calendar AS (
    -- Every month from the first in the data up to last month, so a month with no samples at all still gets a row.
    SELECT strftime(m, '%Y-%m') AS sample_month
    FROM (SELECT unnest(generate_series(date_trunc('month', min(sample_date)), date_trunc('month', (SELECT as_of FROM silver.run_info)) - INTERVAL 1 MONTH, INTERVAL 1 MONTH)) AS m FROM silver.results)
), counts AS (
    SELECT stream, sample_month, count(DISTINCT sample_id) AS samples FROM silver.results WHERE sample_month IS NOT NULL GROUP BY 1, 2
), compared AS (
    -- Each stream in each month, with zero where it sent nothing, against the same month a year earlier.
    SELECT s.stream, c.sample_month, coalesce(n.samples, 0) AS samples, prior.samples AS samples_year_before
    FROM (SELECT DISTINCT stream FROM silver.results) s
    CROSS JOIN calendar c
    LEFT JOIN counts n ON n.stream = s.stream AND n.sample_month = c.sample_month
    JOIN counts prior ON prior.stream = s.stream AND prior.sample_month = strftime(CAST(c.sample_month || '-01' AS DATE) - INTERVAL 1 YEAR, '%Y-%m')
    WHERE prior.samples >= 20
)
SELECT stream || ' ' || sample_month AS record_ref, NULL AS point_id, sample_month,
       samples < 0.5 * samples_year_before AS failed,
       samples || ' samples, against ' || samples_year_before || ' in the same month a year earlier' AS detail,
       NULL AS source_url
FROM compared;
-- @plant
DELETE FROM silver.results WHERE stream = (SELECT stream FROM silver.results GROUP BY 1 ORDER BY count(*) DESC LIMIT 1) AND sample_month = strftime((SELECT as_of FROM silver.run_info) - INTERVAL 2 MONTH, '%Y-%m');
-- @impact
SELECT 'Samples in the latest complete month, as a chart of the raw data would show them, against the same month a year earlier' AS figure,
       samples_year_before AS careful,
       samples AS careless,
       'samples' AS unit
FROM silver.months
WHERE sample_month = strftime((SELECT as_of FROM silver.run_info) - INTERVAL 1 MONTH, '%Y-%m') AND samples_year_before IS NOT NULL;

-- @rule TIM-01
-- @check
WITH stream_dates AS (
    SELECT stream, sample_date FROM silver.results WHERE sample_date IS NOT NULL AND NOT is_seasonal GROUP BY 1, 2
), gaps AS (
    SELECT stream, sample_date, date_diff('day', lag(sample_date) OVER (PARTITION BY stream ORDER BY sample_date), sample_date) AS gap FROM stream_dates
), summary AS (
    SELECT stream, count(*) AS dates, max(sample_date) AS newest, coalesce(max(gap), 0) AS longest_gap FROM gaps GROUP BY 1
)
SELECT stream AS record_ref, NULL AS point_id, NULL AS sample_month,
       date_diff('day', newest, (SELECT as_of FROM silver.run_info)) > greatest(21, longest_gap) AS failed,
       'Newest result ' || strftime(newest, '%-d %b %Y') || ', ' || date_diff('day', newest, (SELECT as_of FROM silver.run_info)) || ' days ago. Its longest silence in the window was ' || longest_gap || ' days' AS detail,
       NULL AS source_url
FROM summary WHERE dates >= 60;
-- @plant
DELETE FROM silver.results WHERE stream = (SELECT stream FROM silver.results WHERE NOT is_seasonal GROUP BY 1 ORDER BY count(*) DESC LIMIT 1) AND sample_date > (SELECT as_of FROM silver.run_info) - INTERVAL 150 DAY;
-- @impact
SELECT 'Days since the newest result: the one date a simple check reads, against the stream that has been silent longest' AS figure,
       max(date_diff('day', newest, (SELECT as_of FROM silver.run_info))) AS careful,
       min(date_diff('day', newest, (SELECT as_of FROM silver.run_info))) AS careless,
       'days' AS unit
FROM (SELECT stream, max(sample_date) AS newest, count(DISTINCT sample_date) AS dates FROM silver.results WHERE NOT is_seasonal GROUP BY 1) WHERE dates >= 60;

-- @rule TIM-02
-- @check
SELECT sample_month AS record_ref, NULL AS point_id, sample_month,
       samples < 0.7 * samples_year_before AS failed,
       samples || ' samples so far, against ' || samples_year_before || ' in the same month a year earlier' AS detail,
       NULL AS source_url
FROM silver.months
WHERE samples_year_before IS NOT NULL AND NOT is_current_month
  AND sample_month >= strftime((SELECT as_of FROM silver.run_info) - INTERVAL 3 MONTH, '%Y-%m');
-- @plant
DELETE FROM silver.results WHERE hash(sample_id) % 10 < 8 AND sample_month = (SELECT max(sample_month) FROM silver.months WHERE NOT is_current_month AND samples_year_before IS NOT NULL AND samples >= 0.7 * samples_year_before AND sample_month >= strftime((SELECT as_of FROM silver.run_info) - INTERVAL 3 MONTH, '%Y-%m'));

-- @rule REC-01
-- @check
WITH wq AS (
    SELECT p.bathing_code, substr(r.raw_time, 1, 16) AS sample_minute, any_value(r.raw_result) AS raw_result, any_value(r.point_id) AS point_id, any_value(r.obs_id) AS obs_id
    FROM silver.results r JOIN silver.points p ON p.point_id = r.point_id
    WHERE r.det_code = '2348' AND p.bathing_code IS NOT NULL
    GROUP BY 1, 2
)
SELECT b.bathing_code || ' ' || b.sample_minute AS record_ref, w.point_id, substr(b.sample_minute, 1, 7) AS sample_month,
       w.raw_result IS NULL OR TRY_CAST(regexp_replace(w.raw_result, '[^0-9.]', '', 'g') AS DOUBLE) IS DISTINCT FROM b.ecoli AS failed,
       'Bathing service: ' || coalesce(CAST(b.ecoli AS VARCHAR), 'blank') || '. Water quality service: ' || coalesce(w.raw_result, 'no sample at that minute') AS detail,
       w.obs_id AS source_url
FROM silver.bathing b
JOIN (SELECT DISTINCT bathing_code FROM silver.points WHERE bathing_code IS NOT NULL) link ON link.bathing_code = b.bathing_code
LEFT JOIN wq w ON w.bathing_code = b.bathing_code AND w.sample_minute = b.sample_minute;
-- @plant
UPDATE silver.bathing SET ecoli = ecoli + 1 WHERE bathing_code = (SELECT min(b.bathing_code) FROM silver.bathing b JOIN silver.points p ON p.bathing_code = b.bathing_code);

-- @rule REC-02
-- @check
WITH season AS (
    SELECT min(sample_minute) AS first_minute, max(sample_minute) AS last_minute FROM silver.bathing
), seen AS (
    SELECT DISTINCT r.point_id FROM silver.results r, season s
    WHERE r.point_group = 'Bathing waters' AND substr(r.raw_time, 1, 16) BETWEEN s.first_minute AND s.last_minute
)
SELECT p.point_id AS record_ref, p.point_id, NULL AS sample_month,
       p.bathing_code IS NULL AS failed,
       CASE WHEN p.bathing_code IS NULL THEN 'No link code in the label, so this point cannot be matched automatically' ELSE 'Link code found' END AS detail,
       '{wq_base}/sampling-point/' || p.point_id AS source_url
FROM silver.points p JOIN seen ON seen.point_id = p.point_id;
-- @plant
UPDATE silver.points SET bathing_code = NULL WHERE point_id IN (SELECT DISTINCT p.point_id FROM silver.points p JOIN silver.results r ON r.point_id = p.point_id WHERE r.point_group = 'Bathing waters' AND p.bathing_code IS NOT NULL AND substr(r.raw_time, 1, 16) >= (SELECT min(sample_minute) FROM silver.bathing) ORDER BY 1 LIMIT 3);
