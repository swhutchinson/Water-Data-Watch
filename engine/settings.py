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
