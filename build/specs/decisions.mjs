// THE DATA AS A WHOLE, beside the map: the overall verdict for each decision. It doesn't change with the map's pickers, and says so,
// because a point can score 100 while the whole dataset isn't fit for a decision.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, panel, chipMarks, message, C, FONT_DISPLAY } from '../style.mjs';

// Fields delivered by Power BI, and the numeric ones among them
const fm = fieldMap([['use_name'], ['use_order'], ['dataset_id'], ['verdict'], ['gates_failed'], ['gates_unchecked'], ['conditions_open']], ['use_order', 'gates_failed', 'gates_unchecked', 'conditions_open']);

export default frame('The overall verdict for each decision', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [...fm.signals, ...sizeSignals(1104, 186), { name: 'chipW', update: '(W - 48 * u - 3 * 12 * u) / 4' }],
  data: [
    ...fm.data,
    // Only the overall column of the board, in the register's order
    { name: 'uses', source: 'src', transform: [
      { type: 'filter', expr: "datum.dataset_id === 'overall'" },
      { type: 'collect', sort: { field: 'use_order' } },
      { type: 'window', ops: ['row_number'], as: ['n'] },
      { type: 'formula', as: 'x', expr: '24 * u + (datum.n - 1) * (chipW + 12 * u)' },
      { type: 'formula', as: 'tip', expr: "{'Decision': datum.use_name, 'Verdict': datum.verdict, 'Must-pass checks failing': datum.gates_failed, 'Must-pass checks not run': datum.gates_unchecked, 'Conditions open': datum.conditions_open, 'How it is worked out': 'One failed must-pass check makes it Not fit. Nothing is averaged. The pickers do not change this'}" },
    ] },
  ],
  marks: [
    panel(),
    txt("'The data as a whole: is it ready for each decision?'", { x: '24 * u', y: '36 * u', size: 22, weight: 700, font: FONT_DISPLAY, limit: 'W - 270 * u' }),
    txt('datum.use_name', { from: 'uses', x: 'datum.x + 2 * u', y: '68 * u', size: 17, weight: 600, color: C.muted, limit: 'chipW - 4 * u' }),
    ...chipMarks('datum.verdict', 'datum.x', '76 * u', 'chipW', '54 * u', { from: 'uses', word: 'datum.verdict', tooltip: 'datum.tip', size: 19, signSize: 19, signAt: 22, textAt: 40 }),
    txt("'A point can score 100 while the whole isn\\'t fit: checks on the whole list, or for one use, aren\\'t in a point\\'s score.'", { x: '24 * u', y: '162 * u', size: 16, color: C.text, limit: 'W - 48 * u' }),
    ...message("'No verdict is available yet'", 'H / 2', "'Try refreshing the data.'", "!length(data('uses'))"),
    fieldMapDiagnostic(),
  ],
});
