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
  const out = fs.readFileSync(TEMPLATE, 'utf8').split('{{PROJECT_NAME}}').join(esc(name)).split('{{REPO}}').join(repo).split('{{PILOT_VERSION}}').join('1.2.3');
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
  check('fresh snapshot: counts and age shown, no stale warning', /1 tickets ouverts/.test(banner) && /instantané pris/.test(banner) && !/Instantané ancien/.test(banner), banner);
  check('fresh snapshot: a refresh button is always there (opens /pilot-dashboard --refresh), with its copy fallback',
        /Actualiser l’instantané/.test(banner) && /Copier \/pilot-dashboard --refresh/.test(banner) &&
        (await page.$$eval('#banner a.btn', (as) => as.map((a) => decodeURIComponent(a.href.split('?q=')[1].split('&repo=')[0])))).includes('/pilot-dashboard --refresh'), banner);
  check('the footer shows the PILOT version', (await text(page, '#version')) === 'Cockpit PILOT · v1.2.3', await text(page, '#version'));
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

  // ---- row options: --next and --multi behind a chevron ----
  const OPT_SNAP = snapshot([
    ticket(99, ['type:tech', 'status:dev-ready', 'priority:P0']), ticket(70, ['type:feature', 'status:review-ready', 'priority:P1']),
    ticket(60, ['type:tech', 'status:in-dev', 'priority:P1']), ticket(50, ['type:feature', 'status:qa', 'priority:P1']),
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
  check('bug: no --with choice, no --with in the command', (await page.$eval('#ideaWithWrap', (e) => e.hidden)) && !(await text(page, '#ideaCmd')).includes('--with'), await text(page, '#ideaCmd'));
  check('bug / tech need: no multi choice, no --multi in the command', (await page.$eval('#ideaMultiWrap', (e) => e.hidden)) && (await text(page, '#ideaCmd')) === '/pilot-spec --bug Mon idée', await text(page, '#ideaCmd'));
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
  view = await tab(page, 'Activité');
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

  // ---- renderer: the project name is HTML-escaped ----
  const escaped = render('A<b>"x"&y', 'o/r', path.join(TMP, 'escaped.html'));
  page = await browser.newPage(); await page.goto(escaped);
  check('renderer escapes the project name', (await page.textContent('h1')) === 'Cockpit A<b>"x"&y' && (await page.$('h1 b')) === null);
  await page.close();

  await browser.close();
  console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
  process.exit(results.every(Boolean) ? 0 : 1);
})();
