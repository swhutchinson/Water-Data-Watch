// Water Data Watch: renders every Deneb spec offline with Vega 6 against real-data fixtures (exported from the model by
// C:/Projects/power-bi-studio/scripts/export_fixtures.ps1 with fixture_queries.json), at the container size used in the report plus smaller sizes,
// to out/<case>.png. Proves the chart logic and empty states only - not live field names or Desktop behaviour.
// Usage: node render.mjs [specNameFilter]
import fs from 'node:fs';
import * as vega from 'vega';
import { spawnSync } from 'node:child_process';

// [spec, fixture, width, height]: the size used in the report first, then smaller sizes and every data state
export const CASES = [
  ['masthead', 'masthead', 1840, 100], ['masthead', 'masthead_changed', 1840, 100], ['masthead', 'masthead', 1100, 100], ['masthead', 'empty', 1840, 100],
  ['board', 'board', 960, 578], ['board', 'board_notchecked', 960, 578], ['board', 'board_allfit', 960, 578], ['board', 'board', 700, 420], ['board', 'empty', 960, 578],
  ['tonight', 'tonight', 1840, 276], ['tonight', 'tonight_first', 1840, 276], ['tonight', 'tonight_bad', 1840, 276], ['tonight', 'tonight', 1280, 200], ['tonight', 'empty', 1840, 276],
  ['slope', 'slope', 1180, 680], ['slope', 'slope', 840, 480], ['slope', 'empty', 1180, 680],
  ['switches', 'switches', 644, 680], ['switches', 'switches', 480, 500], ['switches', 'empty', 644, 680],
  ['grid', 'grid', 1320, 868], ['grid', 'grid_later', 1320, 868], ['grid', 'grid', 960, 620], ['grid', 'empty', 1320, 868],
  ['rulecard', 'rulecard', 504, 764], ['rulecard', 'rulecard_longest', 504, 764], ['rulecard', 'rulecard_widest', 504, 764], ['rulecard', 'rulecard_notchecked', 504, 764], ['rulecard', 'rulecard', 380, 580], ['rulecard', 'empty', 504, 764],
  ['lineage', 'lineage', 1840, 280], ['lineage', 'lineage', 1200, 200], ['lineage', 'empty', 1840, 280],
  ['notes', 'notes', 620, 576], ['notes', 'empty', 620, 576],
  ['pointmap', 'pointmap', 720, 868], ['pointmap', 'pointmap_area', 720, 868], ['pointmap', 'pointmap', 480, 580], ['pointmap', 'empty', 720, 868],
  ['pointtiles', 'pointtiles', 1104, 150], ['pointtiles', 'pointtiles', 800, 110], ['pointtiles', 'empty', 1104, 150],
  ['decisions', 'decisions', 1104, 186], ['decisions', 'decisions', 800, 140], ['decisions', 'empty', 1104, 186],
  ['pointcard', 'pointcard', 620, 780], ['pointcard', 'pointcard_clean', 620, 780], ['pointcard', 'pointcard_grey', 620, 780], ['pointcard', 'pointcard_noplace', 620, 780], ['pointcard', 'empty', 620, 780],
];

const filter = process.argv[2];
// Deneb supplies these two functions; offline they do nothing, so the click handlers still parse
vega.expressionFunction('pbiCrossFilterApply', () => null);
vega.expressionFunction('pbiCrossFilterClear', () => null);
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
fs.mkdirSync('out', { recursive: true });
let failures = 0;
for (const [specName, fixture, w, h, overrides = {}] of CASES) {
  if (filter && !specName.includes(filter)) continue;
  const label = `${specName}__${fixture}__${w}x${h}${Object.keys(overrides).length ? '__' + Object.entries(overrides).map(([k, v]) => k + '-' + v).join('_') : ''}`;
  try {
    const spec = structuredClone((await import(`./specs/${specName}.mjs?t=${Date.now()}`)).default);
    // Deneb injects these two signals; offline we define them
    spec.signals = [{ name: 'pbiContainerWidth', value: w }, { name: 'pbiContainerHeight', value: h }, ...(spec.signals || [])];
    const values = JSON.parse(fs.readFileSync(`fixtures/${fixture}.json`, 'utf8').replace(/^﻿/, ''));
    const ds = spec.data.find(d => d.name === 'dataset');
    ds.values = values;
    const warnings = [];
    const view = new vega.View(vega.parse(spec), { renderer: 'none', logLevel: vega.Warn, logger: { warn: (...a) => warnings.push(a.join(' ')), info() {}, debug() {}, error: (...a) => warnings.push('ERROR ' + a.join(' ')), level() { return this; } } });
    await view.runAsync();
    // Signal overrides (e.g. a timelapse frame) applied after the first run
    for (const [k, v] of Object.entries(overrides)) view.signal(k, v);
    if (Object.keys(overrides).length) await view.runAsync();
    const missing = view.signal('missingFields');
    // resvg crashes on stroked text with opacity 0: drop invisible text first
    const svg = (await view.toSVG()).replace(/<text[^>]*(?<![-\w])opacity="0"[^>]*>[^<]*<\/text>/g, '');
    // resvg in a child process (it can panic on some large clipped paths); headless Edge when it does
    fs.writeFileSync(`out/${label}.svg`, svg);
    const r = spawnSync(process.execPath, ['-e', `const {Resvg}=require('@resvg/resvg-js');const fs=require('fs');fs.writeFileSync(process.argv[2],new Resvg(fs.readFileSync(process.argv[1],'utf8'),{fitTo:{mode:'original'},font:{loadSystemFonts:true,defaultFontFamily:'Segoe UI'}}).render().asPng())`, `out/${label}.svg`, `out/${label}.png`]);
    if (r.status !== 0) spawnSync(EDGE, ['--headless=new', '--disable-gpu', '--hide-scrollbars', `--window-size=${w},${h}`, `--screenshot=${process.cwd()}/out/${label}.png`, `file:///${process.cwd().split(String.fromCharCode(92)).join('/')}/out/${label}.svg`]);
    fs.rmSync(`out/${label}.svg`);
    const note = [missing ? `MISSING FIELDS: ${missing}` : '', ...warnings.slice(0, 3)].filter(Boolean).join(' | ');
    console.log(`${note ? 'WARN' : 'ok  '} ${label}${note ? '  ' + note : ''}`);
    view.finalize(); // stops timers (ticker, live clock) so node can exit
    if (missing) failures++;
  } catch (e) {
    failures++;
    console.log(`FAIL ${label}  ${e.message}`);
  }
}
process.exitCode = failures ? 1 : 0;
