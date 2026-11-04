// Shared design system for every Water Data Watch Deneb spec.
// Rules:
// - Colour carries meaning only, and each colour means one thing everywhere:
//     green = pass or fit, red = fail or not fit, amber = for review or fit with conditions, grey = not checked or no data.
//     Blue is for anything that isn't a verdict, such as lines on a chart.
// - Colour is never the only cue: every status also has a sign and, wherever there is room, a word.
//     Grey is drawn hollow with a dash, so it can never be mistaken for a pass.
// - Readable on a laptop at fit-to-page: on the 1920 x 1080 canvas no text is smaller than 15 px, body text is
//   18-22 px, key numbers 48 px or more, and secondary text uses `muted` (about 11:1 contrast on the panels).
// Validated with the dataviz validator on the panel #121B2C (dark), all pairs: pass #1F9E74, fail #D9542C, review #D9A21B,
// grey #9AA3B2 -> CVD worst dE 9.1 (protan), normal worst dE 15.7, all >= 3:1 contrast. Review and grey sit above the
// lightness band on purpose: they are status colours, not a categorical set, and grey is neutral by design.
export const C = {
  bg: '#0A111E', panel: '#121B2C', panel2: '#1A263C', line: '#2B3A55', grid: '#22304A',
  text: '#FFFFFF', muted: '#CAD4E3', soft: '#A8B5C9',
  pass: '#1F9E74', passText: '#4CD8B0', fail: '#D9542C', failText: '#FF8A73', review: '#D9A21B', reviewText: '#F2CE6B', grey: '#9AA3B2', greyText: '#CAD4E3',
  blue: '#3D8FD9', blueLight: '#8FC6F5', warn: '#FFB020',
};
// Signs, drawn as symbol marks because arrow and tick glyphs fall back to a serif font in Vega.
export const SIGN = { tick: 'M-0.75,0.05 L-0.25,0.55 L0.8,-0.6', cross: 'M-0.6,-0.6 L0.6,0.6 M0.6,-0.6 L-0.6,0.6', bang: 'M0,-0.85 L0,0.2 M0,0.66 L0,0.8', dash: 'M-0.6,0 L0.6,0' };
// Which group an outcome or verdict belongs to: good, bad, review or none. All the helpers below read this.
const isGood = e => `(${e} === 'Pass' || ${e} === 'Fit' || ${e} === 'Caught' || ${e} === 'No flags')`;
const isBad = e => `(${e} === 'Fail' || ${e} === 'Not fit' || ${e} === 'Missed' || ${e} === 'Look closer')`;
const isReview = e => `(${e} === 'For review' || ${e} === 'Fit with conditions' || ${e} === 'A few flags')`;
// The sign for an outcome or a verdict, as a Vega expression.
export const signPath = e => `${isGood(e)} ? '${SIGN.tick}' : ${isBad(e)} ? '${SIGN.cross}' : ${isReview(e)} ? '${SIGN.bang}' : '${SIGN.dash}'`;
// The fill colour for an outcome or a verdict.
export const statusFill = e => `${isGood(e)} ? '${C.pass}' : ${isBad(e)} ? '${C.fail}' : ${isReview(e)} ? '${C.review}' : '${C.grey}'`;
// The text colour for an outcome or a verdict.
export const statusText = e => `${isGood(e)} ? '${C.passText}' : ${isBad(e)} ? '${C.failText}' : ${isReview(e)} ? '${C.reviewText}' : '${C.greyText}'`;
// Whether an outcome counts as grey, which is drawn hollow.
export const isGrey = e => `!(${isGood(e)} || ${isBad(e)} || ${isReview(e)})`;
export const FONT_DISPLAY = 'Bahnschrift, Segoe UI, sans-serif';
export const FONT_BODY = 'Segoe UI, sans-serif';

// Every spec fills its Deneb container exactly; Deneb supplies pbiContainerWidth/Height.
export const frame = (description, extra = {}) => ({
  $schema: 'https://vega.github.io/schema/vega/v6.json',
  description,
  width: { signal: 'pbiContainerWidth' },
  height: { signal: 'pbiContainerHeight' },
  padding: 0,
  autosize: { type: 'none' },
  background: C.bg,
  config: { text: { font: FONT_BODY, fill: C.text }, tooltip: { offset: 12 } },
  ...extra,
});

// Design-unit sizing: everything is drawn at a reference size and scaled by u.
export const sizeSignals = (refW, refH) => [
  { name: 'W', update: 'max(pbiContainerWidth, 10)' },
  { name: 'H', update: 'max(pbiContainerHeight, 10)' },
  { name: 'u', update: `max(0.35, min(W / ${refW}, H / ${refH}))` },
];

// fieldMap pattern (deneb-vega skill): spec names -> names Power BI delivers. Every spec reads 'src', never 'dataset'.
export function fieldMap(fields, numeric = []) {
  const map = Object.fromEntries(fields.map(f => [f[0], f[1] ?? f[0]]));
  const checks = Object.keys(map).map(k => `(isDefined(r0[fieldMap['${k}']]) ? '' : '${k}  ')`).join(' + ');
  return {
    signals: [
      { name: 'fieldMap', value: map, description: 'EDIT HERE if a field arrives under a different name: set the right-hand value to the name Power BI delivers (Deneb editor > Data tab).' },
      { name: 'missingFields', update: `length(data('dataset')) ? (${checks.replaceAll('r0', "data('dataset')[0]")}) : ''` },
    ],
    data: [
      { name: 'dataset' },
      { name: 'src', source: 'dataset', transform: Object.keys(map).map(k => ({
        type: 'formula', as: k,
        expr: numeric.includes(k) ? `toNumber(datum[fieldMap['${k}']])` : `datum[fieldMap['${k}']]`,
      })) },
    ],
  };
}

// Red on-canvas diagnostic when a bound field is missing (always the last mark).
export const fieldMapDiagnostic = () => ({
  type: 'text', name: 'fieldMapDiagnostic', interactive: false,
  encode: { update: {
    x: { signal: 'W / 2' }, y: { signal: 'H - 8' }, align: { value: 'center' }, baseline: { value: 'bottom' },
    text: { signal: "missingFields ? 'Deneb field map: not found in data -> ' + missingFields : ''" },
    fill: { value: C.failText }, fontSize: { value: 15 }, font: { value: FONT_BODY },
  } },
});

// Panel background (rounded rect with hairline).
export const panel = (x = '0', y = '0', w = 'W', h = 'H') => ({
  type: 'rect', interactive: false,
  encode: { update: { x: { signal: x }, y: { signal: y }, width: { signal: w }, height: { signal: h }, cornerRadius: { signal: '16 * u' }, fill: { value: C.panel }, stroke: { value: C.line }, strokeWidth: { value: 1 } } },
});

// Text mark helper. All sizes are design pixels (multiplied by u). `t` is a signal expression for the text.
export const txt = (t, { x = '0', y = '0', size = 18, weight = 400, color = C.text, colorSignal, align = 'left', baseline = 'alphabetic', font = FONT_BODY, limit, opacity, from, angle, zindex, name } = {}) => ({
  type: 'text', interactive: false, ...(name ? { name } : {}), ...(from ? { from: { data: from } } : {}), ...(zindex ? { zindex } : {}),
  encode: { update: {
    x: { signal: x }, y: { signal: y }, text: { signal: t }, fontSize: { signal: `${size} * u` }, fontWeight: { value: weight },
    fill: colorSignal ? { signal: colorSignal } : { value: color }, align: { value: align }, baseline: { value: baseline }, font: { value: font },
    ...(limit ? { limit: { signal: limit } } : {}), ...(opacity ? { opacity: { signal: opacity } } : {}), ...(angle !== undefined ? { angle: { value: angle } } : {}),
  } },
});

// Section title: sentence case, Bahnschrift, bold, white.
export const title = (text, x = '24 * u', y = '40 * u', size = 22) =>
  txt(typeof text === 'string' ? JSON.stringify(text) : text.signal, { x, y, size, weight: 700, font: FONT_DISPLAY });

// Subtitle under a section title, muted.
export const subtitle = (text, x = '24 * u', y = '66 * u', size = 16) =>
  txt(typeof text === 'string' ? JSON.stringify(text) : text.signal, { x, y, size, color: C.muted, limit: 'W - 48 * u' });

// Legend swatch + label, right-aligned group drawn from the right edge leftwards. items: [[label, colour], ...]
export const swatchLegend = (items, rightX = 'W - 24 * u', y = '40 * u', visible = 'true') => {
  const marks = [];
  let offset = '0';
  for (let i = items.length - 1; i >= 0; i--) {
    const [label, colour, show = 'true'] = items[i];
    const w = `(${JSON.stringify(label)}.length * 8.6 + 30)`;
    const x = `${rightX} - (${offset}) * u`;
    marks.push({ type: 'rect', interactive: false, encode: { update: { x: { signal: `${x} - ${w} * u` }, y: { signal: `${y} - 13 * u` }, width: { signal: '16 * u' }, height: { signal: '16 * u' }, cornerRadius: { signal: '3 * u' }, fill: { value: colour }, opacity: { signal: `${visible} && ${show} ? 1 : 0` } } } });
    marks.push(txt(JSON.stringify(label), { x: `${x} - ${w} * u + 22 * u`, y, size: 16, color: C.muted, opacity: `${visible} && ${show} ? 1 : 0` }));
    offset = `${offset} + (${show} ? ${w} + 18 : 0)`;
  }
  return marks;
};

// Centred message used for empty and waiting states: a headline and a helpful second line. show is a signal saying when to
// draw it. Vega's group opacity doesn't carry down to the marks inside, so the text itself goes blank when it isn't wanted.
export const message = (signalText, ySignal = 'H / 2', subSignal = "''", show = 'true') => [
  txt(`(${show}) ? ${signalText} : ''`, { x: 'W / 2', y: ySignal, size: 24, weight: 600, align: 'center', baseline: 'middle', font: FONT_DISPLAY, color: C.text, limit: 'W - 48 * u' }),
  txt(`(${show}) ? ${subSignal} : ''`, { x: 'W / 2', y: `${ySignal} + 34 * u`, size: 18, align: 'center', baseline: 'middle', color: C.muted, limit: 'W - 48 * u' }),
];

// Word wrap for long sentences (Vega text does not wrap): takes one line at a time, breaking at the last space inside
// `charsSignal` characters, so a line can't overrun. Vega has no loops, so each line is its own step. Anything past
// `maxLines` stays on the last line, where the text mark's limit shows an ellipsis, so a cut is never silent.
// Returns a data entry named `name` with one row per line: { line, text }. Draw it with a text mark from that data, y = top + datum.line * lineHeight.
export const wrapData = (name, textSignal, charsSignal, maxLines = 10) => {
  // The steps for one line: where it ends, and what is left after it
  const steps = [...Array(maxLines).keys()].flatMap(i => {
    const head = `substring(datum.r${i}, 0, datum.n + 1)`;
    return [
      { type: 'formula', as: `c${i}`, expr: `length(datum.r${i}) <= datum.n ? length(datum.r${i}) : (lastindexof(${head}, ' ') > 0 ? lastindexof(${head}, ' ') : datum.n)` },
      { type: 'formula', as: `r${i + 1}`, expr: `trim(substring(datum.r${i}, datum.c${i}))` },
    ];
  });
  // Every line but the last ends where its step said, and the last line takes whatever is left
  const lines = [...Array(maxLines).keys()].map(i => (i < maxLines - 1 ? `substring(datum.r${i}, 0, datum.c${i})` : `datum.r${i}`));
  return {
    name, values: [{}], transform: [
      { type: 'formula', as: 'r0', expr: `trim('' + (${textSignal} || ''))` },
      { type: 'formula', as: 'n', expr: `max(10, floor(${charsSignal}))` },
      ...steps,
      { type: 'formula', as: 'lines', expr: `[${lines.join(', ')}]` },
      { type: 'flatten', fields: ['lines'], as: ['text'], index: 'line' },
      { type: 'filter', expr: "datum.text !== '' || datum.line === 0" },
    ],
  };
};

// A sign drawn as a stroked symbol. e is the outcome expression; x, y and sz are signals (sz is the sign's width in design px).
export const signMark = (e, x, y, sz, opts = {}) => ({
  type: 'symbol', interactive: !!opts.tooltip, ...(opts.from ? { from: { data: opts.from } } : {}), ...(opts.name ? { name: opts.name } : {}),
  encode: { update: {
    x: { signal: x }, y: { signal: y }, shape: { signal: signPath(e) }, size: { signal: `pow((${sz}) * u / 1.6, 2)` },
    stroke: opts.color ? { value: opts.color } : { signal: statusText(e) }, strokeWidth: { signal: `${opts.width || 3} * u` }, strokeCap: { value: 'round' }, strokeJoin: { value: 'round' }, fill: { value: 'transparent' },
    ...(opts.opacity ? { opacity: { signal: opts.opacity } } : {}), ...(opts.tooltip ? { tooltip: { signal: opts.tooltip } } : {}),
  } },
});

// A status chip: a tinted rounded box with a sign and a word. Grey is hollow and dashed, so it never reads as a pass.
export const chipMarks = (e, x, y, w, h, opts = {}) => {
  const seen = opts.show ? `(${opts.show}) ? 1 : 0` : null;
  return [
    { type: 'rect', ...(opts.from ? { from: { data: opts.from } } : {}), interactive: !!opts.tooltip, encode: { update: {
      x: { signal: x }, y: { signal: y }, width: { signal: w }, height: { signal: h }, cornerRadius: { signal: '9 * u' },
      fill: { signal: statusFill(e) }, fillOpacity: { signal: `${isGrey(e)} ? 0 : 0.22` }, stroke: { signal: statusFill(e) }, strokeWidth: { signal: '1.5 * u' }, strokeDash: { signal: `${isGrey(e)} ? [5 * u, 4 * u] : []` },
      ...(seen ? { opacity: { signal: seen } } : {}), ...(opts.tooltip ? { tooltip: { signal: opts.tooltip } } : {}),
    } } },
    signMark(e, `${x} + (${opts.signAt || 28}) * u`, `${y} + (${h}) / 2`, opts.signSize || 22, { from: opts.from, width: opts.signWidth || 3.5, ...(seen ? { opacity: seen } : {}) }),
    txt(opts.word || e, { from: opts.from, x: `${x} + (${opts.textAt || 56}) * u`, y: `${y} + (${h}) / 2 + 1 * u`, size: opts.size || 22, weight: opts.weight || 600, font: FONT_DISPLAY, baseline: 'middle', colorSignal: statusText(e), limit: `(${w}) - (${opts.textAt || 56} + 8) * u` }),
  ];
};
