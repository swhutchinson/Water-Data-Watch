// THE MAP. Every sampling point, by the quality of its records. Colour, shape and a word each say the same thing, and the title
// says it is about the records, not the water. The points arrive packed into short text rows, because a chart's cost grows with
// rows and not marks. Flagged points each have a row of their own, so clicking one can find exactly that point in the list.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, panel, message, C, FONT_DISPLAY } from '../style.mjs';
import { NW_OUTLINE } from './nw_outline.mjs';

// Fields delivered by Power BI, and the numeric ones among them
const fm = fieldMap([['pack_id'], ['point_group'], ['area_name'], ['band'], ['located'], ['packed']], ['pack_id']);
// The drawing's size in design px, where the map starts, and the bounding box of the region on the grid, in units of 100 m
const REF_W = 720, REF_H = 868, MAP_LEFT = 318, MAP_TOP = 98, MAP_BOTTOM = 852, EAST_MIN = 2925, NORTH_MAX = 5816, NORTH_MIN = 3409;
// Towns to find your way by, on the same grid, each with the side its name sits on
const PLACES = [['Carlisle', 3400, 5560, 'left'], ['Whitehaven', 2975, 5180, 'left'], ['Kendal', 3515, 4925, 'left'], ['Barrow', 3200, 4695, 'right'], ['Lancaster', 3478, 4615, 'left'], ['Blackpool', 3310, 4360, 'right'], ['Preston', 3540, 4295, 'left'], ['Liverpool', 3350, 3905, 'right'], ['Manchester', 3840, 3980, 'left'], ['Chester', 3405, 3665, 'right'], ['Crewe', 3705, 3555, 'left']];
// The four bands in the order they are drawn: the ones needing attention last, so they sit on top
const BANDS = {
  grey: { word: 'No results to check', shape: 'circle', size: 15, fill: 'transparent', stroke: C.grey, width: 1 },
  green: { word: 'No flags', shape: 'circle', size: 20, fill: C.pass, stroke: C.panel, width: 0.3 },
  amber: { word: 'A few flags', shape: 'triangle-up', size: 62, fill: C.review, stroke: C.panel, width: 0.8 },
  red: { word: 'Look closer', shape: 'diamond', size: 110, fill: C.fail, stroke: C.text, width: 1 },
};
// What the hover shows. Keys say what they are, because Deneb shows every key
const TIP = "{'Sampling point': datum.label, 'Type': datum.point_group, 'Area': datum.area_name, 'Record quality': datum.band, 'Score out of 100': datum.score === '' ? 'No score: no results to check' : datum.score, 'Results checked': datum.results, 'About': 'The records, not the water. Scores are illustrative'}";
// One band's dots
const dots = (name, b, clickable) => ({
  type: 'symbol', name: `dots_${name}`, from: { data: `d_${name}` }, interactive: true,
  encode: { update: {
    x: { signal: 'ox + datum.e * k' }, y: { signal: 'oy - datum.n * k' }, shape: { value: b.shape }, size: { signal: `${b.size} * u * u` },
    fill: { value: b.fill }, stroke: { value: b.stroke }, strokeWidth: { signal: `${b.width} * u` }, tooltip: { signal: TIP },
    ...(clickable ? { cursor: { value: 'pointer' } } : {}),
  } },
});
// One line of the legend: its shape, its word and what it means
const key = (b, y, meaning) => [
  { type: 'symbol', interactive: false, encode: { update: { x: { signal: '36 * u' }, y: { signal: `${y - 6} * u` }, shape: { value: b.shape }, size: { signal: `${Math.max(b.size * 2.4, 130)} * u * u` }, fill: { value: b.fill }, stroke: { value: b.stroke === C.panel ? b.fill : b.stroke }, strokeWidth: { signal: `${b.fill === 'transparent' ? 2 : b.width} * u` } } } },
  txt(JSON.stringify(b.word), { x: '60 * u', y: `${y} * u`, size: 19, weight: 700, font: FONT_DISPLAY }),
  txt(JSON.stringify(meaning), { x: '60 * u', y: `${y + 22} * u`, size: 15, color: C.muted, limit: '245 * u' }),
];

export default frame('Map of every sampling point in North West England, by the quality of its records', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [
    ...fm.signals, ...sizeSignals(REF_W, REF_H),
    // Pixels per 100 m, and where the grid's origin falls, so east and north map straight onto the page
    { name: 'k', update: `(${MAP_BOTTOM - MAP_TOP}) * u / ${NORTH_MAX - NORTH_MIN}` },
    { name: 'ox', update: `${MAP_LEFT} * u - ${EAST_MIN} * k` },
    { name: 'oy', update: `${MAP_TOP} * u + ${NORTH_MAX} * k` },
    { name: 'parkedCount', update: "length(data('parked'))" },
    { name: 'drawnCount', update: "length(data('drawn'))" },
    // Clicking a flagged dot finds it in the list beside the map. Clicking anywhere else clears that
    { name: 'pickDot', on: [
      { events: [{ markname: 'dots_amber', type: 'click' }, { markname: 'dots_red', type: 'click' }], update: "pbiCrossFilterApply(event, \"datum['pack_id'] == \" + datum.pack_id)", force: true },
      { events: { markname: 'panelBack', type: 'click' }, update: 'pbiCrossFilterClear()', force: true },
    ] },
  ],
  data: [
    ...fm.data,
    // Unpack each row into its points: east, north, score, results, name
    { name: 'points', source: 'src', transform: [
      { type: 'formula', as: 'items', expr: "split(datum.packed, '|')" },
      { type: 'flatten', fields: ['items'], as: ['item'] },
      { type: 'formula', as: 'f', expr: "split(datum.item, '~')" },
      { type: 'formula', as: 'e', expr: "datum.f[0] === '' ? null : toNumber(datum.f[0])" },
      { type: 'formula', as: 'n', expr: "datum.f[1] === '' ? null : toNumber(datum.f[1])" },
      { type: 'formula', as: 'score', expr: 'datum.f[2]' },
      { type: 'formula', as: 'results', expr: 'datum.f[3]' },
      { type: 'formula', as: 'label', expr: 'datum.f[4]' },
    ] },
    { name: 'drawn', source: 'points', transform: [{ type: 'filter', expr: 'datum.e !== null && datum.n !== null' }] },
    // One list per band
    ...Object.entries(BANDS).map(([name, b]) => ({ name: `d_${name}`, source: 'drawn', transform: [{ type: 'filter', expr: `datum.band === '${b.word}'` }] })),
    // Points with no real location, set out in a grid in their own box rather than drawn in the sea
    { name: 'parked', source: 'points', transform: [
      { type: 'filter', expr: 'datum.e === null || datum.n === null' },
      { type: 'window', ops: ['row_number'], as: ['i'] },
      { type: 'formula', as: 'px', expr: '(38 + ((datum.i - 1) % 13) * 19.5) * u' },
      { type: 'formula', as: 'py', expr: '(734 + floor((datum.i - 1) / 13) * 14.5) * u' },
    ] },
    { name: 'places', values: PLACES.map(([name, e, n, side]) => ({ name, e, n, side })) },
  ],
  marks: [
    { ...panel(), name: 'panelBack', interactive: true },
    // The title says plainly what the colours are about
    txt("'Record quality at every sampling point'", { x: '24 * u', y: '42 * u', size: 25, weight: 700, font: FONT_DISPLAY }),
    txt("'Colours describe the records, not the water.'", { x: '24 * u', y: '72 * u', size: 19, weight: 600, color: C.reviewText, font: FONT_DISPLAY }),
    // The region, with north up the page
    { type: 'path', interactive: false, encode: { update: { x: { signal: 'ox' }, y: { signal: 'oy' }, scaleX: { signal: 'k' }, scaleY: { signal: 'k' }, path: { value: NW_OUTLINE }, fill: { value: C.panel2 }, stroke: { value: C.soft }, strokeWidth: { value: 1 } } } },
    // The dots, with the ones needing attention on top
    dots('grey', BANDS.grey), dots('green', BANDS.green), dots('amber', BANDS.amber, true), dots('red', BANDS.red, true),
    // Towns: a dark outline first, so the name stays readable over dots
    ...[{ stroke: C.bg, sw: 4 }, {}].map(o => {
      const m = txt('datum.name', { from: 'places', x: "ox + datum.e * k + (datum.side === 'left' ? 7 : -7) * u", y: 'oy - datum.n * k + 5 * u', size: 15, weight: 600, color: C.text });
      m.encode.update.align = { signal: "datum.side === 'left' ? 'left' : 'right'" };
      if (o.stroke) { m.encode.update.stroke = { value: o.stroke }; m.encode.update.strokeWidth = { signal: `${o.sw} * u` }; m.encode.update.strokeJoin = { value: 'round' }; }
      return m;
    }),
    // The legend: shape, word and meaning, in the sea to the left of the land
    ...key(BANDS.green, 126, 'Every check passed here'),
    ...key(BANDS.amber, 186, 'Flagged, but scores 95 or more'),
    ...key(BANDS.red, 246, 'Flagged, and scores under 95'),
    ...key(BANDS.grey, 306, 'Open, but nothing to check yet'),
    txt("'Scores and bands are illustrative.'", { x: '24 * u', y: '372 * u', size: 15, color: C.muted }),
    txt("'Hover over any dot for its details.'", { x: '24 * u', y: '402 * u', size: 16, color: C.text }),
    txt("'Click a triangle or diamond to find'", { x: '24 * u', y: '426 * u', size: 16, color: C.text }),
    txt("'it in the list on the right.'", { x: '24 * u', y: '448 * u', size: 16, color: C.text }),
    // The box for points with no real location
    { type: 'rect', interactive: false, encode: { update: { x: { signal: '24 * u' }, y: { signal: '634 * u' }, width: { signal: '268 * u' }, height: { signal: '218 * u' }, cornerRadius: { signal: '10 * u' }, fill: { value: C.bg }, stroke: { value: C.grey }, strokeWidth: { signal: '1.5 * u' }, strokeDash: { signal: '[5 * u, 4 * u]' } } } },
    txt("'No real location: ' + format(parkedCount, ',')", { x: '38 * u', y: '662 * u', size: 19, weight: 700, font: FONT_DISPLAY }),
    txt("'Position is a stand-in or outside'", { x: '38 * u', y: '686 * u', size: 15, color: C.muted, limit: '246 * u' }),
    txt("'the region, so not on the map.'", { x: '38 * u', y: '706 * u', size: 15, color: C.muted, limit: '246 * u' }),
    ...Object.values(BANDS).map(b => ({ type: 'symbol', from: { data: 'parked' }, interactive: true, encode: { update: {
      x: { signal: 'datum.px' }, y: { signal: 'datum.py' }, shape: { value: b.shape }, size: { signal: `min(${b.size}, 50) * u * u` }, fill: { value: b.fill }, stroke: { value: b.stroke }, strokeWidth: { signal: `${b.width} * u` },
      opacity: { signal: `datum.band === '${b.word}' ? 1 : 0` }, tooltip: { signal: `datum.band === '${b.word}' ? ${TIP} : null` },
    } } })),
    // Empty state
    ...message("'No sampling points match these choices'", 'H / 2', "'Try clearing one of the pickers.'", "!length(data('src'))"),
    fieldMapDiagnostic(),
  ],
});
