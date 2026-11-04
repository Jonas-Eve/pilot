#!/usr/bin/env node
/* Browser test of assets/templates/pilot-dashboard.html.tmpl: renders it (as /pilot-dashboard does),
 * loads it in headless Chromium with a stubbed `window.claude` (an in-memory db with the
 * `snapshots`, `events` and `activity` collections) and checks the snapshot view, the live event
 * and activity layers, pagination, the stale-snapshot hint and the renderer's HTML escaping.
 * Run: node scripts/test_dashboard.js   (needs `playwright` with a Chromium available) */
const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');

const TEMPLATE = path.resolve(__dirname, '../assets/templates/pilot-dashboard.html.tmpl');
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
const render = (name, repo, file) => {
  const out = fs.readFileSync(TEMPLATE, 'utf8').split('{{PROJECT_NAME}}').join(esc(name)).split('{{REPO}}').join(repo);
  if (out.includes('{{')) throw new Error('unrendered placeholder');
  fs.writeFileSync(file, out); return 'file://' + file;
};
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'pilot-dashboard-'));
const REPO = 'Jonas-Eve/myavimobility';
const FILE = render('myavimobility', REPO, path.join(TMP, 'page.html'));

const iso = (minAgo) => new Date(Date.now() - minAgo * 60000).toISOString();
const snapshot = (issues, minAgo = 120) => ({ repo: REPO, at: iso(minAgo), total: issues.length, truncated: false, issues });
const ticket = (n, labels, extra = {}) => ({ n, t: `Ticket ${n}`, l: labels, u: iso(60 + n), ...extra });

// Stub of claude.ai's runtime: only the db capability, recording every capability asked for.
const STUB = (opts) => `
(() => {
  const OPTS = ${JSON.stringify(opts)};
  const data = { snapshots: {}, events: {}, activity: {} }; const listeners = { snapshots: [], events: [], activity: [] };
  (OPTS.preload || []).forEach(d => { data.snapshots[d.repo.replace('/', '__')] = d; });
  (OPTS.events || []).forEach((d, k) => { data.events['e' + k] = d; });
  (OPTS.activity || []).forEach((d, k) => { data.activity['a' + k] = d; });
  const snap = (c) => ({ docs: Object.entries(data[c]).map(([id, d]) => ({ id, data: () => d, exists: true })) });
  const fire = (c) => listeners[c].forEach(f => f(snap(c)));
  const sub = (c) => ({ onSnapshot: (next) => { listeners[c].push(next); setTimeout(() => next(snap(c)), 0); return () => {}; } });
  window.__uses = []; window.__push = (c, id, d) => { data[c][id] = d; fire(c); };
  window.claude = { use: async (name) => {
    window.__uses.push(name);
    if (name === 'db') return { collection: (c) => Object.assign(sub(c), { orderBy: () => ({ limit: () => sub(c) }) }) };
    return null;
  } };
})();`;

(async () => {
  const browser = await chromium.launch();
  const results = [];
  const check = (name, ok, detail) => { results.push(!!ok); console.log((ok ? 'PASS ' : 'FAIL ') + name + (ok ? '' : '  -> ' + detail)); };
  const open = async (opts, file = FILE) => {
    const page = await browser.newPage({ viewport: { width: 400, height: 900 } });
    page.errors = []; page.on('pageerror', e => page.errors.push(String(e)));
    await page.addInitScript(STUB(opts));
    await page.goto(file); await page.waitForTimeout(350);
    return page;
  };
  const text = (page, sel) => page.textContent(sel);
  const tab = async (page, name) => { await page.click(`nav >> text=${name}`); await page.waitForTimeout(150); return text(page, '#view'); };
  const rows = (page) => page.$$eval('#view .row', (r) => r.length);

  const BASE = snapshot([ticket(99, ['type:tech', 'status:dev-ready', 'priority:P1'], { t: 'Ticket de l instantane' })], 120);
  const ev = (o) => ({ kind: 'ticket', n: 99, title: 'Ticket de l instantane', labels: ['type:tech', 'status:in-dev'], assignees: ['alice'],
                       state: 'open', action: 'set', phase: 'dev', by: 'alice', at: iso(5), ...o });

  // ---- identity, and no connector at all ----
  let page = await open({ preload: [BASE] });
  check('title and heading carry the project name', (await page.title()) === 'Cockpit myavimobility' && /Cockpit myavimobility/.test(await text(page, 'h1')), await page.title());
  check('no repo selector, no source selector', (await page.$('#repoInput')) === null && (await page.$('#modeSeg')) === null);
  check('only the database capability is requested (no connector, no user)', JSON.stringify(await page.evaluate(() => window.__uses)) === '["db"]', JSON.stringify(await page.evaluate(() => window.__uses)));
  const banner = await text(page, '#banner');
  check('fresh snapshot: counts and age shown, no refresh hint', /1 tickets ouverts/.test(banner) && /instantané pris/.test(banner) && !/Copier/.test(banner), banner);
  check('no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  // ---- stale snapshot: hint with a copyable command ----
  page = await open({ preload: [snapshot([ticket(1, ['status:backlog'])], 60 * 30)] });
  let b = await text(page, '#banner');
  check('stale snapshot (> 24 h): hint and copy button for /pilot-dashboard --refresh', /Instantané ancien/.test(b) && /Copier \/pilot-dashboard --refresh/.test(b), b);
  await page.click('text=Copier /pilot-dashboard --refresh'); await page.waitForTimeout(200);
  check('copy button gives feedback instead of throwing', page.errors.length === 0 && /Copié|Copie impossible/.test(await text(page, '#banner')), page.errors.join('|'));
  await page.close();

  // ---- no snapshot yet ----
  page = await open({});
  b = await text(page, '#banner');
  check('no snapshot: examples named as such, with the command to run', /Données d.exemple/.test(b) && /Aucun instantané/.test(b) && /Copier \/pilot-dashboard --refresh/.test(b), b);
  await page.close();

  // ---- live events fold over the snapshot ----
  page = await open({ preload: [BASE], events: [ev({})] });
  let view = await tab(page, 'Vue d’ensemble');
  check('event newer than the snapshot moves the ticket (dev-ready -> in-dev)', /dev en cours/.test(view) && !/prêt à coder/.test(view), view);
  check('banner counts the applied change', /1 changement appliqué depuis/.test(await text(page, '#banner')), await text(page, '#banner'));
  await page.close();

  page = await open({ preload: [BASE], events: [ev({ at: iso(300) })] });
  view = await tab(page, 'Vue d’ensemble');
  check('event older than the snapshot is ignored', /prêt à coder/.test(view) && !/dev en cours/.test(view), view);
  await page.close();

  page = await open({ preload: [BASE], events: [ev({ state: 'closed', labels: ['status:done'] })] });
  check('closed event removes the ticket', !/Ticket de l instantane/.test(await tab(page, 'Vue d’ensemble')));
  await page.close();

  page = await open({ preload: [BASE], events: [ev({ n: 7, title: 'Nouveau ticket', labels: ['type:feature', 'status:backlog'], assignees: [] })] });
  view = await tab(page, 'Vue d’ensemble');
  check('event for a ticket absent from the snapshot adds it', /Nouveau ticket/.test(view) && /à spécifier/.test(view), view);
  await page.close();

  page = await open({ preload: [BASE], events: [ev({ at: iso(30) }), ev({ at: iso(2), labels: ['type:tech', 'status:review-ready'], assignees: [] })] });
  view = await tab(page, 'Vue d’ensemble');
  check('latest event per ticket wins', /à relire/.test(view) && !/dev en cours/.test(view), view);
  await page.close();

  page = await open({ preload: [BASE] });
  check('before the pushed event: dev-ready', /prêt à coder/.test(await tab(page, 'Vue d’ensemble')));
  await page.evaluate((e) => window.__push('events', 'live1', e), ev({}));
  await page.waitForTimeout(200);
  check('real time: a pushed event updates the board without reload', /dev en cours/.test(await text(page, '#view')) && !/prêt à coder/.test(await text(page, '#view')));
  check('real time: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  // ---- activity tab ----
  page = await open({ preload: [BASE],
    activity: [
      { kind: 'activity', id: 'dev-99-1', phase: 'dev', n: 99, title: 'Ticket vivant', mode: 'fresh', auto: true, by: 'alice', startedAt: iso(30), lastBeat: iso(3) },
      { kind: 'activity', id: 'spec-5-1', phase: 'spec', n: 5, title: 'Ticket muet', mode: 'fresh', auto: false, by: 'bob', startedAt: iso(300), lastBeat: iso(180) },
      { kind: 'activity', id: 'qa-6-1', phase: 'qa', n: 6, title: 'Ticket ancien', mode: 'fresh', by: 'carol', startedAt: iso(3000), lastBeat: iso(2900) },
    ],
    events: [ev({ action: 'claim:fresh', at: iso(4) })] });
  check('activity tab and chip show the live count', /Activité \(1\)/.test(await text(page, 'nav')) && /Sessions · 1 en cours/.test(await text(page, '#conn')));
  view = await tab(page, 'Activité');
  check('activity: live session with phase and mode', /Ticket vivant/.test(view) && /en cours/.test(view) && /Dev/.test(view) && /auto/.test(view), view);
  check('activity: silent session flagged', /Ticket muet/.test(view) && /sans signe de vie/.test(view), view);
  check('activity: entries older than a day hidden', !/Ticket ancien/.test(view), view);
  check('activity: recent changes feed', /pris en charge \(Dev\)/.test(view), view);
  check('activity: hash route', (await page.evaluate(() => location.hash)) === '#activite');
  check('activity: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  page = await open({ preload: [BASE] });
  view = await tab(page, 'Activité');
  check('activity: empty states', /Aucune session/.test(view) && /Aucun changement/.test(view), view);
  await page.close();

  // ---- pagination of "Ma file" ----
  const many = [];
  for (let n = 1; n <= 45; n++) many.push(ticket(n, ['type:tech', 'status:dev-ready', n === 30 ? 'priority:P0' : 'priority:P2']));
  page = await open({ preload: [snapshot(many)] });
  check('page 1: 20 rows and a pager', (await rows(page)) === 20 && /Page 1 sur 3 · 45 tickets/.test(await text(page, '#view')), await text(page, '#view'));
  check('most urgent ticket (P0) comes first', /#30/.test(await page.textContent('#view .row')), await page.textContent('#view .row'));
  check('"Précédent" disabled on the first page', await page.isDisabled('button:has-text("Précédent") >> nth=0'));
  await page.click('button:has-text("Suivant") >> nth=0'); await page.waitForTimeout(150);
  check('page 2: next 20, pager updated', (await rows(page)) === 20 && /Page 2 sur 3/.test(await text(page, '#view')));
  await page.click('button:has-text("Suivant") >> nth=0'); await page.waitForTimeout(150);
  check('last page: remaining 5, "Suivant" disabled', (await rows(page)) === 5 && /Page 3 sur 3/.test(await text(page, '#view')) && await page.isDisabled('button:has-text("Suivant") >> nth=0'));
  await page.click('#roleSeg >> text=Produit'); await page.waitForTimeout(150);
  check('changing role goes back to a valid page', /Ma file · Discovery et QA humaine · 0/.test(await text(page, '#view')) && !(await page.$('.pager')));
  await page.click('#roleSeg >> text=Tech'); await page.waitForTimeout(150);
  check('back on the first page after a role change', /Page 1 sur 3/.test(await text(page, '#view')));
  check('pagination: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.screenshot({ path: path.join(TMP, 'pagination.png') });
  await page.close();

  page = await open({ preload: [snapshot(many.slice(0, 12))] });
  check('12 tickets: no pager', !(await page.$('.pager')) && (await rows(page)) === 12);
  await page.close();

  // ---- overview columns collapse ----
  page = await open({ preload: [snapshot(many.slice(0, 12))] });
  await page.click('nav >> text=Vue d’ensemble'); await page.waitForTimeout(150);
  const cards = () => page.$$eval('section[aria-label="Dev"] .card', (c) => c.length);
  check('overview: a long column shows 8 cards and an expander', (await cards()) === 8 && /Afficher les 4 autres/.test(await text(page, 'section[aria-label="Dev"]')));
  await page.click('text=Afficher les 4 autres'); await page.waitForTimeout(150);
  check('overview: expanding shows all 12 and offers to collapse', (await cards()) === 12 && /Réduire/.test(await text(page, 'section[aria-label="Dev"]')));
  await page.click('section[aria-label="Dev"] >> text=Réduire'); await page.waitForTimeout(150);
  check('overview: collapsing goes back to 8', (await cards()) === 8);
  await page.close();

  // ---- renderer: the project name is HTML-escaped ----
  const escaped = render('A<b>"x"&y', 'o/r', path.join(TMP, 'escaped.html'));
  page = await browser.newPage(); await page.goto(escaped);
  check('renderer escapes the project name', (await page.textContent('h1')) === 'Cockpit A<b>"x"&y' && (await page.$('h1 b')) === null);
  await page.close();

  await browser.close();
  console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
  process.exit(results.every(Boolean) ? 0 : 1);
})();
