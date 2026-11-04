// THE RULE PICKED, as a card: what it found, why it matters, who answers for it, whether it still works, and whether the
// problem changes the answer. Blocks of text stack down the card, and each wraps to the width available.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, panel, chipMarks, wrapData, message, C, FONT_DISPLAY } from '../style.mjs';

const fm = fieldMap([['title'], ['status'], ['why'], ['severity'], ['dimension'], ['owner_role'], ['steward_role'], ['action'], ['root_cause'], ['Result', 'Rule Card Text'], ['Threshold', 'Rule Threshold Text'], ['Effect', 'Rule Effect Text'], ['Test', 'Rule Test Text']]);

// True when exactly one rule is picked
const ONE = "length(data('src')) === 1";
// How many characters fit on a line of 18 px text
const CHARS = '(W - 48 * u) / (9.6 * u)';
// One block of the card: where its lines go, its heading, and the text
const blocks = [
  ['resultLines', 'What it found', 'r0.Result'], ['whyLines', 'Why it matters', 'r0.why'], ['actionLines', 'What to do', 'r0.action'],
  ['effectLines', 'Does it change the answer?', 'r0.Effect'], ['testLines', 'Does the rule still work?', 'r0.Test'],
  ['ownerLines', 'Who answers for it (illustrative)', "(r0.owner_role || '') + '. Steward: ' + (r0.steward_role || '') + '. ' + (r0.severity || '') + ' severity. ' + (r0.Threshold || '')"],
];
// Where the title ends and the chip's bottom sits
const AFTER_CHIP = "(40 + 30 * length(data('titleLines')) + 34) * u";
// The y position of each block depends on how many lines the blocks above it took
const blockY = i => '(' + [AFTER_CHIP, ...blocks.slice(0, i).map(b => `(34 + 24 * length(data('${b[0]}'))) * u`)].join(' + ') + ')';

export default frame('The rule picked: what it found, why it matters, who answers for it', {
  usermeta: { denebFields: fm.signals[0].value },
  signals: [...fm.signals, ...sizeSignals(504, 764), { name: 'r0', update: "length(data('src')) === 1 ? data('src')[0] : {}" }],
  data: [
    ...fm.data,
    wrapData('titleLines', 'r0.title', '(W - 48 * u) / (11 * u)'),
    ...blocks.map(b => wrapData(b[0], b[2], CHARS)),
  ],
  marks: [
    panel(),
    txt('datum.text', { from: 'titleLines', x: '24 * u', y: '40 * u + datum.line * 30 * u', size: 24, weight: 700, font: FONT_DISPLAY }),
    // Today's outcome, in a chip under the title
    ...chipMarks('r0.status', '24 * u', "(40 + 30 * (length(data('titleLines')) - 1) + 14) * u", '230 * u', '42 * u', { word: 'r0.status', size: 21, signSize: 20, signAt: 24, textAt: 46, show: ONE }),
    // The blocks
    ...blocks.flatMap((b, i) => [
      txt(`${ONE} ? ${JSON.stringify(b[1])} : ''`, { x: '24 * u', y: `${blockY(i)} + 20 * u`, size: 16, weight: 700, color: C.muted, font: FONT_DISPLAY }),
      txt('datum.text', { from: b[0], x: '24 * u', y: `${blockY(i)} + (43 + datum.line * 24) * u`, size: 18, limit: 'W - 28 * u' }),
    ]),
    ...message("'Pick a rule'", 'H / 2', "'Use the picker at the top to see one rule in full.'", `!(${ONE})`),
    fieldMapDiagnostic(),
  ],
});
