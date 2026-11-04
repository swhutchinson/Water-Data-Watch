-- Rules for uniqueness, validity, consistency and accuracy. The column contract is explained at the top of reconciliation_timeliness.sql.

-- @rule UNI-01
-- @check
SELECT obs_id AS record_ref, point_id, sample_month,
       count(*) OVER (PARTITION BY obs_id) > 1 AS failed,
       'This record address appears more than once' AS detail,
       obs_id AS source_url
FROM silver.results;
-- @plant
INSERT INTO silver.results SELECT * FROM silver.results ORDER BY obs_id LIMIT 3;
-- @impact
SELECT 'Rows counted if duplicate addresses were present' AS figure, count(DISTINCT obs_id) AS careful, count(*) AS careless, 'rows' AS unit FROM silver.results;

-- @rule UNI-02
-- @check
SELECT point_id || ' ' || raw_time || ' ' || det_code AS record_ref, point_id, any_value(sample_month) AS sample_month,
       count(DISTINCT raw_result) > 1 AS failed,
       'Values recorded: ' || string_agg(DISTINCT raw_result, ' and ') AS detail,
       any_value(obs_id) AS source_url
FROM silver.results
GROUP BY point_id, raw_time, det_code;
-- @plant
INSERT INTO silver.results SELECT * REPLACE ('planted-' || obs_id AS obs_id, '999999' AS raw_result) FROM silver.results WHERE result_kind = 'number' ORDER BY obs_id LIMIT 3;
-- @impact
WITH d AS (
    SELECT point_id, raw_time, det_code, count(DISTINCT raw_result) AS versions FROM silver.results WHERE det_code = '0111' AND is_river GROUP BY 1, 2, 3
), r AS (
    SELECT r.*, d.versions, row_number() OVER (PARTITION BY r.point_id, r.raw_time, r.det_code ORDER BY r.obs_id) AS version_no
    FROM silver.results r JOIN d USING (point_id, raw_time, det_code)
    WHERE r.result_kind IN ('number', 'below')
)
SELECT 'Average river ammonia, keeping one value per point and time, against keeping them all' AS figure,
       avg(coalesce(result_value, limit_value / 2)) FILTER (WHERE version_no = 1) AS careful,
       avg(coalesce(result_value, limit_value / 2)) AS careless,
       'mg/l' AS unit
FROM r;

-- @rule UNI-03
-- @check
SELECT point_id AS record_ref, point_id, NULL AS sample_month,
       count(*) OVER (PARTITION BY label_raw) > 1 AS failed,
       CASE WHEN count(*) OVER (PARTITION BY label_raw) > 1 THEN 'Shares its label with ' || (count(*) OVER (PARTITION BY label_raw) - 1) || ' other points' ELSE 'Has its own label' END AS detail,
       '{wq_base}/sampling-point/' || point_id AS source_url
FROM silver.points;
-- @plant
UPDATE silver.points SET label_raw = 'PLANTED SHARED LABEL' WHERE point_id IN (SELECT point_id FROM silver.points ORDER BY point_id LIMIT 3);

-- @rule VAL-01
-- @check
SELECT obs_id AS record_ref, point_id, sample_month,
       result_kind = 'empty' OR (result_kind = 'text' AND text_kind IS NULL) AS failed,
       'Result reads: ' || coalesce(raw_result, 'empty') AS detail,
       obs_id AS source_url
FROM silver.results;
-- @plant
UPDATE silver.results SET raw_result = 'n/a', result_kind = 'text', text_kind = NULL, result_value = NULL WHERE obs_id IN (SELECT obs_id FROM silver.results WHERE result_kind = 'number' ORDER BY obs_id LIMIT 3);

-- @rule VAL-02
-- @check
SELECT obs_id AS record_ref, point_id, sample_month,
       result_value < 0 OR result_value > 14 AS failed,
       'pH of ' || raw_result AS detail,
       obs_id AS source_url
FROM silver.results WHERE det_code IN ('0061', '3169') AND result_kind = 'number';
-- @plant
UPDATE silver.results SET result_value = 15, raw_result = '15' WHERE obs_id IN (SELECT obs_id FROM silver.results WHERE det_code = '0061' AND result_kind = 'number' ORDER BY obs_id LIMIT 3);

-- @rule VAL-03
-- @check
SELECT obs_id AS record_ref, point_id, sample_month,
       sampled_at IS NULL OR sampled_at >= (SELECT as_of FROM silver.run_info) + INTERVAL 1 DAY AS failed,
       'Sample time reads: ' || coalesce(raw_time, 'empty') AS detail,
       obs_id AS source_url
FROM silver.results;
-- @plant
UPDATE silver.results SET sampled_at = TIMESTAMP '2099-01-01 09:00:00', raw_time = '2099-01-01T09:00:00' WHERE obs_id IN (SELECT obs_id FROM silver.results ORDER BY obs_id LIMIT 3);

-- @rule VAL-04
-- @check
SELECT point_id AS record_ref, point_id, NULL AS sample_month,
       location_kind <> 'Inside the North West' AS failed,
       location_kind || ' (' || coalesce(CAST(CAST(easting AS BIGINT) AS VARCHAR), '?') || ', ' || coalesce(CAST(CAST(northing AS BIGINT) AS VARCHAR), '?') || ')' AS detail,
       '{wq_base}/sampling-point/' || point_id AS source_url
FROM silver.points;
-- @plant
UPDATE silver.points SET easting = 500000, northing = 4, location_kind = 'Stand-in location' WHERE point_id IN (SELECT point_id FROM silver.points WHERE location_kind = 'Inside the North West' ORDER BY point_id LIMIT 3);
-- @impact
SELECT 'Share of all results that can be put on a map at their true place' AS figure,
       100.0 AS careful,
       100.0 * count(*) FILTER (WHERE p.location_kind = 'Inside the North West') / nullif(count(*), 0) AS careless,
       '%' AS unit
FROM silver.results r LEFT JOIN silver.points p ON p.point_id = r.point_id;

-- @rule VAL-05
-- @check
WITH used AS (
    SELECT DISTINCT 'determinand' AS code_list, det_code AS code FROM silver.results
    UNION SELECT DISTINCT 'purpose', purpose FROM silver.results
    UNION SELECT DISTINCT 'point_type', point_type FROM silver.results
), official AS (
    SELECT code_list, code FROM bronze.codes WHERE code_list = 'determinand'
    UNION SELECT code_list, regexp_replace(label, '\s+', ' ', 'g') FROM bronze.codes WHERE code_list IN ('purpose', 'point_type')
)
SELECT u.code_list || ': ' || coalesce(u.code, '(blank)') AS record_ref, NULL AS point_id, NULL AS sample_month,
       o.code IS NULL AS failed,
       CASE WHEN o.code IS NULL THEN 'Used in the results but not in the official list' ELSE 'In the official list' END AS detail,
       NULL AS source_url
FROM used u LEFT JOIN official o ON o.code_list = u.code_list AND o.code = u.code;
-- @plant
UPDATE silver.results SET det_code = 'ZZ99' WHERE obs_id IN (SELECT obs_id FROM silver.results ORDER BY obs_id LIMIT 3);

-- @rule VAL-06
-- @check
SELECT obs_id AS record_ref, point_id, sample_month,
       coalesce(text_kind, '') = 'status' AS failed,
       'Result reads: ' || coalesce(raw_result, 'empty') AS detail,
       obs_id AS source_url
FROM silver.results;
-- @plant
UPDATE silver.results SET raw_result = 'Done', result_kind = 'text', text_kind = 'status', result_value = NULL WHERE obs_id IN (SELECT obs_id FROM silver.results WHERE result_kind = 'number' ORDER BY obs_id LIMIT 3);

-- @rule VAL-07
-- @check
SELECT obs_id AS record_ref, point_id, sample_month,
       result_kind <> 'number' AS failed,
       'Result reads: ' || coalesce(raw_result, 'empty') AS detail,
       obs_id AS source_url
FROM silver.results;
-- @plant
UPDATE silver.results SET raw_result = '<0.03', result_kind = 'below', limit_value = 0.03, result_value = NULL WHERE obs_id IN (SELECT obs_id FROM silver.results WHERE result_kind = 'number' ORDER BY obs_id LIMIT 3);
-- @impact
SELECT 'Average river ammonia with below-limit results dropped, against counted at half the limit' AS figure,
       avg(coalesce(result_value, limit_value / 2)) FILTER (WHERE result_kind IN ('number', 'below')) AS careful,
       avg(result_value) FILTER (WHERE result_kind = 'number') AS careless,
       'mg/l' AS unit
FROM silver.results WHERE det_code = '0111' AND is_river;

-- @rule CON-01
-- @check
SELECT det_code AS record_ref, NULL AS point_id, NULL AS sample_month,
       count(DISTINCT unit) > 1 AS failed,
       'Has ' || count(DISTINCT unit) || ' unit(s)' AS detail,
       NULL AS source_url
FROM silver.results GROUP BY det_code;
-- @plant
UPDATE silver.results SET unit = 'PLANTED UNIT' WHERE obs_id IN (SELECT obs_id FROM silver.results WHERE det_code = '0111' ORDER BY obs_id LIMIT 3);

-- @rule CON-02
-- @check
SELECT det_label AS record_ref, NULL AS point_id, NULL AS sample_month,
       count(DISTINCT unit) > 1 AS failed,
       CASE WHEN count(DISTINCT unit) > 1 THEN 'One name, ' || count(DISTINCT det_code) || ' codes and ' || count(DISTINCT unit) || ' units: ' || string_agg(DISTINCT unit, ' and ') ELSE 'One name, one unit' END AS detail,
       NULL AS source_url
FROM silver.results GROUP BY det_label;
-- @plant
UPDATE silver.results SET det_label = 'Ammoniacal Nitrogen as N', det_code = 'PL01', unit = 'PLANTED UNIT' WHERE obs_id IN (SELECT obs_id FROM silver.results WHERE det_code = '0118' ORDER BY obs_id LIMIT 3);
-- @impact
SELECT 'Average E. coli, keeping the two codes apart, against joining on the name alone' AS figure,
       avg(coalesce(result_value, limit_value)) FILTER (WHERE det_code = '2348') AS careful,
       avg(coalesce(result_value, limit_value)) AS careless,
       'per 100 ml' AS unit
FROM silver.results WHERE det_label = 'Escherichia coli : Confirmed : MF' AND result_kind IN ('number', 'below');

-- @rule CON-03
-- @check
WITH seen AS (
    SELECT point_id, any_value(point_status) AS status_in_results, any_value(label_raw) AS label_in_results, count(DISTINCT point_status) AS statuses, count(DISTINCT label_raw) AS labels
    FROM silver.results GROUP BY 1
)
SELECT s.point_id AS record_ref, s.point_id, NULL AS sample_month,
       p.point_id IS NULL OR s.statuses > 1 OR s.labels > 1 OR s.status_in_results <> p.point_status OR s.label_in_results <> p.label_raw OR p.point_status <> 'OPEN' AS failed,
       CASE WHEN p.point_id IS NULL THEN 'Has results but is not in the register'
            WHEN s.status_in_results <> p.point_status THEN 'The results and the register give different statuses'
            WHEN s.label_in_results <> p.label_raw THEN 'The results and the register give different labels'
            WHEN p.point_status <> 'OPEN' THEN 'Has results in the window, and the register now says it is closed. It may have closed since'
            ELSE 'Agrees with the register' END AS detail,
       '{wq_base}/sampling-point/' || s.point_id AS source_url
FROM seen s LEFT JOIN silver.points p ON p.point_id = s.point_id;
-- @plant
UPDATE silver.points SET point_status = 'CLOSED' WHERE point_id IN (SELECT DISTINCT point_id FROM silver.results ORDER BY point_id LIMIT 3);

-- @rule CON-04
-- @check
SELECT det_code || ' ' || any_value(det_label) AS record_ref, NULL AS point_id, NULL AS sample_month,
       max(limit_value) / nullif(min(limit_value), 0) > 100 AS failed,
       count(DISTINCT limit_value) || ' different limits, from ' || min(limit_value) || ' to ' || max(limit_value) AS detail,
       NULL AS source_url
FROM silver.results WHERE result_kind = 'below' AND limit_value > 0
GROUP BY det_code HAVING count(*) >= 500;
-- @plant
UPDATE silver.results SET limit_value = 1000000, raw_result = '<1000000' WHERE obs_id IN (SELECT obs_id FROM silver.results WHERE result_kind = 'below' AND det_code = (SELECT det_code FROM silver.results WHERE result_kind = 'below' AND limit_value > 0 GROUP BY 1 HAVING max(limit_value) / min(limit_value) <= 100 AND count(*) >= 500 ORDER BY count(*) DESC LIMIT 1) ORDER BY obs_id LIMIT 3);

-- @rule ACC-01
-- @check
SELECT obs_id AS record_ref, point_id, sample_month,
       result_value < 4 OR result_value > 11 AS failed,
       'pH of ' || raw_result || ': possible, but unusual enough to look at' AS detail,
       obs_id AS source_url
FROM silver.results WHERE det_code IN ('0061', '3169') AND result_kind = 'number';
-- @plant
UPDATE silver.results SET result_value = 12, raw_result = '12' WHERE obs_id IN (SELECT obs_id FROM silver.results WHERE det_code = '0061' AND result_kind = 'number' AND result_value BETWEEN 4 AND 11 ORDER BY obs_id LIMIT 3);

-- @rule ACC-02
-- @check
SELECT obs_id AS record_ref, point_id, sample_month,
       result_value < -2 OR result_value > 40 AS failed,
       'Water temperature of ' || raw_result || ' degrees' AS detail,
       obs_id AS source_url
FROM silver.results WHERE det_code = '0076' AND result_kind = 'number';
-- @plant
UPDATE silver.results SET result_value = 95, raw_result = '95' WHERE obs_id IN (SELECT obs_id FROM silver.results WHERE det_code = '0076' AND result_kind = 'number' AND result_value <= 40 ORDER BY obs_id LIMIT 3);

-- @rule ACC-03
-- @check
WITH usual AS (
    SELECT det_code, median(result_value) AS usual_level, count(*) AS measured
    FROM silver.results WHERE result_kind = 'number' AND result_value > 0 GROUP BY 1 HAVING count(*) >= 100
)
SELECT r.obs_id AS record_ref, r.point_id, r.sample_month,
       r.result_value > 1000 * u.usual_level AS failed,
       r.det_label || ' of ' || r.raw_result || ', against a usual level of ' || round(u.usual_level, 4) AS detail,
       r.obs_id AS source_url
FROM silver.results r JOIN usual u ON u.det_code = r.det_code
WHERE r.result_kind = 'number';
-- @plant
UPDATE silver.results SET result_value = 100000000, raw_result = '100000000' WHERE obs_id IN (SELECT obs_id FROM silver.results WHERE det_code = '0111' AND result_kind = 'number' AND result_value < 1 ORDER BY obs_id LIMIT 3);
-- @impact
WITH usual AS (
    SELECT det_code, median(result_value) AS usual_level FROM silver.results WHERE result_kind = 'number' AND result_value > 0 GROUP BY 1
)
SELECT 'Average river ammonia with results over 1,000 times the usual level left out, against kept in' AS figure,
       avg(coalesce(r.result_value, r.limit_value / 2)) FILTER (WHERE coalesce(r.result_value, 0) <= 1000 * u.usual_level) AS careful,
       avg(coalesce(r.result_value, r.limit_value / 2)) AS careless,
       'mg/l' AS unit
FROM silver.results r JOIN usual u ON u.det_code = r.det_code
WHERE r.det_code = '0111' AND r.is_river AND r.result_kind IN ('number', 'below');

-- @rule ACC-04
-- @check
SELECT obs_id AS record_ref, point_id, sample_month,
       result_kind = 'above' AS failed,
       'Result reads ' || raw_result || ': the real value is at least this, not exactly this' AS detail,
       obs_id AS source_url
FROM silver.results WHERE result_kind IN ('number', 'above');
-- @plant
UPDATE silver.results SET raw_result = '>' || raw_result, result_kind = 'above', limit_value = result_value, result_value = NULL WHERE obs_id IN (SELECT obs_id FROM silver.results WHERE result_kind = 'number' ORDER BY obs_id LIMIT 3);
-- @impact
SELECT 'Average E. coli with above-range ceilings left out, against the sign stripped and the ceiling counted as a measurement' AS figure,
       avg(result_value) FILTER (WHERE result_kind = 'number') AS careful,
       avg(stripped_value) FILTER (WHERE result_kind IN ('number', 'above')) AS careless,
       'per 100 ml' AS unit
FROM silver.results WHERE det_code = '2348';
