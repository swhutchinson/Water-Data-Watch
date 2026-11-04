# Water Data Watch

A working data quality system for public water data, built to be seen in Power BI. It answers one question: **can this data be trusted for the decision it is about to feed, and if not, who needs to do what?**

It uses North West England data from the Environment Agency. **It is about the data, not the water.** It says nothing on whether any river or beach is clean or safe.

Independent project, not affiliated with or endorsed by the Environment Agency.

**Status: being built.** The engine and its tests are here. The Power BI report comes next, and this page will link to it once it is live.

## What it does

- **A rule register:** 40 rules, each with a reason, a severity, thresholds, an owner role and an action.
- **Checks on all the data in the window:** about 560,000 results and 8,200 sampling points, in a window of 24 calendar months that includes the current one.
- **Planted defects:** each rule's own defect is put into a private copy of the data, to prove the rule still fires. The copy is then thrown away.
- **Does it change the answer?** Where it can be measured, each problem's figure is worked out carefully and carelessly, which sets the order to fix things in.
- **A verdict for each decision:** Fit, Fit with conditions, Not fit or Not checked, for sending a monthly report, showing a trend, signing off a figure and training an AI model. There is no average score, and a failed gate can't be outvoted.
- **Honest gaps:** a source that is down shows Not checked and an empty table shows No data. Neither counts as a pass.
- **A change ledger:** every record is fingerprinted, so anything that changes after publication can be counted from the first run onwards.

## How it works

```
Environment Agency services
   |  engine/fetch.py
Bronze: everything as text, plus what was asked for and what came back
   |  engine/sql/silver.sql
Silver: the result column read by stated rules, with labels screened
   |  rules/register.yaml + rules/sql/*.sql
Checks, planted defects, effect tests, verdicts, issues, change ledger
   |  engine/sql/gold.sql + engine/publish.py
Small CSV files on the powerbi-data branch, with guards against lost history and personal data
   |
Power BI, refreshing in the Service with no gateway
```

Roles, thresholds, response times and decisions are illustrative. They show how a programme could run, and describe no real organisation.

## Run it yourself

```
pip install -r requirements.txt
python -m pytest -q
python -m engine.run
```

The tests use made-up data and need no network. The engine reads public services and writes to `data/`.

## Documents

- [Data quality framework](docs/DATA_QUALITY_FRAMEWORK.md): the standard this works to.
- [Data contract](docs/DATA_CONTRACT.md): each layer and published file.
- [Sources](docs/SOURCES.md): what was measured about each source, and the licence position.

## Licence and attribution

Code: MIT.

Contains Environment Agency information © Environment Agency and/or database right. Data read under the Open Government Licence v3.0, as the service's own pages state. See [Sources](docs/SOURCES.md) for a difference between that and its catalogue record.
