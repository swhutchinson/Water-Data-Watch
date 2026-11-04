// SAME DATA, DIFFERENT ANSWER. One line per sub-area, from where the quick way ranks it to where the chosen method does.
// Lines that move are blue, and lines that stay are grey, so green and red stay reserved for pass and fail.
// The rank describes the calculation. It says nothing about whose water is better, and the chart says so.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, panel, wrapData, message, C, FONT_DISPLAY } from '../style.mjs';

// One row per sub-area, plus scalars repeated on each row
const fm = fieldMap([['area_name'], ['QuickFig', 'Quick Figure'], ['QuickRank', 'Quick Rank'], ['YourFig', 'Your Figure'], ['YourRank', 'Your Rank'], ['Unit', 'Selected Unit'], ['Head', 'Same Data Headline']],
  ['QuickFig', 'QuickRank', 'YourFig', 'YourRank']);

export default frame('Slope chart: the same sub-areas ranked the quick way and the chosen way', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [
    ...fm.signals, ...sizeSignals(1180, 680),
    { name: 'r0', update: "length(data('rows')) ? data('rows')[0] : {}" },
    { name: 'leftX', update: '330 * u' }, { name: 'rightX', update: 'W - 330 * u' },
    { name: 'topY', update: '216 * u' }, { name: 'bottomY', update: 'H - 76 * u' },
    { name: 'hoverArea', value: null, on: [{ events: '@hit:mouseover', update: 'datum.area_name' }, { events: '@hit:mouseout', update: 'null' }] },
  ],
  data: [
    ...fm.data,
    // Only sub-areas with a figure both ways
    { name: 'rows', source: 'src', transform: [{ type: 'filter', expr: 'isValid(datum.QuickRank) && isValid(datum.YourRank)' }, { type: 'formula', as: 'moved', expr: 'datum.QuickRank - datum.YourRank' },
      // Equal ranks share a number but get their own place on the axis, so labels never sit on top of each other
      { type: 'window', sort: { field: ['QuickRank', 'area_name'] }, ops: ['row_number'], as: ['quickPos'] }, { type: 'window', sort: { field: ['YourRank', 'area_name'] }, ops: ['row_number'], as: ['yourPos'] },
      { type: 'joinaggregate', groupby: ['QuickRank'], ops: ['count'], as: ['quickTies'] }, { type: 'joinaggregate', groupby: ['YourRank'], ops: ['count'], as: ['yourTies'] },
      { type: 'formula', as: 'quickLabel', expr: "(datum.quickTies > 1 ? '=' : '') + datum.QuickRank + '. ' + datum.area_name + '  ' + format(datum.QuickFig, '.2f')" },
      { type: 'formula', as: 'yourLabel', expr: "(datum.yourTies > 1 ? '=' : '') + datum.YourRank + '. ' + datum.area_name + '  ' + format(datum.YourFig, '.2f')" }, { type: 'formula', as: 'tip', expr: "{'Sub-area': datum.area_name, 'The quick way': format(datum.QuickFig, '.2f') + ' ' + datum.Unit + ', ranked ' + datum.QuickRank, 'Your way': format(datum.YourFig, '.2f') + ' ' + datum.Unit + ', ranked ' + datum.YourRank, 'Note': 'A rank describes the calculation, not the water'}" }] },
    wrapData('headLines', 'r0.Head', '(W - 48 * u) / (12.6 * u)'),
  ],
  scales: [{ name: 'y', type: 'point', domain: { data: 'rows', field: 'quickPos', sort: true }, range: [{ signal: 'topY' }, { signal: 'bottomY' }], padding: 0.3 }],
  marks: [
    panel(),
    // The finding, in words
    txt('datum.text', { from: 'headLines', x: '24 * u', y: '42 * u + datum.line * 32 * u', size: 25, weight: 600, font: FONT_DISPLAY }),
    // Column headings
    txt("'The quick way'", { x: 'leftX', y: '150 * u', size: 22, weight: 700, align: 'center', font: FONT_DISPLAY }),
    txt("'Drop below-limit results, use everything, average'", { x: 'leftX', y: '176 * u', size: 16, align: 'center', color: C.muted, limit: '420 * u' }),
    txt("'Your way'", { x: 'rightX', y: '150 * u', size: 22, weight: 700, align: 'center', font: FONT_DISPLAY }),
    txt("'As chosen with the pickers above'", { x: 'rightX', y: '176 * u', size: 16, align: 'center', color: C.muted, limit: '420 * u' }),
    // The lines
    { type: 'rule', from: { data: 'rows' }, interactive: false, encode: { update: {
      x: { signal: 'leftX' }, x2: { signal: 'rightX' }, y: { signal: "scale('y', datum.quickPos)" }, y2: { signal: "scale('y', datum.yourPos)" },
      stroke: { signal: `datum.moved !== 0 ? '${C.blue}' : '${C.grey}'` }, strokeWidth: { signal: `(hoverArea === datum.area_name ? 5 : datum.moved !== 0 ? 3.5 : 2) * u` }, opacity: { signal: 'hoverArea && hoverArea !== datum.area_name ? 0.3 : 1' }, strokeCap: { value: 'round' },
    } } },
    // Dots at both ends
    { type: 'symbol', from: { data: 'rows' }, interactive: false, encode: { update: { x: { signal: 'leftX' }, y: { signal: "scale('y', datum.quickPos)" }, size: { signal: '150 * u * u' }, fill: { signal: `datum.moved !== 0 ? '${C.blue}' : '${C.grey}'` }, stroke: { value: C.panel }, strokeWidth: { signal: '2 * u' } } } },
    { type: 'symbol', from: { data: 'rows' }, interactive: false, encode: { update: { x: { signal: 'rightX' }, y: { signal: "scale('y', datum.yourPos)" }, size: { signal: '150 * u * u' }, fill: { signal: `datum.moved !== 0 ? '${C.blue}' : '${C.grey}'` }, stroke: { value: C.panel }, strokeWidth: { signal: '2 * u' } } } },
    // Labels on the left: rank, name, figure
    txt('datum.quickLabel', { from: 'rows', x: 'leftX - 18 * u', y: "scale('y', datum.quickPos) + 1 * u", size: 20, align: 'right', baseline: 'middle', weight: 600, limit: '300 * u' }),
    // Labels on the right: rank, name, figure, with the direction of the move
    txt('datum.yourLabel', { from: 'rows', x: 'rightX + 18 * u', y: "scale('y', datum.yourPos) + 1 * u", size: 20, baseline: 'middle', weight: 600, limit: '300 * u' }),
    // Wide invisible hit areas, so hover works anywhere on a line's row
    { type: 'rule', name: 'hit', from: { data: 'rows' }, encode: { update: { x: { signal: 'leftX' }, x2: { signal: 'rightX' }, y: { signal: "scale('y', datum.quickPos)" }, y2: { signal: "scale('y', datum.yourPos)" }, stroke: { value: 'transparent' }, strokeWidth: { signal: '26 * u' }, tooltip: { signal: 'datum.tip' } } } },
    // The caveat, on the chart itself
    txt("'1 is the highest figure. A rank describes the calculation, and says nothing about whose water is better. Figures in ' + (r0.Unit || '') + '.'", { x: 'W / 2', y: 'H - 26 * u', size: 17, align: 'center', color: C.muted, limit: 'W - 48 * u' }),
    // Empty state
    ...message("'No sub-area has a figure for this combination'", 'H / 2', "'Try a different choice with the pickers above.'", "!length(data('rows'))"),
    fieldMapDiagnostic(),
  ],
});
