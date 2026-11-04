// PBIR writer helpers for generated Power BI reports. Its output has passed the Microsoft PBIR schemas and rendered
// in Desktop: Deneb visuals, tables, dropdown slicers with defaults, the Input slicer (search box), textboxes,
// visual-level filters, sorting, drill-through page binding, page background/outspace, theme registration.
// Run generators only while Power BI Desktop is CLOSED. Ids are sha1 hashes of stable keys, so re-running updates in place.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const VC = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json';
const PG = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json';

// ---------- primitives ----------
export const id = key => crypto.createHash('sha1').update(key).digest('hex').slice(0, 20);
export const lit = v => ({ expr: { Literal: { Value: v } } });
// Text literal: PBIR wants 'text' with any apostrophe doubled
export const str = s => lit("'" + String(s).replace(/'/g, "''") + "'");
export const write = (p, obj) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, JSON.stringify(obj, null, 2)); };
export const colExpr = (t, c) => ({ Column: { Expression: { SourceRef: { Entity: t } }, Property: c } });
export const msrExpr = (t, m) => ({ Measure: { Expression: { SourceRef: { Entity: t } }, Property: m } });

// Categorical "In" filter (visual filter or slicer default); not = true gives "is not"
export const inFilter = (table, column, values, not = false) => {
  const cond = { In: { Expressions: [{ Column: { Expression: { SourceRef: { Source: 'f' } }, Property: column } }], Values: values.map(v => [{ Literal: { Value: "'" + String(v).replace(/'/g, "''") + "'" } }]) } };
  return { Version: 2, From: [{ Name: 'f', Entity: table, Type: 0 }], Where: [{ Condition: not ? { Not: { Expression: cond } } : cond }] };
};

// The colour tokens panelChrome uses
const DEFAULT_COLORS = { bg: '#06101F', panel: '#0B1A30', line: '#1C3150', text: '#E6EEF8' };

export function createReport({ reportDir, measureTable, denebId, colors = {}, displayFont = 'Bahnschrift' }) {
  const C = { ...DEFAULT_COLORS, ...colors };
  const DEF = `${reportDir}/definition`;
  const col = (t, c) => ({ field: colExpr(t, c), queryRef: `${t}.${c}`, nativeQueryRef: c });
  // msr takes ONE argument so ['A', 'B'].map(msr) works (map passes the index as a second argument); msrIn for other tables
  const msrIn = (t, m) => ({ field: msrExpr(t, m), queryRef: `${t}.${m}`, nativeQueryRef: m });
  const msr = m => msrIn(measureTable, m);

  // Container chrome off (full-bleed Deneb, textboxes)
  const chromeOff = {
    background: [{ properties: { show: lit('false') } }], border: [{ properties: { show: lit('false') } }],
    dropShadow: [{ properties: { show: lit('false') } }], title: [{ properties: { show: lit('false') } }],
    padding: [{ properties: { top: lit('0D'), bottom: lit('0D'), left: lit('0D'), right: lit('0D') } }],
  };
  // Native visuals in a rounded panel that matches Deneb panels, with a title and alt text
  const panelChrome = (titleText, alt) => ({
    background: [{ properties: { show: lit('true'), color: { solid: { color: str(C.panel) } }, transparency: lit('0D') } }],
    border: [{ properties: { show: lit('true'), color: { solid: { color: str(C.line) } }, radius: lit('14D') } }],
    dropShadow: [{ properties: { show: lit('false') } }],
    title: [{ properties: { show: lit(titleText ? 'true' : 'false'), text: str(titleText || ''), fontColor: { solid: { color: str(C.text) } }, fontFamily: str(displayFont), fontSize: lit('14D'), bold: lit('true') } }],
    padding: [{ properties: { top: lit('8D'), bottom: lit('8D'), left: lit('12D'), right: lit('12D') } }],
    general: [{ properties: { altText: str(alt) } }],
  });
  // pos = [x, y, width, height]; tab = z-order and tab order; top = container-level extras (e.g. filterConfig)
  const container = (name, [x, y, width, height], tab, visual, top = {}) => ({ $schema: VC, name, position: { x, y, z: tab, width, height, tabOrder: tab }, visual, ...top });

  // Deneb visual: spec is a Vega spec object; projections = list of col()/msr()
  // opts.renderMode 'canvas' draws thousands of marks much faster than the default SVG
  const deneb = (name, pos, tab, spec, projections, alt, opts = {}) => container(name, pos, tab, {
    visualType: denebId,
    query: { queryState: { dataset: { projections } } },
    objects: { vega: [{ properties: { provider: str('vega'), jsonSpec: str(JSON.stringify(spec)), jsonConfig: str('{}'), isNewDialogOpen: lit('false'), enableTooltips: lit('true'), enableContextMenu: lit('true'), ...(opts.renderMode ? { renderMode: str(opts.renderMode) } : {}), ...(opts.crossFilter ? { enableSelection: lit('true'), selectionMode: str('advanced') } : {}) } }] },
    visualContainerObjects: { ...chromeOff, general: [{ properties: { altText: str(alt) } }] },
    drillFilterOtherVisuals: true,
  });

  // Textbox: paragraphs = [[ [text, {font, size, color, bold}], ... ], ...]
  const textbox = (name, pos, tab, paragraphs, alt, defaultColor = C.text) => container(name, pos, tab, {
    visualType: 'textbox',
    objects: { general: [{ properties: { paragraphs: paragraphs.map(runs => ({ textRuns: runs.map(([value, s = {}]) => ({ value, ...(s.url ? { url: s.url } : {}), textStyle: { fontFamily: s.font || 'Segoe UI', fontSize: s.size || '10pt', color: s.color || defaultColor, ...(s.bold ? { fontWeight: 'bold' } : {}) } })) })) } }] },
    visualContainerObjects: { ...chromeOff, general: [{ properties: { altText: str(alt) } }] },
  });

  // Table: extra.sort = [{field: colExpr()/msrExpr(), direction}], extra.filters = [{name, field, type: 'Categorical', filter: inFilter(...)}]
  const tableEx = (name, pos, tab, projections, titleText, alt, extra = {}) => container(name, pos, tab, {
    visualType: 'tableEx',
    query: { queryState: { Values: { projections } }, ...(extra.sort ? { sortDefinition: { sort: extra.sort, isDefaultSort: false } } : {}) },
    // No totals row, set here as well as in the theme, so it holds before the theme is switched on
    objects: { total: [{ properties: { totals: lit('false') } }] },
    visualContainerObjects: panelChrome(titleText, alt),
    drillFilterOtherVisuals: true,
  }, extra.filters ? { filterConfig: { filters: extra.filters } } : {});

  // Dropdown slicer; defaultValue (optional) is saved as the starting selection, single-select
  const dropdown = (name, pos, tab, table, column, titleText, alt, defaultValue) => container(name, pos, tab, {
    visualType: 'slicer',
    query: { queryState: { Values: { projections: [col(table, column)] } }, ...(defaultValue !== undefined ? { sortDefinition: { sort: [{ field: colExpr(table, column), direction: 'Ascending' }], isDefaultSort: false } } : {}) },
    objects: {
      data: [{ properties: { mode: str('Dropdown') } }],
      ...(defaultValue !== undefined ? {
        selection: [{ properties: { singleSelect: lit('true') } }],
        general: [{ properties: { filter: { filter: inFilter(table, column, [defaultValue]) } } }],
      } : {}),
    },
    visualContainerObjects: panelChrome(titleText, alt),
  });

  // Input slicer (search box). Match type / placeholder are set in the theme: visualStyles.textSlicer['*']['*']
  const searchBox = (name, pos, tab, table, column, titleText, alt) => container(name, pos, tab, {
    visualType: 'textSlicer',
    query: { queryState: { Values: { projections: [col(table, column)] } } },
    visualContainerObjects: panelChrome(titleText, alt),
  });

  // Theme file + registration in report.json (activate once in Desktop: View > Themes > Browse for themes)
  const registerTheme = (fileName, theme) => {
    write(`${reportDir}/StaticResources/RegisteredResources/${fileName}`, theme);
    const reportJson = JSON.parse(fs.readFileSync(`${DEF}/report.json`, 'utf8'));
    reportJson.themeCollection.customTheme = { name: fileName, reportVersionAtImport: reportJson.themeCollection.baseTheme.reportVersionAtImport, type: 'RegisteredResources' };
    reportJson.resourcePackages = (reportJson.resourcePackages || []).filter(p => p.name !== 'RegisteredResources');
    reportJson.resourcePackages.push({ name: 'RegisteredResources', type: 'RegisteredResources', items: [{ name: fileName, path: fileName, type: 'CustomTheme' }] });
    reportJson.objects = reportJson.objects || {};
    reportJson.objects.outspacePane = [{ properties: { expanded: lit('false') } }];
    write(`${DEF}/report.json`, reportJson);
  };

  // pages = [{name, displayName, visuals, drillthrough?: {table, column}}]. Removes page folders it does not own
  // (e.g. Desktop's blank "Page 1"), rewrites each page's visuals folder, and sets page order.
  const writePages = (pages, { width = 1920, height = 1080, displayOption = 'FitToPage', background = C.bg } = {}) => {
    const pagesDir = `${DEF}/pages`;
    const meta = JSON.parse(fs.readFileSync(`${pagesDir}/pages.json`, 'utf8'));
    const keep = new Set(pages.map(pg => pg.name));
    for (const d of fs.readdirSync(pagesDir, { withFileTypes: true })) if (d.isDirectory() && !keep.has(d.name)) { fs.rmSync(`${pagesDir}/${d.name}`, { recursive: true }); console.log('removed page folder', d.name); }
    const bg = { background: [{ properties: { color: { solid: { color: str(background) } }, transparency: lit('0D') } }], outspace: [{ properties: { color: { solid: { color: str(background) } } } }] };
    for (const pg of pages) {
      const dir = `${pagesDir}/${pg.name}`;
      if (fs.existsSync(`${dir}/visuals`)) fs.rmSync(`${dir}/visuals`, { recursive: true });
      const page = { $schema: PG, name: pg.name, displayName: pg.displayName, displayOption, height, width, objects: bg };
      // A drill-through page stays out of the page tabs, and is reached from a chosen row
      if (pg.hidden) page.visibility = 'HiddenInViewMode';
      if (pg.drillthrough) {
        const { table, column } = pg.drillthrough;
        const filterName = id(`drill/${pg.name}/${column}`);
        page.pageBinding = { name: id(`binding/${pg.name}`), type: 'Drillthrough', parameters: [{ name: id(`param/${pg.name}`), boundFilter: filterName, fieldExpr: colExpr(table, column) }] };
        page.filterConfig = { filters: [{ name: filterName, field: colExpr(table, column), type: 'Categorical', howCreated: 'Drillthrough' }] };
      }
      write(`${dir}/page.json`, page);
      for (const v of pg.visuals) write(`${dir}/visuals/${v.name}/visual.json`, v);
      console.log(`page ${pg.displayName}: ${pg.visuals.length} visuals`);
    }
    meta.pageOrder = pages.map(pg => pg.name);
    meta.activePageName = pages[0].name;
    write(`${pagesDir}/pages.json`, meta);
  };

  return {
    C, col, msr, msrIn, chromeOff, panelChrome, container, deneb, textbox, tableEx, dropdown, searchBox, registerTheme, writePages,
    pid: n => id(`page/${n}`),
    vid: (page, n) => id(`visual/${page}/${n}`),
  };
}
