# Builds a small, made-up, entirely clean set of source files, so tests can prove each rule stays quiet on good data and fires on bad.
# Nothing here comes from a real record. Sampling points, labels and values are invented.

# Writes CSV files.
import csv
# Packs files as they are written.
import gzip
# Writes JSON lines.
import json
# Works out dates.
from datetime import date, datetime, timedelta
# The engine's month windows and agreed columns.
from engine import fetch, layers

# The fixed date every test pretends is today.
AS_OF = date(2026, 11, 4)
# Five rivers, so there is plenty of history per point.
RIVERS = [f"NW-R{n}" for n in range(1, 6)]
# The measurements taken at every river visit: code, name, unit and a typical value.
DETERMINANDS = [("0111", "Ammoniacal Nitrogen as N", "MILLIGRAM PER LITRE", 0.2), ("0192", "Phosphate :- {TIP}", "MILLIGRAM PER LITRE", 0.1), ("0118", "Nitrite as N", "MILLIGRAM PER LITRE", 0.05), ("0135", "Solids, Suspended at 105 C", "MILLIGRAM PER LITRE", 8.0), ("0085", "BOD : 5 Day ATU", "MILLIGRAM PER LITRE", 2.0), ("0180", "Orthophosphate, reactive as P", "MILLIGRAM PER LITRE", 0.06), ("0116", "Nitrogen, Total Oxidised as N", "MILLIGRAM PER LITRE", 2.5), ("0061", "pH", "PH UNITS", 7.5), ("0076", "Temperature of Water", "CELSIUS", 12.0)]
# The monitoring purposes used, which must be in the reference list.
PURPOSES = ["ENVIRONMENTAL MONITORING STATUTORY (EU DIRECTIVES)", "MONITORING  (NATIONAL AGENCY POLICY)"]
# The river point type.
RIVER_TYPE = "FRESHWATER - RIVERS"
# The bathing beach point type.
BATHING_TYPE = "SALINE WATER - DESIGNATED BATHING BEACHES"
# The discharge point type.
DISCHARGE_TYPE = "SEWAGE DISCHARGES - FINAL/TREATED EFFLUENT - WATER COMPANY"


# One sampling point's record, as the service would send it.
def point_record(notation, label, point_type, easting=350000, northing=420000, status="OPEN"):
    # The nested shape the service uses.
    return {"notation": notation, "prefLabel": label, "samplingPointStatus": {"prefLabel": status}, "samplingPointType": {"prefLabel": point_type}, "area": {"prefLabel": "NORTH WEST - TEST"}, "subArea": {"prefLabel": "TEST AREA"}, "geometry": {"asWKT": f"POINT({easting} {northing}) <http://www.opengis.net/def/crs/EPSG/0/27700>"}}


# Every sampling point in the made-up register.
def all_points():
    # The rivers.
    points = [point_record(p, f"RIVER {i} AT TESTFORD", RIVER_TYPE, 350000 + i * 1000, 420000) for i, p in enumerate(RIVERS, start=1)]
    # Two bathing beaches, each with the five-digit link code in its label.
    points += [point_record("NW-B1", "TESTSANDS NORTH (41200)", BATHING_TYPE, 330000, 430000), point_record("NW-B2", "TESTSANDS SOUTH (41201)", BATHING_TYPE, 331000, 431000)]
    # One discharge, which always has its label withheld.
    points.append(point_record("NW-D1", "TESTFORD OUTFALL", DISCHARGE_TYPE, 352000, 421000))
    # Hand them back.
    return points


# One row of results, in the service's column order.
def result_row(obs_id, point, sampled_at, purpose, code, name, unit, result, point_type, label):
    # Build the row by column name.
    values = {"id": obs_id, "samplingPoint.notation": point, "samplingPoint.prefLabel": label, "samplingPoint.easting": "350000", "samplingPoint.northing": "420000", "samplingPoint.region": "NorthWest", "samplingPoint.area": "NORTH WEST - TEST", "samplingPoint.subArea": "TEST AREA", "samplingPoint.samplingPointStatus": "OPEN", "samplingPoint.samplingPointType": point_type, "phenomenonTime": sampled_at, "samplingPurpose": purpose, "sampleMaterialType": "RIVER / RUNNING SURFACE WATER", "determinand.notation": code, "determinand.prefLabel": name, "result": result, "unit": unit}
    # Return the values in the agreed order.
    return [values[column] for column in layers.RESULT_COLUMNS]


# Every result in the made-up data, by month.
def all_results():
    # Rows grouped by the month they belong to.
    by_month = {}
    # The first day of the window.
    start = date.fromisoformat(fetch.month_windows(AS_OF)[0][0])
    # A running sample number.
    sample_no = 1000
    # Every day of the window up to yesterday.
    for day_no in range((AS_OF - start).days):
        # This day's date.
        day = start + timedelta(days=day_no)
        # Each river is visited every day, at a time that sweeps the whole week. Hour cycles against weekday, and minutes vary, so no clock time dominates.
        for river_no, point in enumerate(RIVERS):
            # The next sample number.
            sample_no += 1
            # This visit's time.
            sampled_at = datetime(day.year, day.month, day.day, (day_no + river_no) % 24, (day_no * 7 + river_no * 11) % 60).isoformat()
            # Alternate the two monitoring streams between rivers.
            purpose = PURPOSES[river_no % 2]
            # Each measurement taken on this visit.
            for code_no, (code, name, unit, typical) in enumerate(DETERMINANDS):
                # One in seven ammonia readings is below the limit, which is under the AI readiness threshold.
                below = code == "0111" and sample_no % 7 == 0
                # The result text, with a small daily wobble.
                result = "<0.03" if below else str(round(typical * (1 + (sample_no % 10) / 50), 4))
                # The record's own address.
                obs_id = f"https://environment.data.gov.uk/water-quality/sampling-point/{point}/sample/{sample_no}/observation/{code_no:04d}"
                # Add the row to its month.
                by_month.setdefault(day.strftime("%Y-%m"), []).append(result_row(obs_id, point, sampled_at, purpose, code, name, unit, result, RIVER_TYPE, f"RIVER {river_no + 1} AT TESTFORD"))
        # The discharge is sampled on the first of each month, so the register's every open point has a result.
        if day.day == 1:
            # The next sample number.
            sample_no += 1
            # Add it to its month.
            by_month.setdefault(day.strftime("%Y-%m"), []).append(result_row(f"https://environment.data.gov.uk/water-quality/sampling-point/NW-D1/sample/{sample_no}/observation/0000", "NW-D1", datetime(day.year, day.month, 1, day.month, day.day * 3).isoformat(), PURPOSES[1], "0085", "BOD : 5 Day ATU", "MILLIGRAM PER LITRE", "3.1", DISCHARGE_TYPE, "TESTFORD OUTFALL"))
    # Hand them back.
    return by_month


# Every bathing water sample and the matching results, in the bathing season.
def bathing_rows():
    # Rows from the second service.
    service = []
    # Matching rows in the results service, by month.
    matching = {}
    # A running sample number.
    sample_no = 900000
    # Weekly through the 2026 season.
    for week in range(18):
        # This week's day.
        day = date(2026, 5, 20) + timedelta(days=week * 7)
        # Each beach and its link code.
        for point, link in [("NW-B1", "41200"), ("NW-B2", "41201")]:
            # The next sample number.
            sample_no += 1
            # The same minute in both services.
            sampled_at = f"{day.isoformat()}T{10 + week % 5:02d}:{week * 3:02d}:00"
            # The same count in both services.
            count = 10 + week
            # The bathing service's row.
            service.append({"bathing_code": link, "sampled_at": sampled_at, "ecoli": str(count), "ecoli_qualifier": "actual"})
            # The results service's row.
            label = "TESTSANDS NORTH (41200)" if point == "NW-B1" else "TESTSANDS SOUTH (41201)"
            # Add it to its month.
            matching.setdefault(day.strftime("%Y-%m"), []).append(result_row(f"https://environment.data.gov.uk/water-quality/sampling-point/{point}/sample/{sample_no}/observation/0000", point, sampled_at, PURPOSES[0], "2348", "Escherichia coli : Confirmed : MF", "NUMBER PER HUNDRED MILLILITRES", str(count), BATHING_TYPE, label))
    # Hand both back.
    return service, matching


# Write the whole clean set of raw files, and return the fetch step's record of them.
def write_clean_raw(raw_dir):
    # Make the folder.
    raw_dir.mkdir(parents=True, exist_ok=True)
    # The register.
    points = all_points()
    # Write it.
    with gzip.open(raw_dir / "points.jsonl.gz", "wt", encoding="utf-8") as out:
        # One point per line.
        out.writelines(json.dumps(point) + "\n" for point in points)
    # The results.
    by_month = all_results()
    # The second service, and its matching results.
    bathing, matching = bathing_rows()
    # Merge the matching results into their months.
    for month, rows in matching.items():
        # Add them.
        by_month[month] = by_month.get(month, []) + rows
    # The record of what was fetched.
    manifest = [{"source": "points", "window_start": "", "window_end": "", "api_total": len(points), "calls": 1, "seconds": 0, "status": "ok", "error": ""}]
    # Each monthly window.
    for start, end in fetch.month_windows(AS_OF):
        # This month's rows.
        rows = by_month.get(start[:7], [])
        # Write its file, with its header.
        with gzip.open(raw_dir / f"results_{start[:7]}.csv.gz", "wt", encoding="utf-8", newline="") as out:
            # A CSV writer.
            writer = csv.writer(out)
            # The header line.
            writer.writerow(layers.RESULT_COLUMNS)
            # Every row.
            writer.writerows(rows)
        # Record it.
        manifest.append({"source": "results", "window_start": start, "window_end": end, "api_total": len(rows), "calls": 1, "seconds": 0, "status": "ok", "error": ""})
    # Write the second service's samples.
    with gzip.open(raw_dir / "bathing.jsonl.gz", "wt", encoding="utf-8") as out:
        # One sample per line.
        out.writelines(json.dumps(row) + "\n" for row in bathing)
    # Record them.
    manifest.append({"source": "bathing", "window_start": "2026-05-01", "window_end": "2026-10-01", "api_total": len(bathing), "calls": 1, "seconds": 0, "status": "ok", "error": ""})
    # Every code the made-up results use, as the official lists would hold them.
    codes = [{"code_list": "determinand", "code": c, "label": n} for c, n, _, _ in DETERMINANDS] + [{"code_list": "determinand", "code": "2348", "label": "Escherichia coli : Confirmed : MF"}]
    # The purposes.
    codes += [{"code_list": "purpose", "code": str(i), "label": p} for i, p in enumerate(PURPOSES)]
    # The point types.
    codes += [{"code_list": "point_type", "code": str(i), "label": t} for i, t in enumerate([RIVER_TYPE, BATHING_TYPE, DISCHARGE_TYPE])]
    # Write them.
    with gzip.open(raw_dir / "codes.jsonl.gz", "wt", encoding="utf-8") as out:
        # One code per line.
        out.writelines(json.dumps(code) + "\n" for code in codes)
    # Record them.
    manifest.append({"source": "codes", "window_start": "", "window_end": "", "api_total": len(codes), "calls": 1, "seconds": 0, "status": "ok", "error": ""})
    # Hand back the record.
    return manifest


# The publisher's statements on a good night: unchanged, and with every licence statement agreeing.
def clean_watch():
    # The four things watched.
    return [{"item": "API specification", "kind": "spec", "value": "version 1.0", "fingerprint": "aaaa", "status": "ok", "checked_on": AS_OF.isoformat()}, {"item": "Licence: water quality service", "kind": "licence", "value": "Open Government Licence", "fingerprint": "bbbb", "status": "ok", "checked_on": AS_OF.isoformat()}, {"item": "Licence: catalogue record", "kind": "licence", "value": "Open Government Licence", "fingerprint": "bbbb", "status": "ok", "checked_on": AS_OF.isoformat()}, {"item": "Licence: bathing water service", "kind": "licence", "value": "Open Government Licence", "fingerprint": "bbbb", "status": "ok", "checked_on": AS_OF.isoformat()}]


# Write the history of a long-running engine: a run every day for 40 days, and last night's statements.
def write_mature_history(pub_dir, source_rows):
    # Where history lives.
    history = pub_dir / "history"
    # Make the folder.
    history.mkdir(parents=True, exist_ok=True)
    # A run log with one row per day, and only the columns the engine reads back.
    with open(history / "run_log.csv", "w", newline="", encoding="utf-8") as out:
        # A CSV writer.
        writer = csv.writer(out)
        # The header line.
        writer.writerow(["run_id", "as_of", "source_rows"])
        # One row per day, oldest first.
        for back in range(40, 0, -1):
            # This day's date.
            day = AS_OF - timedelta(days=back)
            # The row.
            writer.writerow([f"{day.isoformat()}T03:00Z", day.isoformat(), source_rows])
    # Last night's reading of the publisher's statements, identical to tonight's.
    with open(history / "source_watch.csv", "w", newline="", encoding="utf-8") as out:
        # A CSV writer.
        writer = csv.writer(out)
        # The header line.
        writer.writerow(["run_id", "item", "kind", "value", "fingerprint", "previous_fingerprint", "changed", "status", "checked_on"])
        # Each statement.
        for watch in clean_watch():
            # Its row.
            writer.writerow(["last", watch["item"], watch["kind"], watch["value"], watch["fingerprint"], "", False, "ok", "2026-11-03"])
