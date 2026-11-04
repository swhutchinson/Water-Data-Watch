// HEADER on every page. Left: a water drop with a tick, the report's name, the question this page answers and, in large
// type, what is selected, with a reminder when it is only the starting example. Right: when the data was last checked.
import { frame, sizeSignals, fieldMap, fieldMapDiagnostic, txt, signMark, C, FONT_DISPLAY } from '../style.mjs';

// opts.measure: the measure saying what's selected. opts.defaultMeasure: 1 while the page shows its starting example.
// opts.fixed: a fixed "Showing" line for pages with no pickers.
export const masthead = (question, opts = {}) => {
  const fields = [['Fresh', 'Freshness Text'], ...(opts.measure ? [['Showing', opts.measure]] : []), ...(opts.defaultMeasure ? [['IsDefault', opts.defaultMeasure]] : [])];
  const fm = fieldMap(fields, opts.defaultMeasure ? ['IsDefault'] : []);
  return frame('Water Data Watch: header', {
    usermeta: { denebFields: fm.signals[0].value },
    signals: [...fm.signals, ...sizeSignals(1840, 100), { name: 'r0', update: "length(data('src')) ? data('src')[0] : {}" }],
    data: fm.data,
    marks: [
      // The water drop
      { type: 'path', interactive: false, encode: { update: { x: { signal: '24 * u' }, y: { signal: '27 * u' }, path: { value: 'M0,-23 C9,-10 17,-2 17,8 C17,18 9,24 0,24 C-9,24 -17,18 -17,8 C-17,-2 -9,-10 0,-23 Z' }, scaleX: { signal: 'u' }, scaleY: { signal: 'u' }, fill: { value: C.blue } } } },
      // The tick inside the drop
      signMark("'Pass'", '24 * u', '34 * u', 18, { color: C.text, width: 3 }),
      txt("'Water Data Watch'", { x: '58 * u', y: '38 * u', size: 34, weight: 700, font: FONT_DISPLAY }),
      txt(JSON.stringify(question), { x: '368 * u', y: '37 * u', size: 20, color: C.muted, limit: 'W - 1030 * u' }),
      // What is selected, in large type, with the starting-example reminder after it
      txt(opts.fixed ? JSON.stringify('Showing: ' + opts.fixed) : "r0.Showing ? 'Showing: ' + r0.Showing : ''", { x: '0', y: '84 * u', size: 27, weight: 700, font: FONT_DISPLAY, limit: 'W', name: 'showing' }),
      txt(opts.fixed || !opts.defaultMeasure ? "''" : `r0.IsDefault === 1 && length(r0.Showing || '') < 92 ? ${JSON.stringify(opts.hint || 'an example to start with: change it below')} : ''`,
        { x: "(length('Showing: ' + (r0.Showing || '')) * 12 + 24) * u", y: '83 * u', size: 19, color: C.muted, limit: 'W - 900 * u' }),
      // Freshness, top right
      txt("r0.Fresh || ''", { x: 'W', y: '34 * u', size: 18, align: 'right', color: C.muted, limit: '660 * u' }),
      fieldMapDiagnostic(),
    ],
  });
};
export default masthead('Can this data be trusted for the decision it is about to feed?', { measure: 'Showing Trust', defaultMeasure: 'Is Default Use' });
