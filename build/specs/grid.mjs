// RULES AND RESULTS. Every rule against every sample month, usable from day one because months come from the data, beside
// tonight's outcome and whether the rule caught its planted defect. A second strip adds a cell for each night, labelled with
// the date tracking began. Each rule's history arrives packed in one text field, because Deneb's cost grows with rows.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, panel, message, statusFill, statusText, isGrey, C, FONT_DISPLAY } from '../style.mjs';

const fm = fieldMap([['rule_order'], ['id'], ['title'], ['dimension'], ['severity'], ['status'], ['failed'], ['eligible'], ['failed_pct'], ['test_outcome'], ['owner_role'], ['why'], ['months_packed'], ['runs_packed'], ['Picked', 'Selected Rule Id'], ['Since', 'Tracking Text']],
  ['rule_order', 'failed', 'eligible', 'failed_pct']);
// Column positions, in design px
const X = { title: 74, now: 472, test: 510, months: 556, strip: 1112 };
const CELL = 22;
const TOP = 104;
// The sign inside a cell, by its word, and its colour: dark on a filled cell, pale in a hollow one
const CELL_SIGN = "datum.word === 'Pass' ? 'M-0.75,0.05 L-0.25,0.55 L0.8,-0.6' : datum.word === 'Fail' ? 'M-0.6,-0.6 L0.6,0.6 M0.6,-0.6 L-0.6,0.6' : datum.word === 'For review' ? 'M0,-0.85 L0,0.2 M0,0.66 L0,0.8' : 'M-0.6,0 L0.6,0'";
const CELL_STROKE = `datum.word === 'Pass' ? '${C.text}' : datum.word === 'Fail' || datum.word === 'For review' ? '${C.bg}' : '${C.greyText}'`;

export default frame('Every rule against every sample month, with tonight\'s outcome and the planted defect result', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [
    ...fm.signals, ...sizeSignals(1320, 868),
    { name: 'r0', update: "length(data('rules')) ? data('rules')[0] : {}" },
    { name: 'rowH', update: `(H - (${TOP} + 8) * u) / max(1, length(data('src')))` },
    { name: 'letterWord', value: { P: 'Pass', F: 'Fail', R: 'For review', N: 'Not checked', D: 'No data' } },
  ],
  data: [
    ...fm.data,
    // The key to the cells
    { name: 'key', values: [{ word: 'Pass', x: 14 }, { word: 'For review', x: 92 }, { word: 'Fail', x: 208 }, { word: 'Not checked', x: 280 }] },
    // One row per rule, in register order
    { name: 'rules', source: 'src', transform: [
      { type: 'collect', sort: { field: 'rule_order' } }, { type: 'window', ops: ['row_number'], as: ['rowNo'] },
      { type: 'formula', as: 'y', expr: `${TOP} * u + (datum.rowNo - 1) * rowH` },
      { type: 'formula', as: 'tip', expr: "{'Rule': datum.id + ' · ' + datum.title, 'Why it matters': datum.why, 'At the last check': datum.status, 'Failed records': format(datum.failed, ',') + ' of ' + format(datum.eligible, ','), 'Planted defect': datum.test_outcome, 'Owner (illustrative)': datum.owner_role}" },
    ] },
    // A rule whose dimension differs from the row above starts a new group, which gets a thin line
    { name: 'groups', source: 'rules', transform: [{ type: 'window', ops: ['lag'], fields: ['dimension'], as: ['prev'] }, { type: 'filter', expr: 'datum.rowNo > 1 && datum.prev !== datum.dimension' }] },
    // Unpack the months: month, status letter, failed, checked
    { name: 'cells', source: 'rules', transform: [
      { type: 'filter', expr: 'length(datum.months_packed || \'\') > 0' },
      { type: 'formula', as: 'piece', expr: "split(datum.months_packed, ';')" }, { type: 'flatten', fields: ['piece'] },
      { type: 'formula', as: 'p', expr: "split(datum.piece, ':')" },
      { type: 'formula', as: 'month', expr: 'datum.p[0]' }, { type: 'formula', as: 'word', expr: 'letterWord[datum.p[1]]' },
      { type: 'formula', as: 'tip', expr: "{'Rule': datum.id + ' · ' + datum.title, 'Month': datum.month, 'Outcome': datum.word, 'Failed records': format(toNumber(datum.p[2]), ',') + ' of ' + format(toNumber(datum.p[3]), ',')}" },
    ] },
    // The months, oldest first
    { name: 'monthList', source: 'cells', transform: [{ type: 'aggregate', groupby: ['month'] }, { type: 'collect', sort: { field: 'month' } }, { type: 'window', ops: ['row_number'], as: ['n'] }] },
    { name: 'placed', source: 'cells', transform: [{ type: 'lookup', from: 'monthList', key: 'month', fields: ['month'], values: ['n'], as: ['n'] }, { type: 'formula', as: 'cx', expr: `(${X.months} + (datum.n - 1) * ${CELL}) * u` }] },
    // Unpack the nights: day, status letter, failed
    { name: 'nights', source: 'rules', transform: [
      { type: 'formula', as: 'piece', expr: "split(datum.runs_packed || '', ';')" }, { type: 'flatten', fields: ['piece'] }, { type: 'filter', expr: 'length(datum.piece) > 0' },
      { type: 'formula', as: 'p', expr: "split(datum.piece, ':')" }, { type: 'formula', as: 'day', expr: 'datum.p[0]' }, { type: 'formula', as: 'word', expr: 'letterWord[datum.p[1]]' },
      { type: 'formula', as: 'tip', expr: "{'Rule': datum.id + ' · ' + datum.title, 'Night': datum.day, 'Outcome': datum.word, 'Failed records': format(toNumber(datum.p[2]), ',')}" },
    ] },
    // The latest nights that fit, oldest first
    { name: 'dayList', source: 'nights', transform: [{ type: 'aggregate', groupby: ['day'] }, { type: 'window', sort: { field: 'day', order: 'descending' }, ops: ['row_number'], as: ['back'] }, { type: 'filter', expr: 'datum.back <= 12' }, { type: 'collect', sort: { field: 'day' } }, { type: 'window', ops: ['row_number'], as: ['n'] }] },
    { name: 'nightsPlaced', source: 'nights', transform: [{ type: 'lookup', from: 'dayList', key: 'day', fields: ['day'], values: ['n'], as: ['n'] }, { type: 'filter', expr: 'isValid(datum.n)' }, { type: 'formula', as: 'cx', expr: `(${X.strip} + (datum.n - 1) * 16) * u` }] },
    // Month labels, every fourth month
    { name: 'monthTicks', source: 'monthList', transform: [{ type: 'filter', expr: "(datum.n - 1) % 4 === 0" }] },
  ],
  marks: [
    panel(),
    // A key to the cells
    { type: 'rect', from: { data: 'key' }, interactive: false, encode: { update: { opacity: { signal: "length(data('rules')) ? 1 : 0" }, x: { signal: 'datum.x * u' }, y: { signal: '20 * u' }, width: { signal: '20 * u' }, height: { signal: '18 * u' }, cornerRadius: { signal: '2 * u' }, fill: { signal: statusFill('datum.word') }, fillOpacity: { signal: `${isGrey('datum.word')} ? 0 : datum.word === 'Pass' ? 0.55 : 1` }, stroke: { signal: statusFill('datum.word') }, strokeWidth: { signal: '1 * u' } } } },
    { type: 'symbol', from: { data: 'key' }, interactive: false, encode: { update: { opacity: { signal: "length(data('rules')) ? 1 : 0" }, x: { signal: '(datum.x + 10) * u' }, y: { signal: '29 * u' }, shape: { signal: CELL_SIGN }, size: { signal: 'pow(12 * u / 1.6, 2)' }, stroke: { signal: CELL_STROKE }, strokeWidth: { signal: '2 * u' }, strokeCap: { value: 'round' }, fill: { value: 'transparent' } } } },
    txt("length(data('rules')) ? datum.word : ''", { from: 'key', x: '(datum.x + 26) * u', y: '35 * u', size: 16, color: C.muted }),
    txt("length(data('rules')) ? 'Now: the last check.  Test: caught its own planted defect.' : ''", { x: '14 * u', y: '60 * u', size: 15, color: C.muted, limit: `${X.months - 28} * u` }),
    // Column headings
    txt("length(data('rules')) ? 'Rule' : ''", { x: '14 * u', y: `${TOP - 14} * u`, size: 16, weight: 700, color: C.muted, font: FONT_DISPLAY }),
    txt("length(data('rules')) ? 'Now' : ''", { x: `${X.now} * u`, y: `${TOP - 14} * u`, size: 16, weight: 700, color: C.muted, align: 'center', font: FONT_DISPLAY }),
    txt("length(data('rules')) ? 'Test' : ''", { x: `${X.test} * u`, y: `${TOP - 14} * u`, size: 16, weight: 700, color: C.muted, align: 'center', font: FONT_DISPLAY }),
    txt("length(data('rules')) ? 'By sample month, from the data' : ''", { x: `${X.months} * u`, y: '34 * u', size: 18, weight: 700, font: FONT_DISPLAY }),
    txt("length(data('rules')) ? 'A line means the rule checks a whole list, so it has no months.' : ''", { x: `${X.months} * u`, y: '60 * u', size: 15, color: C.muted, limit: `${X.strip - X.months - 20} * u` }),
    txt("timeFormat(datetime(toNumber(substring(datum.month, 0, 4)), toNumber(substring(datum.month, 5, 7)) - 1, 1), '%b %y')", { from: 'monthTicks', x: `(${X.months} + (datum.n - 1) * ${CELL}) * u`, y: `${TOP - 14} * u`, size: 15, color: C.muted }),
    txt("length(data('rules')) ? 'By night' : ''", { x: `${X.strip} * u`, y: '34 * u', size: 18, weight: 700, font: FONT_DISPLAY }),
    txt("r0.Since || ''", { x: 'W - 14 * u', y: `${TOP - 36} * u`, size: 15, color: C.muted, align: 'right' }),
    // Highlight behind the rule picked
    { type: 'rect', from: { data: 'rules' }, interactive: false, encode: { update: { x: { signal: '6 * u' }, x2: { signal: 'W - 6 * u' }, y: { signal: 'datum.y' }, height: { signal: 'rowH' }, cornerRadius: { signal: '4 * u' }, fill: { value: C.panel2 }, stroke: { value: C.muted }, strokeWidth: { signal: '1.2 * u' }, opacity: { signal: 'datum.id === r0.Picked ? 1 : 0' } } } },
    // Lines between dimensions
    { type: 'rule', from: { data: 'groups' }, interactive: false, encode: { update: { x: { signal: '10 * u' }, x2: { signal: 'W - 10 * u' }, y: { signal: 'datum.y' }, stroke: { value: C.line }, strokeWidth: { signal: '1 * u' } } } },
    // The rule's reference and title, with hover across the whole label
    { type: 'rect', from: { data: 'rules' }, encode: { update: { x: { signal: '6 * u' }, width: { signal: `${X.now - 24} * u` }, y: { signal: 'datum.y' }, height: { signal: 'rowH' }, fill: { value: 'transparent' }, tooltip: { signal: 'datum.tip' } } } },
    txt('datum.id', { from: 'rules', x: '14 * u', y: 'datum.y + rowH / 2 + 1 * u', size: 15, weight: 600, color: C.muted, baseline: 'middle' }),
    txt('datum.title', { from: 'rules', x: `${X.title} * u`, y: 'datum.y + rowH / 2 + 1 * u', size: 15, baseline: 'middle', limit: `${X.now - X.title - 18} * u` }),
    // Tonight's outcome
    { type: 'symbol', from: { data: 'rules' }, encode: { update: { x: { signal: `${X.now} * u` }, y: { signal: 'datum.y + rowH / 2' }, shape: { signal: "datum.status === 'Pass' ? 'M-0.75,0.05 L-0.25,0.55 L0.8,-0.6' : datum.status === 'Fail' ? 'M-0.6,-0.6 L0.6,0.6 M0.6,-0.6 L-0.6,0.6' : datum.status === 'For review' ? 'M0,-0.8 L0,0.2 M0,0.68 L0,0.72' : 'M-0.6,0 L0.6,0'" }, size: { signal: 'pow(16 * u / 1.6, 2)' }, stroke: { signal: statusText('datum.status') }, strokeWidth: { signal: '2.6 * u' }, strokeCap: { value: 'round' }, fill: { value: 'transparent' }, tooltip: { signal: 'datum.tip' } } } },
    // The planted defect result
    { type: 'symbol', from: { data: 'rules' }, encode: { update: { x: { signal: `${X.test} * u` }, y: { signal: 'datum.y + rowH / 2' }, shape: { signal: "datum.test_outcome === 'Caught' || datum.test_outcome === 'Proved by its own test' ? 'M-0.75,0.05 L-0.25,0.55 L0.8,-0.6' : datum.test_outcome === 'Missed' ? 'M-0.6,-0.6 L0.6,0.6 M0.6,-0.6 L-0.6,0.6' : 'M-0.6,0 L0.6,0'" }, size: { signal: 'pow(16 * u / 1.6, 2)' }, stroke: { signal: `datum.test_outcome === 'Caught' || datum.test_outcome === 'Proved by its own test' ? '${C.passText}' : datum.test_outcome === 'Missed' ? '${C.failText}' : '${C.greyText}'` }, strokeWidth: { signal: '2.6 * u' }, strokeCap: { value: 'round' }, fill: { value: 'transparent' }, tooltip: { signal: "{'Rule': datum.id, 'Planted defect': datum.test_outcome}" } } } },
    // A rule about a whole list has no months: a quiet line, with the reason in its tooltip
    { type: 'rule', from: { data: 'rules' }, encode: { update: { x: { signal: `${X.months} * u` }, x2: { signal: `(${X.strip} - 16) * u` }, y: { signal: 'datum.y + rowH / 2' }, stroke: { value: C.line }, strokeWidth: { signal: '2 * u' }, opacity: { signal: "length(datum.months_packed || '') > 0 ? 0 : 1" }, tooltip: { signal: "{'Rule': datum.id + ' · ' + datum.title, 'By month': 'This rule checks the whole list, so it has no months'}" } } } },
    // Month cells: filled by outcome, grey hollow. Fails and reviews also carry a small sign below
    { type: 'rect', from: { data: 'placed' }, encode: { update: { x: { signal: 'datum.cx' }, y: { signal: 'datum.y + 1.5 * u' }, width: { signal: `${CELL - 2} * u` }, height: { signal: 'rowH - 3 * u' }, cornerRadius: { signal: '2 * u' }, fill: { signal: statusFill('datum.word') }, fillOpacity: { signal: `${isGrey('datum.word')} ? 0 : datum.word === 'Pass' ? 0.55 : 1` }, stroke: { signal: statusFill('datum.word') }, strokeWidth: { signal: '1 * u' }, tooltip: { signal: 'datum.tip' } } } },
    { type: 'symbol', from: { data: 'placed' }, interactive: false, encode: { update: { x: { signal: `datum.cx + ${(CELL - 2) / 2} * u` }, y: { signal: 'datum.y + rowH / 2' }, shape: { signal: CELL_SIGN }, size: { signal: 'pow(11 * u / 1.6, 2)' }, stroke: { signal: CELL_STROKE }, strokeWidth: { signal: '1.8 * u' }, strokeCap: { value: 'round' }, fill: { value: 'transparent' } } } },
    // Night cells
    { type: 'rect', from: { data: 'nightsPlaced' }, encode: { update: { x: { signal: 'datum.cx' }, y: { signal: 'datum.y + 1.5 * u' }, width: { signal: '14 * u' }, height: { signal: 'rowH - 3 * u' }, cornerRadius: { signal: '2 * u' }, fill: { signal: statusFill('datum.word') }, fillOpacity: { signal: `${isGrey('datum.word')} ? 0 : datum.word === 'Pass' ? 0.55 : 1` }, stroke: { signal: statusFill('datum.word') }, strokeWidth: { signal: '1 * u' }, tooltip: { signal: 'datum.tip' } } } },
    { type: 'symbol', from: { data: 'nightsPlaced' }, interactive: false, encode: { update: { x: { signal: 'datum.cx + 7 * u' }, y: { signal: 'datum.y + rowH / 2' }, shape: { signal: CELL_SIGN }, size: { signal: 'pow(9 * u / 1.6, 2)' }, stroke: { signal: CELL_STROKE }, strokeWidth: { signal: '1.6 * u' }, strokeCap: { value: 'round' }, fill: { value: 'transparent' } } } },
    // Empty state
    ...message("'No rules have been run yet'", 'H / 2', "'The nightly check publishes the results. Try refreshing the data.'", "!length(data('src'))"),
    fieldMapDiagnostic(),
  ],
});
