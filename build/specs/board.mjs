// THE VERDICT BOARD. The page's answer in a sentence, then one row per decision and one column per dataset, with a sign and
// a word in every cell. There is no average: the overall column is the worst of the datasets a decision depends on.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, panel, chipMarks, wrapData, message, C, FONT_DISPLAY } from '../style.mjs';

// Fields delivered by Power BI, and the numeric ones among them
const fm = fieldMap([['use_id'], ['use_name'], ['use_order'], ['dataset_id'], ['dataset_name'], ['dataset_order'], ['verdict'], ['gates_failed'], ['gates_unchecked'], ['conditions_open'], ['in_scope'], ['note'], ['Picked', 'Selected Use Id'], ['Headline']],
  ['use_order', 'dataset_order', 'gates_failed', 'gates_unchecked', 'conditions_open']);
// Where the grid starts, the width of the row labels and of the overall column, in design px
const TOP = 184, LEFT = 306, OVERALL = 214;

export default frame('Verdict board: every decision against every dataset', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [
    ...fm.signals, ...sizeSignals(960, 578),
    { name: 'r0', update: "length(data('src')) ? data('src')[0] : {}" },
    { name: 'rowH', update: '(H - (' + TOP + ' + 16) * u) / max(1, length(data(\'uses\')))' },
    { name: 'colW', update: '(W - (' + (LEFT + OVERALL + 34) + ') * u) / max(1, length(data(\'sets\')))' },
  ],
  data: [
    ...fm.data,
    // The sentence, wrapped to the panel
    wrapData('headLines', 'r0.Headline', '(W - 48 * u) / (13.4 * u)'),
    // One row per decision
    { name: 'uses', source: 'src', transform: [{ type: 'aggregate', groupby: ['use_id', 'use_name', 'use_order'] }, { type: 'collect', sort: { field: 'use_order' } }, { type: 'window', ops: ['row_number'], as: ['rowNo'] }] },
    // One column per dataset, without the overall column
    { name: 'sets', source: 'src', transform: [{ type: 'filter', expr: "datum.dataset_id !== 'overall'" }, { type: 'aggregate', groupby: ['dataset_id', 'dataset_name', 'dataset_order'] }, { type: 'collect', sort: { field: 'dataset_order' } }, { type: 'window', ops: ['row_number'], as: ['colNo'] }] },
    // Every cell, placed by its row and column
    { name: 'cells', source: 'src', transform: [
      { type: 'lookup', from: 'uses', key: 'use_id', fields: ['use_id'], values: ['rowNo'], as: ['rowNo'] },
      { type: 'lookup', from: 'sets', key: 'dataset_id', fields: ['dataset_id'], values: ['colNo'], as: ['colNo'] },
      { type: 'formula', as: 'isOverall', expr: "datum.dataset_id === 'overall'" },
      { type: 'formula', as: 'cx', expr: `datum.isOverall ? ${LEFT} * u : (${LEFT + OVERALL + 22}) * u + (datum.colNo - 1) * colW` },
      { type: 'formula', as: 'cy', expr: `${TOP} * u + (datum.rowNo - 1) * rowH + 5 * u` },
      { type: 'formula', as: 'cw', expr: `datum.isOverall ? ${OVERALL} * u : colW - 10 * u` },
      { type: 'formula', as: 'ch', expr: 'rowH - 10 * u' },
      // Short words for the narrower dataset columns
      { type: 'formula', as: 'inUse', expr: "!(datum.in_scope === false || datum.in_scope === 'False')" },
      { type: 'formula', as: 'word', expr: "!datum.inUse ? 'Not used' : datum.isOverall ? datum.verdict : datum.verdict === 'Fit with conditions' ? 'Conditions' : datum.verdict" },
      // Hover text. Keys say what they are, because Deneb shows every key
      { type: 'formula', as: 'tip', expr: "datum.inUse ? {'Decision': datum.use_name, 'Dataset': datum.dataset_name, 'Verdict': datum.verdict, 'Must-pass checks failing': datum.gates_failed, 'Must-pass checks not run': datum.gates_unchecked, 'Conditions open': datum.conditions_open, 'How it is worked out': datum.isOverall ? 'The worst across the datasets this decision uses. Nothing is averaged' : 'From the rules that apply to this dataset'} : {'Decision': datum.use_name, 'Dataset': datum.dataset_name, 'Verdict': 'Not used', 'Why': 'This decision does not use this dataset'}" },
    ] },
  ],
  marks: [
    panel(),
    // The page's answer, in a sentence
    txt('datum.text', { from: 'headLines', x: '24 * u', y: '42 * u + datum.line * 37 * u', size: 28, weight: 600, font: FONT_DISPLAY }),
    // Column headings
    txt("'Overall'", { x: `${LEFT + 4} * u`, y: `${TOP - 12} * u`, size: 18, weight: 700, color: C.muted, font: FONT_DISPLAY }),
    txt("join(slice(split(datum.dataset_name, ' '), 0, 2), ' ')", { from: 'sets', x: `(${LEFT + OVERALL + 26}) * u + (datum.colNo - 1) * colW`, y: `${TOP - 32} * u`, size: 16, weight: 700, color: C.muted, limit: 'colW - 8 * u', font: FONT_DISPLAY }),
    txt("join(slice(split(datum.dataset_name, ' '), 2), ' ')", { from: 'sets', x: `(${LEFT + OVERALL + 26}) * u + (datum.colNo - 1) * colW`, y: `${TOP - 12} * u`, size: 16, weight: 700, color: C.muted, limit: 'colW - 8 * u', font: FONT_DISPLAY }),
    // A highlight behind the decision picked
    { type: 'rect', from: { data: 'uses' }, interactive: false, encode: { update: { x: { signal: '10 * u' }, x2: { signal: 'W - 10 * u' }, y: { signal: `${TOP} * u + (datum.rowNo - 1) * rowH` }, height: { signal: 'rowH' }, cornerRadius: { signal: '10 * u' }, fill: { value: C.panel2 }, stroke: { value: C.muted }, strokeWidth: { signal: '1.5 * u' }, opacity: { signal: 'datum.use_id === r0.Picked ? 1 : 0' } } } },
    // Decision names
    txt('datum.use_name', { from: 'uses', x: '24 * u', y: `${TOP} * u + (datum.rowNo - 0.5) * rowH + 1 * u`, size: 21, weight: 600, baseline: 'middle', limit: `${LEFT - 30} * u`, font: FONT_DISPLAY }),
    // The cells
    ...chipMarks('datum.verdict', 'datum.cx', 'datum.cy', 'datum.cw', 'datum.ch', { from: 'cells', word: 'datum.word', tooltip: 'datum.tip', size: 16, signSize: 16, signAt: 15, textAt: 28 }),
    // Empty state
    ...message("'No verdict is available yet'", 'H / 2', "'The nightly check publishes one. Try refreshing the data.'", "!length(data('src'))"),
    fieldMapDiagnostic(),
  ],
});
