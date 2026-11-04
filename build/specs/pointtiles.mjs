// THE KEY NUMBERS beside the map: how many sampling points fall in each band, each with a sign and a word as well as a colour.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, signMark, statusFill, isGrey, C, FONT_DISPLAY } from '../style.mjs';

// Fields delivered by Power BI: one row of measures
const fm = fieldMap([['Shown', 'Points Shown'], ['NoFlags', 'Points No Flags'], ['FewFlags', 'Points A Few Flags'], ['LookCloser', 'Points Look Closer'], ['NoResults', 'Points No Results']], ['Shown', 'NoFlags', 'FewFlags', 'LookCloser', 'NoResults']);
// The tiles in order, with what each one means on hover
const TILES = [
  { word: 'No flags', field: 'NoFlags', means: 'Every check that reached this point passed. That says the records are complete and consistent, not that a reading is true or the water is clean' },
  { word: 'A few flags', field: 'FewFlags', means: 'At least one record was flagged, and the point still scores 95 or more. Illustrative' },
  { word: 'Look closer', field: 'LookCloser', means: 'Flagged, and the point scores under 95, so a person should look. These are observations for review. Illustrative' },
  { word: 'No results to check', field: 'NoResults', means: 'The point is listed as open but has no results in the window, so nothing can be scored. Not a pass and not a fail' },
];

export default frame('Key numbers: how many sampling points fall in each record quality band', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [
    ...fm.signals, ...sizeSignals(1104, 150),
    { name: 'r0', update: "length(data('src')) ? data('src')[0] : {}" },
    { name: 'tileW', update: '(W - 3 * 12 * u) / 4' },
  ],
  data: [
    ...fm.data,
    // One row per tile, each reading its own number
    { name: 'tiles', values: TILES.map((t, i) => ({ ...t, i })), transform: [
      { type: 'formula', as: 'x', expr: 'datum.i * (tileW + 12 * u)' },
      { type: 'formula', as: 'value', expr: 'r0[datum.field] || 0' },
      { type: 'formula', as: 'tip', expr: "{'Record quality': datum.word, 'Sampling points': format(datum.value, ','), 'Share of those showing': r0.Shown ? format(datum.value / r0.Shown, '.1%') : '', 'What it means': datum.means}" },
    ] },
  ],
  marks: [
    // Each tile: tinted for its band, and hollow and dashed if it is grey
    { type: 'rect', from: { data: 'tiles' }, interactive: true, encode: { update: {
      x: { signal: 'datum.x' }, y: { value: 0 }, width: { signal: 'tileW' }, height: { signal: 'H' }, cornerRadius: { signal: '14 * u' }, fill: { signal: statusFill('datum.word') }, fillOpacity: { signal: `${isGrey('datum.word')} ? 0 : 0.2` },
      stroke: { signal: statusFill('datum.word') }, strokeWidth: { signal: '1.5 * u' }, strokeDash: { signal: `${isGrey('datum.word')} ? [6 * u, 4 * u] : [0]` }, tooltip: { signal: 'datum.tip' },
    } } },
    signMark('datum.word', 'datum.x + 30 * u', '44 * u', 26, { from: 'tiles', width: 4 }),
    txt("format(datum.value, ',')", { from: 'tiles', x: 'datum.x + 58 * u', y: '66 * u', size: 56, weight: 700, font: FONT_DISPLAY }),
    txt('datum.word', { from: 'tiles', x: 'datum.x + 20 * u', y: '112 * u', size: 22, weight: 600, font: FONT_DISPLAY, limit: 'tileW - 30 * u' }),
    txt("r0.Shown ? format(datum.value / r0.Shown, '.0%') + ' of those showing' : ''", { from: 'tiles', x: 'datum.x + 20 * u', y: '136 * u', size: 16, color: C.muted, limit: 'tileW - 30 * u' }),
    fieldMapDiagnostic(),
  ],
});
