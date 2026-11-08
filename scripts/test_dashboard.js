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
  const out = fs.readFileSync(TEMPLATE, 'utf8').split('{{PROJECT_NAME}}').join(esc(name)).split('{{REPO}}').join(repo).split('{{PILOT_VERSION}}').join('1.2.3').split('{{DEPLOYED_AT}}').join('2026-01-02T03:04:05Z');
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
  const data = { snapshots: {}, events: {}, activity: {}, design: {}, wiki: {}, architecture: {}, protos: {}, protoHtml: {} }; const listeners = { snapshots: [], events: [], activity: [], design: [], wiki: [], architecture: [], protos: [], protoHtml: [] };
  (OPTS.preload || []).forEach(d => { data.snapshots[d.repo.replace('/', '__')] = d; });
  (OPTS.events || []).forEach((d, k) => { data.events['e' + k] = d; });
  (OPTS.activity || []).forEach((d, k) => { data.activity['a' + k] = d; });
  (OPTS.design || []).forEach((d, k) => { data.design['d' + k] = d; });
  (OPTS.wiki || []).forEach((d, k) => { data.wiki['w' + k] = d; });
  (OPTS.architecture || []).forEach((d, k) => { data.architecture['r' + k] = d; });
  (OPTS.protos || []).forEach((d) => { data.protos['p' + d.n] = d; });
  (OPTS.protoHtml || []).forEach((d) => { data.protoHtml[d.n + '-' + d.k] = d; });
  const snap = (c) => ({ docs: Object.entries(data[c]).map(([id, d]) => ({ id, data: () => d, exists: true })) });
  const fire = (c) => listeners[c].forEach(f => f(snap(c)));
  const sub = (c) => ({ onSnapshot: (next) => { listeners[c].push(next); setTimeout(() => next(snap(c)), 0); return () => {}; } });
  window.__uses = []; window.__push = (c, id, d) => { data[c][id] = d; fire(c); };
  window.claude = { use: async (name) => {
    window.__uses.push(name);
    if (name === 'db') return { collection: (c) => Object.assign(sub(c), { orderBy: () => ({ limit: () => sub(c) }) }),
      doc: (path) => ({ get: async () => { const [c, id] = path.split('/'); const d = (data[c] || {})[id]; return { id, exists: !!d, data: () => d }; } }) };
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
  check('fresh snapshot: counts and age shown, no stale warning', /1 tickets ouverts/.test(banner) && /instantané pris/.test(banner) && !/Instantané ancien/.test(banner), banner);
  check('fresh snapshot: a refresh button is always there (opens /pilot-dashboard --refresh), with its copy fallback',
        /Actualiser l’instantané/.test(banner) && /Copier \/pilot-dashboard --refresh/.test(banner) &&
        (await page.$$eval('#banner a.btn', (as) => as.map((a) => decodeURIComponent(a.href.split('?q=')[1].split('&repo=')[0])))).includes('/pilot-dashboard --refresh'), banner);
  check('the footer shows the PILOT version and the deployment date', (await text(page, '#version')) === 'Cockpit PILOT · v1.2.3 · déployé le 2026-01-02T03:04:05Z', await text(page, '#version'));
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
  check('activity: hash route', (await page.evaluate(() => location.hash)) === '#activite');
  await page.click('#subtabs >> text=Changements'); await page.waitForTimeout(150);
  view = await text(page, '#view');
  check('activity: recent changes feed (Changements sub-tab)', /pris en charge \(Dev\)/.test(view) && !/Ticket vivant/.test(view), view);
  check('activity: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  page = await open({ preload: [BASE] });
  view = await tab(page, 'Activité');
  check('activity: empty sessions', /Aucune session/.test(view), view);
  await page.click('#subtabs >> text=Changements'); await page.waitForTimeout(150);
  check('activity: empty changes', /Aucun changement/.test(await text(page, '#view')), await text(page, '#view'));
  await page.close();

  // ---- open in Claude Code: links with the command typed in ----
  const hrefs = (page, sel) => page.$$eval(sel, (as) => as.map((a) => ({ href: a.href, target: a.target, rel: a.rel, text: a.textContent.trim() })));
  const QA_SNAP = snapshot([ticket(99, ['type:tech', 'status:dev-ready', 'priority:P1']), ticket(50, ['type:feature', 'status:qa', 'priority:P1'])], 120);
  page = await open({ preload: [QA_SNAP] });
  await page.click('#roleSeg >> text=Tous'); await page.waitForTimeout(150);
  const links = await hrefs(page, '#view .row a.btn');
  const base = 'https://claude.ai/code/new?q=';
  const repoParam = '&repo=' + encodeURIComponent(REPO);
  const find = (cmd) => links.find((l) => l.href === base + encodeURIComponent(cmd) + repoParam);
  check('auto-capable ticket: open links for auto and pair', find('/pilot-dev 99 --auto') && find('/pilot-dev 99'), JSON.stringify(links));
  check('pair-only ticket (QA): a single open link, no --auto', find('/pilot-qa 50') && !links.some((l) => /pilot-qa%2050%20--auto/.test(l.href)), JSON.stringify(links));
  check('links open in a new tab without opener', links.length >= 3 && links.every((l) => l.target === '_blank' && /noopener/.test(l.rel)), JSON.stringify(links));
  check('the command and the repository are URL-encoded (documented claude.ai/code/new?q=&repo= form)', links.every((l) => !/ /.test(l.href)) && links.every((l) => l.href.endsWith(repoParam)) && links.every((l) => l.href.startsWith(base)));
  check('copy buttons stay as a fallback', /Copier auto/.test(await text(page, '#view')) && /Copier pair/.test(await text(page, '#view')));
  await page.screenshot({ path: path.join(TMP, 'links.png') });
  await page.close();

  page = await open({ preload: [snapshot([ticket(1, ['status:backlog'])], 60 * 30)] });
  check('stale snapshot: open link for the refresh command', (await hrefs(page, '#banner a.btn')).some((l) => l.href === base + encodeURIComponent('/pilot-dashboard --refresh') + repoParam));
  await page.close();
  page = await open({});
  check('no snapshot: open link for the refresh command', (await hrefs(page, '#banner a.btn')).some((l) => /pilot-dashboard%20--refresh/.test(l.href)));
  await page.close();

  // ---- new request: Discovery / tech Spec / bug Spec from scratch ----
  page = await open({ preload: [BASE] });
  check('new request card is folded by default, behind a chevron', (await page.getAttribute('#ideaToggle', 'aria-expanded')) === 'false' && (await page.$eval('#ideaBody', (e) => e.hidden)));
  await page.click('#ideaToggle');
  check('the chevron opens it', (await page.getAttribute('#ideaToggle', 'aria-expanded')) === 'true' && !(await page.$eval('#ideaBody', (e) => e.hidden)));
  const ideaOpen = () => page.$eval('#ideaOpen', (a) => ({ href: a.getAttribute('href'), disabled: a.getAttribute('aria-disabled'), target: a.target, rel: a.rel }));
  const encBase = 'https://claude.ai/code/new?q=';
  const encRepo = '&repo=' + encodeURIComponent(REPO);
  check('new request card is shown on "Ma file" and hidden on the other tabs',
        !(await page.$eval('#idea', (e) => e.hidden)) && (await tab(page, 'Vue d’ensemble')) !== null && (await page.$eval('#idea', (e) => e.hidden)) &&
        (await tab(page, 'Ma file')) !== null && !(await page.$eval('#idea', (e) => e.hidden)));
  check('empty text: link disabled without a target, copy disabled, command previewed',
        (await ideaOpen()).href === null && (await ideaOpen()).disabled === 'true' && (await page.isDisabled('#ideaCopy')) &&
        /^\/pilot-spec --tech …$/.test(await text(page, '#ideaCmd')), JSON.stringify(await ideaOpen()) + await text(page, '#ideaCmd'));
  await page.fill('#ideaText', 'Mon besoin');
  let o = await ideaOpen();
  check('tech role defaults to the tech Spec command, link carries command and repo',
        o.href === encBase + encodeURIComponent('/pilot-spec --tech Mon besoin') + encRepo && o.disabled === null && o.target === '_blank' && /noopener/.test(o.rel), JSON.stringify(o));
  await page.click('#kindSeg >> text=Idée produit');
  check('product idea -> /pilot-discovery', (await ideaOpen()).href === encBase + encodeURIComponent('/pilot-discovery Mon besoin') + encRepo && /^\/pilot-discovery Mon besoin$/.test(await text(page, '#ideaCmd')));
  await page.click('#kindSeg >> text=Bug');
  check('bug -> /pilot-spec --bug', (await ideaOpen()).href === encBase + encodeURIComponent('/pilot-spec --bug Mon besoin') + encRepo);
  await page.click('#roleSeg >> text=Produit');
  check('a kind chosen by hand is kept when the role changes', (await ideaOpen()).href.includes(encodeURIComponent('/pilot-spec --bug')));
  await page.fill('#ideaText', 'ligne 1\n   ligne 2\n\nligne 3');
  check('multi-line text becomes a single-line command', (await text(page, '#ideaCmd')) === '/pilot-spec --bug ligne 1 ligne 2 ligne 3', await text(page, '#ideaCmd'));
  check('text length is capped', (await page.getAttribute('#ideaText', 'maxlength')) === '1500');
  check('new request: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.screenshot({ path: path.join(TMP, 'idea.png') });
  await page.close();

  page = await open({ preload: [BASE] });
  await page.click('#roleSeg >> text=Produit'); await page.waitForTimeout(100);
  await page.click('#ideaToggle');
  await page.fill('#ideaText', 'Idée');
  check('product role defaults to /pilot-discovery', (await page.$eval('#ideaOpen', (a) => a.getAttribute('href'))).includes(encodeURIComponent('/pilot-discovery Idée')));
  await page.close();

  // typing is not lost nor interrupted by a live update
  page = await open({ preload: [BASE] });
  await page.click('#ideaToggle');
  await page.click('#ideaText'); await page.keyboard.type('texte en cours');
  await page.evaluate((e) => window.__push('events', 'live2', e), ev({}));
  await page.waitForTimeout(250);
  check('a live update keeps the typed text and the focus',
        (await page.inputValue('#ideaText')) === 'texte en cours' && (await page.evaluate(() => document.activeElement && document.activeElement.id)) === 'ideaText');
  await page.keyboard.type('!');
  check('typing continues after the update', (await page.inputValue('#ideaText')) === 'texte en cours!');
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
  check('changing role goes back to a valid page', /Ma file · Prototypes, Discovery et QA humaine · 0/.test(await text(page, '#view')) && !(await page.$('.pager')));
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

  // ---- row options: --next and --multi behind a chevron ----
  const OPT_SNAP = snapshot([
    ticket(99, ['type:tech', 'status:dev-ready', 'priority:P0']), ticket(70, ['type:feature', 'status:review-ready', 'priority:P1']),
    ticket(60, ['type:tech', 'status:in-dev', 'priority:P1']), ticket(50, ['type:feature', 'status:qa', 'priority:P1']),
    ticket(80, ['type:bug', 'level:task', 'status:backlog', 'priority:P1']), ticket(81, ['type:tech', 'level:story', 'status:backlog', 'priority:P1']),
  ], 120);
  page = await open({ preload: [OPT_SNAP] });
  await page.click('#roleSeg >> text=Tous'); await page.waitForTimeout(150);
  const rowOf = (n) => page.locator('#view .row', { hasText: '#' + n + ' ' });
  const rowHrefs = (n) => rowOf(n).locator('a.btn').evaluateAll((as) => as.map((a) => decodeURIComponent(a.href.split('?q=')[1].split('&repo=')[0])));
  const optBtn = (n) => rowOf(n).locator('button:has-text("Options")');
  check('options are folded by default: no panel, a chevron button on auto-capable rows only',
        (await page.$$('#view .opts')).length === 0 && (await optBtn(99).count()) === 1 && (await optBtn(70).count()) === 1 &&
        (await optBtn(60).count()) === 0 && (await optBtn(50).count()) === 1);
  await optBtn(99).click(); await page.waitForTimeout(100);
  const panel99 = () => rowOf(99).locator('.opts');
  check('chevron opens the panel with --next and multi', (await panel99().count()) === 1 && /Enchaîner \(--next\)/.test(await panel99().textContent()) && /Multi/.test(await panel99().textContent()));
  check('the other rows stay folded', (await rowOf(70).locator('.opts').count()) === 0);
  check('default commands unchanged', JSON.stringify(await rowHrefs(99)) === JSON.stringify(['/pilot-dev 99 --auto', '/pilot-dev 99']), JSON.stringify(await rowHrefs(99)));
  await panel99().locator('text=Enchaîner').click(); await page.waitForTimeout(100);
  check('--next: auto rides the ticket through /pilot-auto, pair unchanged', JSON.stringify(await rowHrefs(99)) === JSON.stringify(['/pilot-auto 99 --next', '/pilot-dev 99']), JSON.stringify(await rowHrefs(99)));
  await panel99().locator('.seg button', { hasText: /^3$/ }).click(); await page.waitForTimeout(100);
  check('--next + multi 3: /pilot-auto 99 --multi 3 --next, pair gets --multi 3', JSON.stringify(await rowHrefs(99)) === JSON.stringify(['/pilot-auto 99 --multi 3 --next', '/pilot-dev 99 --multi 3']), JSON.stringify(await rowHrefs(99)));
  check('active options shown as chips and in the command line', /enchaîné/.test(await rowOf(99).textContent()) && /multi 3/.test(await rowOf(99).textContent()) && /\/pilot-auto 99 --multi 3 --next/.test(await rowOf(99).locator('.cmd').textContent()));
  await panel99().locator('text=Enchaîner').click(); await page.waitForTimeout(100);
  check('multi without --next: /pilot-dev 99 --auto --multi 3', JSON.stringify(await rowHrefs(99)) === JSON.stringify(['/pilot-dev 99 --auto --multi 3', '/pilot-dev 99 --multi 3']), JSON.stringify(await rowHrefs(99)));
  await page.evaluate((e) => window.__push('events', 'live4', e), ev({ n: 70, title: 'Ticket 70', labels: ['type:feature', 'status:review-ready'] }));
  await page.waitForTimeout(250);
  check('a live update keeps the opened panel and the chosen options', (await panel99().count()) === 1 && JSON.stringify(await rowHrefs(99)) === JSON.stringify(['/pilot-dev 99 --auto --multi 3', '/pilot-dev 99 --multi 3']));
  await optBtn(99).click(); await page.waitForTimeout(100);
  check('chevron folds the panel again, the options stay applied', (await panel99().count()) === 0 && /multi 3/.test(await rowOf(99).textContent()));
  await optBtn(70).click(); await rowOf(70).locator('.opts .seg button', { hasText: /^2$/ }).click(); await page.waitForTimeout(100);
  check('review row: multi forwarded (/pilot-review 70 --auto --multi 2)', JSON.stringify(await rowHrefs(70)) === JSON.stringify(['/pilot-review 70 --auto --multi 2', '/pilot-review 70 --multi 2']), JSON.stringify(await rowHrefs(70)));
  await optBtn(99).click(); await page.waitForTimeout(100);
  await panel99().locator('.tog', { hasText: 'designer' }).click(); await panel99().locator('.tog', { hasText: 'tech lead' }).click(); await page.waitForTimeout(100);
  check('dev row: --with adds the chosen personas, auto and pair alike', JSON.stringify(await rowHrefs(99)) === JSON.stringify(['/pilot-dev 99 --auto --multi 3 --with techlead,designer', '/pilot-dev 99 --multi 3 --with techlead,designer']), JSON.stringify(await rowHrefs(99)));
  await panel99().locator('text=Enchaîner').click(); await page.waitForTimeout(100);
  check('--next hides --with and drops it from the commands', (await panel99().locator('text=Avec').count()) === 0 && JSON.stringify(await rowHrefs(99)) === JSON.stringify(['/pilot-auto 99 --multi 3 --next', '/pilot-dev 99 --multi 3']), JSON.stringify(await rowHrefs(99)));
  await panel99().locator('text=Enchaîner').click(); await optBtn(99).click(); await page.waitForTimeout(100);
  const panel70 = () => rowOf(70).locator('.opts');
  await panel70().locator('.tog', { hasText: 'PM' }).click(); await page.waitForTimeout(100);
  check('review row: --only drops --auto, keeps --multi, replaces --with', JSON.stringify(await rowHrefs(70)) === JSON.stringify(['/pilot-review 70 --multi 2 --only pm']) && (await panel70().locator('text=Avec').count()) === 0, JSON.stringify(await rowHrefs(70)));
  await panel70().locator('.tog', { hasText: 'PM' }).click(); await panel70().locator('.grp', { hasText: 'Avec' }).locator('.tog', { hasText: 'architecte' }).click(); await page.waitForTimeout(100);
  check('review row: --with architect', JSON.stringify(await rowHrefs(70)) === JSON.stringify(['/pilot-review 70 --auto --multi 2 --with architect', '/pilot-review 70 --multi 2 --with architect']), JSON.stringify(await rowHrefs(70)));
  await optBtn(50).click(); await rowOf(50).locator('.opts .tog', { hasText: 'designer' }).click(); await page.waitForTimeout(100);
  check('QA row: --with designer, pair only', JSON.stringify(await rowHrefs(50)) === JSON.stringify(['/pilot-qa 50 --with designer']), JSON.stringify(await rowHrefs(50)));
  await rowOf(50).locator('.opts .tog', { hasText: 'designer' }).click(); await optBtn(50).click(); await page.waitForTimeout(100);
  await optBtn(80).click(); await optBtn(81).click(); await page.waitForTimeout(100);
  check('spec row of a bug offers the architect, not the designer; a tech story offers the designer',
        (await rowOf(80).locator('.opts .grp', { hasText: 'Avec' }).textContent()).includes('architecte') && !(await rowOf(80).locator('.opts .grp', { hasText: 'Avec' }).textContent()).includes('designer') &&
        (await rowOf(81).locator('.opts .grp', { hasText: 'Avec' }).textContent()).includes('designer'));
  await rowOf(80).locator('.opts .grp', { hasText: 'Avec' }).locator('.tog', { hasText: 'architecte' }).click(); await page.waitForTimeout(100);
  check('bug spec: /pilot-spec 80 --auto --with architect', JSON.stringify(await rowHrefs(80)) === JSON.stringify(['/pilot-spec 80 --auto --with architect', '/pilot-spec 80 --with architect']), JSON.stringify(await rowHrefs(80)));
  await optBtn(80).click(); await optBtn(81).click(); await page.waitForTimeout(100);
  check('resume and QA rows never get --multi or --next', JSON.stringify(await rowHrefs(60)) === JSON.stringify(['/pilot-dev --resume 60']) && JSON.stringify(await rowHrefs(50)) === JSON.stringify(['/pilot-qa 50']), JSON.stringify([await rowHrefs(60), await rowHrefs(50)]));
  check('row options: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.screenshot({ path: path.join(TMP, 'options.png') });
  await page.close();

  // ---- batch: /pilot-auto with --again / --next / --multi, folded by default ----
  page = await open({ preload: [BASE] });
  const batchOpen = () => page.$eval('#batchOpen', (a) => ({ href: a.getAttribute('href'), disabled: a.getAttribute('aria-disabled') }));
  const batchCmdText = () => text(page, '#batchCmd');
  const bt = (grp, label) => page.locator(`#${grp} button`, { hasText: label }).first().click();
  check('batch card: shown on "Ma file", folded by default', !(await page.$eval('#batch', (e) => e.hidden)) && (await page.getAttribute('#batchToggle', 'aria-expanded')) === 'false' && (await page.$eval('#batchBody', (e) => e.hidden)));
  check('batch card hidden on the other tabs', (await tab(page, 'Vue d’ensemble')) !== null && (await page.$eval('#batch', (e) => e.hidden)));
  await tab(page, 'Ma file');
  await page.click('#batchToggle');
  check('batch default: bare /pilot-auto, all phases', (await batchCmdText()) === '/pilot-auto', await batchCmdText());
  await bt('batchMode', '--again');
  check('--again', (await batchCmdText()) === '/pilot-auto --again', await batchCmdText());
  await bt('batchMulti', /^3$/);
  check('--multi 3 goes before --again (the documented order)', (await batchCmdText()) === '/pilot-auto --multi 3 --again', await batchCmdText());
  await bt('batchPh', 'spec');
  check('a subset of phases is listed explicitly', (await batchCmdText()) === '/pilot-auto review dev --multi 3 --again', await batchCmdText());
  await bt('batchMode', '--next');
  check('--next replaces --again (they never combine)', (await batchCmdText()) === '/pilot-auto review dev --multi 3 --next', await batchCmdText());
  check('open link carries the command and the repo', (await batchOpen()).href === 'https://claude.ai/code/new?q=' + encodeURIComponent('/pilot-auto review dev --multi 3 --next') + '&repo=' + encodeURIComponent(REPO), JSON.stringify(await batchOpen()));
  await bt('batchPh', 'review'); await bt('batchPh', 'dev');
  check('no phase selected: link and copy disabled', (await batchOpen()).href === null && (await batchOpen()).disabled === 'true' && (await page.isDisabled('#batchCopy')));
  check('batch: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.screenshot({ path: path.join(TMP, 'batch.png') });
  await page.close();

  // ---- new request: --multi for a product idea only ----
  page = await open({ preload: [BASE] });
  await page.click('#ideaToggle'); await page.click('#roleSeg >> text=Produit'); await page.waitForTimeout(100);
  await page.fill('#ideaText', 'Mon idée');
  check('product idea: multi choices shown', !(await page.$eval('#ideaMultiWrap', (e) => e.hidden)));
  await page.locator('#ideaMultiSeg button', { hasText: /^3$/ }).click();
  check('product idea + multi: /pilot-discovery <idea> --multi 3', (await text(page, '#ideaCmd')) === '/pilot-discovery Mon idée --multi 3' && (await page.$eval('#ideaOpen', (a) => a.getAttribute('href'))).includes(encodeURIComponent('/pilot-discovery Mon idée --multi 3')), await text(page, '#ideaCmd'));
  await page.click('#ideaWithSeg >> text=Designer');
  check('product idea + designer: --with designer after --multi', (await text(page, '#ideaCmd')) === '/pilot-discovery Mon idée --multi 3 --with designer', await text(page, '#ideaCmd'));
  await page.click('#kindSeg >> text=Besoin technique');
  check('tech need + designer: --with designer, no --multi', (await text(page, '#ideaCmd')) === '/pilot-spec --tech Mon idée --with designer', await text(page, '#ideaCmd'));
  await page.click('#kindSeg >> text=Bug');
  check('bug report: the designer is summonable too, no --multi', !(await page.$eval('#ideaWithWrap', (e) => e.hidden)) && (await text(page, '#ideaCmd')) === '/pilot-spec --bug Mon idée --with designer', await text(page, '#ideaCmd'));
  check('bug / tech need: no multi choice, no --multi in the command', (await page.$eval('#ideaMultiWrap', (e) => e.hidden)) && (await text(page, '#ideaCmd')) === '/pilot-spec --bug Mon idée --with designer', await text(page, '#ideaCmd'));
  await page.close();

  // ---- sub-issues of an epic or a story: listed under it, each one launchable ----
  const KIDS_SNAP = snapshot([
    ticket(10, ['type:feature', 'level:epic'], { t: 'Epic parent', k: [4, 6] }),
    ticket(11, ['type:feature', 'level:story', 'status:backlog', 'priority:P1'], { t: 'Story A', p: 10, k: [1, 3] }),
    ticket(12, ['type:feature', 'level:story', 'status:qa', 'priority:P2'], { t: 'Story B', p: 10 }),
    ticket(13, ['type:tech', 'level:task', 'status:dev-ready', 'priority:P1'], { t: 'Tâche de A', p: 11 }),
    ticket(14, ['type:tech', 'level:task', 'status:in-dev', 'needs-human'], { t: 'Tâche bloquée de A', p: 11 }),
    ticket(20, ['type:tech', 'level:story', 'status:backlog'], { t: 'Sans parent' }),
  ], 120);
  page = await open({ preload: [KIDS_SNAP] });
  await tab(page, 'Recherche');
  const kidsBtn = (scope) => scope.locator('button:has-text("Sous-tickets")');
  const topRow = (n) => page.locator('#view > .list > .row', { has: page.locator(`.main > .t:has-text("#${n} ")`) });
  check('parent row: progress chip and a collapsed sub-tickets chevron with the open count',
        /4\/6 terminés/.test(await topRow(10).textContent()) && (await kidsBtn(topRow(10)).first().textContent()).includes('Sous-tickets (2)') &&
        (await page.$$('#view .kids')).length === 0);
  check('a ticket without sub-issues has no sub-tickets chevron', (await kidsBtn(topRow(20)).count()) === 0);
  await kidsBtn(topRow(10)).first().click(); await page.waitForTimeout(100);
  const kidNames = () => page.$$eval('#view .kids > .row > .main > .t', (e) => e.map((x) => x.textContent.trim()));
  check('opening lists the open sub-issues, most urgent first', JSON.stringify(await kidNames()) === JSON.stringify(['#11 Story A', '#12 Story B']), JSON.stringify(await kidNames()));
  const kidCmds = (sel) => page.locator(sel).locator('a.btn').evaluateAll((as) => as.map((a) => decodeURIComponent(a.href.split('?q=')[1].split('&repo=')[0])));
  check('each sub-issue can be launched on its own (/pilot-spec 11 auto + pair, /pilot-qa 12)',
        JSON.stringify(await kidCmds('#view .kids > .row:nth-child(1) > .acts')) === JSON.stringify(['/pilot-spec 11 --auto', '/pilot-spec 11']) &&
        JSON.stringify(await kidCmds('#view .kids > .row:nth-child(2) > .acts')) === JSON.stringify(['/pilot-qa 12']), JSON.stringify(await kidCmds('#view .kids > .row > .acts')));
  await page.locator('#view .kids > .row:nth-child(1) > .acts button:has-text("Sous-tickets")').click(); await page.waitForTimeout(100);
  check('nesting goes one level further (story -> tasks), blocked task flagged', JSON.stringify(await page.$$eval('#view .kids .kids > .row > .main > .t', (e) => e.map((x) => x.textContent.trim()))) === JSON.stringify(['#14 Tâche bloquée de A', '#13 Tâche de A']), JSON.stringify(await page.$$eval('#view .kids .kids > .row > .main > .t', (e) => e.map((x) => x.textContent.trim()))));
  check('a task is launchable (/pilot-dev 13 --auto) and has no sub-tickets chevron', (await kidCmds('#view .kids .kids > .row:has-text("#13 ") > .acts')).includes('/pilot-dev 13 --auto') && (await page.locator('#view .kids .kids button:has-text("Sous-tickets")').count()) === 0);
  await page.evaluate((e) => window.__push('events', 'live5', e), ev({ n: 13, title: 'Tâche de A', labels: ['type:tech', 'level:task', 'status:in-dev'], assignees: [] }));
  await page.waitForTimeout(250);
  check('a live update keeps the nesting and moves the sub-ticket (dev-ready -> in-dev)',
        (await page.$$('#view .kids .kids')).length === 1 && /dev en cours/.test(await page.locator('#view .kids .kids > .row:has-text("#13 ")').textContent()));
  await kidsBtn(topRow(10)).first().click(); await page.waitForTimeout(100);
  check('the chevron folds the epic\'s whole subtree (a ticket opened elsewhere in the list keeps its own state)', (await topRow(10).locator('.kids').count()) === 0 && (await topRow(11).locator('.kids').count()) === 1);
  check('sub-tickets: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.screenshot({ path: path.join(TMP, 'kids.png') });
  await page.close();

  // ---- events that carry a parent and a PR (a ticket created, or a PR opened, since the snapshot) ----
  const EV_SNAP = snapshot([
    ticket(10, ['type:feature', 'level:epic'], { t: 'Epic', k: [0, 1] }),
    ticket(11, ['type:feature', 'level:story', 'status:split', 'priority:P1'], { t: 'Story A', p: 10, k: [0, 1] }),
    ticket(13, ['type:tech', 'level:task', 'status:in-dev'], { t: 'Tâche en cours', p: 11, a: 'alice' }),
  ], 120);
  page = await open({ preload: [EV_SNAP], events: [
    ev({ n: 30, title: 'Tâche créée par un split', labels: ['type:tech', 'level:task', 'status:dev-ready'], assignees: [], action: 'created', phase: 'spec', parent: 11, at: iso(10) }),
    ev({ n: 13, title: 'Tâche en cours', labels: ['type:tech', 'level:task', 'status:review-ready'], assignees: [], action: 'set', phase: null, pr: 77, at: iso(5) }),
    ev({ n: 40, title: 'Idée approuvée', labels: ['type:feature', 'level:story', 'status:backlog'], assignees: [], action: 'approved', phase: 'discovery', at: iso(3) }),
  ] });
  await tab(page, 'Recherche');
  const evRow = (n) => page.locator('#view > .list > .row', { has: page.locator(`:scope > .main > .t:has-text("#${n} ")`) });
  check('a ticket created since the snapshot is nested under its parent from the event alone', (await evRow(11).locator('button:has-text("Sous-tickets (2)")').count()) === 1, await evRow(11).textContent());
  await evRow(11).locator('button:has-text("Sous-tickets")').click(); await page.waitForTimeout(100);
  check('both sub-tickets are listed under the story', JSON.stringify(await page.$$eval('#view > .list > .row:has(.kids) .kids > .row > .main > .t', (e) => e.map((x) => x.textContent.trim().split(' ')[0]).sort())) === JSON.stringify(['#13', '#30']));
  const prLinks = (n) => evRow(n).locator('a:has-text("PR #")').evaluateAll((as) => as.map((a) => a.href));
  check('an event carrying a PR gives the ticket its PR link', JSON.stringify(await prLinks(13)) === JSON.stringify([`https://github.com/${REPO}/pull/77`]), JSON.stringify(await prLinks(13)));
  await tab(page, 'Activité'); await page.click('#subtabs >> text=Changements'); await page.waitForTimeout(150);
  view = await text(page, '#view');
  check('activity feed words a created and an approved ticket', /créé \(prêt à coder\)/.test(view) && /approuvé \(à spécifier\)/.test(view), view);
  check('events: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  // ---- search: keyword (case/accent-insensitive contains) + level + type ----
  const SEARCH_SNAP = snapshot([
    ticket(10, ['type:feature', 'level:epic'], { t: 'Profil d\'accessibilité : page profil' }),
    ticket(11, ['type:feature', 'level:story', 'status:qa'], { t: 'Saisir mes données sensibles' }),
    ticket(12, ['type:tech', 'level:story', 'status:backlog'], { t: 'Cache des états d\'équipements' }),
    ticket(13, ['type:bug', 'level:task', 'status:backlog'], { t: 'Bug : pictogramme masqué' }),
    ticket(14, ['type:feature', 'level:task', 'status:dev-ready'], { t: 'ÉCRAN du Profil voyageur' }),
    ticket(15, ['type:feature', 'level:story', 'status:split'], { t: 'Story déjà découpée' }),
  ], 120);
  page = await open({ preload: [SEARCH_SNAP] });
  view = await tab(page, 'Recherche');
  check('filters are folded by default behind a chevron, with no count', (await page.getAttribute('#filtersToggle', 'aria-expanded')) === 'false' && (await page.$eval('#searchFilters', (e) => e.hidden)) && (await page.$eval('#filtersCount', (e) => e.hidden)));
  await page.click('#filtersToggle');
  check('the chevron opens the filter panel: five groups', !(await page.$eval('#searchFilters', (e) => e.hidden)) && (await page.locator('#searchFilters .fgrp').count()) === 5);
  check('search tab: shown, hash route, search card visible, new-request card hidden',
        !(await page.$eval('#search', (e) => e.hidden)) && (await page.$eval('#idea', (e) => e.hidden)) && (await page.evaluate(() => location.hash)) === '#recherche');
  check('no filter: every ticket is listed, epics and split stories included', (await rows(page)) === 6 && /6 sur 6 tickets ouverts/.test(view), view);
  const names = () => page.$$eval('#view .row .t', (e) => e.map((x) => x.textContent.trim()));
  await page.fill('#searchText', 'PROFIL');
  check('keyword: case-insensitive contains on the title', (await rows(page)) === 2 && (await names()).every((n) => /profil/i.test(n)), JSON.stringify(await names()));
  await page.fill('#searchText', 'ecran');
  check('keyword: accent-insensitive (ecran matches ÉCRAN)', (await rows(page)) === 1 && /#14/.test((await names())[0]), JSON.stringify(await names()));
  await page.fill('#searchText', 'profil voyageur');
  check('several words: all must be present', (await rows(page)) === 1 && /#14/.test((await names())[0]), JSON.stringify(await names()));
  await page.fill('#searchText', '#12');
  check('keyword: matches the ticket number', (await rows(page)) === 1 && /#12/.test((await names())[0]), JSON.stringify(await names()));
  await page.fill('#searchText', 'zzz');
  check('no match: empty state', (await rows(page)) === 0 && /Aucun ticket ne correspond/.test(await text(page, '#view')));
  await page.fill('#searchText', '');
  await page.click('#searchFilters >> text=epic'); await page.waitForTimeout(100);
  check('level filter: epic only', (await rows(page)) === 1 && /#10/.test((await names())[0]) && /epic/.test(await text(page, '#view .row .meta')), JSON.stringify(await names()));
  await page.click('#searchFilters >> text=story'); await page.waitForTimeout(100);
  check('level filter: several levels are OR-ed (epic + story)', (await rows(page)) === 4, String(await rows(page)));
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(100);
  await page.click('#searchFilters >> text=bug'); await page.waitForTimeout(100);
  check('type filter: bug only', (await rows(page)) === 1 && /#13/.test((await names())[0]), JSON.stringify(await names()));
  await page.click('#searchFilters >> text=bug');
  await page.click('#searchFilters >> text=feature'); await page.click('#searchFilters >> text=tâche'); await page.fill('#searchText', 'profil'); await page.waitForTimeout(100);
  check('keyword + type + level are AND-ed', (await rows(page)) === 1 && /#14/.test((await names())[0]), JSON.stringify(await names()));
  check('filter buttons reflect their state', (await page.getAttribute('#searchFilters >> text=feature', 'aria-pressed')) === 'true' && (await page.getAttribute('#searchFilters >> text=bug', 'aria-pressed')) === 'false');
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(100);
  check('reset clears the keyword and the filters', (await page.inputValue('#searchText')) === '' && (await rows(page)) === 6);
  check('search results: levels shown as chips', /story/.test(await text(page, '#view')) && /epic/.test(await text(page, '#view')));
  const searchCmds = () => page.$$eval('#view .row a.btn', (as) => as.map((a) => decodeURIComponent(a.href.split('?q=')[1].split('&repo=')[0])));
  check('an epic and a split story get a /pilot-auto action (auto only, no pair)', (await searchCmds()).includes('/pilot-auto 10') && (await searchCmds()).includes('/pilot-auto 15') && !(await searchCmds()).includes('/pilot-spec 15'), JSON.stringify(await searchCmds()));
  const epicRow = page.locator('#view .row', { hasText: '#10 ' });
  check('an epic row has no pair button', (await epicRow.locator('a.btn', { hasText: /pair/ }).count()) === 0 && (await epicRow.locator('a.btn', { hasText: /auto/ }).count()) === 1);
  await epicRow.locator('button:has-text("Options")').click(); await page.waitForTimeout(100);
  await epicRow.locator('.opts >> text=Enchaîner').click(); await epicRow.locator('.opts .seg button', { hasText: /^3$/ }).click(); await page.waitForTimeout(100);
  check('epic options: /pilot-auto 10 --multi 3 --next', (await searchCmds()).includes('/pilot-auto 10 --multi 3 --next'), JSON.stringify(await searchCmds()));
  check('no active filter and no keyword: no chip, no reset button', (await page.locator('#activeFilters').textContent()) === '');
  await page.click('#searchText'); await page.keyboard.type('profil');
  await page.evaluate((e) => window.__push('events', 'live3', e), ev({}));
  await page.waitForTimeout(250);
  check('a live update keeps the typed keyword and the focus', (await page.inputValue('#searchText')) === 'profil' && (await page.evaluate(() => document.activeElement && document.activeElement.id)) === 'searchText');
  check('search: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.screenshot({ path: path.join(TMP, 'search.png') });
  await page.close();

  page = await open({ preload: [snapshot(many)] });
  await tab(page, 'Recherche');
  check('search results are paginated', (await rows(page)) === 20 && /Page 1 sur 3 · 45 tickets/.test(await text(page, '#view')));
  await page.close();

  // ---- search: state filter (and flags) ----
  const STATE_SNAP = snapshot([
    ticket(10, ['type:feature', 'level:epic'], { t: 'Epic sans statut' }),
    ticket(11, ['type:feature', 'level:story', 'status:qa'], { t: 'Story à tester' }),
    ticket(12, ['type:tech', 'level:story', 'status:backlog'], { t: 'Story backlog' }),
    ticket(13, ['type:bug', 'level:task', 'status:backlog', 'needs-human'], { t: 'Bug backlog bloqué' }),
    ticket(14, ['type:feature', 'level:task', 'status:dev-ready', 'on-hold'], { t: 'Tâche en pause' }),
    ticket(15, ['type:feature', 'level:story', 'status:split'], { t: 'Story découpée' }),
    ticket(16, ['type:tech', 'level:task', 'status:scoping'], { t: 'Statut hors processus' }),
  ], 120);
  page = await open({ preload: [STATE_SNAP] });
  await tab(page, 'Recherche');
  await page.click('#filtersToggle');
  const stBtn = (grp, key) => page.locator(`#searchFilters button[data-map="${grp}"][data-key="${key}"]`);
  const nums = async () => (await page.locator('#view .row > .main > .t').allTextContents()).map((x) => x.trim().split(' ')[0]).sort();
  const setOf = (...a) => JSON.stringify(a.sort());
  check('state filter: one chip per PILOT status in process order, "sans statut", and a status found in the tickets but not in the process',
        (await stBtn('states', 'qa').count()) === 1 && (await stBtn('states', 'none').count()) === 1 && (await stBtn('states', 'scoping').count()) === 1 &&
        (await page.locator('#searchFilters button[data-map="states"]').first().getAttribute('data-key')) === 'draft');
  check('state chips use the French names', /à tester/.test(await stBtn('states', 'qa').textContent()) && /sans statut/.test(await stBtn('states', 'none').textContent()));
  await stBtn('states', 'qa').click(); await page.waitForTimeout(100);
  check('one state: only those tickets', JSON.stringify(await nums()) === setOf('#11'), JSON.stringify(await nums()));
  await stBtn('states', 'backlog').click(); await page.waitForTimeout(100);
  check('several states are OR-ed', JSON.stringify(await nums()) === setOf('#11', '#12', '#13'), JSON.stringify(await nums()));
  await page.locator('#searchFilters button[data-map="types"][data-key="bug"]').click(); await page.waitForTimeout(100);
  check('state + type are AND-ed', JSON.stringify(await nums()) === setOf('#13'), JSON.stringify(await nums()));
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(100);
  await stBtn('states', 'none').click(); await page.waitForTimeout(100);
  check('"sans statut" finds the epics', JSON.stringify(await nums()) === setOf('#10'), JSON.stringify(await nums()));
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(100);
  await stBtn('states', 'scoping').click(); await page.waitForTimeout(100);
  check('a status outside the process still filters', JSON.stringify(await nums()) === setOf('#16'), JSON.stringify(await nums()));
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(100);
  await stBtn('flags', 'needs-human').click(); await page.waitForTimeout(100);
  check('flag "attend un humain"', JSON.stringify(await nums()) === setOf('#13'), JSON.stringify(await nums()));
  await stBtn('flags', 'on-hold').click(); await page.waitForTimeout(100);
  check('flags are OR-ed', JSON.stringify(await nums()) === setOf('#13', '#14'), JSON.stringify(await nums()));
  await stBtn('states', 'backlog').click(); await page.waitForTimeout(100);
  check('flag + state are AND-ed', JSON.stringify(await nums()) === setOf('#13'), JSON.stringify(await nums()));
  check('chips reflect their state', (await stBtn('states', 'backlog').getAttribute('aria-pressed')) === 'true' && (await stBtn('states', 'qa').getAttribute('aria-pressed')) === 'false');
  check('active filters are listed as removable chips with a count, even when the panel is folded',
        (await page.locator('#activeFilters .chip.rm').allTextContents()).map((x) => x.trim()).sort().join('|') === 'Drapeau : attend un humain ✕|Drapeau : en pause ✕|État : à spécifier ✕' &&
        (await text(page, '#filtersCount')) === '3', await page.locator('#activeFilters').textContent());
  await page.click('#filtersToggle');
  check('folding the panel keeps the chips and the count', (await page.$eval('#searchFilters', (e) => e.hidden)) && (await page.locator('#activeFilters .chip.rm').count()) === 3 && (await text(page, '#filtersCount')) === '3');
  await page.locator('#activeFilters .chip.rm', { hasText: 'en pause' }).click(); await page.waitForTimeout(100);
  check('a chip removes its filter', JSON.stringify(await nums()) === setOf('#13') && (await text(page, '#filtersCount')) === '2' && (await page.locator('#activeFilters .chip.rm').count()) === 2, JSON.stringify(await nums()));
  await page.click('#filtersToggle');
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(100);
  check('reset clears state and flag filters', (await nums()).length === 7 && (await stBtn('states', 'backlog').getAttribute('aria-pressed')) === 'false' && (await stBtn('flags', 'on-hold').getAttribute('aria-pressed')) === 'false');
  check('state filter: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.screenshot({ path: path.join(TMP, 'states.png') });
  await page.close();

  // ---- assignee (chip, "à prendre" / "assignés à moi", search filter) and the open PR link ----
  const ASSIGN_SNAP = snapshot([
    ticket(1, ['type:tech', 'status:dev-ready', 'priority:P1'], { t: 'Libre dev' }),
    ticket(2, ['type:tech', 'status:in-dev', 'priority:P1'], { t: 'À alice dev', a: 'alice', r: 33 }),
    ticket(3, ['type:tech', 'status:dev-ready', 'needs-human'], { t: 'Libre mais bloqué' }),
    ticket(4, ['type:feature', 'status:review-ready', 'priority:P2'], { t: 'Libre review' }),
    ticket(5, ['type:feature', 'status:qa', 'priority:P2'], { t: 'Libre qa' }),
    ticket(6, ['type:feature', 'status:in-qa', 'priority:P2'], { t: 'À alice qa', a: 'alice' }),
    ticket(7, ['type:tech', 'status:in-review', 'priority:P2'], { t: 'À bob review', a: 'bob', r: 34 }),
    ticket(8, ['type:tech', 'status:changes-requested', 'priority:P2'], { t: 'Corrections demandées' }),
    ticket(9, ['type:tech', 'status:in-dev', 'priority:P2'], { t: 'Ancien verdict, assigné', a: 'carol' }),
  ], 120);
  page = await open({ preload: [ASSIGN_SNAP] });
  const fileNums = async () => (await page.locator('#view .row > .main > .t').allTextContents()).map((x) => x.trim().split(' ')[0]).sort();
  const setOf2 = (...a) => JSON.stringify(a.sort());
  check('default scope "Tous": the role\'s tickets, assigned or not', JSON.stringify(await fileNums()) === setOf2('#1', '#2', '#3', '#4', '#7', '#8', '#9'), JSON.stringify(await fileNums()));
  check('an assignee shows as a chip', /@alice/.test(await page.locator('#view .row', { hasText: '#2 ' }).textContent()) && !/@/.test(await page.locator('#view .row', { hasText: '#1 ' }).textContent()));
  const prHref = (n) => page.locator('#view .row', { hasText: '#' + n + ' ' }).locator('a:has-text("PR #")').evaluateAll((as) => as.map((a) => ({ href: a.href, text: a.textContent.trim(), target: a.target, rel: a.rel })));
  check('a ticket with an open PR links to it (new tab, no opener)', JSON.stringify(await prHref(2)) === JSON.stringify([{ href: `https://github.com/${REPO}/pull/33`, text: 'PR #33', target: '_blank', rel: 'noopener' }]), JSON.stringify(await prHref(2)));
  check('a ticket without a PR has no PR link', (await prHref(1)).length === 0);
  await page.locator('#view .seg button', { hasText: 'À prendre' }).click(); await page.waitForTimeout(100);
  check('"À prendre": role tickets that are unassigned (a changes-requested one included, review unassigns it) and neither blocked nor on hold', JSON.stringify(await fileNums()) === setOf2('#1', '#4', '#8'), JSON.stringify(await fileNums()));
  await page.click('#roleSeg >> text=Produit'); await page.waitForTimeout(100);
  check('"À prendre" follows the role (product: the QA ticket)', JSON.stringify(await fileNums()) === setOf2('#5'), JSON.stringify(await fileNums()));
  await page.click('#roleSeg >> text=Tech'); await page.waitForTimeout(100);
  await page.locator('#view .seg button', { hasText: 'Assignés à moi' }).click(); await page.waitForTimeout(100);
  check('"Assignés à moi" without an identity asks for it', (await fileNums()).length === 0 && /Indiquez votre identifiant GitHub/.test(await text(page, '#view')));
  check('the known assignees are offered in the identity field', (await page.locator('#meList option').evaluateAll((o) => o.map((x) => x.value).sort())).join(',') === 'alice,bob,carol');
  await page.fill('#meInput', '@alice'); await page.waitForTimeout(100);
  check('with an identity: every ticket assigned to me, whatever the role (a dev one and a QA one)', JSON.stringify(await fileNums()) === setOf2('#2', '#6'), JSON.stringify(await fileNums()));
  await page.screenshot({ path: path.join(TMP, 'mine.png') });
  check('my own tickets are highlighted and the title names me', /@alice/.test(await text(page, '#view h2')) && (await page.locator('#view .row', { hasText: '#2 ' }).locator('.chip.acc', { hasText: '@alice' }).count()) === 1);
  await page.fill('#meInput', 'nobody'); await page.waitForTimeout(100);
  check('an identity with no ticket: dedicated empty state', /Aucun ticket ne vous est assigné/.test(await text(page, '#view')));
  await page.fill('#meInput', 'bob'); await page.waitForTimeout(100);
  check('bob sees his review ticket', JSON.stringify(await fileNums()) === setOf2('#7'), JSON.stringify(await fileNums()));
  await page.evaluate((e) => window.__push('events', 'live6', e), ev({ n: 1, title: 'Libre dev', labels: ['type:tech', 'status:in-dev'], assignees: ['bob'] }));
  await page.waitForTimeout(250);
  check('a live event assigning a ticket moves it into my list', JSON.stringify(await fileNums()) === setOf2('#1', '#7'), JSON.stringify(await fileNums()));
  check('assignee: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  page = await open({ preload: [ASSIGN_SNAP] });
  await page.fill('#meInput', 'alice');
  await tab(page, 'Recherche'); await page.click('#filtersToggle');
  const asBtn = (key) => page.locator(`#searchFilters button[data-map="assignees"][data-key="${key}"]`);
  const sNums = async () => (await page.locator('#view .row > .main > .t').allTextContents()).map((x) => x.trim().split(' ')[0]).sort();
  check('assignee filter: moi, non assigné and each assignee found', (await asBtn('me').count()) === 1 && (await asBtn('none').count()) === 1 && (await asBtn('alice').count()) === 1 && (await asBtn('bob').count()) === 1);
  await asBtn('none').click(); await page.waitForTimeout(100);
  check('"non assigné"', JSON.stringify(await sNums()) === setOf2('#1', '#3', '#4', '#5', '#8'), JSON.stringify(await sNums()));
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(100);
  await asBtn('me').click(); await page.waitForTimeout(100);
  check('"moi" = the identity typed at the top', JSON.stringify(await sNums()) === setOf2('#2', '#6'), JSON.stringify(await sNums()));
  await asBtn('bob').click(); await page.waitForTimeout(100);
  check('assignees are OR-ed (moi + bob)', JSON.stringify(await sNums()) === setOf2('#2', '#6', '#7'), JSON.stringify(await sNums()));
  check('chips: "Assigné : moi ✕" and "Assigné : @bob ✕"', (await page.locator('#activeFilters .chip.rm').allTextContents()).map((x) => x.trim()).sort().join('|') === 'Assigné : @bob ✕|Assigné : moi ✕');
  await page.fill('#meInput', '');
  await page.waitForTimeout(100);
  check('"moi" without an identity: a hint, and only the other assignees left', /Indiquez votre identifiant GitHub/.test(await text(page, '#view')) && JSON.stringify(await sNums()) === setOf2('#7'), JSON.stringify(await sNums()));
  check('search by assignee: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  // ---- design tab: the project's design document, edited through a /pilot-design session ----
  const DESIGN = { kind: 'design', repo: REPO, at: iso(30),
    charter: { name: 'myAVI <img src=x onerror=window.__pwn=1>', summary: 'Voyager sans obstacle', logo: '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>',
      colors: [{ name: 'Bleu', hex: '#1747C9', use: 'actions' }, { name: 'Piège', hex: 'red;background:url(//evil)', use: 'x' }], voice: 'Clair et bienveillant', rules: 'Pas de blanc sur jaune' },
    colors: [{ name: 'Fond', light: '#FFFFFF', dark: '#0E141B', use: 'page' }],
    type: { family: 'IBM Plex Sans', scale: [{ name: 'Titre', size: 22, weight: 600, use: 'titres' }] },
    space: { spacing: [{ name: 'm', value: '16px' }], radius: [{ name: 's', value: '8px' }] },
    components: [{ name: 'Bouton', description: 'Action principale', rules: 'Cible de 44 px' }],
    a11y: ['Contraste AA minimum'] };
  page = await open({ preload: [BASE] });
  await page.click('nav >> text=Design'); await page.waitForTimeout(150);
  check('design tab: empty state with the edit card, no ticket banner', /Aucun design system/.test(await text(page, '#view')) && !(await page.$eval('#designEdit', (e) => e.hidden)) && (await page.$eval('#banner', (e) => e.hidden)));
  check('design edit card and banner back on the other tabs', (await tab(page, 'Vue d’ensemble')) !== null && (await page.$eval('#designEdit', (e) => e.hidden)) && !(await page.$eval('#banner', (e) => e.hidden)));
  await page.click('nav >> text=Design'); await page.waitForTimeout(100);
  check('design: the edit card is folded by default, so the content comes first', (await page.$eval('#designEBody', (e) => e.hidden)));
  await page.click('#designEToggle'); await page.waitForTimeout(100);
  const dCmd = () => text(page, '#designCmd');
  const dHref = async () => decodeURIComponent((await page.$eval('#designOpen', (a) => a.getAttribute('href'))).split('?q=')[1].split('&repo=')[0]);
  check('design: bare command, link carries it', (await dCmd()) === '/pilot-design' && (await dHref()) === '/pilot-design', await dCmd());
  await page.fill('#designText', 'ajouter un thème\nà fort contraste'); await page.waitForTimeout(100);
  check('design: with no document yet, the request alone (it creates the whole document)', (await dCmd()) === '/pilot-design ajouter un thème à fort contraste' && (await dHref()) === (await dCmd()), await dCmd());
  await page.evaluate((d) => window.__push('design', 'd0', d), DESIGN); await page.waitForTimeout(200);
  let dv = '';
  for (const lab of ['Charte', 'Couleurs', 'Typographie', 'Espacements', 'Composants', 'Accessibilité']) {
    await page.click('#subtabs >> text=' + lab); await page.waitForTimeout(120); dv += await text(page, '#view');
  }
  await page.click('#subtabs >> text=Charte'); await page.waitForTimeout(120);
  check('design: a live document fills every section', /Voyager sans obstacle/.test(dv) && /clair #FFFFFF/.test(dv) && /sombre #0E141B/.test(dv) && /IBM Plex Sans/.test(dv) && /22 px · 600/.test(dv) && /Espacement m/.test(dv) && /Rayon s/.test(dv) && /Cible de 44 px/.test(dv) && /Contraste AA minimum/.test(dv) && /Clair et bienveillant/.test(dv), dv);
  check('design: the edit card now says "Modifier", the typed request is kept', /^Modifier/.test(await text(page, '#designHint')) && (await page.inputValue('#designText')).includes('fort contraste'));
  await page.click('#subtabs >> text=Couleurs'); await page.waitForTimeout(150);
  check('design: the command targets the open section, with the request', (await dCmd()) === '/pilot-design --section colors ajouter un thème à fort contraste' && (await dHref()) === (await dCmd()), await dCmd());
  await page.click('#designAll'); await page.waitForTimeout(100);
  check('design: "Tout le design system" drops the section', (await dCmd()) === '/pilot-design ajouter un thème à fort contraste' && /tout le design system/.test(await text(page, '#designHint')), await dCmd());
  await page.click('#designAll'); await page.click('#subtabs >> text=Charte'); await page.waitForTimeout(150);
  check('design: HTML in a value stays text, an invalid hex gets no swatch', (await page.$('#view [onerror]')) === null && (await page.evaluate(() => window.__pwn)) === undefined && /myAVI <img src=x/.test(dv) && !(await page.$('#view [style*="evil"]')), dv);
  check('design: a valid logo renders as an image', (await page.$$('#view img.logo')).length === 1 && (await page.$eval('#view img.logo', (i) => i.src.startsWith('data:image/svg+xml'))));
  await page.evaluate((d) => window.__push('design', 'd0', Object.assign({}, d, { charter: Object.assign({}, d.charter, { logo: '<img src=x onerror=1>' }) })), DESIGN); await page.waitForTimeout(200);
  check('design: a logo that is not an SVG is ignored', (await page.$$('#view img.logo')).length === 0);
  await page.evaluate((d) => window.__push('design', 'd1', Object.assign({}, d, { repo: 'o/other', charter: { name: 'Autre projet' } })), DESIGN); await page.waitForTimeout(150);
  check('design: another repo\'s document is not shown', !/Autre projet/.test(await text(page, '#view')));
  check('design tab: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();
  page = await open({ preload: [BASE], design: [DESIGN] });
  await page.goto(FILE + '#design'); await page.waitForTimeout(350);
  check('design: #design opens the tab, a preloaded document is shown', /myAVI/.test(await text(page, '#view')) && (await page.$eval('nav a[aria-current=page]', (a) => a.textContent)) === 'Design');
  await page.close();

  // ---- design tab: a component shows a live preview in an isolated frame, themed by the document's own tokens ----
  const PV = Object.assign({}, DESIGN, {
    colors: [{ name: 'Action', light: '#1747C9', dark: '#7EA2FF', use: 'boutons' }, { name: 'Fond clair', light: '#FFFFFF', dark: '#0E141B', use: 'page' }],
    space: { spacing: [{ name: 'm', value: '16px' }], radius: [{ name: 's', value: '8px' }] },
    type: { family: 'IBM Plex Sans', scale: [{ name: 'Corps', size: 14, weight: 400, use: 'texte' }] },
    components: [
      { name: 'Bouton', description: 'Action principale', rules: 'Cible de 44 px', height: 70,
        preview: '<button id="b" style="padding:var(--space-m);border-radius:var(--radius-s);background:var(--color-action);color:#fff;border:0">Démarrer</button>' },
      { name: 'Piège', description: 'Aperçu hostile', height: 60,
        preview: '<script>parent.__pwn=1<\/script><img src="https://evil.example/x.png" onerror="parent.__pwn=2"><p id="t">texte</p>' },
      { name: 'Trop gros', description: 'Aperçu hors limite', preview: '<p>' + 'x'.repeat(4100) + '</p>' },
      { name: 'Sans aperçu', description: 'Seulement une description' },
    ] });
  page = await open({ preload: [BASE], design: [PV] });
  await page.goto(FILE + '#design/components'); await page.waitForTimeout(500);
  const frames = () => page.$$('#view iframe.prev');
  check('preview: one frame per component that has a valid preview (not the oversized or missing ones)', (await frames()).length === 2, String((await frames()).length));
  check('preview: the frame is sandboxed with no permission at all', (await page.$$eval('#view iframe.prev', (fs) => fs.every((f) => f.getAttribute('sandbox') === '' && !f.hasAttribute('src')))));
  const sd = await page.$eval('#view iframe.prev', (f) => f.getAttribute('srcdoc'));
  check('preview: the frame defines the tokens, with a policy that forbids script and network',
        /--color-action:#1747C9/.test(sd) && /--color-fond-clair:#FFFFFF/.test(sd) && /--space-m:16px/.test(sd) && /--radius-s:8px/.test(sd) && /--text-corps:14px/.test(sd) &&
        /prefers-color-scheme:dark\)\{:root\{--color-action:#7EA2FF/.test(sd) && /Content-Security-Policy[^>]*default-src 'none'/.test(sd), sd.slice(0, 400));
  const bf = await (await page.$('#view iframe.prev')).contentFrame();
  const bg = await bf.$eval('#b', (b) => getComputedStyle(b).backgroundColor);
  check('preview: the component renders with the document\'s color token', bg === 'rgb(23, 71, 201)', bg);
  check('preview: a hostile fragment cannot run script nor reach the page', (await page.evaluate(() => window.__pwn)) === undefined);
  check('preview: the oversized one says so, the one without preview has no frame',
        /Aperçu trop volumineux/.test(await text(page, '#view')) && /Seulement une description/.test(await text(page, '#view')));
  check('preview: height comes from the document, clamped', (await page.$$eval('#view iframe.prev', (fs) => fs.map((f) => f.style.height))).join() === '70px,60px');
  check('preview: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  // ---- overview sub-tabs: the board, then one tab per phase, addressed as #ensemble/<phase> ----
  const SUB_SNAP = snapshot([
    ticket(1, ['type:feature', 'level:story', 'status:draft', 'priority:P1']),
    ticket(2, ['type:tech', 'status:backlog', 'priority:P1']), ticket(3, ['type:tech', 'status:backlog', 'priority:P2']), ticket(4, ['type:tech', 'status:in-spec', 'priority:P1']),
    ticket(5, ['type:tech', 'status:dev-ready', 'priority:P1']), ticket(6, ['type:tech', 'status:dev-ready', 'priority:P0']), ticket(7, ['type:tech', 'status:dev-ready', 'priority:P2']),
    ticket(8, ['type:tech', 'status:in-dev', 'priority:P1']), ticket(9, ['type:tech', 'status:in-dev', 'priority:P1']), ticket(10, ['type:tech', 'status:changes-requested', 'priority:P1']),
    ticket(11, ['type:feature', 'level:story', 'status:qa', 'priority:P1']),
  ], 120);
  page = await open({ preload: [SUB_SNAP] });
  await page.click('nav >> text=Vue d’ensemble'); await page.waitForTimeout(200);
  const subLabels = () => page.$$eval('#subtabs a', (as) => as.map((a) => a.textContent));
  const subNow = () => page.$eval('#subtabs a[aria-current=page]', (a) => a.textContent);
  check('overview: a second row of tabs with the board first and a count per phase',
        JSON.stringify(await subLabels()) === JSON.stringify(['Tableau', 'Discovery (1)', 'Spec (3)', 'Dev (6)', 'Review (0)', 'QA humaine (1)']), JSON.stringify(await subLabels()));
  check('overview: the board is the default sub-tab', (await subNow()) === 'Tableau' && !!(await page.$('#view .board')));
  await page.click('#subtabs >> text=Dev'); await page.waitForTimeout(200);
  const grp = () => page.$$eval('#view h3.gh', (hs) => hs.map((h) => h.textContent));
  check('phase tab: only that phase\'s tickets, grouped by state in pipeline order, most urgent first',
        (await subNow()).startsWith('Dev') && !(await page.$('#view .board')) && (await rows(page)) === 6 &&
        JSON.stringify(await grp()) === JSON.stringify(['prêt à coder · 3', 'dev en cours · 2', 'corrections demandées · 1']) &&
        /#6 /.test((await page.$$eval('#view .row', (r) => r[0].textContent))), JSON.stringify(await grp()));
  check('phase tab: no ticket of another phase', !/Ticket 1\b/.test(await text(page, '#view')) && !/Ticket 11\b/.test(await text(page, '#view')));
  check('phase tab: the address follows (#ensemble/dev)', (await page.evaluate(() => location.hash)) === '#ensemble/dev');
  await page.screenshot({ path: path.join(TMP, 'subtabs.png') });
  await page.click('#subtabs >> text=Review'); await page.waitForTimeout(200);
  check('phase tab: an empty phase says so', /Aucun ticket dans cette phase/.test(await text(page, '#view')));
  await page.click('#subtabs >> text=Spec'); await page.waitForTimeout(200);
  await page.goBack(); await page.waitForTimeout(250);
  check('phase tab: the browser back button returns to the previous sub-tab', (await subNow()).startsWith('Review'), await subNow());
  await page.click('nav >> text=Ma file'); await page.waitForTimeout(200);
  check('sub-tabs are hidden, and empty, on a tab that has none', (await page.$eval('#subtabs', (e) => e.hidden)) && (await page.$$('#subtabs a')).length === 0);
  await page.click('nav >> text=Vue d’ensemble'); await page.waitForTimeout(200);
  check('coming back to the overview keeps the chosen sub-tab', (await subNow()).startsWith('Review'), await subNow());
  await page.evaluate((e) => window.__push('events', 'sub1', e), ev({ n: 5, title: 'Ticket 5', labels: ['type:tech', 'status:review-ready'] })); await page.waitForTimeout(250);
  check('a live update moves the ticket and the counts', (await subLabels()).includes('Dev (5)') && (await subLabels()).includes('Review (1)'), JSON.stringify(await subLabels()));
  check('overview sub-tabs: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();
  page = await open({ preload: [SUB_SNAP] });
  await page.goto(FILE + '#ensemble/spec'); await page.waitForTimeout(350);
  check('#ensemble/spec opens that phase directly', (await subNow()).startsWith('Spec') && (await rows(page)) === 3 && (await page.$eval('nav a[aria-current=page]', (a) => a.textContent)) === 'Vue d’ensemble');
  await page.close();
  const MANY2 = []; for (let n = 1; n <= 45; n++) MANY2.push(ticket(n, ['type:tech', 'status:dev-ready', 'priority:P2']));
  page = await open({ preload: [snapshot(MANY2, 120)] });
  await page.goto(FILE + '#ensemble/dev'); await page.waitForTimeout(350);
  check('phase tab: paginated like the other lists (20 per page)', (await rows(page)) === 20 && /Page 1 sur 3/.test(await text(page, '#view')));
  await page.close();

  // ---- sub-tabs of Design (one per section) and of Activité (sessions, changes) ----
  page = await open({ preload: [BASE], design: [DESIGN] });
  await page.goto(FILE + '#design'); await page.waitForTimeout(400);
  const dLabels = () => page.$$eval('#subtabs a', (as) => as.map((a) => a.textContent));
  const dNow = () => page.$eval('#subtabs a[aria-current=page]', (a) => a.textContent);
  check('design sub-tabs: one per section, with a count where there is one',
        JSON.stringify(await dLabels()) === JSON.stringify(['Charte', 'Couleurs (1)', 'Typographie (1)', 'Espacements (2)', 'Composants (1)', 'Accessibilité (1)']), JSON.stringify(await dLabels()));
  check('design sub-tabs: the charter is the default, alone on the page',
        (await dNow()) === 'Charte' && /Voyager sans obstacle/.test(await text(page, '#view')) && !/IBM Plex Sans/.test(await text(page, '#view')));
  await page.click('#subtabs >> text=Couleurs'); await page.waitForTimeout(200);
  check('design sub-tabs: a section shows only itself, the address follows',
        /clair #FFFFFF/.test(await text(page, '#view')) && !/Voyager sans obstacle/.test(await text(page, '#view')) && (await page.evaluate(() => location.hash)) === '#design/colors');
  await page.screenshot({ path: path.join(TMP, 'design-subtabs.png') });
  check('design sub-tabs: the edit card follows the open section (/pilot-design --section colors)', (await text(page, '#designCmd')) === '/pilot-design --section colors', await text(page, '#designCmd'));
  await page.click('#subtabs >> text=Accessibilité'); await page.waitForTimeout(200);
  check('design sub-tabs: moving on updates the section of the command', (await text(page, '#designCmd')) === '/pilot-design --section a11y' && /Contraste AA minimum/.test(await text(page, '#view')), await text(page, '#designCmd'));
  await page.close();
  page = await open({ preload: [BASE] });
  await page.goto(FILE + '#design'); await page.waitForTimeout(350);
  check('design sub-tabs: none while there is no document', (await page.$eval('#subtabs', (e) => e.hidden)) && (await page.$$('#subtabs a')).length === 0);
  await page.close();
  page = await open({ preload: [BASE], design: [DESIGN] });
  await page.goto(FILE + '#design/space'); await page.waitForTimeout(400);
  check('design sub-tabs: #design/space opens that section directly', (await dNow()).startsWith('Espacements') && /Espacement m/.test(await text(page, '#view')) && /Rayon s/.test(await text(page, '#view')));
  check('design sub-tabs: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  const ACT = { activity: [
    { kind: 'activity', id: 'dev-99-1', phase: 'dev', n: 99, title: 'Ticket vivant', mode: 'fresh', auto: true, by: 'alice', startedAt: iso(30), lastBeat: iso(3) },
    { kind: 'activity', id: 'spec-5-1', phase: 'spec', n: 5, title: 'Ticket muet', mode: 'fresh', auto: false, by: 'bob', startedAt: iso(300), lastBeat: iso(180) },
  ], events: [ev({ at: iso(2), action: 'claim:fresh' })] };
  page = await open(Object.assign({ preload: [BASE] }, ACT));
  await page.click('nav >> text=Activité'); await page.waitForTimeout(200);
  check('activity sub-tabs: sessions and changes, with their counts', JSON.stringify(await dLabels()) === JSON.stringify(['Sessions (2)', 'Changements (1)']), JSON.stringify(await dLabels()));
  check('activity sub-tabs: sessions first, without the changes', /Ticket vivant/.test(await text(page, '#view')) && !/pris en charge/.test(await text(page, '#view')));
  await page.click('#subtabs >> text=Changements'); await page.waitForTimeout(200);
  check('activity sub-tabs: the changes alone, the address follows', /pris en charge \(Dev\)/.test(await text(page, '#view')) && !/Ticket vivant/.test(await text(page, '#view')) && (await page.evaluate(() => location.hash)) === '#activite/changements');
  await page.close();
  page = await open(Object.assign({ preload: [BASE] }, ACT));
  await page.goto(FILE + '#activite/changements'); await page.waitForTimeout(400);
  check('activity sub-tabs: #activite/changements opens that sub-tab directly', (await dNow()).startsWith('Changements') && /pris en charge/.test(await text(page, '#view')));
  check('activity sub-tabs: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  // ---- prototypes tab: type:poc tickets joined to their metadata; sub-tabs En cours / Acceptés (3 more) / Rejetés ----
  const PSNAP = snapshot([
    ticket(701, ['type:poc', 'level:story', 'status:poc-draft'], { t: 'Proto brouillon' }),
    ticket(702, ['type:poc', 'level:story', 'status:poc-review'], { t: 'Proto à décider' }),
    ticket(703, ['type:poc', 'level:story', 'status:poc-validated'], { t: 'Proto accepté sans story' }),
    ticket(704, ['type:poc', 'level:story', 'status:poc-validated'], { t: 'Proto accepté avec stories' }),
    ticket(801, ['type:feature', 'level:story', 'status:in-dev'], { t: 'Story du proto 704' }),
  ], 120);
  const PM = (n, o = {}) => Object.assign({ kind: 'proto', n, repo: REPO, title: 'Proto ' + n, brief: 'Brief du proto ' + n, parts: 0, at: iso(60) }, o);
  const PROTOS = [
    PM(702, { title: 'Proto à décider', parts: 2, height: 300 }),
    PM(704, { title: 'Proto accepté avec stories', decision: 'accepted', decidedAt: iso(30), stories: [801, 802] }),
    PM(705, { title: 'Proto terminé', decision: 'accepted', decidedAt: iso(20), stories: [803] }),
    PM(706, { title: 'Proto rejeté', decision: 'rejected', decidedAt: iso(10), reason: 'Trop complexe pour le gain', parts: 1 }),
    PM(900, { repo: 'o/other', title: 'Proto d un autre projet' }),
  ];
  const PHTML = [
    { n: 702, k: 0, html: '<!doctype html><h1 id="t">Maquette A</h1><button id="b" onclick="document.getElementById(\'t\').textContent=\'cliqué\'">Cliquer</button>' },
    { n: 702, k: 1, html: '<p id="end">fin de la maquette</p><script>try{parent.__pwn=1}catch(e){document.body.setAttribute("data-blocked","1")}<\/script>' },
    { n: 706, k: 0, html: '<p>Maquette rejetée</p>' },
  ];
  page = await open({ preload: [PSNAP], protos: PROTOS, protoHtml: PHTML });
  const mainTabs = () => page.$$eval('nav#tabs a', (as) => as.map((a) => a.textContent));
  const pSubs = () => page.$$eval('#subtabs a', (as) => as.map((a) => a.textContent));
  const pSubs2 = () => page.$$eval('#subtabs2 a', (as) => as.map((a) => a.textContent));
  const pRows = () => page.$$eval('#view .row .t', (ts) => ts.map((t) => t.textContent));
  await page.click('nav >> text=Prototypes'); await page.waitForTimeout(250);
  check('prototypes: the third main tab, with the count of those in progress', JSON.stringify((await mainTabs()).slice(0, 4)) === JSON.stringify(['Ma file', 'Vue d’ensemble', 'Prototypes (2)', 'Recherche']), JSON.stringify(await mainTabs()));
  check('prototypes: sub-tabs En cours / Acceptés / Rejetés with their counts', JSON.stringify(await pSubs()) === JSON.stringify(['En cours (2)', 'Acceptés (3)', 'Rejetés (1)']), JSON.stringify(await pSubs()));
  check('prototypes: "En cours" lists the draft and the one to decide, not the others', JSON.stringify((await pRows()).map((x) => x.replace(/^#\d+ /, '')).sort()) === JSON.stringify(['Proto brouillon', 'Proto à décider']), JSON.stringify(await pRows()));
  check('prototypes: a draft is resumed, one under review is accepted or rejected (never sent to the Discovery yet) — all by command',
        JSON.stringify(await rowHrefs(701)) === JSON.stringify(['/pilot-proto --resume 701']) &&
        JSON.stringify(await rowHrefs(702)) === JSON.stringify(['/pilot-proto 702 --accept', '/pilot-proto 702 --reject']), JSON.stringify(await rowHrefs(702)));
  check('prototypes: no link to GitHub anywhere in the list', (await page.$$('#view a[href*="github.com"]')).length === 0);
  check('prototypes: the brief is shown', /Brief du proto 702/.test(await text(page, '#view')));
  check('prototypes: a prototype with no mockup says so; one with a mockup does not',
        /Pas de maquette enregistrée/.test(await page.locator('#view .row', { hasText: '#701 ' }).textContent()) && !/Pas de maquette enregistrée/.test(await page.locator('#view .row', { hasText: '#702 ' }).textContent()));
  await page.click('#subtabs >> text=Acceptés'); await page.waitForTimeout(200);
  check('prototypes: Acceptés has its own three sub-tabs, with counts', JSON.stringify(await pSubs2()) === JSON.stringify(['À lancer (1)', 'En cours (1)', 'Terminés (1)']), JSON.stringify(await pSubs2()));
  await page.screenshot({ path: path.join(TMP, 'protos.png') });
  check('prototypes: accepted and not started: only the Discovery and a rejection are offered', (await pRows()).join().includes('Proto accepté sans story') && JSON.stringify(await rowHrefs(703)) === JSON.stringify(['/pilot-discovery --from-proto 703', '/pilot-proto 703 --reject']), JSON.stringify(await rowHrefs(703)));
  await page.click('#subtabs2 >> text=En cours'); await page.waitForTimeout(200);
  check('prototypes: accepted with a story still open: in progress, its stories are listed',
        (await pRows()).join().includes('Proto accepté avec stories') && /2 stories : #801 #802/.test(await text(page, '#view')) && (await page.evaluate(() => location.hash)) === '#prototypes/acceptes/encours', await text(page, '#view'));
  await page.click('#subtabs2 >> text=Terminés'); await page.waitForTimeout(200);
  check('prototypes: accepted with no story left open: finished (it need not be an open ticket)', (await pRows()).join().includes('Proto terminé') && !/Lancer la Discovery/.test(await text(page, '#view')));
  await page.click('#subtabs >> text=Rejetés'); await page.waitForTimeout(200);
  check('prototypes: rejected ones stay, with their reason, and no third level', (await pRows()).join().includes('Proto rejeté') && /Raison : Trop complexe pour le gain/.test(await text(page, '#view')) && (await page.$$('#subtabs2 a')).length === 0);
  check('prototypes: another project\'s prototype is not shown', !/d un autre projet/.test(await page.textContent('body')));
  await page.goto(FILE + '#prototypes/encours'); await page.waitForTimeout(300);
  const row702 = page.locator('#view .row', { hasText: '#702 ' });
  await row702.locator('button:has-text("la maquette")').click(); await page.waitForTimeout(500);
  check('viewer: the mockup (read in two parts) is in an isolated frame that may run its own script only',
        (await page.$eval('#view iframe.prev', (f) => f.getAttribute('sandbox'))) === 'allow-scripts' && /Content-Security-Policy[^>]*default-src 'none'[^>]*script-src 'unsafe-inline'/.test(await page.$eval('#view iframe.prev', (f) => f.getAttribute('srcdoc'))) &&
        (await page.$eval('#view iframe.prev', (f) => f.style.height)) === '300px');
  const pf = await (await page.$('#view iframe.prev')).contentFrame();
  check('viewer: both parts are joined and the page is interactive', /fin de la maquette/.test(await pf.textContent('body')) && (await pf.$('#b')) !== null);
  await pf.click('#b'); await page.waitForTimeout(100);
  check('viewer: the mockup\'s own script works (click) but cannot reach the page', (await pf.textContent('#t')) === 'cliqué' && (await pf.$eval('body', (b) => b.getAttribute('data-blocked'))) === '1' && (await page.evaluate(() => window.__pwn)) === undefined);
  await row702.locator('button:has-text("la maquette")').click(); await page.waitForTimeout(100);
  check('viewer: hidden again on demand', (await page.$$('#view iframe.prev')).length === 0);
  await page.goto(FILE + '#prototypes'); await page.waitForTimeout(200);
  check('new prototype card: folded by default; command with the idea, and with the architect when asked',
        (await page.$eval('#protoNBody', (e) => e.hidden)) && (await page.$eval('#protoNew', (e) => !e.hidden)) && (await text(page, '#protoCmd')) === '/pilot-proto');
  await page.click('#protoNToggle'); await page.fill('#protoText', 'Choisir un itinéraire\nsans escalier'); await page.click('#protoWith'); await page.waitForTimeout(100);
  const pHref = async () => decodeURIComponent((await page.$eval('#protoOpen', (a) => a.getAttribute('href'))).split('?q=')[1].split('&repo=')[0]);
  check('new prototype card: /pilot-proto <idea> --with architect, and the link carries it', (await text(page, '#protoCmd')) === '/pilot-proto Choisir un itinéraire sans escalier --with architect' && (await pHref()) === (await text(page, '#protoCmd')), await text(page, '#protoCmd'));
  await page.click('#protoSrcImp'); await page.waitForTimeout(100);
  const openOff = () => page.$eval('#protoOpen', (a) => a.getAttribute('aria-disabled') === 'true');
  check('import: the address field replaces "with", and the link stays off until the address is a claude.ai artifact',
        !(await page.$eval('#protoUrlWrap', (e) => e.hidden)) && (await page.$eval('#protoWithWrap', (e) => e.hidden)) && (await openOff()));
  await page.fill('#protoUrl', 'https://evil.example/artifact/abc'); await page.waitForTimeout(50);
  check('import: another host is refused', await openOff());
  await page.fill('#protoUrl', 'https://claude.ai/artifact/UW8nJwYM98FHMFTsY15r1K'); await page.waitForTimeout(100);
  check('import: /pilot-proto --from-artifact <url> <note>, and the link carries it',
        (await text(page, '#protoCmd')) === '/pilot-proto --from-artifact https://claude.ai/artifact/UW8nJwYM98FHMFTsY15r1K Choisir un itinéraire sans escalier' && (await pHref()) === (await text(page, '#protoCmd')), await text(page, '#protoCmd'));
  await page.click('#protoSrcIdea'); await page.waitForTimeout(100);
  check('back to an idea: the architect option returns', !(await page.$eval('#protoWithWrap', (e) => e.hidden)) && (await text(page, '#protoCmd')).indexOf('--from-artifact') < 0);
  check('new prototype card hidden on the other tabs', (await tab(page, 'Recherche')) !== null && (await page.$eval('#protoNew', (e) => e.hidden)));
  await page.evaluate((d) => window.__push('protos', 'p702', Object.assign({}, d, { decision: 'accepted', decidedAt: new Date().toISOString() })), PM(702, { title: 'Proto à décider', parts: 2 }));
  await page.click('nav >> text=Prototypes'); await page.waitForTimeout(300);
  check('a live update moves a prototype: accepted, so one fewer in progress', JSON.stringify(await pSubs()) === JSON.stringify(['En cours (1)', 'Acceptés (4)', 'Rejetés (1)']), JSON.stringify(await pSubs()));
  check('prototypes: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();
  page = await open({ preload: [PSNAP], protos: PROTOS });
  await page.goto(FILE + '#prototypes/acceptes/termines'); await page.waitForTimeout(350);
  check('#prototypes/acceptes/termines opens that third level directly', (await pRows()).join().includes('Proto terminé') && (await page.$eval('#subtabs2 a[aria-current=page]', (a) => a.textContent)).startsWith('Terminés'));
  await tab(page, 'Recherche'); await page.fill('#searchText', '702'); await page.waitForTimeout(200);
  check('search shows a prototype with its state in words and the command to accept it, not the Discovery', /prototype à décider/.test(await text(page, '#view')) && JSON.stringify(await rowHrefs(702)) === JSON.stringify(['/pilot-proto 702 --accept', '/pilot-proto 702 --reject']), await text(page, '#view'));
  await page.close();
  page = await open({ preload: [BASE] });
  await page.goto(FILE + '#prototypes'); await page.waitForTimeout(300);
  check('prototypes: with none at all, a hint to start one', /Aucun prototype pour l’instant/.test(await text(page, '#view')) && /Prototypes$/.test((await mainTabs())[2]));
  await page.close();

  // ---- prototype in full screen: its own address, a way back, the whole screen for the frame ----
  page = await open({ preload: [PSNAP], protos: PROTOS, protoHtml: PHTML });
  await page.goto(FILE + '#prototypes'); await page.waitForTimeout(300);
  check('full view: only a prototype that has a mockup offers it', (await page.locator('#view .row', { hasText: '#702 ' }).locator('button:has-text("Plein écran")').count()) === 1 && (await page.locator('#view .row', { hasText: '#701 ' }).locator('button:has-text("Plein écran")').count()) === 0);
  await page.locator('#view .row', { hasText: '#702 ' }).locator('button:has-text("Plein écran")').click(); await page.waitForTimeout(500);
  check('full view: the address is #proto/<n> and the prototype is on its own, no sub-tabs and no card',
        (await page.evaluate(() => location.hash)) === '#proto/702' && (await page.$$('#subtabs a')).length === 0 && (await page.$eval('#protoNew', (e) => e.hidden)) && /#702 Proto à décider/.test(await text(page, '#view')));
  check('full view: the ticket banner is out of the way', await page.$eval('#banner', (e) => e.hidden));
  const big = await page.$eval('#view iframe.prev', (f) => f.getBoundingClientRect().height);
  await page.screenshot({ path: path.join(TMP, 'protofull.png') });
  check('full view: the frame takes the room of the screen, more than the list\'s 300 px', big >= 420, String(big));
  const ff = await (await page.$('#view iframe.prev')).contentFrame();
  check('full view: it is the same live mockup (its own script runs)', (await ff.click('#b'), await ff.textContent('#t')) === 'cliqué');
  await page.click('#view >> text=← Prototypes'); await page.waitForTimeout(300);
  check('full view: the way back returns to the list with its sub-tabs', (await page.evaluate(() => location.hash)) === '#prototypes' && (await page.$$('#subtabs a')).length === 3);
  await page.goto(FILE + '#proto/702'); await page.waitForTimeout(500);
  check('full view: a direct link #proto/702 opens it', /#702 Proto à décider/.test(await text(page, '#view')) && (await page.$('#view iframe.prev')) !== null && (await page.$eval('nav a[aria-current=page]', (a) => a.textContent)).startsWith('Prototypes'));
  await page.goto(FILE + '#proto/999'); await page.waitForTimeout(300);
  check('full view: an unknown prototype says so and offers the way back', /Prototype introuvable/.test(await text(page, '#view')) && (await page.$('#view >> text=← Prototypes')) !== null);
  check('full view: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  // ---- the Discovery only for an accepted prototype; the prototype visible from everywhere it matters ----
  const VSNAP = snapshot([
    ticket(710, ['type:poc', 'level:story', 'status:poc-review'], { t: 'Proto en revue' }),
    ticket(711, ['type:poc', 'level:story', 'status:poc-validated'], { t: 'Proto accepté' }),
    ticket(801, ['type:feature', 'level:story', 'status:backlog', 'priority:P1'], { t: 'Story issue du proto' }),
  ], 120);
  const VP = [PM(710, { title: 'Proto en revue', parts: 1 }), PM(711, { title: 'Proto accepté', decision: 'accepted', parts: 1 }), PM(712, { title: 'Proto source', decision: 'accepted', stories: [801], parts: 1 })];
  const VH = [710, 711, 712].map((n) => ({ n, k: 0, html: '<p id="t">Maquette ' + n + '</p>' }));
  page = await open({ preload: [VSNAP], protos: VP, protoHtml: VH });
  await page.goto(FILE + '#prototypes'); await page.waitForTimeout(300);
  const allHrefs = async () => (await page.$$eval('#view a.btn', (as) => as.map((a) => decodeURIComponent(a.href.split('?q=')[1] || '').split('&repo=')[0]))).join(' | ');
  check('discovery rule: a prototype under review offers Accepter / Rejeter and no Discovery', /pilot-proto 710 --accept/.test(await allHrefs()) && /pilot-proto 710 --reject/.test(await allHrefs()) && !/from-proto 710/.test(await allHrefs()), await allHrefs());
  await page.click('#subtabs >> text=Acceptés'); await page.waitForTimeout(250);
  check('discovery rule: the Discovery is offered once accepted', /pilot-discovery --from-proto 711/.test(await allHrefs()), await allHrefs());
  await tab(page, 'Recherche'); await page.fill('#searchText', 'proto'); await page.waitForTimeout(250);
  check('from everywhere: in Recherche a prototype is its prototype row (state, command, and its mockup one tap away)',
        (await page.locator('#view .row', { hasText: '#710 ' }).locator('button:has-text("Plein écran")').count()) === 1 && !/from-proto 710/.test(await allHrefs()));
  await page.locator('#view .row', { hasText: '#711 ' }).locator('button:has-text("la maquette")').click(); await page.waitForTimeout(500);
  check('from everywhere: the mockup opens in place from Recherche', (await page.$('#view iframe.prev')) !== null);
  await page.goto(FILE + '#file'); await page.click('#roleSeg >> text=Tous'); await page.waitForTimeout(250);
  const storyRow = page.locator('#view .row', { hasText: '#801 ' });
  check('from everywhere: a story created from a prototype offers it (Ma file)', (await storyRow.locator('button:has-text("Voir le proto")').count()) === 1);
  await storyRow.locator('button:has-text("Voir le proto")').click(); await page.waitForTimeout(500);
  check('from everywhere: it opens that prototype in full screen', (await page.evaluate(() => location.hash)) === '#proto/712' && /#712 Proto source/.test(await text(page, '#view')) && (await page.$('#view iframe.prev')) !== null);
  check('from everywhere: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.evaluate(() => { location.hash = 'file'; }); await page.waitForTimeout(100);
  await page.click('#roleSeg >> text=Produit'); await page.waitForTimeout(150);
  const myFile = await text(page, '#view');
  check('my queue (product): a prototype to decide and an accepted one to launch',
        /#710 Proto en revue/.test(myFile) && /#711 Proto accepté/.test(myFile) && /Accepter/.test(myFile) && /Lancer la Discovery/.test(myFile), myFile.slice(280, 700));
  await page.click('#roleSeg >> text=Tech'); await page.waitForTimeout(150);
  check('my queue (tech): no prototype', !/Proto en revue/.test(await text(page, '#view')));

  // reference page (#aide): the agents and the roster, kept in step with pilot-process.md §4 "Roster"
  await page.evaluate(() => { location.hash = 'file'; }); await page.waitForTimeout(100);
  check('reference page: a discreet info button, and the tab is untouched until it is used',
        (await text(page, '#helpLink')) === 'i' && (await page.$eval('#helpLink', (a) => a.getAttribute('href'))) === '#aide' && !(await page.$eval('#idea', (e) => e.hidden)));
  await page.click('#helpLink'); await page.waitForTimeout(150);
  check('reference page: its own page (#aide) with the 7 agents, replacing the tab content, no tab marked current',
        (await page.$$('#view .agents .row')).length === 7 && (await page.$$('#view button, #view a.btn')).length === 0 && (await page.$eval('#idea', (e) => e.hidden)) && (await page.$eval('#banner', (e) => e.hidden)) &&
        (await page.$$('#tabs a[aria-current="page"]')).length === 0 && (await page.$eval('#helpLink', (a) => a.getAttribute('aria-current'))) === 'page');
  check('reference page: sub-tabs Agents (open) and Steps; the agents are not mixed with the table',
        JSON.stringify(await page.$$eval('#subtabs a', (as) => as.map((a) => a.textContent + (a.getAttribute('aria-current') ? '*' : '')))) === JSON.stringify(['Agents*', 'Steps']) && (await page.$$('#view table')).length === 0);
  await page.click('#subtabs >> text=Steps'); await page.waitForTimeout(150);
  check('reference page: Steps shows the table and the rule, #aide/steps, no agent cards',
        (await page.evaluate(() => location.hash)) === '#aide/steps' && (await page.$$('#view table')).length === 1 && (await page.$$('#view .agents .row')).length === 0 && /le lead ouvre la discussion/.test(await text(page, '#view')));
  const docRows = fs.readFileSync(path.resolve(__dirname, '../assets/docs/pilot-process.md'), 'utf8').split('\n')
    .filter((l) => /^\| (Discovery|Spec|Dev|Review|QA|Proto|Design)\b/.test(l)).map((l) => l.split('|').slice(1, 5).map((c) => new Set((c.match(/pilot-(\w+)/g) || []).map((x) => x.slice(6)))));
  const KEYS = [['pm', 'PM'], ['architect', 'Architecte'], ['techlead', 'Tech lead'], ['dev', 'Dev'], ['e2e', 'E2E'], ['qa', 'QA'], ['designer', 'Designer']];
  const roster = (await page.$$eval('#view tbody tr', (trs) => trs.map((tr) => [...tr.querySelectorAll('td')].map((td) => td.textContent))))
    .map((cells) => cells.map((c) => new Set(KEYS.filter(([, n]) => new RegExp('\\b' + n + '\\b', 'i').test(c)).map(([k]) => k))));
  const same = (a, b) => a.size === b.size && [...a].every((x) => b.has(x));
  check('reference page: the roster has the same steps and the same personas per column as pilot-process.md',
        docRows.length === roster.length && docRows.every((d, i) => [0, 1, 2].every((k) => same(d[k + 1], roster[i][k]))), JSON.stringify([docRows.length, roster.length]));
  check('reference page: the table shows one row per step, with Lead, Validateur and Convocable',
        (await page.$$('#view tbody tr')).length === docRows.length && /Discovery[\s\S]*PM[\s\S]*Architecte[\s\S]*Designer/.test(await text(page, '#view tbody tr')));
  await page.click('#tabs >> text=Ma file'); await page.waitForTimeout(150);
  check('reference page: clicking another tab leaves it, no back button needed',
        (await page.evaluate(() => location.hash)) === '#file' && !(await page.$eval('#idea', (e) => e.hidden)) && /Ma file/.test(await text(page, '#view')) && (await page.$$('#subtabs a')).length === 0);

  // ---- wiki tab: the project's wiki document (built by `pilot.py wiki snapshot`), read-only ----
  const WIKI = { kind: 'wiki', repo: REPO, at: iso(20), total: 4, truncated: false, entries: [
    { id: 'search-by-name', title: 'Search places by name', description: 'A traveler searches places by name.', path: 'search/search-by-name.md', status: 'implemented', derived: 'verified', display: 'implemented · verified', tickets: [1], verifiedAt: iso(30), text: 'A traveler searches places <img src=x onerror="window.__pwn=1"> by part of their name.' },
    { id: 'sort-by-distance', title: 'Results are sorted by distance', description: 'Nearest first.', path: 'search/sort-by-distance.md', status: 'implemented', derived: '', display: 'implemented', tickets: [3], verifiedAt: '', text: 'Nearest place first.' },
    { id: 'default-text-output', title: 'Default output', description: 'One line per place.', path: 'output/default-text-output.md', status: 'specified', derived: 'in-review', display: 'specified · in-review', tickets: [12, 14], verifiedAt: '', text: 'One line per place.' },
    { id: 'old-rule', title: 'Old rule', description: 'Retired.', path: 'old-rule.md', status: 'deprecated', derived: '', display: 'deprecated', tickets: [], verifiedAt: '', text: '' }] };
  { let page = await open({ preload: [BASE] });
  await page.goto(FILE + '#wiki'); await page.waitForTimeout(350);
  check('wiki tab: empty state names the commands, no ticket banner', /Aucun wiki publié/.test(await text(page, '#view')) && /pilot-wiki --bootstrap/.test(await text(page, '#view')) && (await page.$eval('#banner', (e) => e.hidden)) && (await page.$eval('nav a[aria-current=page]', (a) => a.textContent)) === 'Wiki');
  await page.evaluate((d) => window.__push('wiki', 'w0', d), WIKI); await page.waitForTimeout(200);
  const wv = await text(page, '#view');
  check('wiki tab: the tab counts the entries, the page shows them grouped by page', (await page.$$eval('#tabs a', (a) => a.map((x) => x.textContent))).includes('Wiki (4)') && /search/.test(wv) && /Search places by name/.test(wv) && /A traveler searches places by name\./.test(wv) && /output/.test(wv), wv);
  check('wiki sub-tabs: Tous, then one per functional domain with its count',
        JSON.stringify(await page.$$eval('#subtabs a', (a) => a.map((x) => x.textContent))) === JSON.stringify(['Tous (4)', 'général (1)', 'output (1)', 'search (2)']), JSON.stringify(await page.$$eval('#subtabs a', (a) => a.map((x) => x.textContent))));
  check('wiki summary: one chip per status', /2 implémenté/.test(wv) && /1 spécifié/.test(wv) && /1 déprécié/.test(wv), wv);
  check('wiki entry chips: stamp, never verified, in-flight status, ticket link',
        /vérifié il y a|vérifié /.test(wv) && /non vérifié/.test(wv) && /en review/.test(wv) && (await page.$eval('#view a[href$="/issues/12"]', (a) => a.getAttribute('href'))) === 'https://github.com/' + REPO + '/issues/12');
  check('wiki: HTML in an entry stays text', (await page.$('#view [onerror]')) === null && (await page.evaluate(() => window.__pwn)) === undefined && (await page.$eval('#view details', (d) => d.textContent)).includes('<img src=x'));
  await page.click('#subtabs >> text=search'); await page.waitForTimeout(150);
  const wf = await text(page, '#view');
  check('wiki sub-tab: shows only that domain, the address follows', /Search places by name/.test(wf) && /sorted by distance/.test(wf) && !/Default output/.test(wf) && (await page.evaluate(() => location.hash)) === '#wiki/search', wf);
  await page.evaluate((d) => window.__push('wiki', 'w1', Object.assign({}, d, { repo: 'o/other', entries: [{ id: 'x', title: 'Autre projet', path: 'x/y.md', status: 'proposed', tickets: [], text: '' }] })), WIKI); await page.waitForTimeout(150);
  check('wiki: another repo\'s document is not shown', !/Autre projet/.test(await text(page, '#view')));
  check('wiki tab: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();
  page = await open({ preload: [BASE], wiki: [WIKI] });
  await page.goto(FILE + '#wiki/output'); await page.waitForTimeout(400);
  check('wiki: #wiki/<domain> opens that domain, a preloaded document is shown',
        /Default output/.test(await text(page, '#view')) && !/Search places by name/.test(await text(page, '#view')) && (await page.$eval('#subtabs a[aria-current=page]', (a) => a.textContent)).startsWith('output'));
  await page.evaluate(() => { location.hash = 'wiki/zzz'; }); await page.waitForTimeout(200);
  check('wiki: an unknown domain falls back to Tous', /Search places by name/.test(await text(page, '#view')) && /Default output/.test(await text(page, '#view')) && (await page.$eval('#subtabs a[aria-current=page]', (a) => a.textContent)).startsWith('Tous'));
  const wwide = [];
  for (const scheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme: scheme });
    for (const r of ['wiki', 'wiki/search', 'wiki/output']) {
      await page.evaluate((x) => { location.hash = x; }, r); await page.waitForTimeout(150);
      const w = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (w > 0) wwide.push(scheme + ' #' + r + ' (+' + w + 'px)');
    }
  }
  check('wiki tab fits a 400px phone, light and dark', wwide.length === 0 && page.errors.length === 0, wwide.join(', ') + ' ' + page.errors.join(' | '));
  await page.close();
  }

  // ---- architecture tab: the project's `architecture` document (built by `pilot.py arch snapshot`), read-only ----
  const ARCH = { kind: 'architecture', repo: REPO, at: iso(20), total: 4, truncated: false, entries: [
    { id: 'overview', title: 'Overview', description: 'The apps and how they relate.', path: 'overview.md', status: 'accepted', tickets: [], supersedes: '', supersededBy: '', text: 'One CLI <img src=x onerror="window.__pwn=1">.' },
    { id: 'layering', title: 'Layering', description: 'Domain never imports adapters.', path: 'guidelines/layering.md', status: 'accepted', tickets: [], supersedes: '', supersededBy: '', text: 'Domain never imports adapters.' },
    { id: '0001-compute', title: 'Catalog computed', description: 'Compute the catalog.', path: 'adr/0001-compute.md', status: 'superseded', tickets: [5], supersedes: '', supersededBy: '0002-store', text: '' },
    { id: '0002-store', title: 'Catalog stored', description: 'The catalog is stored, not computed.', path: 'adr/0002-store.md', status: 'accepted', tickets: [12], supersedes: '0001-compute', supersededBy: '', text: 'Stored.' }] };
  { let page = await open({ preload: [BASE] });
  await page.goto(FILE + '#architecture'); await page.waitForTimeout(350);
  check('architecture tab: empty state names the commands, no ticket banner', /Aucune architecture publiée/.test(await text(page, '#view')) && /pilot-architecture --bootstrap/.test(await text(page, '#view')) && (await page.$eval('#banner', (e) => e.hidden)) && (await page.$eval('nav a[aria-current=page]', (a) => a.textContent)) === 'Architecture');
  await page.evaluate((d) => window.__push('architecture', 'r0', d), ARCH); await page.waitForTimeout(200);
  const av = await text(page, '#view');
  check('architecture tab: counted in the tab, grouped by overview, rules and decisions', (await page.$$eval('#tabs a', (a) => a.map((x) => x.textContent))).includes('Architecture (4)') && /Vue d’ensemble/.test(av) && /Règles/.test(av) && /Décisions/.test(av) && /Catalog stored/.test(av), av);
  check('architecture sub-tabs: Tous, then one per group with its count',
        JSON.stringify(await page.$$eval('#subtabs a', (a) => a.map((x) => x.textContent))) === JSON.stringify(['Tous (4)', 'Vue d’ensemble (1)', 'Règles (1)', 'Décisions (2)']), JSON.stringify(await page.$$eval('#subtabs a', (a) => a.map((x) => x.textContent))));
  check('architecture summary and supersession chips', /3 accepté/.test(av) && /1 remplacé/.test(av) && /remplace 0001-compute/.test(av) && /remplacé par 0002-store/.test(av), av);
  check('architecture: ticket link, and HTML in an entry stays text', (await page.$eval('#view a[href$="/issues/12"]', (a) => a.getAttribute('href'))) === 'https://github.com/' + REPO + '/issues/12' && (await page.$('#view [onerror]')) === null && (await page.evaluate(() => window.__pwn)) === undefined);
  await page.click('#subtabs >> text=Décisions'); await page.waitForTimeout(150);
  const af = await text(page, '#view');
  check('architecture sub-tab: shows only that group, the address follows', /Catalog stored/.test(af) && !/Layering/.test(af) && (await page.evaluate(() => location.hash)) === '#architecture/adr', af);
  await page.evaluate((d) => window.__push('architecture', 'r1', Object.assign({}, d, { repo: 'o/other', entries: [{ id: 'x', title: 'Autre projet', path: 'overview.md', status: 'proposed', tickets: [], text: '' }] })), ARCH); await page.waitForTimeout(150);
  check('architecture: another repo\'s document is not shown', !/Autre projet/.test(await text(page, '#view')));
  check('architecture tab: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();
  page = await open({ preload: [BASE], architecture: [ARCH] });
  await page.goto(FILE + '#architecture/guidelines'); await page.waitForTimeout(400);
  check('architecture: #architecture/<group> opens that group from a preloaded document', /Layering/.test(await text(page, '#view')) && !/Catalog stored/.test(await text(page, '#view')));
  await page.evaluate(() => { location.hash = 'architecture/zzz'; }); await page.waitForTimeout(200);
  check('architecture: an unknown group falls back to Tous', /Layering/.test(await text(page, '#view')) && /Catalog stored/.test(await text(page, '#view')));
  const awide = [];
  for (const scheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme: scheme });
    for (const r of ['architecture', 'architecture/adr', 'architecture/guidelines']) {
      await page.evaluate((x) => { location.hash = x; }, r); await page.waitForTimeout(150);
      const w = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (w > 0) awide.push(scheme + ' #' + r + ' (+' + w + 'px)');
    }
  }
  check('architecture tab fits a 400px phone, light and dark', awide.length === 0 && page.errors.length === 0, awide.join(', ') + ' ' + page.errors.join(' | '));
  await page.close();
  }

  // ---- tabs follow the modules the snapshot says the project has on ----
  {
    const tabs = async (pg) => pg.$$eval('#tabs a', (a) => a.map((x) => x.textContent.replace(/ \(\d+\)$/, '')));
    const withMods = (m) => Object.assign({}, BASE, { modules: m });
    let page = await open({ preload: [withMods({ dashboard: true, wiki: false, architecture: false, design: false, proto: false })] });
    check('modules: a module that is off hides its tab (Design, Prototypes, Wiki, Architecture)',
          JSON.stringify(await tabs(page)) === JSON.stringify(['Ma file', 'Vue d’ensemble', 'Recherche', 'Activité']), JSON.stringify(await tabs(page)));
    await page.goto(FILE + '#design'); await page.waitForTimeout(350);
    check('modules: an address into a tab whose module is off falls back to the queue',
          (await page.$eval('nav a[aria-current=page]', (a) => a.textContent)) === 'Ma file' && !(await page.$eval('#idea', (e) => e.hidden)));
    await page.goto(FILE + '#proto/702'); await page.waitForTimeout(350);
    check('modules: a prototype address with the proto module off falls back too', (await page.$eval('nav a[aria-current=page]', (a) => a.textContent)) === 'Ma file');
    await page.evaluate((d) => window.__push('snapshots', 'Jonas-Eve__myavimobility', d), withMods({ dashboard: true, wiki: true, architecture: false, design: false, proto: true })); await page.waitForTimeout(250);
    check('modules: turning a module on shows its tab at the next snapshot, the others stay hidden',
          JSON.stringify(await tabs(page)) === JSON.stringify(['Ma file', 'Vue d’ensemble', 'Prototypes', 'Recherche', 'Activité', 'Wiki']), JSON.stringify(await tabs(page)));
    check('modules: no page errors', page.errors.length === 0, page.errors.join('|'));
    await page.close();
    page = await open({ preload: [BASE] });
    check('modules: a snapshot without the field shows every tab, as before',
          JSON.stringify(await tabs(page)) === JSON.stringify(['Ma file', 'Vue d’ensemble', 'Prototypes', 'Recherche', 'Activité', 'Design', 'Wiki', 'Architecture']), JSON.stringify(await tabs(page)));
    await page.close();
  }

  // every tab and sub-tab fits a phone, in both themes, with no script error
  const ROUTES = ['file', 'ensemble', 'ensemble/discovery', 'ensemble/spec', 'ensemble/dev', 'ensemble/review', 'ensemble/qa',
    'prototypes/encours', 'prototypes/acceptes/alancer', 'prototypes/acceptes/encours', 'prototypes/acceptes/termines', 'prototypes/rejetes', 'proto/702',
    'recherche', 'activite/sessions', 'activite/changements', 'aide/agents', 'aide/steps',
    'design/charter', 'design/colors', 'design/type', 'design/space', 'design/components', 'design/a11y'];
  const wide = [];
  for (const scheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme: scheme });
    for (const r of ROUTES) {
      await page.evaluate((x) => { location.hash = x; }, r); await page.waitForTimeout(150);
      const w = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (w > 0) wide.push(scheme + ' #' + r + ' (+' + w + 'px)');
    }
  }
  check('every tab and sub-tab fits a 400px phone, light and dark', wide.length === 0 && page.errors.length === 0, wide.join(', ') + ' ' + page.errors.join(' | '));
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
