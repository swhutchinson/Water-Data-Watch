# Power BI notes

What was confirmed while building Water Data Watch, so nobody has to work it out twice.

## How the project is built

- **Model:** `build/model.py` writes the tables and Power Query (run with Desktop closed). Measures and calculated tables are created through the Power BI modeling MCP from `build/new_measures.dax` and `build/calc_tables.dax`, and Desktop writes them into the TMDL on save.
- **Report:** `build/report.mjs` writes every page (run with Desktop closed). Charts are Deneb specs in `build/specs/`, sharing the tokens in `build/style.mjs`.
- **Fixtures:** `build/fixtures/` holds data for rendering charts offline with `node build/render.mjs`.

## Vega behaviour found in this build

| Finding | What to do |
|---|---|
| A group's `opacity` doesn't carry down to the marks inside it. An empty-state message in a hidden group still drew on top of the chart | Blank the text itself when it isn't wanted (`message()` in `style.mjs` takes a `show` signal) |
| A line of Vega text wrapped by counting where each word starts can overrun and be cut with an ellipsis | `wrapData` in `style.mjs` now breaks at the last space inside the limit, one step per line |
| A signal that reads a dataset which reads that signal is a cycle, and the chart doesn't draw | Size rows from the unfiltered `src` data, not from the dataset that uses the row height |
| Equal ranks on a slope chart draw their labels on top of each other | Give each its own place on the axis with a tie-break, and show `=5` |

## Decisions

| Decision | Why |
|---|---|
| The stated method defaults to an average, like the quick way | The difference then comes from the below-limit results, samples and months. The median stays available as its own switch |
| The reasons table sorts on what it shows: role, then sign | Power BI tables can't sort on a field that isn't in the visual. The signs happen to sort fails first, then not checked, then for review |
| `Exceptions[month_label]` says "Whole list" | A rule about a whole list has no month, and a slicer showing "(Blank)" isn't plain English |
| Bathing copy kept in the repository | The bathing water service refuses GitHub's servers, so the copy is taken by hand from a home connection, and rule SRC-06 fails when it goes out of date |

## Model findings

| Finding | What to do |
|---|---|
| A table of plain columns isn't filtered through a relationship: VAL-07 listed 4,121 rows instead of 500 | Include a measure that is blank for rows outside the filter (`Exception Rule`) |
| A measure on a grouped chart sees only its own row (`Headline` on the board) | Remove the filter on that table inside the measure |
| `Current` can't be a variable name, and `FORMAT(10, "0.###")` gives `10.` | Use another name; join the number to the text instead |
| Desktop sat on "Working on it" because of a sign-in box Sam had to answer | Ask Sam to look for a sign-in box before suspecting a hang |

## Still to confirm in Desktop

- Column widths on tables (`columnWidth` selector shape).
- The link on a text box run (`url`).
- `urlIcon` set through the theme.
- A wrapped title from a measure (`titleWrap`).
