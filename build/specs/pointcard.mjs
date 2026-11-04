// ONE POINT'S CARD, on the drill-through page: its score and band, the facts about it, where it is, and what the score means.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, panel, chipMarks, wrapData, message, C, FONT_DISPLAY } from '../style.mjs';
import { NW_OUTLINE } from './nw_outline.mjs';

// Fields delivered by Power BI, and the numeric ones among them
const fm = fieldMap([['point_label'], ['point_group'], ['area_name'], ['point_status'], ['location_kind'], ['band'], ['score'], ['results'], ['samples'], ['newest_date'], ['flags'], ['map_e'], ['map_n'], ['Ran', 'Checks Ran'], ['Flagged', 'Checks Flagged'], ['Explain', 'Point Explain Text']],
  ['score', 'results', 'samples', 'flags', 'map_e', 'map_n', 'Ran', 'Flagged']);
// The grid's limits for the small map, in units of 100 m
const EAST_MIN = 2925, NORTH_MAX = 5816, NORTH_MIN = 3409;
// Where the facts and the lower half start, in design px
const FACTS = 234, LOWER = 508, MAP_H = 280;

export default frame('One sampling point: its record quality score, band, facts and location', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [
    ...fm.signals, ...sizeSignals(620, 780),
    { name: 'one', update: "length(data('src')) === 1" },
    { name: 'r0', update: "one ? data('src')[0] : {}" },
    { name: 'hasScore', update: 'isValid(r0.score) && r0.results > 0' },
    { name: 'hasPlace', update: 'isValid(r0.map_e) && isValid(r0.map_n) && r0.map_e > 0' },
    { name: 'k', update: `${MAP_H} * u / ${NORTH_MAX - NORTH_MIN}` },
    { name: 'ox', update: `24 * u - ${EAST_MIN} * k` },
    { name: 'oy', update: `${LOWER + 8} * u + ${NORTH_MAX} * k` },
  ],
  data: [
    ...fm.data,
    wrapData('nameLines', 'r0.point_label', '(W - 48 * u) / (15 * u)', 3),
    wrapData('explainLines', 'r0.Explain', '(W - 210 * u) / (8.6 * u)', 12),
    // The facts, each only as long as it needs to be
    { name: 'facts', values: [
      { i: 0, k: 'Type', v: 'r0.point_group' }, { i: 1, k: 'Area', v: 'r0.area_name' }, { i: 2, k: 'Listed as', v: 'r0.point_status' }, { i: 3, k: 'Results checked', v: 'r0.results' }, { i: 4, k: 'Samples', v: 'r0.samples' }, { i: 5, k: 'Newest sample', v: 'r0.newest_date' }, { i: 6, k: 'Checks that reached it', v: 'r0.Ran' },
    ], transform: [
      { type: 'formula', as: 'value', expr: "datum.k === 'Type' ? r0.point_group : datum.k === 'Area' ? r0.area_name : datum.k === 'Listed as' ? (r0.point_status === 'OPEN' ? 'Open' : r0.point_status === 'CLOSED' ? 'Closed' : r0.point_status) : datum.k === 'Results checked' ? format(r0.results || 0, ',') : datum.k === 'Samples' ? format(r0.samples || 0, ',') : datum.k === 'Newest sample' ? (r0.newest_date ? timeFormat(toDate(r0.newest_date), '%-d %b %Y') : 'None in the window') : (r0.Ran || 0) + ', of which ' + (r0.Flagged || 0) + ' flagged something'" },
    ] },
  ],
  marks: [
    panel(),
    txt('one ? datum.text : \'\'', { from: 'nameLines', x: '24 * u', y: '42 * u + datum.line * 34 * u', size: 26, weight: 700, font: FONT_DISPLAY }),
    // The score, large, with its band beside it
    txt("!one ? '' : hasScore ? format(r0.score, '.1f') : 'No score'", { x: '24 * u', y: '180 * u', size: 72, weight: 700, font: FONT_DISPLAY }),
    txt("one && hasScore ? 'out of 100, illustrative' : ''", { x: '24 * u', y: '210 * u', size: 16, color: C.muted }),
    ...chipMarks('r0.band', 'W - 270 * u', '132 * u', '246 * u', '54 * u', { word: 'r0.band', show: 'one', size: 19, signSize: 19, signAt: 22, textAt: 40 }),
    // The facts
    txt("one ? datum.k : ''", { from: 'facts', x: '24 * u', y: `(${FACTS + 22} + datum.i * 34) * u`, size: 17, color: C.muted }),
    txt("one ? datum.value : ''", { from: 'facts', x: '224 * u', y: `(${FACTS + 22} + datum.i * 34) * u`, size: 17, weight: 600, limit: 'W - 248 * u' }),
    // Where it is
    { type: 'path', interactive: false, encode: { update: { x: { signal: 'ox' }, y: { signal: 'oy' }, scaleX: { signal: 'k' }, scaleY: { signal: 'k' }, path: { value: NW_OUTLINE }, fill: { value: C.panel2 }, stroke: { value: C.soft }, strokeWidth: { value: 1 }, opacity: { signal: 'one ? 1 : 0' } } } },
    { type: 'symbol', interactive: true, encode: { update: { x: { signal: 'ox + (r0.map_e || 0) * k' }, y: { signal: 'oy - (r0.map_n || 0) * k' }, size: { signal: '150 * u * u' }, fill: { value: C.text }, stroke: { value: C.blue }, strokeWidth: { signal: '3 * u' }, opacity: { signal: 'one && hasPlace ? 1 : 0' }, tooltip: { signal: "{'Sampling point': r0.point_label, 'Where': r0.area_name}" } } } },
    txt("one && !hasPlace ? 'No real location' : ''", { x: '86 * u', y: `${LOWER + 150} * u`, size: 16, weight: 600, align: 'center', color: C.text }),
    // What the score means
    txt("one ? datum.text : ''", { from: 'explainLines', x: '180 * u', y: `(${LOWER + 24}) * u + datum.line * 24 * u`, size: 17 }),
    // Asked for without choosing a point
    ...message("'Choose a point first'", 'H / 2', "'On the map page or the list, pick a row, then press the button or right-click and choose Drill through.'", '!one'),
    fieldMapDiagnostic(),
  ],
});
