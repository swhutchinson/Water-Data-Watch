# Turns build/new_measures.dax into the JSON list of measure definitions the Power BI modeling MCP's Create call takes.
# Each measure's description also goes in as a "//" comment on the first line of its DAX, so the formula explains itself.
# Usage: python build/measures_json.py > out.json

# Read the DAX file and write JSON
import json
# Split the file into measures
import re
# Path handling
from pathlib import Path

# This script's folder
HERE = Path(__file__).resolve().parent
# Whole numbers, shown with a thousands comma
WHOLE = {"Latest Run No", "Run Count", "Days Tracked", "Hours Since Check", "Source Rows", "Arrived Rows", "Checked Rows", "Summarised Rows", "Totals Agree", "Rules Pass", "Rules Fail", "Rules Review", "Rules Not Checked", "Rules No Data", "Rules Total", "Planted Caught", "Planted Tested", "Run Seconds", "Issues Open", "Records New", "Records Changed", "Records Removed", "Changes Count", "Is Default Use", "Gates Failed", "Gates Unchecked", "Conditions Open", "Quick Rank", "Your Rank", "Is Default Same Data", "Is Default Rule", "Exceptions Shown", "Lineage Lost Rows"}
# Measures that are dates
DATES = {"Tracking Since"}
# Figures shown with two decimals
FIGURES = {"Quick Figure", "Your Figure", "Region Quick", "Region Yours", "Switch Figure", "Switch Base"}
# A point's score, to one decimal place
SCORES = {"Point Score"}
# Shares shown as a percentage
SHARES = {"Check Share"}
# Whole numbers on the point pages
WHOLE_POINTS = {"Points Shown", "Points No Flags", "Points A Few Flags", "Points Look Closer", "Points No Results", "Point Flags", "Point Results", "Checks Ran", "Checks Flagged", "Check Records", "Check Flagged Records"}
# Anything else returns text, so it gets no number format
# Helpers kept out of the field list
HIDDEN = set()

# Split the file at each MEASURE header (the first piece is the file's own comments)
blocks = re.split(r"^MEASURE 'Report Measures'\[", (HERE / "new_measures.dax").read_text(encoding="utf-8"), flags=re.M)[1:]
# The definitions to hand to the MCP
out = []
# Each measure in turn
for block in blocks:
    # The name, then everything after "] ="
    name, rest = block.split("] =", 1)
    # Its lines without the trailing blank ones
    lines = rest.strip("\n").splitlines()
    # The display folder line
    folder = next(l.split(":", 1)[1].strip() for l in lines if l.startswith("-- folder:"))
    # The description line
    desc = next(l.split(":", 1)[1].strip() for l in lines if l.startswith("-- desc:"))
    # The DAX: every line that isn't a folder/desc line or a section divider
    dax = [l for l in lines if not l.startswith(("-- folder:", "-- desc:", "-- ===="))]
    # Drop blank lines at the end
    while dax and not dax[-1].strip():
        # Remove the last blank line
        dax.pop()
    # The definition: a comment line, then the formula
    d = {"name": name, "tableName": "Report Measures", "displayFolder": folder, "description": desc,
         "expression": "// " + desc + "\n" + "\n".join(dax)}
    # Pick the number format
    if name in DATES:
        # Dates as 26 Oct 2026
        d["formatString"] = "d mmm yyyy"
    elif name in FIGURES:
        # Figures with two decimals
        d["formatString"] = "0.00"
    elif name in SCORES:
        # One decimal place
        d["formatString"] = "0.0"
    elif name in SHARES:
        # A percentage
        d["formatString"] = "0.0%"
    elif name in WHOLE or name in WHOLE_POINTS:
        # Whole numbers
        d["formatString"] = "#,0"
    # Hide helpers
    if name in HIDDEN:
        # Out of the field list
        d["isHidden"] = True
    # Add it to the list
    out.append(d)
# Print the JSON for the MCP call
print(json.dumps(out, ensure_ascii=True))
