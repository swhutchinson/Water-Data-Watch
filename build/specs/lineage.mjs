// HOW THE DATA TRAVELS, with the row count at each stage, so a loss anywhere shows on one line. Each box says what happens
// there, and the last line says who decides what: automation checks and reports, and people decide.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, panel, signMark, message, C, FONT_DISPLAY } from '../style.mjs';

const fm = fieldMap([['Source', 'Source Rows'], ['Arrived', 'Arrived Rows'], ['Checked', 'Checked Rows'], ['Summarised', 'Summarised Rows'], ['Lost', 'Lineage Lost Rows'], ['Agree', 'Totals Agree']], ['Source', 'Arrived', 'Checked', 'Summarised', 'Lost', 'Agree']);

export default frame('The route from the source to this report, with the row count at each stage', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [...fm.signals, ...sizeSignals(1840, 280), { name: 'r0', update: "length(data('src')) ? data('src')[0] : {}" }, { name: 'boxW', update: '(W - 48 * u - 4 * 44 * u) / 5' }],
  data: [
    ...fm.data,
    { name: 'stages', values: [
      { i: 0, head: 'The source', a: 'Environment Agency', b: 'public services', tip: 'What the source says it holds, read from its own count for each month' },
      { i: 1, head: 'Kept as served', a: 'Nothing changed,', b: 'every field as text', tip: 'Every field kept as it arrived, beside a record of what was asked for and what came back' },
      { i: 2, head: 'Read and screened', a: 'Numbers, limits and', b: 'words kept apart', tip: 'The result column is read into numbers, limits and words. Labels are screened for personal details' },
      { i: 3, head: 'Checked and tested', a: 'Every rule, with a', b: 'planted defect for each', tip: 'Every rule runs. Planted defects prove each still works. Effects on figures are measured' },
      { i: 4, head: 'Summarised for this report', a: 'Small public files,', b: 'refreshed each morning', tip: 'Small files on a public branch, guarded against lost history and personal details' },
    ], transform: [
      { type: 'formula', as: 'x', expr: '24 * u + datum.i * (boxW + 44 * u)' },
      { type: 'formula', as: 'n', expr: '[r0.Source, r0.Arrived, r0.Checked, r0.Checked, r0.Summarised][datum.i]' },
      { type: 'formula', as: 'tipRow', expr: "{'Stage': datum.head, 'What happens': datum.tip, 'Rows here': format(datum.n, ',')}" },
    ] },
    { name: 'joins', source: 'stages', transform: [{ type: 'filter', expr: 'datum.i < 4' }] },
  ],
  marks: [
    panel(),
    txt("length(data('src')) ? 'How the data travels' : ''", { x: '24 * u', y: '38 * u', size: 24, weight: 700, font: FONT_DISPLAY }),
    // The boxes
    { type: 'rect', from: { data: 'stages' }, encode: { update: { x: { signal: 'datum.x' }, y: { signal: '56 * u' }, width: { signal: 'boxW' }, height: { signal: '162 * u' }, cornerRadius: { signal: '10 * u' }, fill: { value: C.panel2 }, stroke: { value: C.line }, strokeWidth: { signal: '1 * u' }, tooltip: { signal: 'datum.tipRow' } } } },
    txt('datum.head', { from: 'stages', x: 'datum.x + 16 * u', y: '88 * u', size: 22, weight: 700, font: FONT_DISPLAY, limit: 'boxW - 24 * u' }),
    txt('datum.a', { from: 'stages', x: 'datum.x + 16 * u', y: '116 * u', size: 18, color: C.muted, limit: 'boxW - 24 * u' }),
    txt('datum.b', { from: 'stages', x: 'datum.x + 16 * u', y: '140 * u', size: 18, color: C.muted, limit: 'boxW - 24 * u' }),
    txt("format(datum.n, ',') + ' rows'", { from: 'stages', x: 'datum.x + 16 * u', y: '196 * u', size: 26, weight: 700, font: FONT_DISPLAY, limit: 'boxW - 24 * u' }),
    // The joins between boxes, drawn as lines with a small head
    { type: 'rule', from: { data: 'joins' }, interactive: false, encode: { update: { x: { signal: 'datum.x + boxW + 8 * u' }, x2: { signal: 'datum.x + boxW + 34 * u' }, y: { signal: '137 * u' }, stroke: { value: C.muted }, strokeWidth: { signal: '3 * u' }, strokeCap: { value: 'round' } } } },
    { type: 'symbol', from: { data: 'joins' }, interactive: false, encode: { update: { x: { signal: 'datum.x + boxW + 34 * u' }, y: { signal: '137 * u' }, shape: { value: 'triangle-right' }, size: { signal: '90 * u * u' }, fill: { value: C.muted } } } },
    // The verdict on the line as a whole
    signMark("r0.Agree === 1 ? 'Pass' : 'Fail'", '38 * u', '252 * u', 24, { width: 4 }),
    txt("r0.Agree === 1 ? 'No rows were lost on the way.' : format(abs(r0.Lost), ',') + ' rows differ between the source and this report, so look before relying on the latest figures.'", { x: '60 * u', y: '259 * u', size: 20, weight: 600, colorSignal: `r0.Agree === 1 ? '${C.passText}' : '${C.failText}'`, limit: 'W - 90 * u' }),
    ...message("'No check has been recorded yet'", 'H / 2', "''", "!length(data('src'))"),
    fieldMapDiagnostic(),
  ],
});
