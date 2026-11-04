# Gives each sampling point a record quality score, from the same rule results as everything else.
# The score describes the point's records, never the water. It doesn't feed any verdict, and a must-pass check still can't be outvoted.

# The score's rules, weights and bands.
from engine import settings

# Every line of the point file, in order.
POINT_COLUMNS = ["point_id", "point_label", "display_name", "label_withheld", "point_group", "area_name", "point_status", "location_kind", "map_e", "map_n", "results", "samples", "newest_date", "score", "band", "band_order", "flags", "rules_flagged", "source_url", "pack_id"]
# Every line of the file saying which checks reached which point, and what they found.
CHECK_COLUMNS = ["point_id", "rule_id", "checked", "flagged", "counts_in_score"]
# Every line of the file the map draws from.
PACK_COLUMNS = ["pack_id", "point_group", "area_name", "band", "band_order", "located", "points_in_pack", "packed"]


# Make the empty table each rule's point counts go into, before any rule runs.
def start_counts(con):
    # One row per rule and point.
    con.execute("CREATE OR REPLACE TEMP TABLE point_rule_counts (rule_id VARCHAR, point_id VARCHAR, eligible BIGINT, failed BIGINT)")


# Keep the latest rule's counts for each point it names. Rules about a whole list name no point, so they add nothing.
def keep_counts(con, rule_id):
    # Only the rules a point can be scored or informed by are kept, which holds the table to what is used.
    if rule_id in settings.POINT_SCORE_RULES or rule_id in settings.POINT_INFO_RULES:
        # Count what was checked and what failed, point by point.
        con.execute("INSERT INTO point_rule_counts SELECT ?, CAST(point_id AS VARCHAR), count(*) FILTER (WHERE failed IS NOT NULL), count(*) FILTER (WHERE failed) FROM rule_rows WHERE point_id IS NOT NULL GROUP BY 2", [rule_id])


# Work out one point's score from its rule counts, so the sum can be tested without a database. Each count is (weight, eligible, failed).
def score_from(counts):
    # Each rule's pass share, multiplied by how much that rule counts.
    top = sum(weight * (1 - failed / eligible) for weight, eligible, failed in counts if eligible)
    # The total weight of the rules that reached this point.
    bottom = sum(weight for weight, eligible, _ in counts if eligible)
    # No rule reached it means there is no score, never a perfect one.
    return 100.0 * top / bottom if bottom else None


# Name the band for a point. Having no results is grey, because nobody knows yet.
def band_for(results, flags, score):
    # Nothing to check is never a pass.
    if not results:
        # The grey band.
        return settings.POINT_BANDS[3]
    # Nothing flagged.
    if not flags:
        # The green band.
        return settings.POINT_BANDS[0]
    # Flagged, but only lightly.
    if score >= settings.POINT_LOOK_CLOSER_BELOW:
        # The amber band.
        return settings.POINT_BANDS[1]
    # Flagged enough to be worth a person's time.
    return settings.POINT_BANDS[2]


# Round a flagged point's score down, so a point with a flag can never read as a perfect 100.
def shown_score(score, flags):
    # Keep one decimal place, always rounding down when something was flagged.
    return int(score * 10) / 10 if flags else 100.0


# Build the three files' rows from the rule counts and the published point list.
def build(con, rules):
    # How much each scored rule counts, from its severity in the register.
    weights = {r["id"]: settings.POINT_WEIGHTS[r["severity"]] for r in rules if r["id"] in settings.POINT_SCORE_RULES}
    # Each point's counts, gathered from the rule runs.
    by_point = {}
    # Every rule's count for every point.
    for rule_id, point_id, eligible, failed in con.execute("SELECT rule_id, point_id, eligible, failed FROM point_rule_counts").fetchall():
        # File it under the point.
        by_point.setdefault(point_id, []).append((rule_id, eligible, failed))
    # The rows of each file.
    points, check_rows = [], []
    # Open points, and any point with results, in a stable order. Closed points with no results raise no question, so they stay out.
    for row in con.execute("SELECT point_id, display_name, label_withheld, point_status, point_group, sub_area, location_kind, easting, northing, results_in_window, samples_in_window, newest_date FROM gold.points_public WHERE point_status = 'OPEN' OR results_in_window > 0 ORDER BY point_id").fetchall():
        # Name the columns.
        point_id, display_name, withheld, status, group, sub_area, kind, easting, northing, results, samples, newest = row
        # This point's rule counts.
        here = by_point.get(point_id, [])
        # Only rules in the score count towards it.
        scored = [(weights[r], e, f) for r, e, f in here if r in weights]
        # How many records the scored rules flagged. A record flagged by two rules counts twice, so these are called flags.
        flags = sum(f for r, e, f in here if r in weights)
        # A point with no results has no score.
        score = score_from(scored) if results else None
        # The score as shown.
        shown = shown_score(score, flags) if score is not None else None
        # The band.
        band = band_for(results, flags, shown)
        # A withheld label already contains the code, and any other name gets the code beside it, as some names are shared.
        label = display_name if withheld else f"{display_name} ({point_id})"
        # The point's row.
        points.append({
            "point_id": point_id, "point_label": label, "display_name": display_name, "label_withheld": withheld, "point_group": group,
            # The sub-area in title case, using the name list where a plain conversion would look wrong.
            "area_name": settings.POINT_AREA_NAMES.get(sub_area or "", (sub_area or "Unknown").title()),
            "point_status": status, "location_kind": kind,
            # The map's position in units of 100 metres, or blank for a point with no real location.
            "map_e": round(easting / 100) if easting is not None else None, "map_n": round(northing / 100) if northing is not None else None,
            "results": results, "samples": samples, "newest_date": newest, "score": shown, "band": band, "band_order": settings.POINT_BANDS.index(band) + 1,
            "flags": flags if results else 0, "rules_flagged": sum(1 for r, e, f in here if r in weights and f) if results else 0,
            # The publisher's own page for this point, so anyone can check it at source.
            "source_url": f"{settings.WQ_BASE}/sampling-point/{point_id}",
        })
        # Each check that reached this point, including the ones it passed, so its page can show the whole picture.
        for rule_id, eligible, failed in here:
            # A rule with nothing to check here isn't listed.
            if eligible:
                # One row, saying plainly whether it counted. Nothing counts at a point with no results, as it has no score.
                check_rows.append({"point_id": point_id, "rule_id": rule_id, "checked": eligible, "flagged": failed, "counts_in_score": bool(results) and rule_id in weights})
    # Hand back the points, the checks and the map's packed rows.
    return points, check_rows, pack_points(points)


# Pack the points into short text rows, because a chart's cost grows with rows, not marks. Each point records which row holds it.
def pack_points(points):
    # Points gathered by the three things the pickers can filter on, and by whether they can be drawn.
    groups = {}
    # Every point.
    for point in points:
        # File it under its group, area, band and whether it has a real location.
        groups.setdefault((point["point_group"], point["area_name"], point["band"], point["band_order"], point["map_e"] is not None), []).append(point)
    # The packed rows.
    packs = []
    # Each combination, in a stable order.
    for (group, area, band, order, located), members in sorted(groups.items()):
        # A flagged point gets a row of its own, so clicking it on the map finds exactly that point.
        size = 1 if band in settings.POINT_BANDS[1:3] else settings.POINT_PACK_SIZE
        # Split a large combination into rows of that size.
        for start in range(0, len(members), size):
            # This row's points.
            chunk = members[start:start + size]
            # This row's number.
            pack_id = len(packs) + 1
            # Each point remembers it.
            for point in chunk:
                # The link from a point to its row.
                point["pack_id"] = pack_id
            # Each point in the fixed order the chart reads: east, north, score, results, label. The separators are removed from labels first.
            packed = "|".join(f'{"" if p["map_e"] is None else p["map_e"]}~{"" if p["map_n"] is None else p["map_n"]}~{"" if p["score"] is None else p["score"]}~{p["results"]}~{p["point_label"].replace("|", " ").replace("~", " ")[:70]}' for p in chunk)
            # One row for the chart.
            packs.append({"pack_id": pack_id, "point_group": group, "area_name": area, "band": band, "band_order": order, "located": located, "points_in_pack": len(chunk), "packed": packed})
    # Hand them back.
    return packs
