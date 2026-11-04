# The bronze step: copy each public source exactly as served, and write down what was asked for and what came back.
# A source that can't be reached never stops the run. It is recorded as failed, so its rules show "Not checked" rather than a pass.

# Packs files as they are written.
import gzip
# Fingerprints the publisher's specification and pages.
import hashlib
# Reads the replies.
import json
# Finds the licence wording on a web page.
import re
# Waits between attempts, and times each download.
import time
# Makes the web requests.
import urllib.error
# Makes the web requests.
import urllib.request
# Works out dates for the monthly windows.
from datetime import date, datetime, timezone
# Reads the shared settings.
from engine import settings


# Raised when a source still fails after every retry.
class SourceDown(Exception):
    # No extra behaviour is needed beyond the name and message.
    pass


# Fetch one address, retrying politely, and return the reply as text.
def get_text(url, accept, method="GET", attempts=4):
    # The last error seen, reported if every attempt fails.
    last_error = None
    # Try up to the allowed number of times.
    for attempt in range(attempts):
        # Network and server errors are caught below.
        try:
            # Build the request. POST here sends no body, which is what the results route expects.
            request = urllib.request.Request(url, method=method, headers={"Accept": accept, "User-Agent": settings.USER_AGENT})
            # Send it and wait up to three minutes.
            with urllib.request.urlopen(request, timeout=180) as reply:
                # Decode and hand back the text.
                return reply.read().decode("utf-8")
        # Anything that went wrong with the web request.
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            # Remember it.
            last_error = error
            # Wait a little longer after each failure, but not after the last one.
            if attempt < attempts - 1:
                # Five, ten, then fifteen seconds.
                time.sleep(5 * (attempt + 1))
    # Every attempt failed, so say which address and why.
    raise SourceDown(f"{url} failed after {attempts} attempts: {last_error}")


# List the monthly windows to read: each runs from the first of a month up to the first of the next.
def month_windows(today, months=settings.WINDOW_MONTHS):
    # Windows found so far.
    windows = []
    # Count the months as a single number, which makes stepping back simple.
    current = today.year * 12 + today.month - 1
    # Walk from the oldest month to the current one.
    for number in range(current - months + 1, current + 1):
        # This month's first day.
        start = date(number // 12, number % 12 + 1, 1)
        # Next month's first day. The service's end date excludes the day it names, so this covers the whole month with no overlap.
        end = date((number + 1) // 12, (number + 1) % 12 + 1, 1)
        # Keep the pair.
        windows.append((start.isoformat(), end.isoformat()))
    # Oldest first.
    return windows


# Download one month of results into its own packed file, and return that month's manifest row.
def fetch_month(raw_dir, start, end, base):
    # The address parameters for this month.
    query = f"region={settings.REGION}&dateFrom={start}&dateTo={end}"
    # The clock for this window.
    began = time.time()
    # Ask the service how many rows it holds, in the one reply format that states a total.
    total = json.loads(get_text(f"{base}/data/observation?{query}&limit=1", "application/ld+json", "POST"))["totalItems"]
    # One call so far.
    calls = 1
    # The file for this month, named after the month.
    path = raw_dir / f"results_{start[:7]}.csv.gz"
    # Open it for writing.
    with gzip.open(path, "wt", encoding="utf-8", newline="") as out:
        # Start at the first row.
        skip = 0
        # Remember whether the header line has been written.
        wrote_header = False
        # Carry on until a short page arrives.
        while True:
            # One page of CSV.
            body = get_text(f"{base}/data/observation?{query}&limit={settings.PAGE_ROWS}&skip={skip}", "text/csv", "POST")
            # Count the call.
            calls += 1
            # Split into lines, keeping line endings exactly as served.
            lines = body.splitlines(keepends=True)
            # Nothing but a header means this month has ended.
            if len(lines) <= 1:
                # Keep the header of an empty month, so its columns can still be checked.
                if not wrote_header and lines:
                    # Write it.
                    out.write(lines[0])
                # Finished this month.
                break
            # Write the header only once.
            out.writelines(lines if not wrote_header else lines[1:])
            # The header is now written.
            wrote_header = True
            # A short page is the last one.
            if len(lines) - 1 < settings.PAGE_ROWS:
                # Finished this month.
                break
            # Move to the next page.
            skip += settings.PAGE_ROWS
    # The record of what was asked for. Rows actually received are counted later, from the file itself.
    return {"source": "results", "window_start": start, "window_end": end, "api_total": total, "calls": calls, "seconds": round(time.time() - began, 1), "status": "ok", "error": ""}


# Download every month of results. A failure marks the whole dataset as failed, because part of a window can't be trusted.
def fetch_results(raw_dir, today, base=settings.WQ_BASE):
    # Manifest rows so far.
    rows = []
    # Each monthly window, oldest first.
    for start, end in month_windows(today):
        # Web failures are caught below.
        try:
            # Download this month.
            rows.append(fetch_month(raw_dir, start, end, base))
            # Show progress in the run's log.
            print(f"results {start[:7]}: {rows[-1]['api_total']} rows, {rows[-1]['calls']} calls, {rows[-1]['seconds']} s", flush=True)
        # The source failed after its retries.
        except SourceDown as error:
            # Record the failed window.
            rows.append({"source": "results", "window_start": start, "window_end": end, "api_total": None, "calls": 0, "seconds": 0, "status": "failed", "error": str(error)[:300]})
            # Say so in the log.
            print(f"results {start[:7]}: FAILED {error}", flush=True)
            # Don't keep hammering a service that is down.
            break
    # Hand back the record.
    return rows


# Download the whole sampling point register for the region.
def fetch_points(raw_dir, base=settings.WQ_BASE):
    # The clock for this source.
    began = time.time()
    # Calls made so far.
    calls = 0
    # The total stated by the service.
    total = None
    # Web failures are caught below.
    try:
        # Open the output file.
        with gzip.open(raw_dir / "points.jsonl.gz", "wt", encoding="utf-8") as out:
            # Start at the first point.
            skip = 0
            # Carry on until a short page arrives.
            while True:
                # One page of points. This route returns 404 unless the Accept header is set.
                page = json.loads(get_text(f"{base}/sampling-point?region={settings.REGION}&limit={settings.PAGE_POINTS}&skip={skip}", "application/ld+json"))
                # Count the call.
                calls += 1
                # The service states its own total on every page.
                total = page.get("totalItems")
                # Write each point on its own line.
                for member in page["member"]:
                    # One line of JSON.
                    out.write(json.dumps(member) + "\n")
                # A short page is the last one.
                if len(page["member"]) < settings.PAGE_POINTS:
                    # Finished.
                    break
                # Move to the next page.
                skip += settings.PAGE_POINTS
        # All went well.
        return [{"source": "points", "window_start": "", "window_end": "", "api_total": total, "calls": calls, "seconds": round(time.time() - began, 1), "status": "ok", "error": ""}]
    # The source failed after its retries.
    except SourceDown as error:
        # Record the failure, so its rules show "Not checked".
        return [{"source": "points", "window_start": "", "window_end": "", "api_total": total, "calls": calls, "seconds": round(time.time() - began, 1), "status": "failed", "error": str(error)[:300]}]


# Work out the latest bathing season that has begun: dates run from the first of May to the first of October.
def bathing_season(today):
    # Before May, the latest season is last year's.
    year = today.year if today.month >= 5 else today.year - 1
    # The season's start and end.
    return f"{year}-05-01", f"{year}-10-01"


# Download the latest season of bathing water samples, keeping only the fields the reconciliation needs.
def fetch_bathing(raw_dir, today, base=settings.BW_BASE):
    # The clock for this source.
    began = time.time()
    # The season to read.
    start, end = bathing_season(today)
    # Calls and rows so far.
    calls = 0
    # Rows written so far.
    written = 0
    # Web failures are caught below.
    try:
        # Open the output file.
        with gzip.open(raw_dir / "bathing.jsonl.gz", "wt", encoding="utf-8") as out:
            # Pages count from zero.
            page_number = 0
            # Carry on until the service says there is no next page.
            while True:
                # One page of 500 samples.
                reply = json.loads(get_text(f"{base}/bathing-water-quality/in-season/sample.json?_pageSize=500&_page={page_number}&min-sampleDateTime.inXSDDateTime={start}T00:00:00&max-sampleDateTime.inXSDDateTime={end}T00:00:00", "application/json"))["result"]
                # Count the call.
                calls += 1
                # Each sample on this page.
                for item in reply["items"]:
                    # Write the fields that matter, with plain names.
                    out.write(json.dumps({"bathing_code": item["bwq_samplingPoint"]["samplePointNotation"], "sampled_at": item["sampleDateTime"]["inXSDDateTime"]["_value"], "ecoli": item.get("escherichiaColiCount"), "ecoli_qualifier": (item.get("escherichiaColiQualifier") or {}).get("countQualifierNotation")}) + "\n")
                    # Count the row.
                    written += 1
                # No next page, or an empty one, means the end.
                if not reply.get("next") or not reply["items"]:
                    # Finished.
                    break
                # Move to the next page.
                page_number += 1
                # A safety stop far above the 16 pages a season normally takes.
                if page_number > 60:
                    # Fail loudly rather than loop for ever.
                    raise SourceDown("the bathing water service kept offering more pages than any season should have")
        # All went well. This service states no total, so what arrived is compared with itself and that is said on the page.
        return [{"source": "bathing", "window_start": start, "window_end": end, "api_total": written, "calls": calls, "seconds": round(time.time() - began, 1), "status": "ok", "error": ""}]
    # The source failed after its retries.
    except SourceDown as error:
        # Record the failure, so its rules show "Not checked".
        return [{"source": "bathing", "window_start": start, "window_end": end, "api_total": None, "calls": calls, "seconds": round(time.time() - began, 1), "status": "failed", "error": str(error)[:300]}]


# Download the code lists used to check that every code in the results is an official one.
def fetch_code_lists(raw_dir, base=settings.WQ_BASE):
    # The clock for this source.
    began = time.time()
    # The lists to read: the name in the address, and the name used here.
    lists = {"determinand": "determinand", "sampling-purpose": "purpose", "sampling-point-type": "point_type"}
    # Calls so far.
    calls = 0
    # Items written so far.
    written = 0
    # Web failures are caught below.
    try:
        # Open the output file.
        with gzip.open(raw_dir / "codes.jsonl.gz", "wt", encoding="utf-8") as out:
            # Each list.
            for address_name, plain_name in lists.items():
                # Start at the first item.
                skip = 0
                # Carry on until a short page arrives.
                while True:
                    # One page of codes.
                    page = json.loads(get_text(f"{base}/codelist/{address_name}?limit={settings.PAGE_POINTS}&skip={skip}", "application/ld+json"))
                    # Count the call.
                    calls += 1
                    # Each code on this page.
                    for member in page["member"]:
                        # Write the list name, code and label.
                        out.write(json.dumps({"code_list": plain_name, "code": member.get("notation"), "label": member.get("prefLabel")}) + "\n")
                        # Count the item.
                        written += 1
                    # A short page is the last one.
                    if len(page["member"]) < settings.PAGE_POINTS:
                        # On to the next list.
                        break
                    # Move to the next page.
                    skip += settings.PAGE_POINTS
        # All went well.
        return [{"source": "codes", "window_start": "", "window_end": "", "api_total": written, "calls": calls, "seconds": round(time.time() - began, 1), "status": "ok", "error": ""}]
    # The source failed after its retries.
    except SourceDown as error:
        # Record the failure, so its rules show "Not checked".
        return [{"source": "codes", "window_start": "", "window_end": "", "api_total": None, "calls": calls, "seconds": round(time.time() - began, 1), "status": "failed", "error": str(error)[:300]}]


# Say which licence a page's text states.
def licence_wording(text):
    # Open Government Licence wording, where the page gives it.
    if re.search(r"Open Government Licen[cs]e", text, re.I):
        # The usual statement.
        return "Open Government Licence"
    # The catalogue's wording when it gives none.
    if re.search(r"No Licen[cs]e Provided", text, re.I):
        # Say exactly that.
        return "No licence provided"
    # Anything else counts as not stated.
    return "Not stated"


# Read what the publisher says about the service tonight: its specification, and its licence wording in three places.
def fetch_source_watch(today_text, base=settings.WQ_BASE):
    # Each thing being watched: its name, its address and how to read it.
    pages = [("API specification", f"{base}/openapi.json", "spec"), ("Licence: water quality service", f"{base}/", "licence"), ("Licence: catalogue record", settings.CATALOGUE_URL, "licence"), ("Licence: bathing water service", settings.BW_HELP_URL, "licence")]
    # Rows so far.
    rows = []
    # Each page.
    for name, url, kind in pages:
        # A failure on one page doesn't stop the others.
        try:
            # Read the page.
            text = get_text(url, "application/json" if kind == "spec" else "text/html", attempts=2)
            # The specification is fingerprinted whole, with its version as the plain-English value.
            if kind == "spec":
                # Its stated version number.
                value = "version " + str(json.loads(text).get("info", {}).get("version"))
                # A fingerprint of the whole document, so any change shows.
                fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            # Licence pages change for many harmless reasons, so only the licence wording is fingerprinted.
            else:
                # The licence stated.
                value = licence_wording(text)
                # A fingerprint of the wording alone.
                fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
            # Record it.
            rows.append({"item": name, "kind": kind, "value": value, "fingerprint": fingerprint, "status": "ok", "checked_on": today_text})
        # The page could not be read.
        except (SourceDown, json.JSONDecodeError) as error:
            # Record that it couldn't be read, so its rule says "Not checked".
            rows.append({"item": name, "kind": kind, "value": "", "fingerprint": "", "status": "failed", "checked_on": today_text})
            # Say so in the log.
            print(f"source watch {name}: FAILED {error}", flush=True)
    # Hand back the rows.
    return rows


# Run the whole bronze step and return the manifest and source watch rows.
def fetch_all(raw_dir, today=None):
    # Today's date in UTC unless a test gives another.
    today = today or datetime.now(timezone.utc).date()
    # Make the folder if it's missing.
    raw_dir.mkdir(parents=True, exist_ok=True)
    # Clear last time's files, so a failed download can't be mistaken for fresh data.
    for old in raw_dir.glob("*.gz"):
        # Remove it.
        old.unlink()
    # The register comes first, because it is quick and shows at once if the service is down.
    manifest = fetch_points(raw_dir)
    # Then the results, month by month.
    manifest += fetch_results(raw_dir, today)
    # Then the second, independent service.
    manifest += fetch_bathing(raw_dir, today)
    # Then the official code lists.
    manifest += fetch_code_lists(raw_dir)
    # Then what the publisher says about itself.
    watch = fetch_source_watch(today.isoformat())
    # Hand both back.
    return manifest, watch
