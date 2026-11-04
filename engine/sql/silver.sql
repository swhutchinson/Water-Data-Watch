-- SILVER LAYER: typed and parsed copies of what the sources served.
-- Nothing is corrected here. Each record keeps its raw value, and any interpretation sits beside it in its own column.

-- A broad grouping of sampling point types. It keeps pages at region and water-body level, and it says nothing about who runs a site.
CREATE OR REPLACE MACRO silver.point_group(point_type) AS CASE
    WHEN point_type = 'FRESHWATER - RIVERS' THEN 'Rivers'
    WHEN point_type IN ('FRESHWATER - BATHING WATER', 'SALINE WATER - DESIGNATED BATHING BEACHES') THEN 'Bathing waters'
    WHEN point_type LIKE 'FRESHWATER%' THEN 'Lakes and other fresh waters'
    WHEN point_type LIKE 'SALINE%' THEN 'Coast and estuaries'
    WHEN point_type LIKE 'GROUNDWATER%' THEN 'Groundwater'
    WHEN point_type IS NULL OR point_type LIKE 'UNSPECIFIED%' THEN 'Unspecified'
    ELSE 'Discharges and sites'
END;

-- RESULTS: one row per result, as served, with its text parsed into a kind, a value and a limit.
CREATE OR REPLACE TABLE silver.results AS
WITH typed AS (
    SELECT
        -- The record's own web address, which is also its unique key and a working link to the source.
        id AS obs_id,
        -- The sampling point's code.
        "samplingPoint.notation" AS point_id,
        -- The label as served. It is used only to compare the two sources and is never published.
        "samplingPoint.prefLabel" AS label_raw,
        -- The point's status as this record states it.
        "samplingPoint.samplingPointStatus" AS point_status,
        -- The point's type as this record states it.
        "samplingPoint.samplingPointType" AS point_type,
        -- The area and sub-area names.
        "samplingPoint.area" AS area,
        "samplingPoint.subArea" AS sub_area,
        -- The sample number, which the service only gives inside the record's address.
        regexp_extract(id, '/sample/([0-9]+)/', 1) AS sample_id,
        -- The time exactly as served. It carries no time zone marker, so it is never converted.
        phenomenonTime AS raw_time,
        -- The same time as a real date-time, empty when it can't be read.
        TRY_CAST(phenomenonTime AS TIMESTAMP) AS sampled_at,
        -- The purpose with repeated spaces closed up, so it matches the reference list.
        regexp_replace(samplingPurpose, '\s+', ' ', 'g') AS purpose,
        -- The kind of material sampled.
        sampleMaterialType AS material,
        -- What was measured: its code and its name.
        "determinand.notation" AS det_code,
        "determinand.prefLabel" AS det_label,
        -- The result as text, exactly as served.
        result AS raw_result,
        -- The unit as served.
        unit,
        -- The monthly window this record arrived in.
        fetch_window
    FROM bronze.results
), parsed AS (
    SELECT
        *,
        -- The result with any < or > sign removed, tried as a number.
        TRY_CAST(regexp_replace(trim(raw_result), '^[<>]\s*', '') AS DOUBLE) AS number_part,
        -- True when the text starts with a below-limit sign.
        regexp_matches(trim(coalesce(raw_result, '')), '^<') AS has_below_sign,
        -- True when the text starts with an above-range sign.
        regexp_matches(trim(coalesce(raw_result, '')), '^>') AS has_above_sign
    FROM typed
)
SELECT
    p.obs_id, p.point_id, p.label_raw, p.point_status, p.point_type,
    -- The broad grouping of the point type.
    silver.point_group(p.point_type) AS point_group,
    p.point_type = 'FRESHWATER - RIVERS' AS is_river,
    p.area, p.sub_area, p.sample_id, p.raw_time, p.sampled_at,
    -- The date, month, hour and weekday, for grouping. These read the clock time as served.
    CAST(p.sampled_at AS DATE) AS sample_date,
    strftime(p.sampled_at, '%Y-%m') AS sample_month,
    hour(p.sampled_at) AS hour_of_day,
    isodow(p.sampled_at) AS weekday_no,
    p.purpose,
    -- The governed name of the stream this purpose belongs to. An unlisted purpose says so.
    coalesce(m.stream, 'Not yet mapped') AS stream,
    coalesce(m.purpose_group, 'Not yet mapped') AS purpose_group,
    coalesce(m.is_seasonal, 0) = 1 AS is_seasonal,
    -- "Routine" leaves out samples taken because of a pollution incident or an investigation. That is a choice about the question, and it is stated on the page.
    coalesce(m.purpose_group, 'Routine') = 'Routine' AS is_routine,
    p.material, p.det_code, p.det_label, p.raw_result, p.unit, p.fetch_window,
    -- What kind of result this is. Only a number can go straight into a sum.
    CASE
        WHEN p.raw_result IS NULL OR trim(p.raw_result) = '' THEN 'empty'
        WHEN p.has_below_sign AND p.number_part IS NOT NULL THEN 'below'
        WHEN p.has_above_sign AND p.number_part IS NOT NULL THEN 'above'
        WHEN p.number_part IS NOT NULL AND NOT p.has_below_sign AND NOT p.has_above_sign THEN 'number'
        ELSE 'text'
    END AS result_kind,
    -- The measured value. It stays empty for anything that is only a limit or a word.
    CASE WHEN NOT p.has_below_sign AND NOT p.has_above_sign THEN p.number_part END AS result_value,
    -- The limit named by a below-limit or above-range result.
    CASE WHEN p.has_below_sign OR p.has_above_sign THEN p.number_part END AS limit_value,
    -- What a careless conversion would produce: the sign stripped and the number kept as though measured.
    p.number_part AS stripped_value,
    -- Whether a word result describes the water or only says something happened at the lab.
    t.text_kind
FROM parsed p
LEFT JOIN read_csv('{reference}/purpose_map.csv', header = true, all_varchar = false) m ON p.purpose = m.purpose
LEFT JOIN read_csv('{reference}/listed_text.csv', header = true, all_varchar = true) t ON trim(p.raw_result) = t.text_value;

-- POINTS: one row per sampling point in the register, with what can safely be shown worked out from its label.
CREATE OR REPLACE TABLE silver.points AS
WITH typed AS (
    SELECT
        notation AS point_id,
        coalesce(prefLabel, '') AS label_raw,
        status AS point_status,
        point_type,
        area,
        sub_area,
        -- Eastings and northings on the national grid, read out of the location text.
        TRY_CAST(regexp_extract(wkt, 'POINT\(([0-9.]+) ', 1) AS DOUBLE) AS easting,
        TRY_CAST(regexp_extract(wkt, 'POINT\([0-9.]+ ([0-9.]+)\)', 1) AS DOUBLE) AS northing
    FROM bronze.points
), flagged AS (
    SELECT
        *,
        upper(label_raw) AS u,
        -- A full postcode, which is often a business address but can be a home.
        regexp_matches(upper(label_raw), '\b[A-Z]{1,2}[0-9][0-9A-Z]? ?[0-9][A-Z]{2}\b') AS has_postcode,
        -- A number followed by a road name, which may be a house address.
        regexp_matches(upper(label_raw), '\b[0-9]{1,3}[A-Z]? [A-Z]+ (ROAD|RD|STREET|ST|LANE|AVENUE|AVE|DRIVE|CLOSE|WAY|CRESCENT|GROVE|PLACE|TERRACE|GARDENS|COURT)\b') AS has_house_number,
        -- A title followed by a word, which may name a person.
        regexp_matches(upper(label_raw), '\b(MR|MRS|MS|MISS|DR)\.? [A-Z]') AS has_person_title,
        -- A word suggesting a home.
        regexp_matches(upper(label_raw), '(DOMESTIC|DWELLING|PRIVATE HOUSE|BUNGALOW|COTTAGE|SEPTIC|FARMHOUSE|RESIDENCE)') AS has_domestic_word,
        -- A business name inside the label. Reports here stay at region level and never name a business.
        regexp_matches(upper(label_raw), '\b(PLC|LTD|LIMITED|LLP|UTILITIES|& SONS)\b') AS has_business_word
    FROM typed
)
SELECT
    point_id, label_raw, point_status, point_type,
    silver.point_group(point_type) AS point_group,
    area, sub_area, easting, northing,
    -- Where the coordinates point: a real place, a known stand-in, or somewhere outside the region.
    CASE
        WHEN easting IS NULL OR northing IS NULL THEN 'No location'
        WHEN (easting = 500000 AND northing = 4) OR (easting = 199999 AND northing = 599999) THEN 'Stand-in location'
        WHEN easting < 290000 OR easting > 410000 OR northing < 340000 OR northing > 600000 THEN 'Outside the North West'
        ELSE 'Inside the North West'
    END AS location_kind,
    has_postcode, has_house_number, has_person_title, has_domestic_word, has_business_word,
    -- The five-digit code that is the only link to the bathing water service, when the label holds one.
    nullif(regexp_extract(label_raw, '\(([0-9]{5})\)\s*$', 1), '') AS bathing_code,
    -- The label as published. Natural waters keep their name; anything flagged, and every discharge, site or borehole, shows no label at all.
    CASE
        WHEN silver.point_group(point_type) IN ('Rivers', 'Bathing waters', 'Lakes and other fresh waters', 'Coast and estuaries')
         AND NOT (has_postcode OR has_house_number OR has_person_title OR has_domestic_word OR has_business_word)
        THEN label_raw
    END AS label_public
FROM flagged;

-- BATHING: one row per sample from the second, independent service.
CREATE OR REPLACE TABLE silver.bathing AS
SELECT
    bathing_code,
    sampled_at AS raw_time,
    -- The minute of the sample, which is how the two services can be matched.
    substr(sampled_at, 1, 16) AS sample_minute,
    TRY_CAST(ecoli AS DOUBLE) AS ecoli,
    ecoli_qualifier
FROM bronze.bathing;

-- MONTHS: how many samples each month has, against the same month a year earlier. A view, so a planted defect flows through.
-- It runs from a calendar, so a month with no samples at all still gets a row and can't quietly vanish.
CREATE OR REPLACE VIEW silver.months AS
WITH calendar AS (
    SELECT strftime(m, '%Y-%m') AS sample_month
    FROM (SELECT unnest(generate_series(date_trunc('month', min(sample_date)), date_trunc('month', (SELECT as_of FROM silver.run_info)), INTERVAL 1 MONTH)) AS m FROM silver.results)
), counts AS (
    SELECT sample_month, count(DISTINCT sample_id) AS samples FROM silver.results WHERE sample_month IS NOT NULL GROUP BY 1
)
SELECT
    c.sample_month,
    coalesce(n.samples, 0) AS samples,
    prior.samples AS samples_year_before,
    -- The calendar month the run falls in is always incomplete.
    c.sample_month = strftime((SELECT as_of FROM silver.run_info), '%Y-%m') AS is_current_month,
    -- A recent month is part-complete while it has under 70% of the same month's samples a year earlier.
    (prior.samples IS NOT NULL AND coalesce(n.samples, 0) < 0.7 * prior.samples)
      OR c.sample_month = strftime((SELECT as_of FROM silver.run_info), '%Y-%m') AS is_part_complete
FROM calendar c
LEFT JOIN counts n ON n.sample_month = c.sample_month
LEFT JOIN counts prior ON prior.sample_month = strftime(CAST(c.sample_month || '-01' AS DATE) - INTERVAL 1 YEAR, '%Y-%m');
