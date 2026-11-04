# Saves a copy of the latest bathing water season into the repository, for nights when the live service can't be read.
# The bathing water service refuses requests from GitHub's servers (HTTP 403), though it answers a normal home connection.
# That refusal is respected: nothing here hides where a request comes from. This script is run by hand from a home PC,
# and rule SRC-06 says when the copy has gone stale. Season over: run it once. During a season: run it at least fortnightly.
# Usage: python -m engine.bathing_copy     (needs data/raw/points.jsonl.gz from an earlier run)

# Writes the copy.
import csv
# Opens packed files.
import gzip
# Reads each sampling point's record.
import json
# Finds the link code inside a label.
import re
# Handles a temporary folder for the download.
import tempfile
# Works out today's date.
from datetime import datetime, timezone
# Handles file paths.
from pathlib import Path
# The engine's fetch step and settings.
from engine import fetch, settings

# The columns of the copy.
COLUMNS = ["season_start", "season_end", "taken_on", "bathing_code", "sampled_at", "ecoli", "ecoli_qualifier"]


# Find the five-digit link codes inside the North West register's labels.
def linked_codes(points_file):
    # Codes so far.
    codes = set()
    # Open the packed file.
    with gzip.open(points_file, "rt", encoding="utf-8") as lines:
        # One sampling point per line.
        for line in lines:
            # The code sits in brackets at the end of the label.
            found = re.search(r"\((\d{5})\)\s*$", json.loads(line).get("prefLabel") or "")
            # Not every label has one.
            if found:
                # Keep it.
                codes.add(found.group(1))
    # Hand them back.
    return codes


# Download the season from the live service, and save the North West's samples in the repository.
def save_copy():
    # Today's date in UTC.
    today = datetime.now(timezone.utc).date()
    # The North West's link codes.
    codes = linked_codes(settings.RAW / "points.jsonl.gz")
    # A temporary folder, so the night's raw files aren't disturbed.
    with tempfile.TemporaryDirectory() as folder:
        # Read the live service only: falling back to the old copy here would copy it onto itself.
        record = fetch.fetch_bathing(Path(folder), today, allow_copy=False)[0]
        # Stop if the service couldn't be read, and leave the existing copy alone.
        if record["status"] != "ok":
            # Say why.
            raise SystemExit("The live service couldn't be read, so the copy is unchanged: " + record["error"])
        # Read what was downloaded.
        with gzip.open(Path(folder) / "bathing.jsonl.gz", "rt", encoding="utf-8") as lines:
            # Only samples at points the North West results can link to.
            rows = [row for row in map(json.loads, lines) if row["bathing_code"] in codes]
    # Write the copy, with the season and the date on every row.
    with open(settings.BATHING_COPY, "w", newline="", encoding="utf-8") as out:
        # A CSV writer with a fixed column order.
        writer = csv.DictWriter(out, fieldnames=COLUMNS)
        # The header line.
        writer.writeheader()
        # Every sample, oldest first, so the file only changes where the data does.
        for row in sorted(rows, key=lambda r: (r["sampled_at"], r["bathing_code"])):
            # Add the season and the date to the row.
            writer.writerow({"season_start": record["window_start"], "season_end": record["window_end"], "taken_on": today.isoformat(), **row})
    # Say what was saved.
    print(f"Saved {len(rows)} of {record['api_total']} samples, season from {record['window_start']}, to {settings.BATHING_COPY}")


# Run when started from the command line.
if __name__ == "__main__":
    # Do it.
    save_copy()
