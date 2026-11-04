// WHAT EACH SWITCH DOES ALONE. Each row changes one thing from the quick way, and shows where the North West figure lands.
// Dropping below-limit results is a mistake. Leaving out pollution samples is a choice about the question. The two aren't
// presented alike: each row says which it is, and the mistake gets a solid label and the choices an outlined one.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, panel, message, C, FONT_DISPLAY } from '../style.mjs';

const fm = fieldMap([['SwitchOrder'], ['SwitchLabel'], ['SwitchKind'], ['Fig', 'Switch Figure'], ['Base', 'Switch Base'], ['Unit', 'Selected Unit']], ['SwitchOrder', 'Fig', 'Base']);

export default frame('What each switch does alone, from the quick way', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [
    ...fm.signals, ...sizeSignals(644, 680),
    { name: 'r0', update: "length(data('rows')) ? data('rows')[0] : {}" },
    { name: 'plotL', update: '30 * u' }, { name: 'plotR', update: 'W - 110 * u' },
    { name: 'rowH', update: '(H - 196 * u) / max(1, length(data(\'rows\')))' },
  ],
  data: [
    ...fm.data,
    { name: 'rows', source: 'src', transform: [
      { type: 'filter', expr: 'isValid(datum.Fig)' }, { type: 'collect', sort: { field: 'SwitchOrder' } }, { type: 'window', ops: ['row_number'], as: ['n'] },
      // How far this switch moves the figure, as a signed percentage
      { type: 'formula', as: 'pct', expr: 'datum.Base ? 100 * (datum.Fig - datum.Base) / datum.Base : null' },
      { type: 'formula', as: 'isMistake', expr: "datum.SwitchKind === 'Fixes a mistake'" },
      { type: 'formula', as: 'tip', expr: "{'Change': datum.SwitchLabel, 'Which is': datum.SwitchKind, 'The quick way': format(datum.Base, '.2f') + ' ' + datum.Unit, 'With this change': format(datum.Fig, '.2f') + ' ' + datum.Unit, 'Moves it by': (datum.pct >= 0 ? '+' : '') + format(datum.pct, '.0f') + '%'}" },
    ] },
    // The largest value decides the scale
    { name: 'span', source: 'rows', transform: [{ type: 'aggregate', ops: ['max', 'max'], fields: ['Fig', 'Base'], as: ['maxFig', 'maxBase'] }, { type: 'formula', as: 'top', expr: 'max(datum.maxFig, datum.maxBase) * 1.02' }] },
  ],
  scales: [{ name: 'x', type: 'linear', domain: [0, { signal: "length(data('span')) ? data('span')[0].top : 1" }], range: [{ signal: 'plotL' }, { signal: 'plotR' }], zero: true }],
  marks: [
    panel(),
    txt("'What each change does alone'", { x: '24 * u', y: '42 * u', size: 25, weight: 700, font: FONT_DISPLAY }),
    txt("'Each row changes one thing from the quick way.'", { x: '24 * u', y: '72 * u', size: 18, color: C.muted, limit: 'W - 48 * u' }),
    txt("length(data('rows')) ? 'The white line marks the quick way: ' + format(r0.Base, '.2f') + ' ' + r0.Unit : ''", { x: '24 * u', y: '98 * u', size: 18, color: C.muted, limit: 'W - 48 * u' }),
    // The quick way's figure, as one line through every row
    { type: 'rule', interactive: false, encode: { update: { x: { signal: "scale('x', r0.Base)" }, x2: { signal: "scale('x', r0.Base)" }, y: { signal: '116 * u' }, y2: { signal: 'H - 36 * u' }, stroke: { value: C.text }, strokeWidth: { signal: '2 * u' }, strokeDash: { signal: '[6 * u, 5 * u]' }, opacity: { signal: "length(data('rows')) ? 1 : 0" } } } },
    // Which kind of change this is: solid for a mistake put right, outlined for a choice
    { type: 'rect', from: { data: 'rows' }, interactive: false, encode: { update: { x: { signal: '24 * u' }, y: { signal: '130 * u + (datum.n - 1) * rowH' }, width: { signal: '(datum.isMistake ? 148 : 92) * u' }, height: { signal: '28 * u' }, cornerRadius: { signal: '6 * u' }, fill: { signal: `datum.isMistake ? '${C.blue}' : 'transparent'` }, stroke: { value: C.blueLight }, strokeWidth: { signal: '1.5 * u' } } } },
    txt('datum.SwitchKind', { from: 'rows', x: '34 * u', y: '150 * u + (datum.n - 1) * rowH', size: 16, weight: 600, color: C.text }),
    // What changes
    txt('datum.SwitchLabel', { from: 'rows', x: '24 * u', y: '186 * u + (datum.n - 1) * rowH', size: 19, weight: 600, limit: 'W - 48 * u' }),
    // A bar from the quick way's figure to this one, so direction shows by position as well as by sign
    { type: 'rect', from: { data: 'rows' }, encode: { update: { x: { signal: "scale('x', min(datum.Base, datum.Fig))" }, x2: { signal: "scale('x', max(datum.Base, datum.Fig))" }, y: { signal: '200 * u + (datum.n - 1) * rowH' }, height: { signal: '22 * u' }, cornerRadius: { signal: '4 * u' }, fill: { value: C.blue }, tooltip: { signal: 'datum.tip' } } } },
    // Where it lands, with its signed change
    txt("format(datum.Fig, '.2f') + '  (' + (datum.pct >= 0 ? '+' : '−') + format(abs(datum.pct), '.0f') + '%)'", { from: 'rows', x: "scale('x', max(datum.Fig, datum.Base)) + 8 * u", y: '217 * u + (datum.n - 1) * rowH', size: 18, weight: 600, limit: 'W - 20 * u' }),
    // Empty state
    ...message("'No figure for this measurement'", 'H / 2', "'Pick another with the picker above.'", "!length(data('rows'))"),
    fieldMapDiagnostic(),
  ],
});
