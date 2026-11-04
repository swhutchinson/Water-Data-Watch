# An independent check of the report's headline numbers.
# It downloads the results straight from the Environment Agency's service and recomputes each number in plain Python.
# It uses none of the engine's code or SQL. Only the reference list of sampling purposes is shared, because it's an input.
# The numbers it compares against come from the report's own model, exported to tools/spot_check_dax.json through the
# Power BI modeling MCP. Run it soon after a nightly run, because the source can gain rows between the two.
# Usage: python tools/spot_check.py <empty download folder>     (exit code 0 when every check agrees)

# Reads the source's CSV pages and the reference list.
import csv
# Reads and writes packed files, so a second run needn't download again.
import gzip
# Splits the CSV text served by the service into lines.
import io
# Reads the model's numbers and the source's total.
import json
# Finds the sample number inside a record's address.
import re
# Handles exit codes and the folder argument.
import sys
# Pauses between attempts.
import time
# Makes the web requests.
import urllib.request
# Works out the months in the window and today's month.
from datetime import date, datetime, timezone
# Handles file paths.
from pathlib import Path

# The service's address.
BASE = "https://environment.data.gov.uk/water-quality"
# A plain name for the requests, saying what this is.
USER_AGENT = "water-data-watch-spot-check/1.0 (independent public data quality project)"
# The region covered.
REGION = "NW"
# Rows in each page.
PAGE = 2500
# How many whole months back the window starts.
MONTHS_BACK = 24
# Ammonia's code in the source's list of measurements.
AMMONIA = "0111"
# The point type treated as a river.
RIVER = "FRESHWATER - RIVERS"
# How far an average may differ from the model's and still count as agreeing.
TOLERANCE = 0.0005
# This project's root folder.
ROOT = Path(__file__).resolve().parent.parent


# Ask the service for one address, trying again if it fails.
def fetch(url, accept):
    # Up to four attempts.
    for attempt in range(4):
        # A failure leads to another attempt.
        try:
            # The service wants a POST for this data, with an empty body.
            request = urllib.request.Request(url, data=b"", method="POST", headers={"Accept": accept, "User-Agent": USER_AGENT})
            # Make the request.
            with urllib.request.urlopen(request, timeout=180) as reply:
                # Hand back the text.
                return reply.read().decode("utf-8")
        # Any web failure.
        except OSError:
            # The last attempt gives up.
            if attempt == 3:
                # Let the error show.
                raise
            # Wait a little longer each time.
            time.sleep(5 * (attempt + 1))


# List the first day of each month from MONTHS_BACK ago up to next month.
def month_starts(today):
    # Count months from year zero, so they're easy to add to.
    first = today.year * 12 + today.month - 1 - MONTHS_BACK
    # One start for every month in the window, plus the one that closes the last window.
    return [date(n // 12, n % 12 + 1, 1) for n in range(first, today.year * 12 + today.month + 1)]


# Download one month of results to a packed file, and return the source's stated total for it.
def download_month(folder, start, end):
    # The month's file.
    path = folder / f"{start:%Y-%m}.csv.gz"
    # The address parameters for this month.
    query = f"region={REGION}&dateFrom={start}&dateTo={end}"
    # The source's own count, read in the only reply format that states one.
    total = json.loads(fetch(f"{BASE}/data/observation?{query}&limit=1", "application/ld+json"))["totalItems"]
    # A complete earlier download needs no second fetch.
    if path.exists():
        # Hand back the count.
        return total, path
    # Open the file for writing.
    with gzip.open(path, "wt", encoding="utf-8", newline="") as out:
        # Start at the first row.
        skip = 0
        # Carry on until a short page arrives.
        while True:
            # One page.
            lines = fetch(f"{BASE}/data/observation?{query}&limit={PAGE}&skip={skip}", "text/csv").splitlines(keepends=True)
            # Keep the header from the first page only.
            out.writelines(lines if skip == 0 else lines[1:])
            # A short page means the month has ended.
            if len(lines) - 1 < PAGE:
                # Stop paging.
                break
            # Move on a page.
            skip += PAGE
    # Hand back the count and the file.
    return total, path


# Read the result column as a kind and a number, in this script's own words.
def read_result(text):
    # Remove surrounding spaces.
    text = (text or "").strip()
    # Nothing there.
    if not text:
        # An empty result.
        return "empty", None
    # A below-limit or above-range sign, if there is one.
    sign = text[0] if text[0] in "<>" else ""
    # Try the rest as a number.
    try:
        # The number after any sign.
        number = float(text[len(sign):].strip())
    # It isn't a number.
    except ValueError:
        # A word result.
        return "text", None
    # Name the kind from the sign.
    return {"<": "below", ">": "above", "": "number"}[sign], number


# The plain average of a list, or nothing for an empty one.
def average(values):
    # Sum over count, guarding against an empty list.
    return sum(values) / len(values) if values else None


# The whole check.
def main():
    # The download folder is passed in, so scripts stay out of it.
    folder = Path(sys.argv[1])
    # Make it if needed.
    folder.mkdir(parents=True, exist_ok=True)
    # Today's date, in UTC like the nightly run.
    today = datetime.now(timezone.utc).date()
    # Read the numbers exported from the report's model.
    model = json.loads((ROOT / "tools" / "spot_check_dax.json").read_text(encoding="utf-8"))
    # Purposes that are not routine, read from the reference list.
    with open(ROOT / "rules" / "reference" / "purpose_map.csv", newline="", encoding="utf-8") as handle:
        # Every listed purpose whose group isn't Routine.
        not_routine = {row["purpose"] for row in csv.DictReader(handle) if row["purpose_group"] != "Routine"}
    # The months in the window.
    starts = month_starts(today)
    # Totals stated by the source.
    stated = 0
    # Rows seen in the downloads.
    rows_seen = 0
    # Every record's address, to test that each appears only once.
    addresses = set()
    # Rows of each kind.
    kinds = {"below": 0, "above": 0, "text": 0, "number": 0, "empty": 0}
    # Distinct samples by month.
    samples = {}
    # River ammonia rows, kept for the two calculations.
    ammonia = []
    # One month at a time.
    for start, end in zip(starts, starts[1:]):
        # Download it.
        total, path = download_month(folder, start, end)
        # Add up the source's own count.
        stated += total
        # Read the month back.
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            # Row by row.
            for row in csv.DictReader(handle):
                # Count the row.
                rows_seen += 1
                # Remember its address.
                addresses.add(row["id"])
                # What kind of result it is.
                kind, number = read_result(row["result"])
                # Count the kind.
                kinds[kind] += 1
                # The month as served.
                month = row["phenomenonTime"][:7]
                # The sample number inside the address.
                found = re.search(r"/sample/([0-9]+)/", row["id"])
                # Count each sample once per month.
                samples.setdefault(month, set()).add(found.group(1) if found else row["id"])
                # Keep river ammonia that has a number or a limit.
                if row["determinand.notation"] == AMMONIA and row["samplingPoint.samplingPointType"] == RIVER and kind in ("number", "below"):
                    # The purpose with repeated spaces closed up.
                    purpose = " ".join((row["samplingPurpose"] or "").split())
                    # What the calculations need.
                    ammonia.append((row["samplingPoint.subArea"], kind, number, purpose not in not_routine, month))
    # Months still filling in: the current month, or under 70% of the same month's samples a year earlier.
    def part_complete(month):
        # The same month a year earlier.
        earlier = f"{int(month[:4]) - 1}{month[4:]}"
        # The test.
        return month == f"{today:%Y-%m}" or (earlier in samples and len(samples.get(month, ())) < 0.7 * len(samples[earlier]))
    # The quick way: drop below-limit results, keep every sample and month, take the average.
    quick_rows = [(area, number) for area, kind, number, routine, month in ammonia if kind == "number"]
    # The stated way: half the limit, routine samples only, complete months only, take the average.
    stated_rows = [(area, number if kind == "number" else number / 2) for area, kind, number, routine, month in ammonia if routine and not part_complete(month)]

    # Each sub-area's average, for the ones the report ranks.
    def by_area(pairs):
        # Values by sub-area.
        groups = {}
        # One pair at a time.
        for area, value in pairs:
            # Add it to its group.
            groups.setdefault(area, []).append(value)
        # Only the sub-areas the report ranks.
        return {area: average(values) for area, values in groups.items() if area in model["ranked_areas"]}

    # The two sets of sub-area averages.
    quick_areas, stated_areas = by_area(quick_rows), by_area(stated_rows)
    # Every check: its name, this script's number, the report's number.
    checks = [
        ("Rows the source says it holds", stated, model["source_rows"]),
        ("Rows downloaded", rows_seen, model["checked_rows"]),
        ("Each record appears once", len(addresses), model["checked_rows"]),
        ("Below-limit results", kinds["below"], model["below"]),
        ("Above-range results", kinds["above"], model["above"]),
        ("Word results", kinds["text"], model["text"]),
        ("Results that can't go straight into a sum (rule VAL-07)", kinds["below"] + kinds["above"] + kinds["text"], model["val07_failed"]),
        ("River ammonia, North West, the quick way", average([v for _, v in quick_rows]), model["quick_figure"]),
        ("River ammonia, North West, the stated way", average([v for _, v in stated_rows]), model["stated_figure"]),
        ("Highest sub-area, the quick way", max(quick_areas, key=quick_areas.get).title(), model["quick_top"]),
        ("Highest sub-area, the stated way", max(stated_areas, key=stated_areas.get).title(), model["stated_top"]),
    ]
    # Count disagreements.
    failures = 0
    # One check at a time.
    for name, mine, theirs in checks:
        # Averages get a small tolerance, and everything else must match exactly.
        agrees = abs(mine - theirs) <= TOLERANCE if isinstance(mine, float) else mine == theirs
        # Count it if not.
        failures += 0 if agrees else 1
        # Report it.
        print(f"{'agrees  ' if agrees else 'DIFFERS '} {name}: recomputed {mine}, report says {theirs}")
    # The closing line.
    print(f"{len(checks) - failures} of {len(checks)} checks agree.")
    # Exit with a failure code if any differed.
    sys.exit(1 if failures else 0)


# Run when started from the command line.
if __name__ == "__main__":
    # Do it.
    main()
