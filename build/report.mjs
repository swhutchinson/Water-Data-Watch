// Writes the Water Data Watch report (PBIR): the theme and its registration, then every page of Deneb and native visuals,
// from the specs in build/specs and the tokens in build/style.mjs. Run only while Power BI Desktop is closed.
// Usage: node build/report.mjs     (REPORT_DIR overrides the output folder, for validating a copy)
import { fileURLToPath } from 'node:url';
import { createReport, colExpr, msrExpr, lit, str, inFilter } from './pbir.mjs';
import { C, FONT_DISPLAY, FONT_BODY } from './style.mjs';
import { masthead } from './specs/masthead.mjs';
import pointmap from './specs/pointmap.mjs';
import pointtiles from './specs/pointtiles.mjs';
import decisions from './specs/decisions.mjs';
import pointcard from './specs/pointcard.mjs';
import board from './specs/board.mjs';
import tonight from './specs/tonight.mjs';
import slope from './specs/slope.mjs';
import switches from './specs/switches.mjs';
import grid from './specs/grid.mjs';
import rulecard from './specs/rulecard.mjs';
import lineage from './specs/lineage.mjs';
import notes from './specs/notes.mjs';

const R = createReport({
  reportDir: process.env.REPORT_DIR || fileURLToPath(new URL('../Water Data Watch.Report', import.meta.url)),
  measureTable: 'Report Measures',
  denebId: 'deneb7E15AEF80B9E4D4F8E12924291ECE89A',
  colors: { bg: C.bg, panel: C.panel, line: C.line, text: C.text },
});
const { col, msr, pid, vid, deneb, textbox, tableEx, dropdown, writePages } = R;
const MT = 'Report Measures';

// ---------- theme ----------
R.registerTheme('WaterDataWatchTheme.json', {
  name: 'Water Data Watch',
  dataColors: [C.blue, C.pass, C.fail, C.review, C.grey, C.blueLight],
  background: C.bg, backgroundLight: C.panel2, backgroundNeutral: C.panel, backgroundDark: '#050A12',
  foreground: C.text, foregroundNeutralSecondary: C.muted, foregroundNeutralTertiary: C.soft,
  tableAccent: C.blue, good: C.pass, bad: C.fail, neutral: C.grey, maximum: C.pass, center: C.review, minimum: C.fail,
  hyperlink: C.blueLight, visitedHyperlink: C.muted,
  textClasses: {
    title: { fontFace: 'Bahnschrift', color: C.text, fontSize: 14 },
    header: { fontFace: 'Bahnschrift', color: C.text, fontSize: 13 },
    label: { fontFace: 'Segoe UI', color: C.muted, fontSize: 12 },
    callout: { fontFace: 'Bahnschrift', color: C.text, fontSize: 32 },
  },
  visualStyles: {
    '*': { '*': {
      background: [{ show: false }], border: [{ show: false }], dropShadow: [{ show: false }], title: [{ show: false }],
      padding: [{ top: 0, bottom: 0, left: 0, right: 0 }],
    } },
    page: { '*': { background: [{ color: { solid: { color: C.bg } }, transparency: 0 }], outspace: [{ color: { solid: { color: C.bg } } }] } },
    // Tables: 13 pt (17 px) text, pale headers, no totals row, and long text wraps
    tableEx: { '*': {
      grid: [{ gridVertical: false, gridHorizontal: true, gridHorizontalColor: { solid: { color: C.line } }, outlineColor: { solid: { color: C.line } }, rowPadding: 6 }],
      columnHeaders: [{ fontColor: { solid: { color: C.muted } }, backColor: { solid: { color: C.panel } }, fontFamily: 'Bahnschrift', fontSize: 12, bold: true, wordWrap: true, autoSizeColumnWidth: false }],
      values: [{ fontColorPrimary: { solid: { color: C.text } }, backColorPrimary: { solid: { color: C.panel } }, fontColorSecondary: { solid: { color: C.text } }, backColorSecondary: { solid: { color: C.panel } }, fontFamily: 'Segoe UI', fontSize: 13, wordWrap: true, urlIcon: true }],
      total: [{ totals: false }],
    } },
    slicer: { '*': {
      items: [{ fontColor: { solid: { color: C.text } }, background: { solid: { color: C.panel2 } }, fontFamily: 'Bahnschrift', textSize: 13 }],
      header: [{ show: false }],
    } },
  },
});

// ---------- shared pieces ----------
// A dropdown picker, 96 px tall with a one-line title, optionally synced with the same picker on other pages.
const picker = (name, pos, tab, table, column, def, titleText, alt, group) => {
  const v = dropdown(name, pos, tab, table, column, titleText, alt, def);
  if (group) v.visual.syncGroup = { groupName: group, fieldChanges: true, filterChanges: true };
  return v;
};
// A column or measure shown under a plainer heading.
const named = (field, displayName) => ({ ...field, displayName });
// Puts the visual's title under the control of a measure, and lets a long one wrap.
const titleFromMeasure = (v, measure) => {
  const t = v.visual.visualContainerObjects.title[0].properties;
  t.show = lit('true');
  t.text = { expr: msrExpr(MT, measure) };
  t.titleWrap = lit('true');
  return v;
};
// Fixes each column's width, by its position in the projections, so long text wraps instead of pushing the table sideways.
const widths = (v, list) => {
  const refs = v.visual.query.queryState.Values.projections.map(p => p.queryRef);
  v.visual.objects = { ...(v.visual.objects || {}), columnWidth: list.map((w, i) => ({ properties: { value: lit(`${w}D`) }, selector: { metadata: refs[i] } })) };
  return v;
};
// The same words on every page: about the data, not the water.
const FOOT = 'About the data, not the water: this isn\'t advice on water safety and doesn\'t judge any river or beach. Independent project, not affiliated with or endorsed by the Environment Agency. Contains Environment Agency information © Environment Agency and/or database right. Roles, thresholds and decisions are illustrative.';
const footer = p => textbox(vid(p, 'footer'), [40, 1000, 1840, 62], 90, [[[FOOT, { size: '11.5pt', color: C.muted }]]], 'Scope, independence, attribution and what is illustrative');
// The header. Measures bound to it are evaluated once, as it has one row.
const header = (p, question, opts) => {
  const fields = ['Freshness Text', ...(opts.measure ? [opts.measure] : []), ...(opts.defaultMeasure ? [opts.defaultMeasure] : [])];
  return deneb(vid(p, 'header'), [40, 14, 1840, 100], 1, masthead(question, opts), fields.map(msr), `Water Data Watch header. ${question} States what is selected and when the data was last checked.`);
};
// A paragraph helper for text boxes: a list of runs, each [text, size in pt, colour, bold].
const para = (...runs) => runs.map(([value, size = '13.5pt', color = C.text, bold = false, url]) => [value, { size, color, bold, font: bold ? FONT_DISPLAY.split(',')[0] : FONT_BODY.split(',')[0], url }]);
const HEAD = t => para([t, '15pt', C.text, true]);
const BODY = t => para([t, '13.5pt', C.text]);
const GAP = para([' ', '6pt', C.text]);
// A dark panel behind a text box, so it matches the charts.
const panelled = v => {
  const o = v.visual.visualContainerObjects;
  o.background = [{ properties: { show: lit('true'), color: { solid: { color: { expr: { Literal: { Value: `'${C.panel}'` } } } } }, transparency: lit('0D') } }];
  o.border = [{ properties: { show: lit('true'), color: { solid: { color: { expr: { Literal: { Value: `'${C.line}'` } } } } }, radius: lit('14D') } }];
  o.padding = [{ properties: { top: lit('14D'), bottom: lit('10D'), left: lit('20D'), right: lit('18D') } }];
  return v;
};

// A button. link holds the action's own properties, such as its type and where it goes.
const button = (name, pos, tab, text, link, alt, fill = C.panel2) => R.container(name, pos, tab, {
  visualType: 'actionButton',
  objects: {
    icon: [{ properties: { show: lit('false') } }],
    text: [{ properties: { show: lit('true') } }, { properties: { text: str(text), fontColor: { solid: { color: str(C.text) } }, fontFamily: str('Bahnschrift'), fontSize: lit('13D'), bold: lit('true') }, selector: { id: 'default' } }],
    fill: [{ properties: { show: lit('true') } }, { properties: { fillColor: { solid: { color: str(fill) } }, transparency: lit('0D') }, selector: { id: 'default' } }],
  },
  visualContainerObjects: {
    ...R.chromeOff,
    border: [{ properties: { show: lit('true'), color: { solid: { color: str(C.soft) } }, radius: lit('10D') } }],
    general: [{ properties: { altText: str(alt) } }],
    visualLink: [{ properties: { show: lit('true'), ...link } }],
  },
});
// Colours one table column's words from a measure holding the colour.
const colourFrom = (v, wordsMeasure, colourMeasure) => {
  v.visual.objects = { ...(v.visual.objects || {}), values: [{ properties: { fontColor: { solid: { color: { expr: msrExpr(MT, colourMeasure) } } } }, selector: { data: [{ dataViewWildcard: { matchingOption: 1 } }], metadata: `${MT}.${wordsMeasure}` } }] };
  return v;
};
// The three pickers that narrow the points, set out by the caller.
const pointPickers = (p, positions, firstTab) => [
  picker(vid(p, 'area'), positions[0], firstTab, 'PointPacks', 'area_name', undefined, 'Area', 'Narrow the sampling points to one or more areas'),
  picker(vid(p, 'type'), positions[1], firstTab + 1, 'PointPacks', 'point_group', undefined, 'Type of point', 'Narrow the sampling points to one or more types'),
  picker(vid(p, 'band'), positions[2], firstTab + 2, 'PointPacks', 'band', undefined, 'Record quality', 'Narrow the sampling points to one or more record quality bands'),
];
// The columns of a list of points, under plain headings.
const POINT_COLS = [named(col('PointQuality', 'point_label'), 'Sampling point'), named(col('PointQuality', 'point_group'), 'Type'), named(col('PointQuality', 'area_name'), 'Area'), named(msr('Point Score'), 'Score'), named(msr('Point Quality'), 'Record quality'), named(msr('Point Flags'), 'Flags')];

// ---------- the map page ----------
const PM = pid('map'), PL = pid('points'), PD = pid('point'), P1 = pid('trust');
const toPoint = { type: str('Drillthrough'), drillthroughSection: str(PD) };
const map = { name: PM, displayName: 'Map', visuals: [
  header(PM, 'How far can the records at each sampling point be trusted?', { measure: 'Showing Points' }),
  deneb(vid(PM, 'map'), [40, 122, 720, 868], 2, pointmap, ['pack_id', 'point_group', 'area_name', 'band', 'located', 'packed'].map(c => col('PointPacks', c)),
    'Map of North West England with a dot for every sampling point. Colour, shape and a word show the quality of its records, not of the water: no flags, a few flags, look closer or no results to check. Points with no real location sit in a labelled box.', { renderMode: 'canvas', crossFilter: true }),
  ...pointPickers(PM, [[776, 122, 358, 96], [1149, 122, 358, 96], [1522, 122, 358, 96]], 3),
  deneb(vid(PM, 'tiles'), [776, 226, 1104, 150], 6, pointtiles, ['Points Shown', 'Points No Flags', 'Points A Few Flags', 'Points Look Closer', 'Points No Results'].map(msr), 'How many sampling points fall in each record quality band, each with a sign and a word.'),
  deneb(vid(PM, 'decisions'), [776, 384, 1104, 186], 7, decisions, ['use_name', 'use_order', 'dataset_id', 'verdict', 'gates_failed', 'gates_unchecked', 'conditions_open'].map(c => col('Verdicts', c)), 'The overall verdict for each decision, with a sign and a word. The pickers do not change these.'),
  button(vid(PM, 'why'), [1668, 392, 200, 42], 8, 'See why', { type: str('PageNavigation'), navigationSection: str(P1) }, 'Go to the page explaining each verdict'),
  widths(colourFrom(tableEx(vid(PM, 'list'), [776, 578, 1104, 352], 9, POINT_COLS, 'Points to look at first, for review', 'The sampling points with flags, lowest score first, with a sign and a word for each band. Choose a row to see that point in full.',
    { sort: [{ field: msrExpr(MT, 'Point Score'), direction: 'Ascending' }], filters: [{ name: vid(PM, 'listfilter'), field: colExpr('PointQuality', 'band'), type: 'Categorical', filter: inFilter('PointQuality', 'band', ['A few flags', 'Look closer']) }] }), 'Point Quality', 'Point Quality Colour'), [430, 170, 170, 76, 150, 64]),
  button(vid(PM, 'open'), [776, 938, 330, 52], 10, 'See this point\'s checks', toPoint, 'Open the page for the sampling point chosen in the list', C.blue),
  textbox(vid(PM, 'openhint'), [1122, 938, 758, 52], 11, [para(['Choose a row in the list, then press the button. Or right-click a row and choose Drill through.', '13pt', C.muted])], 'How to open one sampling point'),
  footer(PM),
] };

// ---------- the list of points ----------
const list = { name: PL, displayName: 'Sampling points', visuals: [
  header(PL, 'What does each sampling point score, and why?', { measure: 'Showing Points' }),
  widths(colourFrom(tableEx(vid(PL, 'list'), [40, 122, 1320, 868], 2, [...POINT_COLS, named(msr('Point Results'), 'Results')], 'Every sampling point', 'Every sampling point with results or listed as open: its type, area, score, record quality band, flags and results. Choose a row to see that point in full.',
    { sort: [{ field: msrExpr(MT, 'Point Score'), direction: 'Ascending' }] }), 'Point Quality', 'Point Quality Colour'), [520, 190, 190, 76, 170, 60, 80]),
  R.searchBox(vid(PL, 'search'), [1376, 122, 504, 150], 3, 'PointQuality', 'point_label', 'Find a point by name or code', 'Type part of a sampling point\'s name or code to find it'),
  ...pointPickers(PL, [[1376, 280, 504, 96], [1376, 384, 504, 96], [1376, 488, 504, 96]], 4),
  button(vid(PL, 'open'), [1376, 592, 504, 64], 7, 'See this point\'s checks', toPoint, 'Open the page for the sampling point chosen in the list', C.blue),
  panelled(textbox(vid(PL, 'score'), [1376, 664, 504, 326], 8, [
    HEAD('How the score works'),
    para(['It is the share of a point\'s records passing the 15 checks that can be tied to one point. Serious checks count more: Critical 3, Major 2, Minor 1.', '12pt']), GAP,
    para(['Below-limit results and clock times aren\'t marked down. The first is normal reporting and the second is an open question. A point\'s page shows both.', '12pt']), GAP,
    para(['It never overrides a must-pass check and feeds no verdict. Closed points with no results are left out. Scores and bands are illustrative.', '12pt', C.text, true]),
  ], 'How the record quality score is worked out, what it leaves out and that it is illustrative')),
  footer(PL),
] };

// ---------- one point, reached by drilling through ----------
const point = { name: PD, displayName: 'Point detail', hidden: true, drillthrough: { table: 'PointQuality', column: 'point_label' }, visuals: [
  header(PD, 'What do the checks say about this sampling point?', { measure: 'Showing Point' }),
  deneb(vid(PD, 'card'), [40, 122, 620, 780], 2, pointcard, [...['point_label', 'point_group', 'area_name', 'point_status', 'location_kind', 'band', 'score', 'results', 'samples', 'newest_date', 'flags', 'map_e', 'map_n'].map(c => col('PointQuality', c)), ...['Checks Ran', 'Checks Flagged', 'Point Explain Text'].map(msr)],
    'One sampling point: its record quality score, band, type, area, results, newest sample, where it is on a small map, and what the score means.'),
  button(vid(PD, 'back'), [40, 914, 240, 76], 3, 'Go back', { type: str('Back') }, 'Go back to the page you came from'),
  button(vid(PD, 'source'), [296, 914, 364, 76], 4, 'Check this point at source', { type: str('WebUrl'), webUrl: { expr: msrExpr(MT, 'Point Source Url') } }, 'Open this sampling point on the publisher\'s website', C.blue),
  widths(colourFrom(titleFromMeasure(tableEx(vid(PD, 'checks'), [676, 122, 1204, 470], 5,
    [named(col('Rules', 'id'), 'Rule'), named(col('Rules', 'title'), 'What it checks'), named(msr('Check Records'), 'Records checked'), named(msr('Check Flagged Records'), 'Flagged'), named(msr('Check Share'), 'Share'), named(msr('Check Outcome'), 'Outcome'), named(msr('Check Counted'), 'In the score?')],
    '', 'Every check that reached this sampling point, what it found and whether it counts towards the score.', { sort: [{ field: msrExpr(MT, 'Check Flagged Records'), direction: 'Descending' }] }), 'Point Checks Title'), 'Check Outcome', 'Check Outcome Colour'), [84, 410, 100, 80, 76, 150, 240]),
  widths(titleFromMeasure(tableEx(vid(PD, 'records'), [676, 604, 1204, 386], 6,
    [named(msr('Exception Rule Here'), 'Rule'), named(col('Exceptions', 'month_label'), 'Sample month'), named(col('Exceptions', 'detail'), 'What was found'), named(col('Exceptions', 'source_url'), 'Check at source')],
    '', 'The flagged records kept for this sampling point, with a link to each one at its source.', { sort: [{ field: colExpr('Exceptions', 'month_label'), direction: 'Descending' }] }), 'Point Records Title'), [90, 150, 730, 170]),
  footer(PD),
] };

// ---------- can I trust it? ----------
const trust = { name: P1, displayName: 'Can I trust it?', visuals: [
  header(P1, 'Can this data be trusted for the decision it is about to feed?', { measure: 'Showing Trust', defaultMeasure: 'Is Default Use', hint: 'an example to start with: change it on the right' }),
  deneb(vid(P1, 'board'), [40, 122, 960, 578], 2, board,
    [...['use_id', 'use_name', 'use_order', 'dataset_id', 'dataset_name', 'dataset_order', 'verdict', 'gates_failed', 'gates_unchecked', 'conditions_open', 'in_scope', 'note'].map(c => col('Verdicts', c)), msr('Selected Use Id'), msr('Headline')],
    'Verdict board: one row per decision and one column per dataset, each cell showing a sign and a word: fit, fit with conditions, not fit or not checked. Nothing is averaged.'),
  picker(vid(P1, 'decision'), [1016, 122, 864, 96], 3, 'Uses', 'use_name', 'Train an AI model', 'Which decision?', 'Choose the decision to see what is holding it back'),
  widths(titleFromMeasure(tableEx(vid(P1, 'reasons'), [1016, 226, 864, 474], 4,
    [named(msr('Reason Part'), 'Role'), named(msr('Reason Sign'), 'Outcome'), named(col('Rules', 'title'), 'Rule'), named(col('Rules', 'owner_role'), 'Who answers (illustrative)'), named(msr('Reason Needed'), 'What is needed')],
    '', 'What is holding the chosen decision back: must-pass checks first, then conditions, with the outcome as a sign and a word, the role who answers for it and what is needed.',
    { sort: [{ field: msrExpr(MT, 'Reason Part'), direction: 'Descending' }, { field: msrExpr(MT, 'Reason Sign'), direction: 'Descending' }] }), 'Selected Verdict Text'), [86, 124, 232, 152, 214]),
  deneb(vid(P1, 'tonight'), [40, 712, 1840, 276], 5, tonight,
    ['Source Rows', 'Arrived Rows', 'Checked Rows', 'Summarised Rows', 'Totals Agree', 'Rules Pass', 'Rules Fail', 'Rules Review', 'Rules Not Checked', 'Rules No Data', 'Rules Total', 'Planted Caught', 'Planted Tested', 'Run Seconds', 'Issues Open', 'Changes Text', 'Ledger Text'].map(msr),
    'The last check, as four instruments: rows in and out at each stage, how many rules passed, failed, need review or could not run, how many planted defects were caught, and what changed since the last check.'),
  footer(P1),
] };

// ---------- same data, different answer ----------
const P2 = pid('same');
const PICK_W = 356, PICK_GAP = 15;
const pickX = i => 40 + i * (PICK_W + PICK_GAP);
const same = { name: P2, displayName: 'Same data, different answer', visuals: [
  header(P2, 'What happens when the same data is worked out two ways?', { measure: 'Showing Same Data', defaultMeasure: 'Is Default Same Data', hint: 'an example: try the pickers' }),
  picker(vid(P2, 'measured'), [pickX(0), 122, PICK_W, 96], 2, 'PickMeasured', 'What was measured', 'Ammonia', 'What was measured', 'Choose what was measured'),
  picker(vid(P2, 'method'), [pickX(1), 122, PICK_W, 96], 3, 'PickMethod', 'Below-limit results', 'Count at half the limit', 'Below-limit results', 'Choose how results below the limit of detection are counted'),
  picker(vid(P2, 'samples'), [pickX(2), 122, PICK_W, 96], 4, 'PickSamples', 'Samples', 'Routine samples only', 'Samples', 'Choose whether pollution and investigation samples are included'),
  picker(vid(P2, 'months'), [pickX(3), 122, PICK_W, 96], 5, 'PickMonths', 'Months', 'Complete months only', 'Months', 'Choose whether months still filling in are included'),
  picker(vid(P2, 'stat'), [pickX(4), 122, PICK_W, 96], 6, 'PickStatistic', 'Statistic', 'Average', 'Average or median', 'Choose an average or a median'),
  deneb(vid(P2, 'slope'), [40, 226, 1180, 680], 7, slope,
    [col('RankedAreas', 'area_name'), ...['Quick Figure', 'Quick Rank', 'Your Figure', 'Your Rank', 'Selected Unit', 'Same Data Headline'].map(msr)],
    'Slope chart: each sub-area ranked the quick way on the left and the chosen way on the right, with figures, showing how the order changes. A rank describes the calculation, not the water.'),
  deneb(vid(P2, 'switches'), [1236, 226, 644, 680], 8, switches,
    [col('SwitchEffects', 'SwitchOrder'), col('SwitchEffects', 'SwitchLabel'), col('SwitchEffects', 'SwitchKind'), col('SwitchEffects', 'Method'), col('SwitchEffects', 'SampleSet'), col('SwitchEffects', 'MonthSet'), col('SwitchEffects', 'StatKey'), ...['Switch Figure', 'Switch Base', 'Selected Unit'].map(msr)],
    'What each change does alone: four changes from the quick way, each labelled a mistake put right or a choice, with the North West figure each gives.'),
  textbox(vid(P2, 'note'), [40, 918, 1840, 72], 9, [
    para(['Dropping below-limit results is a mistake: they are real measurements, just too low to put an exact number on. Leaving out pollution samples is a choice about the question, and it is fine if it is stated.', '13.5pt', C.text]),
    para(['This is about the calculation. It says nothing about whose water is better.', '13.5pt', C.text, true]),
  ], 'The difference between a mistake and a choice, and that this says nothing about whose water is better'),
  footer(P2),
] };

// ---------- page 3: rules and results ----------
const P3 = pid('rules');
const GRID_FIELDS = ['rule_order', 'id', 'title', 'dimension', 'severity', 'status', 'failed', 'eligible', 'failed_pct', 'test_outcome', 'owner_role', 'why', 'months_packed', 'runs_packed'];
const rulePicker = (p, pos, tab) => picker(vid(p, 'rule'), pos, tab, 'Rules', 'rule_label', 'VAL-07 · Results can go straight into a calculation', 'Which rule?', 'Choose a rule to see it in full', 'Rule');
const rules = { name: P3, displayName: 'Rules and results', visuals: [
  header(P3, 'Which rules hold, and since when?', { measure: 'Showing Rules', defaultMeasure: 'Is Default Rule', hint: 'an example: change it on the right' }),
  deneb(vid(P3, 'grid'), [40, 122, 1320, 868], 2, grid,
    [...GRID_FIELDS.map(c => col('RuleGrid', c)), msr('Selected Rule Id'), msr('Tracking Text')],
    'Every rule against every sample month, each cell with a sign, beside the outcome at the last check, whether the rule caught its planted defect, and a strip with one cell per night since tracking began.', { renderMode: 'canvas' }),
  rulePicker(P3, [1376, 122, 504, 96], 3),
  deneb(vid(P3, 'card'), [1376, 226, 504, 764], 4, rulecard,
    [...['title', 'status', 'why', 'severity', 'dimension', 'owner_role', 'steward_role', 'action', 'root_cause'].map(c => col('Rules', c)), ...['Rule Card Text', 'Rule Threshold Text', 'Rule Effect Text', 'Rule Test Text'].map(msr)],
    'The rule picked: what it found, why it matters, what to do, whether it changes the answer, whether the rule still works, and who answers for it.'),
  footer(P3),
] };

// ---------- page 4: exceptions ----------
const P4 = pid('exceptions');
const exceptions = { name: P4, displayName: 'Exceptions', visuals: [
  header(P4, 'Which records broke this rule, and where do I check them?', { measure: 'Showing Exceptions', defaultMeasure: 'Is Default Rule', hint: 'an example: change it below' }),
  rulePicker(P4, [40, 122, 1000, 96], 2),
  picker(vid(P4, 'month'), [1056, 122, 360, 96], 3, 'Exceptions', 'month_label', undefined, 'Sample month', 'Narrow the list to one sample month'),
  widths(titleFromMeasure(tableEx(vid(P4, 'list'), [40, 226, 1840, 764], 4,
    [named(msr('Exception Rule'), 'Rule'), named(col('Exceptions', 'where_label'), 'Where'), named(col('Exceptions', 'month_label'), 'Sample month'), named(col('Exceptions', 'detail'), 'What was found'), named(col('Exceptions', 'source_url'), 'Check at source')],
    '', 'The records that broke the chosen rule, newest first, with a link to each one at its source, and the true total stated in the title.',
    { sort: [{ field: colExpr('Exceptions', 'month_label'), direction: 'Descending' }] }), 'Exceptions Text'), [110, 500, 170, 860, 170]),
  footer(P4),
] };

// ---------- page 5: how it works ----------
const P5 = pid('how');
const how = { name: P5, displayName: 'How it works', visuals: [
  header(P5, 'How does this work, and what should you not read into it?', { fixed: 'the whole system, as it stood at the last check' }),
  deneb(vid(P5, 'lineage'), [40, 122, 1840, 280], 2, lineage,
    ['Source Rows', 'Arrived Rows', 'Checked Rows', 'Summarised Rows', 'Lineage Lost Rows', 'Totals Agree'].map(msr),
    'The route from the source to this report in five stages, with the row count at each, and whether any rows were lost.'),
  panelled(textbox(vid(P5, 'verdicts'), [40, 414, 590, 576], 3, [
    HEAD('How a verdict is reached'), GAP,
    BODY('Each decision lists the rules it depends on. Some must pass, and the rest attach a condition.'), GAP,
    BODY('One failed must-pass check makes the verdict Not fit. Passing the others can\'t outvote it, and nothing is averaged.'), GAP,
    BODY('A must-pass check that couldn\'t run makes the verdict Not checked. That isn\'t a pass and it isn\'t a fail.'), GAP,
    BODY('Issues open by themselves when a rule fails, and close after three passes in a row. A night with no check changes nothing.'), GAP,
    BODY('Automation checks and reports. People decide what to do about anything marked For review.'), GAP,
    para(['Passing every rule doesn\'t make a reading true. It shows the data is complete and consistent against these rules.', '13.5pt', C.text, true]),
  ], 'How a verdict is reached, and what a pass does and does not mean')),
  deneb(vid(P5, 'notes'), [646, 414, 620, 576], 4, notes,
    ['Planted Text', 'Fingerprints Text', 'Ledger Text', 'Bathing Source Text', 'Licence Text'].map(msr),
    'What the last check recorded, in sentences: planted defects, the change ledger, whether a source used a copy, and the licence statements.'),
  widths(tableEx(vid(P5, 'watch'), [1282, 414, 598, 244], 5,
    [named(col('SourceWatch', 'item'), 'What the publisher says'), named(msr('Watch Sign'), 'At the last check')],
    'Source watch: has the publisher changed anything?', 'Source watch: each publisher statement the nightly check reads, and whether it could be read and has changed.'), [360, 200]),
  panelled(textbox(vid(P5, 'about'), [1282, 668, 598, 322], 6, [
    HEAD('What is illustrative'),
    para(['Owner roles, decisions, thresholds and response times are made up to show how this could run. They describe no real organisation\'s policy.', '12pt', C.text]), GAP,
    HEAD('Sources and licence'),
    para(['Contains Environment Agency information © Environment Agency and/or database right. Water Quality Archive and Bathing Water Quality, used under the Open Government Licence v3.0.', '12pt', C.text]), GAP,
    para(['Independent project, not affiliated with or endorsed by the Environment Agency.', '12pt', C.text]), GAP,
    para(['Map outline: Source: Office for National Statistics licensed under the Open Government Licence v.3.0. Contains OS data © Crown copyright and database right.', '12pt', C.text]),
  ], 'What is illustrative, the sources and licence, and independence')),
  button(vid(P5, 'code'), [1520, 932, 344, 46], 7, 'View the code on GitHub', { type: str('WebUrl'), webUrl: str('https://github.com/swhutchinson/Water-Data-Watch') }, 'Open this project\'s code on GitHub'),
  footer(P5),
] };

writePages([map, list, point, trust, same, rules, exceptions, how]);
