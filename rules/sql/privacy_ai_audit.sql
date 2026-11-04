-- Rules for privacy, readiness for AI and the audit trail. The column contract is explained at the top of reconciliation_timeliness.sql.

-- @rule PRV-01
-- @check
SELECT point_id AS record_ref, point_id, NULL AS sample_month,
       has_postcode OR has_house_number OR has_person_title OR has_domestic_word AS failed,
       -- The detail names only the kind of pattern found. It never repeats the label.
       CASE WHEN has_person_title THEN 'The label may name a person'
            WHEN has_house_number THEN 'The label may hold a house address'
            WHEN has_domestic_word THEN 'The label suggests a home'
            WHEN has_postcode THEN 'The label holds a postcode, often a business address'
            ELSE 'Nothing found' END AS detail,
       NULL AS source_url
FROM silver.points;
-- @plant
UPDATE silver.points SET has_postcode = TRUE WHERE point_id IN (SELECT point_id FROM silver.points WHERE NOT (has_postcode OR has_house_number OR has_person_title OR has_domestic_word) ORDER BY point_id LIMIT 3);

-- @rule PRV-02
-- @check
SELECT point_id AS record_ref, point_id, NULL AS sample_month,
       regexp_matches(upper(label_public), '\b[A-Z]{1,2}[0-9][0-9A-Z]? ?[0-9][A-Z]{2}\b')
         OR regexp_matches(upper(label_public), '\b[0-9]{1,3}[A-Z]? [A-Z]+ (ROAD|RD|STREET|ST|LANE|AVENUE|AVE|DRIVE|CLOSE|WAY|CRESCENT|GROVE|PLACE|TERRACE|GARDENS|COURT)\b')
         OR regexp_matches(upper(label_public), '\b(MR|MRS|MS|MISS|DR)\.? [A-Z]')
         OR regexp_matches(upper(label_public), '\b(PLC|LTD|LIMITED|LLP|UTILITIES)\b') AS failed,
       'Checked the label as it would be published' AS detail,
       NULL AS source_url
FROM silver.points WHERE label_public IS NOT NULL;
-- @plant
UPDATE silver.points SET label_public = 'PLANTED 12 HIGH STREET M1 1AA' WHERE point_id IN (SELECT point_id FROM silver.points WHERE label_public IS NOT NULL ORDER BY point_id LIMIT 3);

-- @rule AI-01
-- @check
SELECT f.short_name AS record_ref, NULL AS point_id, NULL AS sample_month,
       count(*) FILTER (WHERE r.result_kind = 'below') > 0.2 * count(*) AS failed,
       round(100.0 * count(*) FILTER (WHERE r.result_kind = 'below') / count(*), 1) || '% of river readings are below a limit, so their true value is unknown' AS detail,
       NULL AS source_url
FROM silver.results r
JOIN read_csv('{reference}/focus_determinands.csv', header = true, all_varchar = true) f ON f.det_code = r.det_code
WHERE r.is_river AND r.result_kind IN ('number', 'below')
GROUP BY f.short_name;
-- @plant
UPDATE silver.results SET raw_result = '<0.03', result_kind = 'below', limit_value = 0.03, result_value = NULL WHERE is_river AND det_code = '0116' AND result_kind = 'number';
-- @impact
WITH usual AS (
    SELECT avg(coalesce(result_value, limit_value / 2)) FILTER (WHERE result_kind IN ('number', 'below')) AS half_limit,
           avg(coalesce(result_value, 0)) FILTER (WHERE result_kind IN ('number', 'below')) AS at_zero,
           avg(coalesce(result_value, limit_value)) FILTER (WHERE result_kind IN ('number', 'below')) AS at_limit
    FROM silver.results WHERE det_code = '0192' AND is_river
)
SELECT 'Average river phosphate if below-limit results are set to the limit, against set to zero: how far the unknown part can move a training target' AS figure,
       at_zero AS careful, at_limit AS careless, 'mg/l' AS unit
FROM usual;

-- @rule AI-02
-- @check
WITH samples AS (
    SELECT DISTINCT sample_id, weekday_no, hour_of_day FROM silver.results
    WHERE is_river AND is_routine AND sampled_at IS NOT NULL
), cells AS (
    SELECT d AS weekday_no, h AS hour_of_day FROM range(1, 8) t1(d), range(0, 24) t2(h)
), counted AS (
    SELECT c.weekday_no, c.hour_of_day, count(s.sample_id) AS samples
    FROM cells c LEFT JOIN samples s ON s.weekday_no = c.weekday_no AND s.hour_of_day = c.hour_of_day GROUP BY 1, 2
)
SELECT ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][weekday_no] || ' ' || lpad(CAST(hour_of_day AS VARCHAR), 2, '0') || ':00' AS record_ref, NULL AS point_id, NULL AS sample_month,
       samples < 0.1 * (SELECT count(*) FROM samples) / 168.0 AS failed,
       samples || ' routine river samples in this hour of the week' AS detail,
       NULL AS source_url
FROM counted;
-- @plant
DELETE FROM silver.results WHERE is_river AND is_routine AND hour_of_day = (SELECT hour_of_day FROM silver.results WHERE is_river AND is_routine GROUP BY 1 ORDER BY count(*) DESC LIMIT 1);
-- @impact
SELECT 'Share of routine river samples taken on a weekday between 07:00 and 17:00, against the share of the week those hours make up' AS figure,
       100.0 * 50 / 168 AS careful,
       100.0 * count(DISTINCT sample_id) FILTER (WHERE weekday_no <= 5 AND hour_of_day BETWEEN 7 AND 16) / nullif(count(DISTINCT sample_id), 0) AS careless,
       '%' AS unit
FROM silver.results WHERE is_river AND is_routine;

-- @rule AI-03
-- @check
SELECT point_id AS record_ref, point_id, NULL AS sample_month,
       count(DISTINCT sample_id) < 24 AS failed,
       count(DISTINCT sample_id) || ' ammonia samples in the 24 month window' AS detail,
       '{wq_base}/sampling-point/' || point_id AS source_url
FROM silver.results WHERE det_code = '0111' AND is_river
GROUP BY point_id;
-- @plant
DELETE FROM silver.results WHERE det_code = '0111' AND is_river AND point_id IN (SELECT point_id FROM silver.results WHERE det_code = '0111' AND is_river GROUP BY 1 HAVING count(DISTINCT sample_id) >= 24 ORDER BY count(*) DESC LIMIT 3) AND hash(sample_id) % 50 > 0;

-- @rule AI-04
-- @check
WITH samples AS (
    SELECT DISTINCT sample_id, stream, substr(raw_time, 12, 5) AS clock, any_value(point_id) OVER (PARTITION BY sample_id) AS point_id, any_value(sample_month) OVER (PARTITION BY sample_id) AS sample_month, any_value(obs_id) OVER (PARTITION BY sample_id) AS obs_id
    FROM silver.results
), stream_clock AS (
    SELECT stream, clock, count(*) AS at_this_time, sum(count(*)) OVER (PARTITION BY stream) AS stream_total FROM samples GROUP BY 1, 2
)
SELECT s.sample_id AS record_ref, s.point_id, s.sample_month,
       c.at_this_time >= 20 AND c.at_this_time >= 0.04 * c.stream_total AS failed,
       'Stamped ' || s.clock || ', like ' || round(100.0 * c.at_this_time / c.stream_total, 1) || '% of the ' || s.stream || ' stream' AS detail,
       s.obs_id AS source_url
FROM samples s JOIN stream_clock c ON c.stream = s.stream AND c.clock = s.clock;
-- @plant
UPDATE silver.results SET raw_time = substr(raw_time, 1, 11) || '03:33:00' WHERE stream = (SELECT stream FROM silver.results WHERE NOT is_seasonal GROUP BY 1 HAVING count(DISTINCT sample_id) >= 20 ORDER BY count(*) DESC LIMIT 1);
-- @impact
SELECT 'Share of all samples that look like they were taken at the stated minute, if every clock time is believed, against if stamped times are set aside' AS figure,
       100.0 * (1 - sum(CASE WHEN at_this_time >= 20 AND at_this_time >= 0.04 * stream_total THEN at_this_time ELSE 0 END) / nullif(sum(at_this_time), 0)) AS careful,
       100.0 AS careless,
       '%' AS unit
FROM (SELECT stream, clock, count(*) AS at_this_time, sum(count(*)) OVER (PARTITION BY stream) AS stream_total
      FROM (SELECT DISTINCT sample_id, stream, substr(raw_time, 12, 5) AS clock FROM silver.results) GROUP BY 1, 2);

-- @rule AUD-01
-- @check
SELECT 'Day ' || d AS record_ref, NULL AS point_id, NULL AS sample_month,
       d > (SELECT days_tracked FROM silver.ledger_info) AS failed,
       (SELECT 'Tracking since ' || tracking_since || ': ' || days_tracked || ' of 35 days' FROM silver.ledger_info) AS detail,
       NULL AS source_url
FROM range(1, 36) t(d);
-- @plant
UPDATE silver.ledger_info SET days_tracked = 0;

-- @rule AUD-02
-- @check
SELECT item AS record_ref, NULL AS point_id, NULL AS sample_month,
       -- A statement that couldn't be read is left out and counted as excluded, because nobody knows what it says.
       CASE WHEN status = 'ok' THEN value <> 'Open Government Licence' END AS failed,
       CASE WHEN status = 'ok' THEN 'States: ' || value ELSE 'Could not be read at this check' END AS detail,
       NULL AS source_url
FROM bronze.source_watch WHERE kind = 'licence';
-- @plant
UPDATE bronze.source_watch SET value = 'Not stated' WHERE kind = 'licence' AND item = (SELECT min(item) FROM bronze.source_watch WHERE kind = 'licence' AND value = 'Open Government Licence');

-- @rule AUD-03
-- @check
SELECT strftime(day_checked, '%Y-%m-%d') AS record_ref, NULL AS point_id, strftime(day_checked, '%Y-%m') AS sample_month,
       NOT had_run AS failed,
       CASE WHEN had_run THEN 'The engine ran' ELSE 'No run recorded on this day' END AS detail,
       NULL AS source_url
FROM silver.run_days;
-- @plant
INSERT INTO silver.run_days VALUES (DATE '2000-01-01', FALSE), (DATE '2000-01-02', FALSE), (DATE '2000-01-03', FALSE);
