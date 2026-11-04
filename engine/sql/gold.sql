-- GOLD LAYER: small, pre-shaped tables for the report. No half a million rows in the model.
-- These summarise; nothing here changes a value. Every governed figure names the method that produced it.

-- MONTH SUMMARY: rows by month, stream and kind of result. Its total must equal the source's total, which the control strip shows.
CREATE OR REPLACE TABLE gold.month_summary AS
SELECT sample_month, stream, purpose_group, point_group, result_kind, count(*) AS row_count, count(DISTINCT sample_id) AS samples
FROM silver.results GROUP BY ALL;

-- STREAM BY MONTH: samples per stream per month, for the freshness view.
CREATE OR REPLACE TABLE gold.stream_month AS
SELECT r.stream, r.sample_month, count(DISTINCT r.sample_id) AS samples, count(*) AS row_count, any_value(m.is_part_complete) AS month_part_complete
FROM silver.results r LEFT JOIN silver.months m ON m.sample_month = r.sample_month
WHERE r.sample_month IS NOT NULL
GROUP BY 1, 2;

-- MONTHS: each month's samples, beside the same month a year earlier.
CREATE OR REPLACE TABLE gold.months AS SELECT * FROM silver.months;

-- FRESHNESS: each stream's newest result against its own normal silence, measured from the run's date.
CREATE OR REPLACE TABLE gold.freshness AS
WITH stream_dates AS (
    SELECT stream, any_value(is_seasonal) AS is_seasonal, sample_date FROM silver.results WHERE sample_date IS NOT NULL GROUP BY stream, sample_date
), gaps AS (
    SELECT *, date_diff('day', lag(sample_date) OVER (PARTITION BY stream ORDER BY sample_date), sample_date) AS gap FROM stream_dates
)
SELECT
    stream,
    any_value(is_seasonal) AS is_seasonal,
    count(*) AS sample_dates,
    strftime(max(sample_date), '%Y-%m-%d') AS newest_date,
    date_diff('day', max(sample_date), (SELECT as_of FROM silver.run_info)) AS days_silent,
    coalesce(max(gap), 0) AS longest_normal_silence,
    greatest(21, coalesce(max(gap), 0)) AS allowed_silence,
    CASE
        WHEN any_value(is_seasonal) THEN 'Seasonal'
        WHEN count(*) < 60 THEN 'Too few dates to judge'
        WHEN date_diff('day', max(sample_date), (SELECT as_of FROM silver.run_info)) > greatest(21, coalesce(max(gap), 0)) THEN 'Late'
        ELSE 'On time'
    END AS freshness_status
FROM gaps GROUP BY stream;

-- COVERAGE: samples in each hour of the week. Hour by weekday is what a model would or wouldn't have seen.
CREATE OR REPLACE TABLE gold.coverage AS
WITH samples AS (
    SELECT DISTINCT sample_id, weekday_no, hour_of_day, is_river AND is_routine AS routine_river FROM silver.results WHERE sampled_at IS NOT NULL
), scopes AS (
    SELECT 'Routine river samples' AS scope, weekday_no, hour_of_day FROM samples WHERE routine_river
    UNION ALL SELECT 'All samples', weekday_no, hour_of_day FROM samples
), cells AS (
    SELECT s.scope, d AS weekday_no, h AS hour_of_day FROM (VALUES ('Routine river samples'), ('All samples')) s(scope), range(1, 8) t1(d), range(0, 24) t2(h)
)
SELECT c.scope, c.weekday_no, c.hour_of_day, count(s.scope) AS samples
FROM cells c LEFT JOIN scopes s ON s.scope = c.scope AND s.weekday_no = c.weekday_no AND s.hour_of_day = c.hour_of_day
GROUP BY 1, 2, 3;

-- SAME DATA, DIFFERENT ANSWER: each figure worked out every way a person might, so the report can switch between them without touching half a million rows.
-- Medians can't be added up, so they are worked out here, and the report only ever reads one row.
CREATE OR REPLACE TABLE gold.same_data AS
WITH focus AS (
    SELECT * FROM read_csv('{reference}/focus_determinands.csv', header = true, all_varchar = true)
), base AS (
    SELECT f.det_code, f.short_name AS det_name, f.plain_name, r.sub_area, r.is_routine, coalesce(m.is_part_complete, FALSE) AS is_part_complete, r.result_kind, r.result_value, r.limit_value
    FROM silver.results r JOIN focus f ON f.det_code = r.det_code LEFT JOIN silver.months m ON m.sample_month = r.sample_month
    WHERE r.is_river AND r.result_kind IN ('number', 'below')
), expanded AS (
    SELECT b.det_code, b.det_name, b.plain_name, b.sub_area, me.method, s.sample_set, mo.month_set,
        -- A measured number always stays as it is. Only a below-limit result depends on the method.
        CASE WHEN b.result_kind = 'number' THEN b.result_value
             WHEN me.method = 'Dropped' THEN NULL
             WHEN me.method = 'Zero' THEN 0
             WHEN me.method = 'Half the limit' THEN b.limit_value / 2
             ELSE b.limit_value END AS v
    FROM base b, (VALUES ('Dropped'), ('Zero'), ('Half the limit'), ('The limit')) me(method), (VALUES ('All samples'), ('Routine samples')) s(sample_set), (VALUES ('All months'), ('Complete months')) mo(month_set)
    WHERE (s.sample_set = 'All samples' OR b.is_routine) AND (mo.month_set = 'All months' OR NOT b.is_part_complete)
), by_area AS (
    SELECT det_code, det_name, plain_name, sub_area, method, sample_set, month_set, avg(v) AS mean_value, median(v) AS median_value, count(v) AS rows_used, count(*) AS rows_in_scope
    FROM expanded GROUP BY ALL
), whole_region AS (
    SELECT det_code, det_name, plain_name, 'North West' AS sub_area, method, sample_set, month_set, avg(v) AS mean_value, median(v) AS median_value, count(v) AS rows_used, count(*) AS rows_in_scope
    FROM expanded GROUP BY det_code, det_name, plain_name, method, sample_set, month_set
), combined AS (
    SELECT *, sub_area <> 'Unknown' AND sub_area NOT LIKE 'ECMAS%' AND rows_in_scope >= 100 AS is_ranked_area FROM by_area
    UNION ALL
    SELECT *, FALSE FROM whole_region
), melted AS (
    SELECT det_code, det_name, plain_name, sub_area, method, sample_set, month_set, 'Average' AS statistic, mean_value AS figure, rows_used, rows_in_scope, is_ranked_area FROM combined
    UNION ALL
    SELECT det_code, det_name, plain_name, sub_area, method, sample_set, month_set, 'Median', median_value, rows_used, rows_in_scope, is_ranked_area FROM combined
)
SELECT
    *,
    -- 1 is the highest figure among the ranked sub-areas. A rank describes this calculation, and says nothing about whose water is better.
    CASE WHEN is_ranked_area THEN rank() OVER (PARTITION BY det_code, method, sample_set, month_set, statistic, is_ranked_area ORDER BY figure DESC) END AS area_rank,
    -- A short key, so the report can find one row quickly.
    det_code || '|' || method || '|' || sample_set || '|' || month_set || '|' || statistic AS scenario_key,
    -- The unit, so each figure can be read on its own.
    (SELECT any_value(f.unit_label) FROM focus f WHERE f.det_code = melted.det_code) AS unit_label
FROM melted;

-- AI SURVIVAL: how many results remain usable at each step for a model of river conditions. Each step keeps only what passed the steps before it.
CREATE OR REPLACE TABLE gold.ai_survival AS
WITH flagged AS (
    SELECT r.sample_id, r.is_river, r.is_routine, r.result_kind, r.raw_time, r.stream, r.point_id, p.location_kind
    FROM silver.results r LEFT JOIN silver.points p ON p.point_id = r.point_id
), clocks AS (
    SELECT stream, substr(raw_time, 12, 5) AS clock, count(DISTINCT sample_id) AS at_this_time, sum(count(DISTINCT sample_id)) OVER (PARTITION BY stream) AS stream_total
    FROM flagged GROUP BY 1, 2
), regular AS (
    SELECT point_id FROM flagged WHERE is_river GROUP BY 1 HAVING count(DISTINCT sample_id) >= 24
), steps AS (
    SELECT
        f.*,
        f.is_river AS s2,
        f.location_kind = 'Inside the North West' AS s3,
        f.is_routine AS s4,
        NOT (c.at_this_time >= 20 AND c.at_this_time >= 0.04 * c.stream_total) AS s5,
        f.result_kind = 'number' AS s6,
        f.point_id IN (SELECT point_id FROM regular) AS s7
    FROM flagged f LEFT JOIN clocks c ON c.stream = f.stream AND c.clock = substr(f.raw_time, 12, 5)
)
SELECT * FROM (VALUES
    (1, 'Every result', (SELECT count(*) FROM steps), 'Everything in the window.'),
    (2, 'From rivers', (SELECT count(*) FILTER (WHERE s2) FROM steps), 'The model is about rivers, so other waters and discharges are set aside.'),
    (3, 'With a real location', (SELECT count(*) FILTER (WHERE s2 AND s3) FROM steps), 'A place the model can learn from, not a stand-in.'),
    (4, 'From routine sampling', (SELECT count(*) FILTER (WHERE s2 AND s3 AND s4) FROM steps), 'Pollution and investigation samples are real, but were taken because someone suspected a problem.'),
    (5, 'With a real clock time', (SELECT count(*) FILTER (WHERE s2 AND s3 AND s4 AND s5) FROM steps), 'Not one of the times that takes a large share of a stream.'),
    (6, 'With a measured value', (SELECT count(*) FILTER (WHERE s2 AND s3 AND s4 AND s5 AND s6) FROM steps), 'Not below a limit, above a range or a word.'),
    (7, 'From points with regular history', (SELECT count(*) FILTER (WHERE s2 AND s3 AND s4 AND s5 AND s6 AND s7) FROM steps), 'At least one sample a month on average.')
) t(step_no, step_name, rows_left, step_note);

-- POINTS, AS PUBLISHED: no raw label ever leaves this layer. A withheld label shows the point's type and code, and links to the source.
CREATE OR REPLACE TABLE gold.points_public AS
WITH counted AS (
    SELECT point_id, count(*) AS results_in_window, count(DISTINCT sample_id) AS samples_in_window, strftime(max(sample_date), '%Y-%m-%d') AS newest_date FROM silver.results GROUP BY 1
)
SELECT
    p.point_id,
    coalesce(p.label_public, p.point_group || ' point ' || p.point_id) AS display_name,
    p.label_public IS NULL AS label_withheld,
    p.point_status, p.point_group, p.area, p.sub_area, p.location_kind,
    CASE WHEN p.location_kind = 'Inside the North West' THEN p.easting END AS easting,
    CASE WHEN p.location_kind = 'Inside the North West' THEN p.northing END AS northing,
    coalesce(c.results_in_window, 0) AS results_in_window,
    coalesce(c.samples_in_window, 0) AS samples_in_window,
    c.newest_date
FROM silver.points p LEFT JOIN counted c ON c.point_id = p.point_id;

-- MAP CELLS: 8,200 points would be slow to draw, so they are counted into 5 km squares first. Stand-in locations stay out and are counted separately.
CREATE OR REPLACE TABLE gold.map_cells AS
SELECT
    CAST(floor(easting / 5000) * 5000 AS BIGINT) AS cell_e,
    CAST(floor(northing / 5000) * 5000 AS BIGINT) AS cell_n,
    count(*) AS points_total,
    count(*) FILTER (WHERE point_status = 'OPEN') AS points_open,
    count(*) FILTER (WHERE point_status = 'OPEN' AND results_in_window = 0) AS points_open_silent,
    sum(results_in_window) AS results_in_window
FROM gold.points_public
WHERE location_kind = 'Inside the North West'
GROUP BY 1, 2;

-- RESULT KINDS: how the result column splits. This is the first thing anyone converting it should see.
CREATE OR REPLACE TABLE gold.result_kinds AS
SELECT result_kind, count(*) AS row_count, round(100.0 * count(*) / nullif(sum(count(*)) OVER (), 0), 2) AS share_pct FROM silver.results GROUP BY 1;

-- CONTROL TOTALS: the row count at each stage, so a loss anywhere shows on one strip.
CREATE OR REPLACE TABLE gold.control_totals AS
SELECT * FROM (VALUES
    (1, 'What the source says it holds', (SELECT coalesce(sum(api_total), 0) FROM bronze.manifest WHERE source = 'results')),
    (2, 'What arrived', (SELECT count(*) FROM bronze.results)),
    (3, 'What was checked', (SELECT count(*) FROM silver.results)),
    (4, 'What the report summarises', (SELECT coalesce(sum(row_count), 0) FROM gold.month_summary))
) t(stage_no, stage_name, row_count);
