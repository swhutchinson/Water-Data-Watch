# Sources

Every source this project reads, and what was measured about it. All of it is free, public data. Probed on 4 November 2026.

This is an independent project, not affiliated with or endorsed by the Environment Agency.

## 1. Water Quality Archive

| | |
|---|---|
| Service | `https://environment.data.gov.uk/water-quality` |
| Specification | `/openapi.json`, version 1.3.1 on 4 Nov 2026. The engine records its version each night (rule SRC-04) |
| Scope used | Region `NW`, a rolling 24 calendar months, one request window per month |
| Volume | 8,200 sampling points. 561,028 results in the window, Dec 2024 to Nov 2026, on 4 Nov 2026 |
| Publisher's update statement | Updated within two working days of a new sample being added, with a monthly refresh that may include corrections from quality assurance. Records may change as quality assurance continues |

### Routes used

| Route | Use | Limits and behaviour |
|---|---|---|
| `POST /data/observation` | Results, as CSV | Send no body: `{}` returns 422. Parameters go in the query string. `limit` 2,500 for CSV, 250 for JSON-LD. A date range can't exceed a year |
| `POST /data/observation` with `limit=1`, JSON-LD | The source's own count for a window | `totalItems`, in about 0.25 s. This is the control total for rule SRC-01 |
| `GET /sampling-point` | The register | `limit` 250. Needs an `Accept` header, or it returns 404 |
| `GET /codelist/determinand`, `/codelist/sampling-purpose`, `/codelist/sampling-point-type` | Official code lists | Paged at 250. A larger `limit` returns 422 |

### Behaviour worth knowing

- **`dateTo` leaves out the day it names.** A year ending `dateTo=2025-12-31` returned 303,085 rows, against 304,501 for `dateTo=2026-01-01`, with no error. Windows here end on the first day of the next month. Rule SRC-02 tests this.
- **Times carry no time zone.** Every time reads `YYYY-MM-DDTHH:MM:SS` with no marker, and the specification states none. They are treated as clock time as served, and never converted.
- **There is no sample column.** The sample number is read from the `id`, which is a working web address. That lets an exception link straight to its source record.
- **Results are text.** The `result` column holds numbers, values below or above a limit such as `<0.03`, and words such as `Not found`.
- **Stepping by month gave no duplicate records,** so paging is stable.
- About 340 requests, one after another, and 4 to 5 minutes a night. No rate limit is stated, so requests are sequential and retries back off.

## 2. Bathing Water Quality service

| | |
|---|---|
| Service | `https://environment.data.gov.uk/doc/bathing-water-quality/in-season/sample.json` |
| Scope used | The latest bathing season that has begun, England-wide, paged at 500. Only points that can be linked to North West results are compared |
| Volume | 7,578 samples in the 2026 season |
| Use here | An independent check on the results service (rules REC-01 and REC-02). Nothing else |

**This service refuses the nightly runner.** From GitHub's servers it returns HTTP 403, while the same request from a home connection succeeds. That refusal is respected: nothing hides where a request comes from. Instead, `python -m engine.bathing_copy` is run by hand from a home connection and saves the North West's samples to `rules/reference/bathing_copy.csv`. The engine still tries the live service each night. If that fails, it uses the copy and records `copy` in the manifest, and rule SRC-06 fails once the copy goes out of date. Samples only arrive in season, so one copy taken after September lasts until the next May.

The only link between the two services is a five-digit code inside a free-text label. Some points can't be linked, and rule REC-02 counts them. The comparison covers E. coli counts at linked points. It doesn't compare the sign on a below-limit or above-limit value.

## 3. Licence position

The sources disagree, so this is recorded rather than smoothed over.

| Where | What it says (4 Nov 2026) |
|---|---|
| Water quality service, page footer | Open Government Licence v3.0, except where otherwise stated. © Crown Copyright 2026 |
| Bathing water help page | Open Government Licence v3.0 |
| Catalogue record for the same data | No Licence Provided. © Environment Agency copyright and/or database right 2025. All rights reserved |

**This project relies on the service's own statement,** the most direct one available. The difference is recorded as an observation for review (rule AUD-02), and the engine re-reads all three each night. It is most likely an out-of-date catalogue entry, but that hasn't been confirmed, so it stays a question.

Attribution used on every page: "Contains Environment Agency information © Environment Agency and/or database right".

The map's outline of North West England is the ONS regions boundary (ultra generalised), converted to the National Grid by `build/make_outline.py` and built into the report. Source: Office for National Statistics licensed under the Open Government Licence v.3.0. Contains OS data © Crown copyright and database right. It is stated in full on the "How it works" page.

## 4. Deliberately left out

- **Storm overflow returns.** North West rows can only be reached by filtering on a company, and this project is scoped by region. It compares no companies.
- **The permit register.** Its value here didn't justify the personal data handling it would need.
- **The undertaker field on bathing water sites.** Not read, for the same reason as storm overflows.
- **Sampling point labels, where they could identify anyone.** See `docs/DATA_CONTRACT.md`.

## 5. Frameworks cited

- [The Government Data Quality Framework](https://www.gov.uk/government/publications/the-government-data-quality-framework/the-government-data-quality-framework) (2020): the six dimensions, and the idea that quality means fitness for purpose.

This project uses the framework's vocabulary. It doesn't claim to comply with it, or with any regulator's process.
