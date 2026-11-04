# Settings shared by every part of the nightly engine, kept in one place so nothing is hidden in the code.

# Handles file paths.
from pathlib import Path

# The project folder, one level above this file.
ROOT = Path(__file__).resolve().parent.parent
# The register of rules, uses, roles and decisions: what people read and approve.
RULES = ROOT / "rules"
# The plain SQL the engine runs to build its layers.
SQL = ROOT / "engine" / "sql"
# Exact copies of what the sources served. Kept on the runner only and never published.
RAW = ROOT / "data" / "raw"
# The published data branch, checked out here so last night's history is tonight's starting point.
PUB = ROOT / "data" / "pub"

# The water quality service's fixed address.
WQ_BASE = "https://environment.data.gov.uk/water-quality"
# The bathing water service's fixed address.
BW_BASE = "https://environment.data.gov.uk/doc"
# The catalogue record for the water quality service, read only for its licence wording.
CATALOGUE_URL = "https://ckan.publishing.service.gov.uk/dataset/water-quality-explorer"
# The bathing water service's help page, read only for its licence wording.
BW_HELP_URL = "https://environment.data.gov.uk/bwq/profiles/help-api.html"
# How the engine introduces itself to the services. It carries no personal details.
USER_AGENT = "water-data-watch/1.0 (independent public data quality project)"
# The region this report covers.
REGION = "NW"
# How many whole calendar months of results each run reads, counting the current one.
WINDOW_MONTHS = 24
# The most rows the service allows in one CSV reply.
PAGE_ROWS = 2500
# The most sampling points or code list items the service allows in one reply.
PAGE_POINTS = 250
# The most exception rows published per rule. The true total is always published beside them.
EXCEPTION_CAP = 500
# How many passes in a row close an open issue.
PASSES_TO_CLOSE = 3
# Illustrative days allowed to respond to an issue, by severity.
RESPONSE_DAYS = {"Critical": 7, "Major": 30, "Minor": 90}
# Version of the engine, recorded with every run.
ENGINE_VERSION = "1.0"
# A saved copy of the latest bathing season, used when the live service can't be read. See engine/bathing_copy.py.
BATHING_COPY = RULES / "reference" / "bathing_copy.csv"

# THE POINT SCORE. These settings say what counts, so nothing about the score is hidden in the code. All of it is illustrative.
# The rules that can be traced to a sampling point and describe a real defect in its records.
POINT_SCORE_RULES = ["UNI-01", "UNI-02", "UNI-03", "VAL-01", "VAL-02", "VAL-03", "VAL-04", "VAL-06", "CON-03", "ACC-01", "ACC-02", "ACC-03", "ACC-04", "REC-01", "REC-02"]
# Rules shown on a point's detail but never counted against it. Below-limit results are a normal way to report. Why clock times are stamped is an open question.
POINT_INFO_RULES = ["VAL-07", "AI-04"]
# How much a rule counts towards a point's score, by its severity.
POINT_WEIGHTS = {"Critical": 3, "Major": 2, "Minor": 1}
# The four bands, best first. The words describe records, because a map of green and red could otherwise read as clean and dirty water.
POINT_BANDS = ["No flags", "A few flags", "Look closer", "No results to check"]
# A flagged point scoring below this needs a person to look. Illustrative.
POINT_LOOK_CLOSER_BELOW = 95
# How many points go in each text row the map draws from.
POINT_PACK_SIZE = 60
# Sub-area names a plain conversion to title case would get wrong.
POINT_AREA_NAMES = {"": "Unknown", "ECMAS SAMPLING (CUMBRIA AND LANCASHIRE)": "ECMAS sampling (Cumbria and Lancashire)", "ECMAS SAMPLING (GTR MANCS MERSEY AND CHES)": "ECMAS sampling (Manchester, Mersey and Cheshire)", "Multiple Values": "More than one area"}
