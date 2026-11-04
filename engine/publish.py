# Writes the night's outputs as small CSV files for Power BI, with guards that refuse to publish anything suspect.
# The data branch has no history of its own, so losing rows from a history file would lose them for ever. That is the guard's first job.

# Writes CSV files.
import csv
# Searches published text for personal data patterns.
import re
# Forms file paths for SQL.
from engine.layers import sql_path
# Reads earlier files.
from engine.layers import read_csv_rows

# The patterns that must never appear in anything published.
POSTCODE = re.compile(r"\b[A-Z]{1,2}[0-9][0-9A-Z]? [0-9][A-Z]{2}\b")
# A title followed by a word, which may name a person.
PERSON = re.compile(r"\b(MR|MRS|MS|MISS)\.? [A-Z]{2,}\b")


# Raised when publishing would lose history or expose something it shouldn't. This fails the run loudly.
class PublishRefused(Exception):
    # No extra behaviour is needed beyond the name and message.
    pass


# Write a list of dictionaries to a CSV file with a fixed column order.
def write_rows(path, rows, columns):
    # Make the folder if it's missing.
    path.parent.mkdir(parents=True, exist_ok=True)
    # Windows needs newline="" or every row gains a blank line.
    with open(path, "w", newline="", encoding="utf-8") as handle:
        # Columns come from the data contract, never from whatever happens to be in the first row.
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        # The header line.
        writer.writeheader()
        # Every row.
        writer.writerows(rows)


# Add tonight's rows to a history file, refusing if the file has lost rows since last time.
def append_history(path, new_rows, columns):
    # Whatever the file already holds.
    previous = read_csv_rows(path)
    # Write the old rows and the new together.
    write_rows(path, previous + new_rows, columns)
    # Read it back to check.
    after = read_csv_rows(path)
    # A history file must never shrink.
    if len(after) < len(previous):
        # Stop the run.
        raise PublishRefused(f"{path.name} would shrink from {len(previous)} to {len(after)} rows")
    # Hand back the combined history.
    return after


# Count the rows in every history file, before tonight's run touches them.
def count_history(folder):
    # One count per file. A missing folder gives no counts.
    return {path.name: len(read_csv_rows(path)) for path in sorted(folder.glob("*.csv"))}


# Stop the run if any history file has fewer rows than it started with, or has gone missing.
def check_history(folder, counts_before):
    # What the files hold now.
    counts_now = count_history(folder)
    # Any file that lost rows, or vanished.
    shrunk = [f"{name} went from {count} to {counts_now.get(name, 0)} rows" for name, count in counts_before.items() if counts_now.get(name, 0) < count]
    # Losing history can't be undone, so nothing is published.
    if shrunk:
        # Name every file affected.
        raise PublishRefused("History would be lost: " + "; ".join(shrunk))


# Copy a gold table to a CSV file.
def copy_table(con, table, path):
    # Make the folder if it's missing.
    path.parent.mkdir(parents=True, exist_ok=True)
    # Quote strings where needed, and write empty for missing.
    con.execute(f"COPY {table} TO '{sql_path(path)}' (HEADER, DELIMITER ',')")


# Search every published CSV for personal data patterns, and refuse to publish if one appears.
def privacy_sweep(folder):
    # What was found.
    hits = []
    # Every CSV file about to be published.
    for path in sorted(folder.rglob("*.csv")):
        # Read it as text.
        text = path.read_text(encoding="utf-8", errors="ignore")
        # Look for a postcode.
        if POSTCODE.search(text.upper()):
            # Record the file, never the match.
            hits.append(f"{path.name}: a postcode pattern")
        # Look for a title followed by a name.
        if PERSON.search(text.upper()):
            # Record the file, never the match.
            hits.append(f"{path.name}: a title followed by a name")
    # Any hit stops the run before anything is pushed.
    if hits:
        # Say where to look.
        raise PublishRefused("Personal data sweep: " + "; ".join(hits))
    # Say how much was swept.
    return len(list(folder.rglob("*.csv")))
