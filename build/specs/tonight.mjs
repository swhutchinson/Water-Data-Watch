// THE LAST CHECK, as four instruments: rows in and out, the rules' outcomes, the planted defects, and what changed.
// It answers "did the system itself work?" before anyone reads what it found.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, panel, signMark, wrapData, message, statusFill, statusText, isGrey, C, FONT_DISPLAY } from '../style.mjs';

// One row of measures
const fm = fieldMap([['Source', 'Source Rows'], ['Arrived', 'Arrived Rows'], ['Checked', 'Checked Rows'], ['Summarised', 'Summarised Rows'], ['Agree', 'Totals Agree'], ['Pass', 'Rules Pass'], ['Fail', 'Rules Fail'], ['Review', 'Rules Review'], ['NotChecked', 'Rules Not Checked'], ['NoData', 'Rules No Data'], ['Total', 'Rules Total'], ['Caught', 'Planted Caught'], ['Tested', 'Planted Tested'], ['Seconds', 'Run Seconds'], ['Issues', 'Issues Open'], ['ChangesText', 'Changes Text'], ['LedgerText', 'Ledger Text']],
  ['Source', 'Arrived', 'Checked', 'Summarised', 'Agree', 'Pass', 'Fail', 'Review', 'NotChecked', 'NoData', 'Total', 'Caught', 'Tested', 'Seconds', 'Issues']);

// Column positions, in design px
const X = { rows: 24, rules: 470, planted: 1000, changes: 1370 };
// True once there is a run to describe
const HAS = "length(data('src')) > 0";

export default frame('The last check: rows in and out, rule outcomes, planted defects and what changed', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [...fm.signals, ...sizeSignals(1840, 276), { name: 'r0', update: "length(data('src')) ? data('src')[0] : {}" }],
  data: [
    ...fm.data,
    // The five outcomes, as a bar and a set of labels
    { name: 'outcomes', values: [{ s: 'Pass', i: 0 }, { s: 'Fail', i: 1 }, { s: 'For review', i: 2 }, { s: 'Not checked', i: 3 }, { s: 'No data', i: 4 }], transform: [
      { type: 'formula', as: 'n', expr: '[r0.Pass, r0.Fail, r0.Review, r0.NotChecked, r0.NoData][datum.i] || 0' },
      { type: 'stack', field: 'n', sort: { field: 'i' }, as: ['b0', 'b1'] },
      { type: 'formula', as: 'tip', expr: "{'Outcome': datum.s, 'Rules': datum.n, 'All rules': r0.Total}" },
    ] },
    // What changed, wrapped
    wrapData('changeLines', 'r0.ChangesText', '(446 * u) / (9.4 * u)'),
    wrapData('ledgerLines', 'r0.LedgerText', '(446 * u) / (8.9 * u)'),
  ],
  marks: [
    panel(),
    // ROWS: one big number when the stages agree, and every stage when they don't
    txt(`${HAS} ? 'Rows in, rows out' : ''`, { x: `${X.rows} * u`, y: '38 * u', size: 22, weight: 700, font: FONT_DISPLAY }),
    { type: 'rect', encode: { update: { x: { signal: `${X.rows} * u` }, y: { signal: '52 * u' }, width: { signal: '420 * u' }, height: { signal: '200 * u' }, fill: { value: 'transparent' }, tooltip: { signal: `${HAS} ? {'The source says it holds': format(r0.Source, ','), 'Arrived': format(r0.Arrived, ','), 'Checked by the rules': format(r0.Checked, ','), 'Summarised for this report': format(r0.Summarised, ',')} : null` } } } },
    txt("r0.Agree === 1 ? format(r0.Source, ',') : ''", { x: `${X.rows} * u`, y: '108 * u', size: 54, weight: 700, font: FONT_DISPLAY }),
    txt("r0.Agree === 1 ? 'the same number at all four stages:' : ''", { x: `${X.rows} * u`, y: '142 * u', size: 20 }),
    txt("r0.Agree === 1 ? 'what the source says it holds, what arrived,' : ''", { x: `${X.rows} * u`, y: '170 * u', size: 18, color: C.muted, limit: '420 * u' }),
    txt("r0.Agree === 1 ? 'what was checked and what was summarised.' : ''", { x: `${X.rows} * u`, y: '194 * u', size: 18, color: C.muted, limit: '420 * u' }),
    // When they differ
    txt("r0.Agree === 0 ? 'The source says ' + format(r0.Source, ',') : ''", { x: `${X.rows} * u`, y: '76 * u', size: 20, weight: 600 }),
    txt("r0.Agree === 0 ? 'Arrived ' + format(r0.Arrived, ',') : ''", { x: `${X.rows} * u`, y: '104 * u', size: 20, weight: 600 }),
    txt("r0.Agree === 0 ? 'Checked ' + format(r0.Checked, ',') : ''", { x: `${X.rows} * u`, y: '132 * u', size: 20, weight: 600 }),
    txt("r0.Agree === 0 ? 'Summarised ' + format(r0.Summarised, ',') : ''", { x: `${X.rows} * u`, y: '160 * u', size: 20, weight: 600 }),
    txt("r0.Agree === 0 ? 'The counts differ, so look before using the latest figures.' : ''", { x: `${X.rows + 28} * u`, y: '194 * u', size: 18, color: C.failText, limit: '394 * u' }),
    signMark("r0.Agree === 1 ? 'Pass' : 'Fail'", `${X.rows + 10} * u`, '188 * u', 22, { width: 4, opacity: 'r0.Agree === 0 ? 1 : 0' }),
    // A sign for the agreeing case, beside the number
    signMark("'Pass'", `${X.rows + 262} * u`, '88 * u', 30, { width: 5, opacity: 'r0.Agree === 1 ? 1 : 0' }),
    txt(`${HAS} ? 'The check took ' + format(r0.Seconds / 60, '.0f') + ' minutes  ·  ' + r0.Issues + ' issues open' : ''`, { x: `${X.rows} * u`, y: '240 * u', size: 18, color: C.muted, limit: '420 * u' }),
    // RULES
    txt(`${HAS} ? 'What ' + r0.Total + ' rules found' : ''`, { x: `${X.rules} * u`, y: '38 * u', size: 22, weight: 700, font: FONT_DISPLAY }),
    { type: 'rect', from: { data: 'outcomes' }, encode: { update: {
      x: { signal: `${X.rules} * u + 490 * u * datum.b0 / max(1, r0.Total)` }, width: { signal: 'max(0, 490 * u * datum.n / max(1, r0.Total) - 2 * u)' }, y: { signal: '56 * u' }, height: { signal: '34 * u' }, cornerRadius: { signal: '4 * u' },
      fill: { signal: statusFill('datum.s') }, fillOpacity: { signal: `${isGrey('datum.s')} ? 0 : 1` }, stroke: { signal: statusFill('datum.s') }, strokeWidth: { signal: 'datum.n > 0 ? 1.5 * u : 0' }, strokeDash: { signal: `${isGrey('datum.s')} ? [4 * u, 3 * u] : []` }, tooltip: { signal: 'datum.tip' },
    } } },
    // Labels under the bar: sign, count and word, in two rows
    signMark('datum.s', `(${X.rules} + 12 + (datum.i % 3) * 166) * u`, '(datum.i < 3 ? 122 : 170) * u', 19, { from: 'outcomes', width: 3.4, opacity: `${HAS} ? 1 : 0` }),
    txt(`${HAS} ? datum.n : ''`, { from: 'outcomes', x: `(${X.rules} + 30 + (datum.i % 3) * 166) * u`, y: '(datum.i < 3 ? 133 : 181) * u', size: 32, weight: 700, font: FONT_DISPLAY, colorSignal: statusText('datum.s') }),
    txt(`${HAS} ? datum.s : ''`, { from: 'outcomes', x: `(${X.rules} + 30 + (datum.i % 3) * 166 + (datum.n > 9 ? 42 : 24)) * u`, y: '(datum.i < 3 ? 132 : 180) * u', size: 18, color: C.text, limit: '110 * u' }),
    txt(`${HAS} ? 'Grey means nobody knows yet. It never counts as a pass.' : ''`, { x: `${X.rules} * u`, y: '240 * u', size: 18, color: C.muted, limit: '510 * u' }),
    // PLANTED DEFECTS
    txt(`${HAS} ? 'Do the rules still work?' : ''`, { x: `${X.planted} * u`, y: '38 * u', size: 22, weight: 700, font: FONT_DISPLAY }),
    txt(`${HAS} ? r0.Caught + ' of ' + r0.Tested : ''`, { x: `${X.planted} * u`, y: '108 * u', size: 54, weight: 700, font: FONT_DISPLAY }),
    signMark("r0.Tested > 0 && r0.Caught === r0.Tested ? 'Pass' : 'Fail'", `${X.planted + 248} * u`, '88 * u', 30, { width: 5, opacity: `${HAS} ? 1 : 0` }),
    txt(`${HAS} ? 'planted defects caught.' : ''`, { x: `${X.planted} * u`, y: '142 * u', size: 20 }),
    txt(`${HAS} ? 'Each rule\\'s own defect goes into a' : ''`, { x: `${X.planted} * u`, y: '170 * u', size: 18, color: C.muted, limit: '340 * u' }),
    txt(`${HAS} ? 'private copy, which is then thrown' : ''`, { x: `${X.planted} * u`, y: '194 * u', size: 18, color: C.muted, limit: '340 * u' }),
    txt(`${HAS} ? 'away. The source is never changed.' : ''`, { x: `${X.planted} * u`, y: '218 * u', size: 18, color: C.muted, limit: '340 * u' }),
    // WHAT CHANGED
    txt(`${HAS} ? 'What changed since the last check' : ''`, { x: `${X.changes} * u`, y: '38 * u', size: 22, weight: 700, font: FONT_DISPLAY, limit: '446 * u' }),
    txt('datum.text', { from: 'changeLines', x: `${X.changes} * u`, y: '74 * u + datum.line * 26 * u', size: 19, limit: '446 * u' }),
    txt('datum.text', { from: 'ledgerLines', x: `${X.changes} * u`, y: "(74 + 26 * length(data('changeLines')) + 10) * u + datum.line * 24 * u", size: 18, color: C.muted, limit: '446 * u' }),
    // Empty state
    ...message("'No check has been recorded yet'", 'H / 2', "'The nightly check publishes one. Try refreshing the data.'", `!(${HAS})`),
    fieldMapDiagnostic(),
  ],
});
