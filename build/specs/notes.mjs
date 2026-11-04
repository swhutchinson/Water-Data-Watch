// WHAT THE LAST CHECK RECORDED, in sentences built from the data: the planted defects, the change ledger, the sources and the
// licence statements. Text blocks stack down the panel, and each wraps to the width available.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, panel, wrapData, message, C, FONT_DISPLAY } from '../style.mjs';

const fm = fieldMap([['Planted', 'Planted Text'], ['Prints', 'Fingerprints Text'], ['Ledger', 'Ledger Text'], ['Bathing', 'Bathing Source Text'], ['Licence', 'Licence Text']]);

// True once there is a run to describe
const HAS = "length(data('src')) > 0";
// How many characters fit on a line of 18 px text
const CHARS = '(W - 48 * u) / (9.3 * u)';
// One block: where its lines go, its heading, and the text
const blocks = [
  ['plantedLines', 'Do the rules still work?', 'r0.Planted'],
  ['ledgerLines', 'Has anything changed after publication?', "(r0.Prints || '') + ' ' + (r0.Ledger || '')"],
  ['bathingLines', 'Is any source running on a copy?', 'r0.Bathing'],
  ['licenceLines', 'What do the licence statements say?', 'r0.Licence'],
];
// The y position of each block depends on how many lines the blocks above it took
const blockY = i => '(' + ['58 * u', ...blocks.slice(0, i).map(b => `(30 + 25 * length(data('${b[0]}')) + 16) * u`)].join(' + ') + ')';

export default frame('What the last check recorded, in sentences', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [...fm.signals, ...sizeSignals(620, 576), { name: 'r0', update: "length(data('src')) ? data('src')[0] : {}" }],
  data: [...fm.data, ...blocks.map(b => wrapData(b[0], b[2], CHARS))],
  marks: [
    panel(),
    txt(`${HAS} ? 'What the last check recorded' : ''`, { x: '24 * u', y: '38 * u', size: 24, weight: 700, font: FONT_DISPLAY }),
    ...blocks.flatMap((b, i) => [
      txt(`${HAS} ? ${JSON.stringify(b[1])} : ''`, { x: '24 * u', y: `${blockY(i)} + 22 * u`, size: 17, weight: 700, color: C.muted, font: FONT_DISPLAY, limit: 'W - 40 * u' }),
      txt('datum.text', { from: b[0], x: '24 * u', y: `${blockY(i)} + (48 + datum.line * 25) * u`, size: 18, limit: 'W - 40 * u' }),
    ]),
    ...message("'No check has been recorded yet'", 'H / 2', "'The nightly check publishes one. Try refreshing the data.'", `!(${HAS})`),
    fieldMapDiagnostic(),
  ],
});
