#!/usr/bin/env node
/* Browser test of assets/templates/pilot-dashboard.html.tmpl: renders it (as /pilot-dashboard does),
 * loads it in headless Chromium with a stubbed `window.claude` (an in-memory db with the
 * `snapshots`, `events`, `design`, `wiki`, `flowRuns`, `architecture`, `protos` and `protoHtml` collections) and checks the
 * snapshot view, the live ticket and run events, the board by status, the command each status launches, the runs, the module tabs,
 * the reference pages, the language switch and the renderer's HTML escaping.
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
  const names = ['snapshots', 'events', 'design', 'wiki', 'flowRuns', 'architecture', 'protos', 'protoHtml'];
  const data = {}; const listeners = {}; names.forEach((c) => { data[c] = {}; listeners[c] = []; });
  (OPTS.preload || []).forEach(d => { data.snapshots[d.repo.replace('/', '__')] = d; });
  (OPTS.events || []).forEach((d, k) => { data.events['e' + k] = d; });
  (OPTS.design || []).forEach((d, k) => { data.design['d' + k] = d; });
  (OPTS.wiki || []).forEach((d, k) => { data.wiki['w' + k] = d; });
  (OPTS.flowRuns || []).forEach((d, k) => { data.flowRuns['f' + k] = d; });
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
    const page = await browser.newPage({ viewport: { width: 400, height: 900 }, deviceScaleFactor: 1 });
    page.setDefaultTimeout(6000);
    page.errors = []; page.on('pageerror', e => page.errors.push(String(e)));
    if (opts.lang !== null) await page.addInitScript(`try{localStorage.setItem('cp.lang',${JSON.stringify(opts.lang || 'fr')})}catch(e){}`);
    await page.addInitScript(`try{localStorage.setItem('cp.role',${JSON.stringify(opts.role || 'tous')})}catch(e){}`);
    await page.addInitScript(`try{localStorage.setItem('cp.view',${JSON.stringify(opts.view || 'liste')})}catch(e){}`);
    await page.addInitScript(STUB(opts));
    await page.goto(file); await page.waitForTimeout(350);
    return page;
  };
  const text = (page, sel) => page.textContent(sel);
  const tab = async (page, name) => { try { await page.click(`nav >> text=${name}`, { timeout: 3000 }); } catch (e) { return ''; } await page.waitForTimeout(150); return text(page, '#view'); };
  const hrefs = (page, sel) => page.$$eval(sel, (as) => as.map((a) => ({ href: a.href, target: a.target, rel: a.rel, text: a.textContent.trim() })));
  const cmdOfHref = (h) => decodeURIComponent((h.split('?q=')[1] || h).split('&repo=')[0]);
  const trows = (page) => page.$$eval('#view > .list > .row', (r) => r.length);          // the tickets of the work list (runs are in their own section)
  const rowCmds = async (page, n) => (await page.locator('#view .row', { hasText: '#' + n + ' ' }).first().locator('a.btn').evaluateAll((as) => as.map((a) => decodeURIComponent((a.href.split('?q=')[1] || a.href).split('&repo=')[0]) + '|' + a.textContent.trim())));

  const WFSTEPS = JSON.parse(require('child_process').execFileSync('python3', ['-c', "import sys,json;sys.path.insert(0,'" + path.resolve(__dirname) + "');import pilot;print(json.dumps(pilot.workflow_steps(pilot.load_workflows())))"], { cwd: TMP }).toString());
  const BASE = snapshot([ticket(99, ['type:tech', 'level:task', 'status:ready', 'priority:P1'], { t: 'Ticket de l instantane' })], 120);
  const ev = (o) => ({ kind: 'ticket', n: 99, title: 'Ticket de l instantane', labels: ['type:tech', 'level:task', 'status:building'], assignees: ['alice'],
                       state: 'open', action: 'set', phase: 'build', by: 'alice', at: iso(5), ...o });
  const run = (o) => ({ kind: 'run', n: 99, workflow: 'build', step: 'implement', state: 'running', loops: {}, action: 'advance:ok', by: 'alice', at: iso(5), ...o });

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

  page = await open({ preload: [snapshot([ticket(1, ['status:ready'])], 60 * 30)] });
  let b = await text(page, '#banner');
  check('stale snapshot (> 24 h): hint and copy button for /pilot-dashboard --refresh', /Instantané ancien/.test(b) && /Copier \/pilot-dashboard --refresh/.test(b), b);
  await page.click('text=Copier /pilot-dashboard --refresh'); await page.waitForTimeout(200);
  check('copy button gives feedback instead of throwing', page.errors.length === 0 && /Copié|Copie impossible/.test(await text(page, '#banner')), page.errors.join('|'));
  await page.close();

  page = await open({});
  b = await text(page, '#banner');
  check('no snapshot: examples named as such, with the command to run', /Données d.exemple/.test(b) && /Aucun instantané/.test(b) && /Copier \/pilot-dashboard --refresh/.test(b), b);
  await page.close();

  // ---- live events fold over the snapshot ----
  page = await open({ preload: [BASE], events: [ev({})] });
  let view = await tab(page, 'Travail');
  check('ticket event newer than the snapshot moves the ticket (ready -> building)', /construction en cours/.test(view) && !/prêt à construire/.test(view), view);
  check('banner counts the applied change', /1 changement appliqué depuis/.test(await text(page, '#banner')), await text(page, '#banner'));
  await page.close();
  page = await open({ preload: [BASE], events: [ev({ at: iso(300) })] });
  view = await tab(page, 'Travail');
  check('event older than the snapshot is ignored', /prêt à construire/.test(view) && !/construction en cours/.test(view), view);
  await page.close();
  page = await open({ preload: [BASE], events: [ev({ state: 'closed', labels: ['status:done'] })] });
  check('closed event removes the ticket', !/Ticket de l instantane/.test(await tab(page, 'Travail')));
  await page.close();
  page = await open({ preload: [BASE], events: [ev({ n: 7, title: 'Nouveau ticket', labels: ['type:feature', 'level:story', 'status:to-plan'], assignees: [], parent: 99, pr: 12 })] });
  view = await tab(page, 'Travail');
  check('event for a ticket absent from the snapshot adds it, with its parent and PR', /Nouveau ticket/.test(view) && /à planifier/.test(view) && /PR #12/.test(view) && /Sous-tickets \(1\)/.test(view), view);
  await page.close();
  page = await open({ preload: [BASE], events: [ev({ at: iso(30) }), ev({ at: iso(2), labels: ['type:tech', 'level:task', 'status:reviewing'], assignees: [] })] });
  view = await tab(page, 'Travail');
  check('latest event per ticket wins', /relecture en cours/.test(view) && !/construction en cours/.test(view), view);
  await page.close();
  page = await open({ preload: [BASE] });
  check('before the pushed event: ready', /prêt à construire/.test(await tab(page, 'Travail')));
  await page.evaluate((e) => window.__push('events', 'live1', e), ev({}));
  await page.waitForTimeout(200);
  check('real time: a pushed event updates the list without reload', /construction en cours/.test(await text(page, '#view')) && !/prêt à construire/.test(await text(page, '#view')));
  check('real time: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  // ---- the work view: every status leads to the skill of the workflow that takes it ----
  const V6 = snapshot([
    ticket(10, ['type:feature', 'level:epic', 'status:planned'], { t: 'Epic planifié', k: [1, 3] }),
    ticket(11, ['type:feature', 'level:story', 'status:forming'], { t: 'Story en formation', p: 10 }),
    ticket(12, ['type:feature', 'level:story', 'status:to-plan', 'priority:P0'], { t: 'Story à planifier' }),
    ticket(13, ['type:tech', 'level:story', 'status:planning', 'can-resume'], { t: 'Story en planification', a: 'alice' }),
    ticket(14, ['type:feature', 'level:story', 'status:planned'], { t: 'Story découpée', k: [1, 2] }),
    ticket(15, ['type:feature', 'level:task', 'status:ready', 'priority:P1'], { t: 'Tâche prête', p: 14 }),
    ticket(16, ['type:tech', 'level:task', 'status:building'], { t: 'Tâche en cours', p: 14, a: 'bob' }),
    ticket(17, ['type:tech', 'level:task', 'status:reviewing'], { t: 'Tâche en relecture', r: 55 }),
    ticket(18, ['type:feature', 'level:story', 'status:merged'], { t: 'Story fusionnée' }),
    ticket(19, ['type:tech', 'level:task', 'status:ready', 'needs-human'], { t: 'Tâche bloquée' }),
    ticket(20, ['type:tech', 'level:story', 'status:ready', 'on-hold'], { t: 'Story en pause' }),
    ticket(21, ['type:feature', 'level:task', 'status:ready', 'fix', 'gap', 'express'], { t: 'Tâche drapeaux' }),
    ticket(30, ['run:proto'], { t: 'run:proto Mon proto' }),
    ticket(31, ['run:technical-frame', 'needs-human'], { t: 'run:technical-frame Une règle' }),
  ], 120);
  V6.workflows = ['accept', 'build', 'express', 'need', 'plan', 'proto', 'report'];
  V6.workflowSteps = WFSTEPS;
  page = await open({ preload: [V6] });
  view = await tab(page, 'Travail');
  check('work list: the tickets, run issues left out (12 tickets)', (await trows(page)) === 12 && /Travail · 12/.test(view) && !/Mon proto/.test(view.split('Runs en cours')[0] || ''), view.slice(0, 200));
  const cmd = async (n) => (await rowCmds(page, n)).map((x) => x.split('|')[0]);
  check('forming: /pilot-need (no number)', (await cmd(11)).includes('/pilot-need'), JSON.stringify(await cmd(11)));
  check('to-plan: /pilot-plan <n>', (await cmd(12)).includes('/pilot-plan 12'), JSON.stringify(await cmd(12)));
  check('planning: /pilot-plan --resume <n>', (await cmd(13)).includes('/pilot-plan --resume 13'), JSON.stringify(await cmd(13)));
  check('ready: /pilot-build <n>', (await cmd(15)).includes('/pilot-build 15'), JSON.stringify(await cmd(15)));
  check('building and reviewing: /pilot-build --resume <n>', (await cmd(16)).includes('/pilot-build --resume 16') && (await cmd(17)).includes('/pilot-build --resume 17'), JSON.stringify([await cmd(16), await cmd(17)]));
  check('merged: /pilot-accept <n>', (await cmd(18)).includes('/pilot-accept 18'), JSON.stringify(await cmd(18)));
  check('planned (a container) and an epic: no command, only GitHub', (await cmd(14)).every((c) => !/\/pilot-/.test(c)) && (await cmd(10)).every((c) => !/\/pilot-/.test(c)), JSON.stringify([await cmd(14), await cmd(10)]));
  check('needs-human: a reply on GitHub, no command; on-hold: only a look on GitHub', /Répondre sur GitHub/.test((await rowCmds(page, 19)).join()) && !(await cmd(19)).some((c) => /\/pilot-/.test(c)) && !(await cmd(20)).some((c) => /\/pilot-/.test(c)) && /Voir sur GitHub/.test((await rowCmds(page, 20)).join()));
  const rowText = (n) => page.locator('#view .row', { hasText: '#' + n + ' ' }).first().textContent();
  check('flags are chips: needs-human, on-hold, can-resume, fix, gap, express', /attend un humain/.test(await rowText(19)) && /en pause/.test(await rowText(20)) && /reprise possible/.test(await rowText(13)) && /correction/.test(await rowText(21)) && /en écart/.test(await rowText(21)) && /express/.test(await rowText(21)));
  check('the command is shown on its row, with the status in words', /\/pilot-build 15/.test(await rowText(15)) && /prêt à construire/.test(await rowText(15)));
  check('the open PR links to GitHub', (await hrefs(page, '#view .row a:has-text("PR #55")')).length === 1);
  const groups = await page.$$eval('#view > .list > h2', (h) => h.map((x) => x.textContent));
  check('groups: action awaited, in progress, to launch, paused, no action', groups.some((g) => /^Action humaine attendue/.test(g)) && groups.some((g) => /^En cours/.test(g)) && groups.some((g) => /^À lancer/.test(g)) && groups.some((g) => /^En pause/.test(g)) && groups.some((g) => /^Sans action/.test(g)), JSON.stringify(groups));
  check('work view: no pilot-auto, no removed phase command anywhere', !/\/pilot-(auto|discovery|spec|dev|review|qa)\b/.test(await page.content()));
  const tiles = await page.$$eval('#view .tile', (t) => t.map((x) => x.textContent));
  check('counters: blocked, forming, to plan, to build, to accept', JSON.stringify(tiles) === JSON.stringify(['1bloqués', '1en formation', '1à planifier', '2à construire', '1à recetter']), JSON.stringify(tiles));
  await page.click('#view .tile >> text=à construire'); await page.waitForTimeout(150);
  check('a counter is a filter: the ready tickets that are neither blocked nor paused', (await trows(page)) === 2, String(await trows(page)));
  await page.click('#view .tile >> text=à construire'); await page.waitForTimeout(150);
  check('clicking it again lifts the filter', (await trows(page)) === 12);
  check('no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.screenshot({ path: path.join(TMP, 'work.png') });
  await page.close();

  // ---- a workflow the snapshot does not list gives no command, no request kind, no help card ----
  { const NARROW = Object.assign({}, V6, { workflows: ['need', 'build'] });
    const pg = await open({ preload: [NARROW] });
    await tab(pg, 'Travail');
    const c = async (n) => (await rowCmds(pg, n)).map((x) => x.split('|')[0]);
    check('workflows listed by the snapshot: only their statuses lead to a command', (await c(11)).includes('/pilot-need') && (await c(15)).includes('/pilot-build 15') && !(await c(12)).some((x) => /\/pilot-plan/.test(x)) && !(await c(18)).some((x) => /\/pilot-accept/.test(x)), JSON.stringify([await c(12), await c(18)]));
    await pg.click('#ideaToggle');
    check('workflows listed by the snapshot: only their request kinds are offered', JSON.stringify(await pg.$$eval('#kindSeg button', (b) => b.map((x) => x.textContent))) === JSON.stringify(['Besoin produit']), JSON.stringify(await pg.$$eval('#kindSeg button', (b) => b.map((x) => x.textContent))));
    await pg.goto(FILE + '#aide/workflows'); await pg.waitForTimeout(250);
    const hv = await text(pg, '#view');
    check('workflows listed by the snapshot: the help lists only those', /\/pilot-need/.test(hv) && /\/pilot-build/.test(hv) && !/\/pilot-plan/.test(hv) && !/\/pilot-express/.test(hv), hv.slice(0, 200));
    await pg.close(); }

  // ---- runs: the events of kind run, and the open run issues ----
  { const RUNS = [
      run({ n: 16, workflow: 'build', step: 'implement', state: 'running', loops: { check: 1, judge: 1 } }),
      run({ n: 13, workflow: 'plan', step: 'ask', state: 'waiting-human', at: iso(3) }),
      run({ n: 40, workflow: 'need', step: 'gate', state: 'waiting-human', at: iso(2) }),
      run({ n: 41, workflow: 'accept', step: 'gate', state: 'failed', at: iso(1) }),
      run({ n: 42, workflow: 'plan', step: 'end', state: 'done', at: iso(1) }),
      run({ n: 31, workflow: 'technical-frame', step: 'gate', state: 'waiting-human', at: iso(1) }),
      run({ n: 43, workflow: 'design-system', step: 'gate', state: 'waiting-human', at: iso(1) }),
    ];
    const pg = await open({ preload: [V6], events: RUNS });
    await tab(pg, 'Travail');
    const sec = () => text(pg, '#view section[aria-label="Runs en cours"]');
    const rr = (n) => pg.locator('#view section[aria-label="Runs en cours"] .row', { hasText: '#' + n + ' ' }).first();
    const rc = async (n) => (await rr(n).locator('a.btn').evaluateAll((as) => as.map((a) => decodeURIComponent((a.href.split('?q=')[1] || a.href).split('&repo=')[0]) + '|' + a.textContent.trim())));
    const s = await sec();
    check('runs: only the ticket workflows, the ones not done; no admin workflow (proto, technical-frame, design-system)', /Runs en cours · 4/.test(s) && !/#42 /.test(s) && !/#30 |#31 |#43 /.test(s) && !/Prototype|Cadre technique|Design system/.test(s), s.slice(0, 300));
    check('runs: workflow, step and state on each row; loops counted', /Réalisation/.test(await rr(16).textContent()) && /implement/.test(await rr(16).textContent()) && /en cours/.test(await rr(16).textContent()) && /2 boucles/.test(await rr(16).textContent()) && /échoué/.test(await rr(41).textContent()));
    check('runs: the title is the ticket\'s, else the workflow\'s', /Tâche en cours/.test(await rr(16).textContent()) && /Besoin/.test(await rr(40).textContent()));
    check('runs: a run in progress is not resumed (it may be alive), unless its ticket can-resume', !(await rc(16)).some((c) => /--resume/.test(c)));
    check('runs: a waiting or failed run is resumed with --resume', (await rc(40)).some((c) => c.startsWith('/pilot-need --resume 40|')) && (await rc(41)).some((c) => c.startsWith('/pilot-accept --resume 41|')) && (await rc(13)).some((c) => c.startsWith('/pilot-plan --resume 13|')), JSON.stringify([await rc(40), await rc(41)]));
    // the workflow timeline of a run
    await rr(16).locator('button:has-text("Workflow")').click(); await pg.waitForTimeout(150);
    const tl = pg.locator('#view section[aria-label="Runs en cours"] .row', { hasText: '#16 ' }).first().locator('.tl');
    const lis = await tl.locator('li').evaluateAll((l) => l.map((x) => x.className.split(' ')[0]));
    const ids = WFSTEPS.build.map((x) => x.id);
    const at = ids.indexOf('implement');
    check('timeline: the steps of the workflow, those before the current one done, the current marked, the rest upcoming', lis.length === ids.length && lis.slice(0, at).every((c) => c === 'done') && lis[at] === 'cur' && lis.slice(at + 1).every((c) => c === 'next') && (await tl.locator('li[aria-current=step]').count()) === 1, JSON.stringify(lis));
    const curText = await tl.locator('li.cur').textContent();
    check('timeline: who acts is shown (the persona of the current step, human, validator, judge, check kinds)', /dev/i.test(curText) && /Dev/.test(curText) && /humain/.test(await tl.textContent()) && /validateur/.test(await tl.textContent()) && /juge/.test(await tl.textContent()) && /contrôle/.test(await tl.textContent()));
    check('timeline: the loops of a step are counted on it', /1 boucle\b/.test(await tl.locator('li', { hasText: 'Code checks' }).first().textContent()) && !/boucle/.test(await tl.locator('li.cur').textContent()), await tl.textContent());
    check('timeline: a running run awaits nothing', !/Attendu/.test(await tl.textContent()));
    await rr(16).locator('button:has-text("Workflow")').click(); await pg.waitForTimeout(100);
    check('timeline: the button folds it again', (await pg.locator('#view .tl').count()) === 0);
    await rr(40).locator('button:has-text("Workflow")').click(); await pg.waitForTimeout(150);
    const tw = pg.locator('#view section[aria-label="Runs en cours"] .row', { hasText: '#40 ' }).first();
    check('timeline: a run waiting for a human says what is awaited at its current gate', /Attendu : décision humaine à ce gate/.test(await tw.locator('li.cur').textContent()) && (await tw.locator('li.cur.wait').count()) === 1, await tw.locator('li.cur').textContent());
    await rr(41).locator('button:has-text("Workflow")').click(); await pg.waitForTimeout(150);
    check('timeline: a failed run says it failed at the current step', /échoué/.test(await rr(41).locator('li.cur').textContent()));
    check('timeline: a step titled from the workflow data', (await tw.locator('li').first().textContent()).includes('1. ' + WFSTEPS.need[0].title));
    { const nw = await open({ preload: [Object.assign({}, V6, { workflowSteps: undefined })], events: RUNS }); await tab(nw, 'Travail');
      check('runs: the Workflow button is hidden when the snapshot has no workflowSteps', (await nw.locator('#view button:has-text("Workflow")').count()) === 0);
      await nw.close(); }
    check('a ticket with a run shows it on its row', /run build · implement/.test(await pg.locator('#view > .list > .row', { hasText: '#16 ' }).first().textContent()));
    check('a run waiting for a human puts its ticket in the human group', (await pg.$$eval('#view > .list > h2', (h) => h.map((x) => x.textContent))).some((g) => /^Action humaine attendue · 2/.test(g)));
    const pgc = await open({ preload: [V6], events: [run({ n: 16, state: 'running' })] });
    await pgc.evaluate((e) => window.__push('events', 'l2', e), run({ n: 41, workflow: 'build', step: 'merge', state: 'waiting-human', at: iso(0) })); await pgc.waitForTimeout(250);
    check('runs: a pushed run event shows without reload', /#41 /.test(await text(pgc, '#view section[aria-label="Runs en cours"]')));
    await pgc.close();
    check('runs: no page errors', pg.errors.length === 0, pg.errors.join('|'));
    await pg.screenshot({ path: path.join(TMP, 'runs.png') });
    await pg.close();
    const none = await open({ preload: [BASE] });
    check('no run: no runs section', (await none.$('#view section[aria-label="Runs en cours"]')) === null);
    await none.close(); }

  // ---- the board: one column per status in workflow order, under a band per stage ----
  const COLS = ['en formation', 'à planifier', 'planification en cours', 'planifié', 'prêt à construire', 'construction en cours', 'relecture en cours', 'fusionné, à recetter'];
  page = await open({ preload: [V6], view: 'board' });
  await tab(page, 'Travail');
  const cols = () => page.$$eval('#view .board section.col:not(.done-fold)', (e) => e.map((x) => x.getAttribute('aria-label')));
  const stage = (name) => page.locator(`#view .board section.col[aria-label="${name}"]`);
  const bands = (pg = page) => pg.$$eval('#view .board button.band', (e) => e.map((x) => x.textContent.replace(/^[▾▸]/, '')));
  const card = (n) => page.locator('#view .board .card', { has: page.locator(`.t a[href="#file/${n}"]`) });
  const cnt = (name) => stage(name).locator('.card').count();
  check('board: one column per status, in workflow order', JSON.stringify(await cols()) === JSON.stringify(COLS), JSON.stringify(await cols()));
  check('board: a thin band per stage above its columns', JSON.stringify(await bands()) === JSON.stringify(['À cadrer', 'En conception', 'En réalisation', 'À recetter']), JSON.stringify(await bands()));
  { const g = await page.$$eval('#view .board button.band', (b) => b.map((x) => x.style.gridColumn)); check('board: each band spans its columns (2, 2, 3, 1)', JSON.stringify(g) === JSON.stringify(['1 / span 2', '3 / span 2', '5 / span 3', '8 / span 1']), JSON.stringify(g)); }
  { const pos = await page.$$eval('#view .board section.col', (s) => s.map((x) => Math.round(x.getBoundingClientRect().left))); check('board: columns sit side by side, left to right', pos.every((x, i) => i === 0 || x > pos[i - 1]), JSON.stringify(pos)); }
  { const w = await page.$$eval('#view .board section.col', (s) => s.map((x) => Math.round(x.getBoundingClientRect().width))); check('board: wide columns are at least 200px', w.every((x) => x >= 199), JSON.stringify(w)); }
  check('board: the columns hold their statuses', (await cnt('en formation')) + (await cnt('à planifier')) === 2 && (await cnt('planification en cours')) + (await cnt('planifié')) === 3 && (await cnt('prêt à construire')) + (await cnt('construction en cours')) + (await cnt('relecture en cours')) === 6 && (await cnt('fusionné, à recetter')) === 1,
        JSON.stringify(await Promise.all(COLS.map((n) => cnt(n)))));
  check('board: the card has no status chip (the column is the status)', !/prêt à construire|construction en cours|relecture en cours|planification en cours/.test(await text(page, '#view .board .card')) && (await card(15).locator('.chip').count()) === 0);
  check('board: the sticky header of a column holds its name, blocked and count', (await stage('construction en cours').locator('.sh .chip.warn').count()) + (await stage('relecture en cours').locator('.sh .chip.warn').count()) + (await stage('prêt à construire').locator('.sh .chip.warn').count()) === 1 && /\d/.test(await stage('prêt à construire').locator('.sh .chips').textContent()) && (await page.$$eval('#view .board section.col:not(.shut) .sh', (h) => h.every((x) => getComputedStyle(x).position === 'sticky'))));
  { const b = page.locator('#view .board'); const sc = await b.evaluate((e) => { e.scrollTop = 0; return e.scrollHeight > e.clientHeight; });
    if (sc) { await b.evaluate((e) => { e.scrollTop = 60; }); const t0 = await b.evaluate((e) => e.getBoundingClientRect().top), t1 = await page.locator('#view .board section.col .sh').first().evaluate((e) => e.getBoundingClientRect().top); check('board: the header stays visible when the board scrolls', t1 - t0 < 80, String(t1 - t0)); await b.evaluate((e) => { e.scrollTop = 0; }); }
    else check('board: (no vertical overflow with the demo data, sticky checked by style)', true); }
  check('board: no run issue as a card, nor a done strip when nothing is done', !/Mon proto/.test(await text(page, '#view .board')) && (await page.locator('#view .done-fold').count()) === 0);
  check('board: epics are cards, at their own stage, with progress and the epic filter', (await stage('planifié').locator('.card.epic', { hasText: 'Epic planifié' }).count()) === 1 && (await card(10).locator('.bar').count()) === 1 && /1\/3/.test(await card(10).textContent()) && (await card(10).locator('button:has-text("Filtrer sur cette epic")').count()) === 1);
  check('board: a parent and its children are all shown (epic, its story, a split story and its tasks)', (await Promise.all([10, 11, 14, 15, 16].map((n) => card(n).count()))).every((c) => c === 1));
  check('board: a card is compact: number, title, at most one action, one chip only when it adds information, no command, no flag chips', (await card(15).locator('.acts > *').count()) === 1 && !/\/pilot-/.test(await card(15).textContent()) && (await card(19).locator('.chip').count()) === 1 && (await card(21).locator('.chip').count()) === 0 && !/correction|en écart|express/.test(await card(21).textContent()));
  check('board: a card launches its command (its one action)', (await card(15).locator('a.btn').evaluateAll((as) => as.map((a) => decodeURIComponent((a.href.split('?q=')[1] || a.href).split('&repo=')[0])))).includes('/pilot-build 15') && (await card(18).locator('a.btn').evaluateAll((as) => as.map((a) => decodeURIComponent((a.href.split('?q=')[1] || a.href).split('&repo=')[0])))).includes('/pilot-accept 18'));
  check('board: a blocked card is flagged and answers on GitHub; a paused or container card has no action', (await page.locator('#view .board .card.flag', { hasText: 'Tâche bloquée' }).count()) === 1 && /Répondre sur GitHub/.test(await card(19).textContent()) && (await card(20).locator('.acts').count()) === 0 && (await card(14).locator('.acts').count()) === 0);
  check('board: the title opens the ticket page, where the details are', (await card(15).locator('.t a').getAttribute('href')) === '#file/15' && (await card(16).locator('.up').count()) === 1 && /#14/.test(await card(16).locator('.up').textContent()));
  check('board: a card fits its column', await card(15).evaluate((e) => e.scrollWidth <= e.clientWidth + 1));
  await page.click('#filtersToggle'); await page.click('#searchFilters button[data-map="levels"][data-key="task"]'); await page.waitForTimeout(150);
  check('board: filtering on tasks keeps the columns a task can have (ready to merged) and their cards', JSON.stringify(await cols()) === JSON.stringify(COLS.slice(4)) && (await page.locator("#view .board .card").count()) === 5, JSON.stringify(await cols()) + await page.locator('#view .board .card').count());
  await page.click('#searchFilters button[data-map="levels"][data-key="task"]'); await page.click('#searchFilters button[data-map="levels"][data-key="epic"]'); await page.waitForTimeout(150);
  check('board: filtering on epics shows the epic statuses only (forming to planned), the epic present', JSON.stringify(await cols()) === JSON.stringify(COLS.slice(0, 4)) && (await page.locator('#view .board .card').count()) === 1 && (await bands()).join() === 'À cadrer,En conception', JSON.stringify(await cols()));
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(150);
  await card(10).locator('button:has-text("Filtrer sur cette epic")').click(); await page.waitForTimeout(150);
  check('board: filtering on an epic keeps it and its tickets', /Story en formation/.test(await text(page, '#view .board')) && !/Story à planifier/.test(await text(page, '#view .board')));
  await card(10).locator('button:has-text("Tout afficher")').click(); await page.waitForTimeout(150);
  await page.click('#view .seg button:has-text("Liste")'); await page.waitForTimeout(150);
  check('list is the other display, and the choice is remembered', (await trows(page)) === 12 && (await page.evaluate(() => localStorage.getItem('cp.view'))) === 'liste');
  check('board: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();
  page = await open({ preload: [Object.assign({}, V6, { issues: V6.issues.concat([ticket(50, ['type:feature', 'level:story', 'status:done'], { t: 'Story terminée' }), ticket(51, ['type:feature', 'level:story', 'status:wont-do'], { t: 'Story écartée' })]) })], view: 'board' });
  await tab(page, 'Travail');
  check('board: done and dropped are a collapsed strip at the end, with their count', /Terminés \(2\)/.test(await page.locator('#view .done-fold button').getAttribute('title')) && !/Story terminée/.test(await text(page, '#view')) && (await page.$$eval('#view .board > section', (s) => s[s.length - 1].classList.contains('done-fold'))), await text(page, '#view .done-fold'));
  await page.click('#view .done-fold button'); await page.waitForTimeout(150);
  check('board: one click shows them', /Story terminée/.test(await text(page, '#view .done-fold')) && /Story écartée/.test(await text(page, '#view .done-fold')));
  await page.close();

  // ---- the board by role: the stages a role does not own stay in place as narrow columns ----
  { const st = async (pg) => pg.$$eval('#view .board section.col:not(.done-fold)', (ss) => ss.map((x) => (x.classList.contains('shut') ? 'n' : 'w')).join(''));
    const pos = async (pg) => pg.$$eval('#view .board section.col:not(.done-fold)', (ss) => ss.map((x) => x.getAttribute('aria-label')));
    let pg = await open({ preload: [V6], view: 'board', role: 'produit' });
    await tab(pg, 'Travail');
    check('role Produit: To frame and To accept wide, In design and In build narrow, all eight columns still in order', (await st(pg)) === 'wwnnnnnw' && JSON.stringify(await pos(pg)) === JSON.stringify(COLS), await st(pg));
    { const nw = await pg.$$eval('#view .board section.col.shut', (ss) => ss.map((x) => Math.round(x.getBoundingClientRect().width))); check('role Produit: a narrow column is a slim strip', nw.length === 5 && nw.every((x) => x <= 60), JSON.stringify(nw)); }
    check('role Produit: a narrow column shows only its count and vertical name, no card', (await pg.locator('#view .board section.col.shut .card').count()) === 0 && /\d/.test(await pg.locator('#view .board section.col[aria-label="construction en cours"] button.sh').textContent()) && (await pg.locator('#view .board section.col.shut .nm.vert').count()) === 5);
    check('role Produit: the band of a narrow stage stays above it', (await bands(pg)).length === 4 && (await pg.locator('#view .board button.band.shut').count()) === 2);
    await pg.click('#view .board section.col[aria-label="planifié"] button.sh'); await pg.waitForTimeout(120);
    check('role Produit: one click on a narrow column widens it (its stage), position kept', (await st(pg)) === 'wwwwnnnw' && JSON.stringify(await pos(pg)) === JSON.stringify(COLS) && (await pg.locator('#view .board section.col[aria-label="planifié"] .card').count()) > 0, await st(pg));
    await pg.click('#roleSeg >> text=Tech'); await pg.waitForTimeout(150);
    check('role Tech: In design and In build wide, To frame and To accept narrow', (await st(pg)) === 'nnwwwwwn', await st(pg));
    await pg.click('#view .board button.band[title="À cadrer"]'); await pg.waitForTimeout(120);
    check('the band of a narrow stage widens it too', (await st(pg)) === 'wwwwwwwn', await st(pg));
    await pg.click('#roleSeg >> text=Produit'); await pg.waitForTimeout(150);
    check('the choice is kept per role, in memory: Produit still has In design wide', (await st(pg)) === 'wwwwnnnw', await st(pg));
    await pg.click('#roleSeg >> text=Tous'); await pg.waitForTimeout(150);
    check('role Tous: every column wide', (await st(pg)) === 'wwwwwwww', await st(pg));
    check('nothing is stored for the stages: only the role, the view and the language', (await pg.evaluate(() => Object.keys(localStorage).sort().join())) === 'cp.lang,cp.role,cp.view', await pg.evaluate(() => Object.keys(localStorage).sort().join()));
    await pg.close();
    const NEST = snapshot([
      ticket(60, ['type:feature', 'level:epic', 'status:planned'], { t: 'Epic parent', k: [0, 2] }),
      ticket(61, ['type:feature', 'level:story', 'status:planned'], { t: 'Story enfant A', p: 60 }),
      ticket(62, ['type:feature', 'level:story', 'status:planning'], { t: 'Story enfant B', p: 60 }),
      ticket(63, ['type:feature', 'level:story', 'status:planned'], { t: 'Story sans lien' }),
    ], 120);
    pg = await open({ preload: [NEST], view: 'board' });
    await tab(pg, 'Travail');
    const order = await pg.$$eval('#view .board section[aria-label="planifié"] .card', (cs) => cs.map((c) => c.querySelector('.t a').getAttribute('href').slice(6) + (c.classList.contains('child') ? 'c' : '')));
    const o2 = await pg.$$eval('#view .board section[aria-label="planification en cours"] .card', (cs) => cs.map((c) => c.querySelector('.t a').getAttribute('href').slice(6) + (c.classList.contains('child') ? 'c' : '')));
    check('board: a child sits under its parent in the same column; one in another column stands on its own with its parent link; every card is there', order.length === 3 && order.indexOf('60') < order.indexOf('61c') && order.includes('63') && JSON.stringify(o2) === '["62"]' && (await pg.locator('#view .board .card:has(a[href="#file/62"]) a.up').count()) === 1, JSON.stringify([order, o2]));
    await pg.close(); }

  // ---- a ticket's page: the chain of its level with the time in each status, its sub-tickets ----
  { const H = Object.assign({}, V6, { issues: V6.issues.map((i) => (i.n === 16 ? Object.assign({}, i, { h: [['ready', iso(300)], ['building', iso(120)]] }) : i)) });
    const pg = await open({ preload: [H] });
    await pg.goto(FILE + '#file/16'); await pg.waitForTimeout(300);
    const chain = await pg.$$eval('#view .row .meta .chip[aria-current], #view .row .meta .chip.ok, #view .row .meta .chip.acc', (c) => c.map((x) => x.textContent));
    check('ticket page: the chain of a task (ready to merged) with the time spent, the current step marked', /prêt à construire 3 h/.test(chain.join('|')) && (await pg.$eval('#view .chip[aria-current=step]', (e) => e.textContent)).startsWith('construction en cours') && !/planifié/.test(await text(pg, '#view')), chain.join('|'));
    await pg.goto(FILE + '#file/14'); await pg.waitForTimeout(300);
    check('ticket page: a split story shows its sub-tickets and the chain of a story', /Sous-tickets · 2/.test(await text(pg, '#view')) && /Tâche prête/.test(await text(pg, '#view')) && /planifié/.test(await text(pg, '#view')) && /en formation/.test(await text(pg, '#view')));
    check('ticket page: the parent is a crumb', (await pg.$$('#view nav.crumbs a')).length === 0);
    await pg.goto(FILE + '#file/15'); await pg.waitForTimeout(300);
    check('ticket page: a task shows its parent as a crumb', (await pg.$$('#view nav.crumbs a')).length === 1 && /Story découpée/.test(await text(pg, '#view nav.crumbs')));
    await pg.goto(FILE + '#file/9999'); await pg.waitForTimeout(300);
    check('ticket page: an unknown ticket says so', /Ticket introuvable/.test(await text(pg, '#view')));
    check('ticket page: no page errors', pg.errors.length === 0, pg.errors.join('|'));
    await pg.close(); }

  // ---- the role: human F (feature) or human T (tech) ----
  { let pg = await open({ preload: [V6], role: 'produit' });
    await tab(pg, 'Travail');
    check('role Produit: the feature tickets only, the product tabs', (await pg.locator('#view > .list > .row .chip', { hasText: /^tech$/ }).count()) === 0 && (await pg.locator('#view > .list > .row .chip', { hasText: /^feature$/ }).count()) > 0 && JSON.stringify(await pg.$$eval('#tabs a', (a) => a.map((x) => x.textContent.replace(/ \(\d+\)$/, '')))) === JSON.stringify(['Travail', 'Prototypes', 'Design', 'Wiki']));
    check('role Produit: the requests of a product role (need, report, express), not the technical one', (await pg.click('#ideaToggle'), JSON.stringify(await pg.$$eval('#kindSeg button', (b) => b.map((x) => x.textContent)))) === JSON.stringify(['Besoin produit', 'Signalement', 'Express']));
    await pg.close();
    pg = await open({ preload: [V6], role: 'tech' });
    await tab(pg, 'Travail');
    check('role Tech: the tech tickets and the epics (they group both kinds), the Architecture tab', (await pg.locator('#view > .list > .row .chip', { hasText: /^feature$/ }).count()) === 1 && /Epic planifié/.test(await text(pg, '#view')) && JSON.stringify(await pg.$$eval('#tabs a', (a) => a.map((x) => x.textContent.replace(/ \(\d+\)$/, '')))) === JSON.stringify(['Travail', 'Architecture']));
    await pg.click('#ideaToggle');
    check('role Tech: the technical request (plan) is the default', (await pg.$eval('#ideaCmd', (e) => e.textContent)) === '/pilot-plan …' && JSON.stringify(await pg.$$eval('#kindSeg button', (b) => b.map((x) => x.textContent))) === JSON.stringify(['Besoin technique', 'Signalement', 'Express']));
    await pg.fill('#searchText', 'Story'); await pg.waitForTimeout(150);
    check('role: a search looks at every ticket', (await pg.locator('#view > .list > .row .chip', { hasText: /^feature$/ }).count()) > 0);
    await pg.close(); }

  // ---- new request: the workflow that takes a request ----
  page = await open({ preload: [V6] });
  await tab(page, 'Travail');
  check('new request: folded by default, the list comes first', await page.$eval('#ideaBody', (e) => e.hidden));
  await page.click('#ideaToggle');
  const iCmd = () => text(page, '#ideaCmd');
  const iHref = async () => decodeURIComponent((await page.$eval('#ideaOpen', (a) => a.getAttribute('href') || '')).split('?q=')[1].split('&repo=')[0]);
  check('new request: all four kinds with no role; need by default, no link while the text is empty', JSON.stringify(await page.$$eval('#kindSeg button', (b) => b.map((x) => x.textContent))) === JSON.stringify(['Besoin produit', 'Besoin technique', 'Signalement', 'Express']) && (await iCmd()) === '/pilot-need …' && (await page.$eval('#ideaOpen', (a) => a.getAttribute('aria-disabled'))) === 'true');
  await page.fill('#ideaText', 'signaler un ascenseur\nen panne'); await page.waitForTimeout(100);
  check('new request: the text becomes one line of the command, the link opens it', (await iCmd()) === '/pilot-need signaler un ascenseur en panne' && (await iHref()) === (await iCmd()) && !(await page.$eval('#ideaCopy', (b) => b.disabled)), await iCmd());
  for (const [label, prefix] of [['Besoin technique', '/pilot-plan '], ['Signalement', '/pilot-report '], ['Express', '/pilot-express ']]) {
    await page.click('#kindSeg >> text=' + label); await page.waitForTimeout(80);
    check('new request: ' + label + ' writes ' + prefix.trim(), (await iCmd()) === prefix + 'signaler un ascenseur en panne' && (await iHref()) === (await iCmd()), await iCmd());
  }
  check('new request: the summary says a draft is under way', /brouillon en cours/.test(await text(page, '#ideaSum')));
  check('new request: no multi, no --with, no pilot-discovery', !/--multi|--with|pilot-discovery|pilot-auto/.test(await text(page, '#idea')));
  check('new request: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();

  // ---- search: keyword, level, type, state, flag, assignee ----
  const SEARCH = snapshot([
    ticket(10, ['type:feature', 'level:epic', 'status:planned'], { t: 'Profil d\'accessibilité : page profil' }),
    ticket(11, ['type:feature', 'level:story', 'status:merged'], { t: 'Saisir mes données sensibles', a: 'alice' }),
    ticket(12, ['type:tech', 'level:story', 'status:to-plan'], { t: 'Cache des états d\'équipements', a: 'bob' }),
    ticket(13, ['type:tech', 'level:task', 'status:ready', 'needs-human'], { t: 'Tâche bloquée' }),
    ticket(14, ['type:feature', 'level:task', 'status:ready', 'on-hold'], { t: 'ÉCRAN du Profil voyageur' }),
    ticket(15, ['type:feature', 'level:story', 'status:planned', 'fix'], { t: 'Story déjà découpée' }),
    ticket(16, ['type:tech', 'level:task', 'status:scoping'], { t: 'Statut hors processus' }),
  ], 120);
  page = await open({ preload: [SEARCH] });
  await tab(page, 'Travail');
  const names = () => page.$$eval('#view > .list > .row > .main > .t', (e) => e.map((x) => x.textContent.trim().split(' ')[0]).sort());
  const setOf = (...a) => JSON.stringify(a.sort());
  check('filters are folded by default behind a chevron, with no count', (await page.getAttribute('#filtersToggle', 'aria-expanded')) === 'false' && (await page.$eval('#searchFilters', (e) => e.hidden)) && (await page.$eval('#filtersCount', (e) => e.hidden)));
  await page.click('#filtersToggle');
  const btn = (map, key) => page.locator(`#searchFilters button[data-map="${map}"][data-key="${key}"]`);
  check('the filter panel: five groups; the states in process order, "sans statut" and an unknown one', (await page.locator('#searchFilters .fgrp').count()) === 5 && (await page.locator('#searchFilters button[data-map="states"]').first().getAttribute('data-key')) === 'forming' && (await btn('states', 'scoping').count()) === 1 && (await btn('states', 'none').count()) === 1);
  check('the type filter is feature or tech; the flag filter has the six flags', (await page.locator('#searchFilters button[data-map="types"]').allTextContents()).join() === 'feature,tech' && (await page.locator('#searchFilters button[data-map="flags"]').count()) === 7);
  await page.fill('#searchText', 'PROFIL');
  check('keyword: case-insensitive contains on the title', setOf(...(await names())) === setOf('#10', '#14'), JSON.stringify(await names()));
  await page.fill('#searchText', 'ecran');
  check('keyword: accent-insensitive', JSON.stringify(await names()) === JSON.stringify(['#14']));
  await page.fill('#searchText', '#12');
  check('keyword: matches the ticket number', JSON.stringify(await names()) === JSON.stringify(['#12']));
  await page.fill('#searchText', 'zzz');
  check('no match: empty state', (await trows(page)) === 0 && /Aucun ticket ne correspond/.test(await text(page, '#view')));
  await page.fill('#searchText', '');
  await btn('states', 'merged').click(); await page.waitForTimeout(100);
  check('state filter: one status, with its French name', JSON.stringify(await names()) === JSON.stringify(['#11']) && /fusionné, à recetter/.test(await btn('states', 'merged').textContent()));
  await btn('states', 'ready').click(); await page.waitForTimeout(100);
  check('several states are OR-ed', setOf(...(await names())) === setOf('#11', '#13', '#14'));
  await btn('types', 'tech').click(); await page.waitForTimeout(100);
  check('state + type are AND-ed', JSON.stringify(await names()) === JSON.stringify(['#13']));
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(100);
  await btn('flags', 'fix').click(); await page.waitForTimeout(100);
  check('flag fix', JSON.stringify(await names()) === JSON.stringify(['#15']));
  await btn('flags', 'needs-human').click(); await page.waitForTimeout(100);
  check('flags are OR-ed', setOf(...(await names())) === setOf('#13', '#15'));
  check('active filters are chips with a count, even when the panel is folded', (await text(page, '#filtersCount')) === '2' && (await page.locator('#activeFilters .chip.rm').allTextContents()).map((x) => x.trim()).sort().join('|') === 'Drapeau : attend un humain ✕|Drapeau : correction ✕');
  await page.locator('#activeFilters .chip.rm', { hasText: 'correction' }).click(); await page.waitForTimeout(100);
  check('a chip removes its filter', JSON.stringify(await names()) === JSON.stringify(['#13']));
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(100);
  await btn('states', 'none').click(); await page.waitForTimeout(100);
  check('no filter, no chip; a status-less ticket has none', (await trows(page)) === 0);
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(100);
  await btn('levels', 'epic').click(); await page.waitForTimeout(100);
  check('level filter: epic only', JSON.stringify(await names()) === JSON.stringify(['#10']) && /epic/.test(await text(page, '#view > .list > .row .meta')));
  await page.click('#activeFilters >> text=Réinitialiser'); await page.waitForTimeout(100);
  await page.fill('#meInput', 'alice'); await page.waitForTimeout(100);
  await btn('assignees', 'me').click(); await page.waitForTimeout(100);
  check('assignee: "moi" is the identity typed at the top', JSON.stringify(await names()) === JSON.stringify(['#11']));
  await btn('assignees', 'bob').click(); await page.waitForTimeout(100);
  check('assignees are OR-ed', setOf(...(await names())) === setOf('#11', '#12'));
  await page.fill('#meInput', ''); await page.waitForTimeout(100);
  check('"moi" without an identity: a hint', /Indiquez votre identifiant GitHub/.test(await text(page, '#view')));
  check('search: no page errors', page.errors.length === 0, page.errors.join('|'));
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
  check('design edit card and banner back on the other tabs', (await tab(page, 'Travail')) !== null && (await page.$eval('#designEdit', (e) => e.hidden)) && !(await page.$eval('#banner', (e) => e.hidden)));
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
  check('design: the command is the request, whatever the section', (await dCmd()) === '/pilot-design ajouter un thème à fort contraste' && (await dHref()) === (await dCmd()), await dCmd());
  await page.click('#subtabs >> text=Charte'); await page.waitForTimeout(150);
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

  // ---- sub-tabs of Design (one per section) ----
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
  check('design sub-tabs: the command has no section flag', (await text(page, '#designCmd')) === '/pilot-design', await text(page, '#designCmd'));
  await page.click('#subtabs >> text=Accessibilité'); await page.waitForTimeout(200);
  check('design sub-tabs: moving on shows the section', /Contraste AA minimum/.test(await text(page, '#view')));
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


  // ---- wiki tab: the project's wiki document (built by `pilot.py wiki snapshot`), read-only ----
  const WIKI = { kind: 'wiki', repo: REPO, at: iso(20), total: 4, truncated: false, entries: [
    { id: 'search-by-name', title: 'Search places by name', description: 'A traveler searches places by name.', path: 'search/search-by-name.md', status: 'implemented', derived: 'verified', display: 'implemented · verified', tickets: [1], verifiedBy: 'process:pilot-qa', verifiedAt: iso(30), text: 'A traveler searches places <img src=x onerror="window.__pwn=1"> by part of their name.' },
    { id: 'sort-by-distance', title: 'Results are sorted by distance', description: 'Nearest first.', path: 'search/sort-by-distance.md', status: 'implemented', derived: '', display: 'implemented', tickets: [3], verifiedAt: '', text: 'Nearest place first.' },
    { id: 'default-text-output', title: 'Default output', description: 'One line per place.', path: 'output/default-text-output.md', status: 'specified', derived: 'in-review', display: 'specified · in-review', tickets: [12, 14], verifiedAt: '', text: 'One line per place.' },
    { id: 'old-rule', title: 'Old rule', description: 'Not built yet.', path: 'old-rule.md', status: 'proposed', derived: '', display: 'proposed', tickets: [], verifiedAt: '', text: '' }] };
  { let page = await open({ preload: [BASE] });
  await page.goto(FILE + '#wiki'); await page.waitForTimeout(350);
  check('wiki tab: empty state names the commands, no ticket banner', /Aucun wiki publié/.test(await text(page, '#view')) && /module enable wiki/.test(await text(page, '#view')) && !/bootstrap/.test(await text(page, '#view')) && (await page.$eval('#banner', (e) => e.hidden)) && (await page.$eval('nav a[aria-current=page]', (a) => a.textContent)) === 'Wiki');
  await page.evaluate((d) => window.__push('wiki', 'w0', d), WIKI); await page.waitForTimeout(200);
  const wv = await text(page, '#view');
  check('wiki tab: the tab counts the entries, the page shows them grouped by page', (await page.$$eval('#tabs a', (a) => a.map((x) => x.textContent))).includes('Wiki (4)') && /search/.test(wv) && /Search places by name/.test(wv) && /A traveler searches places by name\./.test(wv) && /output/.test(wv), wv);
  check('wiki sub-tabs: Tous, then one per functional domain with its count',
        JSON.stringify(await page.$$eval('#subtabs a', (a) => a.map((x) => x.textContent))) === JSON.stringify(['Tous (4)', 'général (1)', 'output (1)', 'search (2)']), JSON.stringify(await page.$$eval('#subtabs a', (a) => a.map((x) => x.textContent))));
  check('wiki summary: one chip per status', /2 implémenté/.test(wv) && /1 spécifié/.test(wv) && /1 proposé/.test(wv) && !/déprécié/.test(wv), wv);
  check('wiki entry chips: stamp, never verified, in-flight status, ticket link',
        /vérifié il y a|vérifié /.test(wv) && /en relecture/.test(wv) && !/non vérifié/.test(wv) && (await page.$eval('#view a[href$="/issues/12"]', (a) => a.getAttribute('href'))) === 'https://github.com/' + REPO + '/issues/12');
  check('wiki: HTML in an entry stays text', (await page.$('#view [onerror]')) === null && (await page.evaluate(() => window.__pwn)) === undefined && (await page.$eval('#view .row details', (d) => d.textContent)).includes('<img src=x'));
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


  // ---- user-flow entries: a launcher that writes the /pilot-accept command (personas are chosen one at a time) ----
  const WIKI_FLOWS = { kind: 'wiki', repo: REPO, at: iso(5), total: 3, truncated: false, entries: [
    { id: 'marie-senior', type: 'Persona', title: 'Marie', description: 'Senior.', path: 'persona/marie-senior.md', status: '', tickets: [], text: 'Senior.' },
    { id: 'paul-aidant', type: 'Persona', title: 'Paul', description: 'Carer.', path: 'persona/paul-aidant.md', status: '', tickets: [], text: 'Carer.' },
    { id: 'find-a-place', type: 'UserFlow', title: 'Find a place', description: 'Search.', path: 'user-flow/find-a-place.md', status: 'implemented', tickets: [], text: 'Goal.\nPersonas: marie-senior\n1. Open the search -> a field.' }] };
  { let page = await open({ preload: [BASE], wiki: [WIKI_FLOWS] });
  await page.goto(FILE + '#wiki/user-flow'); await page.waitForTimeout(400);
  const cmdOf = async () => page.$eval('#view .flow-launch + .cmd', (e) => e.textContent);
  const hrefOf = async () => page.$eval('#view .flow-launch + .cmd + .refresh a', (a) => a.getAttribute('href'));
  check('flow launcher: /pilot-accept <flow>, no persona by default, the link opens it', (await cmdOf()) === '/pilot-accept find-a-place' && decodeURIComponent(await hrefOf()).includes('/pilot-accept find-a-place'), await cmdOf());
  await page.click('#view .flow-launch .tog:nth-of-type(1)'); await page.waitForTimeout(100);
  check('flow launcher: a persona is picked with --persona', (await cmdOf()) === '/pilot-accept find-a-place --persona marie-senior', await cmdOf());
  await page.click('#view .flow-launch .tog:nth-of-type(2)'); await page.waitForTimeout(100);
  check('flow launcher: one persona at a time', (await cmdOf()) === '/pilot-accept find-a-place --persona paul-aidant', await cmdOf());
  await page.click('#view .flow-launch .tog:nth-of-type(2)'); await page.waitForTimeout(100);
  check('flow launcher: picking it again lifts it; no --as, no --url', (await cmdOf()) === '/pilot-accept find-a-place' && !(await page.$('#flowUrl-find-a-place')));
  await page.goto(FILE + '#wiki/persona'); await page.waitForTimeout(300);
  check('a persona has no launcher of its own (a flow is tested as a persona)', (await page.$('#view .flow-launch')) === null);
  await page.evaluate((d) => window.__push('wiki', 'w9', d), Object.assign({}, WIKI_FLOWS, { entries: WIKI_FLOWS.entries.map((e) => (e.type === 'UserFlow' ? Object.assign({}, e, { status: 'proposed' }) : e)) })); await page.waitForTimeout(250);
  await page.goto(FILE + '#wiki/user-flow'); await page.waitForTimeout(300);
  check('flow launcher: a flow that is not implemented yet has no launcher, only a note', (await page.$('#view .flow-launch')) === null && /Pas encore livré/.test(await text(page, '#view')));
  await page.close();
  const NA = await open({ preload: [Object.assign({}, BASE, { workflows: ['need'] })], wiki: [WIKI_FLOWS] });
  await NA.goto(FILE + '#wiki/user-flow'); await NA.waitForTimeout(400);
  check('flow launcher: without the accept workflow in the snapshot, no launcher', (await NA.$('#view .flow-launch')) === null && !/pilot-accept/.test(await NA.$eval('#view', (e) => e.innerHTML)));
  check('flow launcher: no page errors', NA.errors.length === 0, NA.errors.join('|'));
  await NA.close();
  }

  // ---- a user flow's state since it was last played, and the creation card ----
  { const hashes = { flow: 'aaaaaaaaaaaa', marie: 'bbbbbbbbbbbb', paul: 'cccccccccccc' };
  const withHash = Object.assign({}, WIKI_FLOWS, { entries: WIKI_FLOWS.entries.map((e) => Object.assign({}, e, { hash: { 'find-a-place': hashes.flow, 'marie-senior': hashes.marie, 'paul-aidant': hashes.paul }[e.id] })) });
  const run = (over) => Object.assign({ kind: 'flowRun', repo: REPO, flow: 'find-a-place', at: iso(48), hash: hashes.flow, result: 'partial', bugs: [7], report: 'https://claude.ai/artifact/abc',
    personas: [{ id: 'marie-senior', hash: hashes.marie, result: 'passed' }, { id: 'paul-aidant', hash: hashes.paul, result: 'partial' }] }, over || {});
  let page = await open({ preload: [BASE], wiki: [withHash] });
  await page.goto(FILE + '#wiki/user-flow'); await page.waitForTimeout(350);
  const chipsOf = async () => page.$$eval('#view .row .meta .chip', (c) => c.map((x) => x.textContent));
  check('flow status: a flow never played says so', (await chipsOf()).includes('jamais joué'), (await chipsOf()).join('|'));
  await page.evaluate((d) => window.__push('flowRuns', 'f0', d), run()); await page.waitForTimeout(250);
  let c = await chipsOf();
  check('flow status: the result, when, who played with each result, the bug and the report',
        c.includes('partiel') && c.some((x) => /^joué il y a/.test(x)) && c.includes('Marie · passé') && c.includes('Paul · partiel') && c.includes('#7') && c.includes('rapport') && !c.includes('jamais joué') && !c.includes('à rejouer'), c.join('|'));
  await page.evaluate((d) => window.__push('flowRuns', 'f0', d), run({ hash: 'zzzzzzzzzzzz' })); await page.waitForTimeout(250);
  check('flow status: a flow changed since the run is to replay', (await chipsOf()).includes('à rejouer'), (await chipsOf()).join('|'));
  await page.evaluate((d) => window.__push('flowRuns', 'f0', d), run({ personas: [{ id: 'marie-senior', hash: 'zzzzzzzzzzzz', result: 'passed' }] })); await page.waitForTimeout(250);
  check('flow status: a persona changed since the run makes it to replay too', (await chipsOf()).includes('à rejouer'), (await chipsOf()).join('|'));
  await page.evaluate((d) => window.__push('flowRuns', 'f1', d), run({ repo: 'o/other', result: 'failed' })); await page.waitForTimeout(200);
  check('flow status: another repo\'s run is not shown', !(await chipsOf()).includes('échec'));
  await page.evaluate((d) => window.__push('flowRuns', 'f0', d), run({ bugs: ['x', -1, 0], report: 'javascript:alert(1)' })); await page.waitForTimeout(250);
  await page.evaluate((d) => window.__push('flowRuns', 'f0', d), run({ result: 'passed' })); await page.waitForTimeout(250);
  check('flow status: a passing run its flow and personas have not changed since verifies the flow', (await chipsOf()).includes('vérifié') && !(await chipsOf()).includes('à rejouer'), (await chipsOf()).join('|'));
  await page.evaluate((d) => window.__push('flowRuns', 'f0', d), run({ result: 'passed', hash: 'changed' })); await page.waitForTimeout(250);
  check('flow status: once the flow changed it is to replay, not verified', (await chipsOf()).includes('à rejouer') && !(await chipsOf()).includes('vérifié'), (await chipsOf()).join('|'));
  await page.evaluate((d) => window.__push('flowRuns', 'f0', d), run({ bugs: ['x', -1, 0], report: 'javascript:alert(1)' })); await page.waitForTimeout(250);
  check('flow status: a bad bug number or report address is dropped', !(await chipsOf()).some((x) => /^#/.test(x) || x === 'rapport'), (await chipsOf()).join('|'));
  { const en = await open({ preload: [BASE], wiki: [withHash], flowRuns: [run()], lang: 'en' });
  await en.goto(FILE + '#wiki/user-flow'); await en.waitForTimeout(350);
  const ec = await en.$$eval('#view .row .meta .chip', (x) => x.map((y) => y.textContent));
  check('flow status: in English the chips are English, the persona chips too', ec.includes('partial') && ec.some((x) => /^played /.test(x)) && ec.includes('Marie · passed') && ec.includes('Paul · partial') && ec.includes('report') && !ec.some((x) => /passé|partiel|joué|rapport/.test(x)), ec.join('|'));
  await en.close(); }
  check('persona and flow rows are never flagged "non vérifié"', !(await chipsOf()).includes('non vérifié'), (await chipsOf()).join('|'));
  await page.goto(FILE + '#wiki'); await page.waitForTimeout(300);
  check('creation card: it writes the command for a persona, then for a flow, and is disabled while the text is empty',
        (await page.$eval('#view .foldcard .cmd', (e) => e.textContent)) === '/pilot-flow --new persona'
        && (await page.$eval('#view .foldcard a.btn.primary', (a) => a.getAttribute('aria-disabled') === 'true' && !a.hasAttribute('href'))));
  await page.click('#view .foldcard summary'); await page.fill('#flowNewText', 'Marie, 74 ans,\n malvoyante'); await page.waitForTimeout(100);
  check('creation card: the text becomes one line of the command, the link opens it', (await page.$eval('#view .foldcard .cmd', (e) => e.textContent)) === '/pilot-flow --new persona Marie, 74 ans, malvoyante'
        && decodeURIComponent(await page.$eval('#view .foldcard a.btn.primary', (a) => a.getAttribute('href'))).includes('/pilot-flow --new persona Marie, 74 ans, malvoyante'));
  await page.click('#view .foldcard .seg button:nth-of-type(2)'); await page.waitForTimeout(100);
  check('creation card: choosing the flow changes the command', (await page.$eval('#view .foldcard .cmd', (e) => e.textContent)).startsWith('/pilot-flow --new flow '));
  await page.fill('#flowNewText', 'Une description'); await page.click('#view .foldcard .seg button:nth-of-type(1)');
  await page.evaluate((d) => window.__push('flowRuns', 'f5', d), run({ flow: 'other-flow' })); await page.waitForTimeout(300);
  check('creation card: a re-render (a new document arrives) keeps the text, the kind and the open card',
        (await page.$eval('#flowNewText', (e) => e.value)) === 'Une description' && (await page.$eval('#view .foldcard', (d) => d.open)) && (await page.$eval('#view .foldcard .cmd', (e) => e.textContent)) === '/pilot-flow --new persona Une description');
  check('flow status and creation card: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.close();
  }


  // ---- wiki: what happened at a flow's last run, and what a person can ask of each entry ----
  { const run = { kind: 'flowRun', repo: REPO, flow: 'find-a-place', at: iso(48), hash: 'x', result: 'failed', bugs: [99], report: 'https://claude.ai/artifact/abc',
      personas: [{ id: 'marie-senior', hash: 'y', result: 'passed', steps: { passed: 6, failed: 0, untestable: 0 } }, { id: 'paul-aidant', hash: 'z', result: 'failed', steps: { passed: 4, failed: 2, untestable: 1 } }] };
    let pg = await open({ preload: [BASE], wiki: [WIKI_FLOWS], flowRuns: [run] });
    await pg.goto(FILE + '#wiki/user-flow'); await pg.waitForTimeout(350);
    const lr = await text(pg, '#view .lastrun');
    check('last run: when, each persona with its steps, the ticket created with its title, the report', /Dernier lancement/.test(lr) && /Joué il y a 48 min/.test(lr) && /6 passées · 0 échouées · 0 non testables/.test(lr) && /4 passées · 2 échouées · 1 non testables/.test(lr) && /Ticket créé : #99 Ticket de l instantane/.test(lr) && /Rapport/.test(lr), lr);
    check('last run: open when something failed', await pg.$eval('#view .lastrun', (d) => d.open));
    await pg.evaluate((d) => window.__push('flowRuns', 'f0', d), Object.assign({}, run, { result: 'passed', bugs: [] })); await pg.waitForTimeout(250);
    check('last run: closed when it passed, and says no ticket was created', !(await pg.$eval('#view .lastrun', (d) => d.open)) && /Aucun ticket créé/.test(await pg.$eval('#view .lastrun', (d) => d.textContent)));
    const cmdsHere = async () => (await hrefs(pg, '#view .row a.btn')).map((l) => decodeURIComponent(l.href.split('?q=')[1].split('&repo=')[0]).trim());
    let c = await cmdsHere();
    check('wiki: a flow can be edited and removed through /pilot-flow', c.includes('/pilot-flow --edit find-a-place') && c.includes('/pilot-flow --remove find-a-place'), JSON.stringify(c));
    await pg.goto(FILE + '#wiki/persona'); await pg.waitForTimeout(300);
    c = await cmdsHere();
    check('wiki: a persona is edited and removed through /pilot-flow, never checked against the code', c.includes('/pilot-flow --edit marie-senior') && c.includes('/pilot-flow --remove marie-senior') && !c.some((x) => /--lint marie-senior/.test(x)), JSON.stringify(c));
    check('wiki entries: no page errors', pg.errors.length === 0, pg.errors.join('|'));
    await pg.close(); }
  { const DOC = { kind: 'wiki', repo: REPO, at: iso(20), total: 4, truncated: false, entries: [
      { id: 'filter-a11y', type: 'Behavior', title: 'Filter', description: 'Filters.', path: 'search/filter-a11y.md', status: 'implemented', derived: 'verified', tickets: [], verifiedAt: '', text: 'Filters.' },
      { id: 'saved-places', type: 'Behavior', title: 'Saved', description: 'Saved.', path: 'search/saved-places.md', status: 'proposed', derived: 'in-qa', tickets: [], verifiedAt: '', text: 'Saved.' },
      { id: 'vision', type: 'Vision', title: 'Vision', description: 'Why.', path: 'product/vision.md', status: '', derived: '', tickets: [], verifiedAt: '', text: 'Why.' },
      { id: 'words', type: 'Frame', title: 'Words', description: 'Shared words.', path: 'search/words.md', status: 'provisional', derived: 'in-dev', tickets: [], verifiedAt: '', text: 'Words.' } ] };
    const pg = await open({ preload: [BASE], wiki: [DOC] });
    await pg.goto(FILE + '#wiki'); await pg.waitForTimeout(350);
    const c = (await hrefs(pg, '#view a.btn')).map((l) => decodeURIComponent((l.href.split('?q=')[1] || l.href).split('&repo=')[0]).trim());
    const wv = await text(pg, '#view');
    check('wiki: a behavior is never edited or removed from here (a change of behavior goes through /pilot-need); the vision neither', !c.some((x) => /filter-a11y|saved-places|vision/.test(x)), JSON.stringify(c));
    check('wiki: a frame entry is edited or removed through /pilot-wiki', c.includes('/pilot-wiki --edit words') && c.includes('/pilot-wiki --remove words'), JSON.stringify(c));
    check('wiki: the whole wiki is asked or linted', c.includes('/pilot-wiki') && c.includes('/pilot-wiki --lint') && !c.some((x) => /--lint \w/.test(x)), JSON.stringify(c));
    check('wiki: provisional status and the derived states in v6 words', /provisoire/.test(wv) && /recetté/.test(wv) && /à recetter/.test(wv) && /en construction/.test(wv) && !/en review|en QA|en dev\b/.test(wv), wv);
    await pg.close(); }

  // ---- architecture tab: the project's `architecture` document (built by `pilot.py arch snapshot`), read-only ----
  const ARCH = { kind: 'architecture', repo: REPO, at: iso(20), total: 7, truncated: false, entries: [
    { id: 'overview', title: 'Overview', description: 'The apps and how they relate.', path: 'overview.md', status: 'accepted', tickets: [], supersedes: '', supersededBy: '', text: 'One CLI <img src=x onerror="window.__pwn=1">.' },
    { id: 'layering', title: 'Layering', description: 'Domain never imports adapters.', path: 'guidelines/layering.md', status: 'accepted', tickets: [], supersedes: '', supersededBy: '', text: 'Domain never imports adapters.' },
    { id: '0001-compute', title: 'Catalog computed', description: 'Compute the catalog.', path: 'adr/0001-compute.md', status: 'superseded', tickets: [5], supersedes: '', supersededBy: '0002-store', text: '' },
    { id: '0002-store', title: 'Catalog stored', description: 'The catalog is stored, not computed.', path: 'adr/0002-store.md', status: 'accepted', tickets: [12], supersedes: '0001-compute', supersededBy: '', text: 'Stored.' },
    { id: 'web-overview', title: 'Web app', description: 'The web front end.', path: 'apps/web/web-overview.md', status: 'accepted', tickets: [], supersedes: '', supersededBy: '', text: 'React.' },
    { id: 'a11y', title: 'Accessible by default', description: 'Every control has a name.', path: 'apps/web/guidelines/a11y.md', status: 'accepted', tickets: [], supersedes: '', supersededBy: '', text: 'Name every control.' },
    { id: 'deploy', title: 'Deploy', description: 'How a release goes out.', path: 'runbooks/deploy.md', status: 'accepted', tickets: [], supersedes: '', supersededBy: '', text: 'Run the deploy workflow.' }] };
  { let page = await open({ preload: [BASE] });
  await page.goto(FILE + '#architecture'); await page.waitForTimeout(350);
  check('architecture tab: empty state names the commands, no ticket banner', /Aucune architecture publiée/.test(await text(page, '#view')) && /module enable architecture/.test(await text(page, '#view')) && !/bootstrap/.test(await text(page, '#view')) && (await page.$eval('#banner', (e) => e.hidden)) && (await page.$eval('nav a[aria-current=page]', (a) => a.textContent)) === 'Architecture');
  await page.evaluate((d) => window.__push('architecture', 'r0', d), ARCH); await page.waitForTimeout(200);
  const av = await text(page, '#view');
  check('architecture tab: counted in the tab, grouped by overview, rules, decisions and runbooks', (await page.$$eval('#tabs a', (a) => a.map((x) => x.textContent))).includes('Architecture (7)') && /Vue d’ensemble/.test(av) && /Règles/.test(av) && /Décisions/.test(av) && /Procédures/.test(av) && /Run the deploy workflow/.test(av) && /Catalog stored/.test(av), av);
  check('architecture sub-tabs: Tous, then one per group with its count',
        JSON.stringify(await page.$$eval('#subtabs a', (a) => a.map((x) => x.textContent))) === JSON.stringify(['Tous (7)', 'Vue d’ensemble (1)', 'Règles (1)', 'Décisions (2)', 'Procédures (1)', 'App web (2)']), JSON.stringify(await page.$$eval('#subtabs a', (a) => a.map((x) => x.textContent))));
  check('architecture summary and supersession chips', /6 accepté/.test(av) && /1 remplacé/.test(av) && /remplace 0001-compute/.test(av) && /remplacé par 0002-store/.test(av), av);
  check('architecture: ticket link, and HTML in an entry stays text', (await page.$eval('#view a[href$="/issues/12"]', (a) => a.getAttribute('href'))) === 'https://github.com/' + REPO + '/issues/12' && (await page.$('#view [onerror]')) === null && (await page.evaluate(() => window.__pwn)) === undefined);
  await page.click('#subtabs >> text=App web'); await page.waitForTimeout(150);
  const aw = await text(page, '#view');
  check('architecture sub-tab: an app group shows only that app, labelled by its name', /Accessible by default/.test(aw) && /Web app/.test(aw) && !/Catalog stored/.test(aw) && (await page.evaluate(() => location.hash)) === '#architecture/app:web', aw);
  await page.click('#subtabs >> text=Décisions'); await page.waitForTimeout(150);
  const af = await text(page, '#view');
  check('architecture sub-tab: shows only that group, the address follows', /Catalog stored/.test(af) && !/Layering/.test(af) && (await page.evaluate(() => location.hash)) === '#architecture/adr', af);
  await page.evaluate((d) => window.__push('architecture', 'r1', Object.assign({}, d, { repo: 'o/other', entries: [{ id: 'x', title: 'Autre projet', path: 'overview.md', status: 'proposed', tickets: [], text: '' }] })), ARCH); await page.waitForTimeout(150);
  await page.click('#subtabs >> text=Tous'); await page.waitForTimeout(150);
  { const cm = (await hrefs(page, '#view a.btn')).map((l) => decodeURIComponent((l.href.split('?q=')[1] || l.href).split('&repo=')[0]).trim());
    check('architecture: the whole body is asked, a rule added or the body linted; no --adr, --verify or --bootstrap', cm.includes('/pilot-architecture') && cm.includes('/pilot-architecture --guideline') && cm.includes('/pilot-architecture --lint') && !cm.some((x) => /--(adr|verify|bootstrap)/.test(x)), JSON.stringify(cm.slice(0, 5)));
    check('architecture: a rule is edited or removed, an accepted ADR neither, the root overview is not removed', cm.includes('/pilot-architecture --edit layering') && cm.includes('/pilot-architecture --remove layering') && !cm.some((x) => /--(edit|remove) 0002-store/.test(x)) && cm.includes('/pilot-architecture --edit overview') && !cm.includes('/pilot-architecture --remove overview'), JSON.stringify(cm)); }
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



  // ---- prototypes tab: the `protos` mockups joined to their run (issue and events) ----
  const PSNAP = snapshot([
    ticket(701, ['run:proto'], { t: 'run:proto Proto brouillon' }),
    ticket(702, ['run:proto', 'needs-human'], { t: 'run:proto Proto à décider' }),
    ticket(707, ['run:proto'], { t: 'run:proto Proto en cours' }),
  ], 120);
  const PM = (n, o = {}) => Object.assign({ kind: 'proto', n, repo: REPO, title: 'Proto ' + n, brief: 'Brief du proto ' + n, parts: 0, at: iso(60) }, o);
  const PROTOS = [
    PM(701, { title: 'Proto brouillon' }),
    PM(702, { title: 'Proto à décider', parts: 2, height: 300 }),
    PM(703, { title: 'Proto accepté', parts: 1 }),
    PM(704, { title: 'Proto fini sans verdict connu' }),
    PM(706, { title: 'Proto rejeté', parts: 1 }),
    PM(707, { title: 'Proto en cours', parts: 1 }),
    PM(900, { repo: 'o/other', title: 'Proto d un autre projet' }),
  ];
  const PHTML = [
    { n: 702, k: 0, html: '<!doctype html><h1 id="t">Maquette A</h1><button id="b" onclick="document.getElementById(\'t\').textContent=\'cliqué\'">Cliquer</button>' },
    { n: 702, k: 1, html: '<p id="end">fin de la maquette</p><script>try{parent.__pwn=1}catch(e){document.body.setAttribute("data-blocked","1")}<\/script>' },
    { n: 706, k: 0, html: '<p>Maquette rejetée</p>' },
  ];
  const PEVENTS = [
    run({ n: 702, workflow: 'proto', step: 'gate', state: 'waiting-human' }),
    run({ n: 703, workflow: 'proto', step: 'proto-accepte', state: 'done', result: 'accepted' }),
    run({ n: 706, workflow: 'proto', step: 'proto-accepte', state: 'done', result: 'rejected' }),
    run({ n: 707, workflow: 'proto', step: 'build', state: 'running' }),
  ];
  page = await open({ preload: [PSNAP], protos: PROTOS, protoHtml: PHTML, events: PEVENTS });
  const pSubs = () => page.$$eval('#subtabs a', (as) => as.map((a) => a.textContent));
  const pRows = () => page.$$eval('#view > .list > .row .t', (ts) => ts.map((t) => t.textContent.replace(/^#\d+ /, '')).sort());
  const pCmds = async (n) => (await page.locator('#view > .list > .row', { hasText: '#' + n + ' ' }).first().locator('a.btn').evaluateAll((as) => as.map((a) => decodeURIComponent((a.href.split('?q=')[1] || a.href).split('&repo=')[0]))));
  await page.click('nav >> text=Prototypes'); await page.waitForTimeout(250);
  check('prototypes: the tab counts those under way (an open run issue or a run not done)', JSON.stringify((await page.$$eval('nav#tabs a', (as) => as.map((a) => a.textContent))).slice(0, 2)) === JSON.stringify(['Travail', 'Prototypes (3)']));
  check('prototypes: sub-tabs En cours / Terminés with their counts', JSON.stringify(await pSubs()) === JSON.stringify(['En cours (3)', 'Terminés (3)']), JSON.stringify(await pSubs()));
  check('prototypes: "En cours" lists the three, not the others nor another project\'s', JSON.stringify(await pRows()) === JSON.stringify(['Proto brouillon', 'Proto en cours', 'Proto à décider']), JSON.stringify(await pRows()));
  check('prototypes: one under way is resumed or rejected, by command', (await pCmds(707)).includes('/pilot-proto --resume 707') && (await pCmds(707)).includes('/pilot-proto 707 --reject'), JSON.stringify(await pCmds(707)));
  check('prototypes: one flagged is answered on GitHub, never resumed', !(await pCmds(702)).some((c) => /--resume/.test(c)) && (await pCmds(702)).some((c) => /\/issues\/702$/.test(c)) && /attend un humain/.test(await page.locator('#view > .list > .row', { hasText: '#702 ' }).textContent()), JSON.stringify(await pCmds(702)));
  check('prototypes: the brief is shown', /Brief du proto 702/.test(await text(page, '#view')));
  check('prototypes: a prototype with no mockup says so; one with a mockup does not', /Pas de maquette enregistrée/.test(await page.locator('#view > .list > .row', { hasText: '#701 ' }).textContent()) && !/Pas de maquette enregistrée/.test(await page.locator('#view > .list > .row', { hasText: '#702 ' }).textContent()));
  await page.click('#subtabs >> text=Terminés'); await page.waitForTimeout(200);
  check('prototypes: Terminés lists the finished ones, with their verdict when known', JSON.stringify(await pRows()) === JSON.stringify(['Proto accepté', 'Proto fini sans verdict connu', 'Proto rejeté']) && /accepté/.test(await page.locator('#view > .list > .row', { hasText: '#703 ' }).textContent()) && /rejeté/.test(await page.locator('#view > .list > .row', { hasText: '#706 ' }).textContent()));
  check('prototypes: a finished one feeds a need (/pilot-need --proto), a rejected one does not', (await pCmds(703)).includes('/pilot-need --proto 703') && (await pCmds(704)).includes('/pilot-need --proto 704') && !(await pCmds(706)).some((c) => /pilot-need/.test(c)), JSON.stringify([await pCmds(703), await pCmds(706)]));
  check('prototypes: no removed command (accept, discovery, from-proto)', !/--accept|pilot-discovery|--from-proto/.test((await page.$$eval('#view a', (as) => as.map((a) => decodeURIComponent(a.href)))).join()));
  await page.click('#subtabs >> text=En cours'); await page.waitForTimeout(200);
  await page.locator('#view > .list > .row', { hasText: '#702 ' }).locator('button:has-text("la maquette")').click(); await page.waitForTimeout(500);
  const fr = await page.$('#view iframe.prev');
  check('prototypes: the mockup loads from its parts in a frame with scripts only', !!fr && (await fr.getAttribute('sandbox')) === 'allow-scripts' && /Content-Security-Policy[^>]*default-src 'none'/.test(await fr.getAttribute('srcdoc')) && /Maquette A/.test(await fr.getAttribute('srcdoc')) && /fin de la maquette/.test(await fr.getAttribute('srcdoc')));
  const mf = await fr.contentFrame(); await mf.click('#b'); 
  check('prototypes: the mockup is interactive and cannot reach the page', (await mf.$eval('#t', (e) => e.textContent)) === 'cliqué' && (await page.evaluate(() => window.__pwn)) === undefined);
  await page.locator('#view > .list > .row', { hasText: '#702 ' }).locator('button:has-text("Plein écran")').click(); await page.waitForTimeout(500);
  check('prototypes: full screen has its own address and a way back', (await page.evaluate(() => location.hash)) === '#proto/702' && (await page.locator('#view a:has-text("← Prototypes")').count()) === 1 && (await page.$$('#view iframe.prev')).length === 1);
  await page.goto(FILE + '#proto/9999'); await page.waitForTimeout(300);
  check('prototypes: an unknown prototype says so', /Prototype introuvable/.test(await text(page, '#view')));
  await page.goto(FILE + '#prototypes'); await page.waitForTimeout(250);
  await page.click('#protoNToggle'); await page.waitForTimeout(100);
  const pnCmd = () => text(page, '#protoCmd');
  check('new prototype: from an idea, the bare command first, no link while empty', (await pnCmd()) === '/pilot-proto' && (await page.$eval('#protoOpen', (a) => a.getAttribute('aria-disabled'))) === 'true');
  await page.fill('#protoText', 'choisir un itinéraire'); await page.waitForTimeout(100);
  check('new prototype: the idea becomes the command, with no --with', (await pnCmd()) === '/pilot-proto choisir un itinéraire' && !(await page.$('#protoWith')));
  await page.click('#protoSrcImp'); await page.fill('#protoUrl', 'https://claude.ai/artifact/abc123?sk=zzz'); await page.waitForTimeout(100);
  check('new prototype: an imported artifact (its ?sk=… dropped)', (await pnCmd()) === '/pilot-proto --from-artifact https://claude.ai/artifact/abc123 choisir un itinéraire', await pnCmd());
  await page.fill('#protoUrl', 'https://example.com/x'); await page.waitForTimeout(100);
  check('new prototype: anything but an artifact address gives no link', (await page.$eval('#protoOpen', (a) => a.getAttribute('aria-disabled'))) === 'true');
  check('prototypes: no page errors', page.errors.length === 0, page.errors.join('|'));
  await page.screenshot({ path: path.join(TMP, 'protos.png') });
  await page.close();
  page = await open({ preload: [BASE], protos: PROTOS });
  await page.goto(FILE + '#prototypes'); await page.waitForTimeout(300);
  check('prototypes: with no run issue and no event, they are finished', /Aucun prototype dans cette vue/.test(await text(page, '#view')));
  await page.close();

  // ---- the reference pages ("i") ----
  { const pg = await open({ preload: [V6] });
    const get = async (sub) => { await pg.goto(FILE + '#aide/' + sub); await pg.waitForTimeout(250); return pg.$eval('#view', (e) => e.innerText); };
    const subs = async () => pg.$$eval('#subtabs a', (a) => a.map((x) => x.textContent));
    const pr = await get('principes');
    check('help: the "i" opens it, five sub-tabs', JSON.stringify(await subs()) === JSON.stringify(['Principes', 'Workflows', 'Tickets', 'Modules', 'Agents']) && (await pg.$eval('#helpLink', (a) => a.getAttribute('aria-current'))) === 'page', JSON.stringify(await subs()));
    check('help: principles name the six commands and the cockpit refresh', ['/pilot-need', '/pilot-plan', '/pilot-build', '/pilot-accept', '/pilot-report', '/pilot-express', '/pilot-dashboard --refresh'].every((c) => pr.includes(c)), pr.slice(0, 300));
    const wf = await get('workflows');
    check('help: workflows lists those the snapshot lists, with their command and the statuses they take and produce', /\/pilot-build/.test(wf) && /Prend :\s*building, ready, reviewing/.test(wf) && /Produit :\s*merged, reviewing/.test(wf) && !/\/pilot-design/.test(wf), wf.slice(0, 400));
    const tk = await get('tickets');
    check('help: tickets give the statuses per level and the command of each status', /epic : forming → to-plan → planning → planned → done → wont-do/.test(tk) && /task : ready → building → reviewing → merged → done/.test(tk) && /merged\s+\/pilot-accept <n°>/.test(tk) && /ready\s+\/pilot-build <n°>/.test(tk) && /reviewing\s+\/pilot-build --resume <n°>/.test(tk), tk.slice(0, 600));
    check('help: the flags are explained', ['needs-human', 'on-hold', 'can-resume', 'express', 'fix', 'gap'].every((f) => tk.includes(f)));
    const md = await get('modules');
    check('help: modules describe the five tabs, the runs and where the data comes from', ['Travail', 'Prototypes', 'Design', 'Wiki', 'Architecture'].every((t) => md.includes(t)) && /étapes de run/.test(md));
    const ag = await get('agents');
    check('help: the seven personas', ['PM', 'Architecte', 'Tech lead', 'Dev', 'E2E', 'QA', 'Designer'].every((a) => ag.includes(a)));
    check('help: no removed notion anywhere (phases, roster, modes, --human, --multi, pilot-auto, poc, Steps)', !/(?:^|\W)(?:phase|roster|--human|--multi|--auto|--next|pilot-auto|type:poc|poc-|Steps?)(?:\W|$)/i.test([pr, wf, tk, md, ag].join('\n')), [pr, wf, tk, md, ag].join('\n').match(/.{20}(?:phase|roster|--human|--multi|pilot-auto|poc-|Steps?).{20}/i));
    check('help: a role filters the starting points', (await (async () => { const p2 = await open({ preload: [V6], role: 'tech' }); await p2.goto(FILE + '#aide/principes'); await p2.waitForTimeout(250); const t = await p2.$eval('#view', (e) => e.innerText); await p2.close(); return /Vue filtrée pour le rôle Tech/.test(t) && !/\/pilot-need "…"/.test(t) && /\/pilot-build/.test(t); })()));
    check('help: no page errors', pg.errors.length === 0, pg.errors.join('|'));
    await pg.close(); }

  const ROUTES = ['file', 'file/16', 'prototypes/encours', 'prototypes/termines', 'proto/702',
    'aide/principes', 'aide/workflows', 'aide/tickets', 'aide/modules', 'aide/agents',
    'design/charter', 'design/colors', 'design/type', 'design/space', 'design/components', 'design/a11y'];
  page = await open({ preload: [V6], protos: PROTOS, protoHtml: PHTML, events: PEVENTS.concat([run({ n: 16 }), run({ n: 40, workflow: 'need', state: 'waiting-human' })]) });
  { const wide = [];
    for (const view of ['liste', 'board']) {
      await page.evaluate((v) => localStorage.setItem('cp.view', v), view); await page.goto(FILE + '#file'); await page.waitForTimeout(250);
      for (const scheme of ['light', 'dark']) {
        await page.emulateMedia({ colorScheme: scheme });
        for (const r of (view === 'liste' ? ROUTES : ['file'])) {
          await page.evaluate((x) => { location.hash = x; }, r); await page.waitForTimeout(150);
          const w = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
          if (w > 0) wide.push(view + ' ' + scheme + ' #' + r + ' (+' + w + 'px)');
        }
      }
    }
    check('every tab and sub-tab fits a 400px phone, light and dark', wide.length === 0 && page.errors.length === 0, wide.join(', ') + ' ' + page.errors.join(' | ')); }
  await page.close();

  // ---- tabs follow the modules the snapshot says the project has on ----
  {
    const tabs = async (pg) => pg.$$eval('#tabs a', (a) => a.map((x) => x.textContent.replace(/ \(\d+\)$/, '')));
    const withMods = (m) => Object.assign({}, BASE, { modules: m });
    let page = await open({ preload: [withMods({ dashboard: true, wiki: false, architecture: false, design: false, proto: false })] });
    check('modules: a module that is off hides its tab (Design, Prototypes, Wiki, Architecture)',
          JSON.stringify(await tabs(page)) === JSON.stringify(['Travail']), JSON.stringify(await tabs(page)));
    await page.goto(FILE + '#design'); await page.waitForTimeout(350);
    check('modules: an address into a tab whose module is off falls back to the queue',
          (await page.$eval('nav a[aria-current=page]', (a) => a.textContent)) === 'Travail' && !(await page.$eval('#idea', (e) => e.hidden)));
    await page.goto(FILE + '#proto/702'); await page.waitForTimeout(350);
    check('modules: a prototype address with the proto module off falls back too', (await page.$eval('nav a[aria-current=page]', (a) => a.textContent)) === 'Travail');
    await page.evaluate((d) => window.__push('snapshots', 'Jonas-Eve__myavimobility', d), withMods({ dashboard: true, wiki: true, architecture: false, design: false, proto: true })); await page.waitForTimeout(250);
    check('modules: turning a module on shows its tab at the next snapshot, the others stay hidden',
          JSON.stringify(await tabs(page)) === JSON.stringify(['Travail', 'Prototypes', 'Wiki']), JSON.stringify(await tabs(page)));
    {
      const off = withMods({ dashboard: true, wiki: false, architecture: false, design: false, proto: false });
      const p2 = await open({ preload: [off] });
      const get = async (sub) => { await p2.goto(FILE + '#aide/' + sub); await p2.waitForTimeout(250); return p2.$eval('#view', (e) => e.innerText); };
      const md = await get('modules'), pr2 = await get('principes');
      check('modules off: the modules page says so and how to enable them', /désactivé/.test(md) && /module enable wiki/.test(md) && /module enable architecture/.test(md), md.slice(0, 300));
      check('modules off: the starting points do not suggest the commands of a module that is off', !/\/pilot-wiki|\/pilot-architecture|\/pilot-proto|\/pilot-design|\/pilot-flow/.test(pr2), pr2.slice(0, 200));
      await p2.close();
    }
    check('modules: no page errors', page.errors.length === 0, page.errors.join('|'));
    await page.close();
    page = await open({ preload: [BASE] });
    check('modules: a snapshot without the field shows every tab, as before',
          JSON.stringify(await tabs(page)) === JSON.stringify(['Travail', 'Prototypes', 'Design', 'Wiki', 'Architecture']), JSON.stringify(await tabs(page)));
    await page.close();
  }



  // ---- admin workflows: their runs show in their module's tab only; each has a launcher writing its exact command ----
  { const ADM = Object.assign({}, V6, { workflows: ['accept', 'build', 'design-system', 'express', 'functional-frame', 'need', 'personas-flows', 'plan', 'proto', 'report', 'technical-frame'],
      modules: { wiki: true, architecture: true, design: true, proto: true, dashboard: true },
      issues: V6.issues.concat([ticket(32, ['run:design-system'], { t: 'run:design-system Thème contraste' }), ticket(33, ['run:personas-flows', 'needs-human'], { t: 'run:personas-flows Persona Léa' }),
        ticket(34, ['run:functional-frame'], { t: 'run:functional-frame Vocabulaire' }), ticket(35, ['run:proto'], { t: 'run:proto Mon second proto' })]) });
    const AR = [
      run({ n: 31, workflow: 'technical-frame', step: 'write', state: 'running' }),
      run({ n: 32, workflow: 'design-system', step: 'build', state: 'running', loops: { check: 1 } }),
      run({ n: 33, workflow: 'personas-flows', step: 'gate', state: 'waiting-human' }),
      run({ n: 34, workflow: 'functional-frame', step: 'gate', state: 'failed' }),
      run({ n: 35, workflow: 'proto', step: 'build', state: 'running' }),
      run({ n: 36, workflow: 'technical-frame', step: 'end', state: 'done' }),
      run({ n: 16, workflow: 'build', step: 'implement', state: 'running' }),
    ];
    const ARUNS = 'section[aria-label="Runs de ce module"]';
    const o = { preload: [ADM], events: AR, design: [DESIGN], wiki: [{ kind: 'wiki', repo: REPO, at: iso(5), total: WIKI.entries.length + WIKI_FLOWS.entries.length, truncated: false, entries: WIKI.entries.concat(WIKI_FLOWS.entries) }], architecture: [ARCH], protos: PROTOS, protoHtml: PHTML };
    let pg = await open(Object.assign({ view: 'board' }, o));
    await tab(pg, 'Travail');
    check('admin runs: absent from the board', !/Thème contraste|Persona Léa|Vocabulaire|Mon second proto|Cadre technique/.test(await text(pg, '#view .board')) && (await pg.locator('#view .board .card').count()) === 12);
    await pg.click('#view .seg button:has-text("Liste")'); await pg.waitForTimeout(150);
    const wk = await text(pg, '#view');
    check('admin runs: absent from the Work tab (list and "Runs en cours"); the build run stays', !/Thème contraste|Persona Léa|Vocabulaire|Mon second proto/.test(wk) && /Runs en cours · 1\b/.test(wk) && (await pg.locator('#view section[aria-label="Runs en cours"] .row').count()) === 1);
    const rowsOf = (n) => pg.locator(`#view ${ARUNS} .row`, { hasText: '#' + n + ' ' }).first();
    const cmdsOf = async (n) => rowsOf(n).locator('a.btn').evaluateAll((as) => as.map((a) => decodeURIComponent((a.href.split('?q=')[1] || a.href).split('&repo=')[0]) + '|' + a.textContent.trim()));
    // Architecture
    await tab(pg, 'Architecture');
    check('Architecture: the technical-frame run at the top, with its Workflow button; the run of another module is not there', (await pg.locator(`#view ${ARUNS} .row`).count()) === 1 && /#31 /.test(await text(pg, `#view ${ARUNS}`)) && /Cadre technique/.test(await text(pg, `#view ${ARUNS}`)) && (await pg.locator(`#view ${ARUNS} button:has-text("Workflow")`).count()) === 1 && !/#36 /.test(await text(pg, '#view')));
    check('Architecture: the run is the first thing under the title', await pg.evaluate(() => { const v = document.querySelector('#view > .list'); return v.children[1].matches('section[aria-label="Runs de ce module"]'); }));
    await pg.click(`#view ${ARUNS} button:has-text("Workflow")`); await pg.waitForTimeout(150);
    check('Architecture: its timeline marks the current step (write) with the architect', (await pg.locator('#view .tl li[aria-current=step]').count()) === 1 && /Writer|Rédacteur|Architecte/.test(await pg.locator('#view .tl li.cur').textContent()) && /Architecte|Architect/.test(await pg.locator('#view .tl li.cur').textContent()));
    const archCmds = (await pg.$$eval('#view a.btn', (as) => as.map((a) => decodeURIComponent((a.href.split('?q=')[1] || '').split('&repo=')[0])))).filter(Boolean);
    check('Architecture: launchers write /pilot-architecture (question, --guideline, --lint) and the entry actions', ['/pilot-architecture', '/pilot-architecture --guideline', '/pilot-architecture --lint'].every((c) => archCmds.includes(c)) && archCmds.some((c) => /^\/pilot-architecture --(edit|accept|remove) /.test(c)) && !archCmds.some((c) => /--(bootstrap|verify|adr|scaffold)/.test(c)), JSON.stringify(archCmds.slice(0, 8)));
    // Design
    await tab(pg, 'Design');
    check('Design: the design-system run at the top, running, with its Workflow button and no resume (the workflow has none)', /#32 /.test(await text(pg, `#view ${ARUNS}`)) && /Design system/.test(await text(pg, `#view ${ARUNS}`)) && !(await cmdsOf(32)).some((c) => /--resume/.test(c)) && (await rowsOf(32).locator('button:has-text("Workflow")').count()) === 1);
    await pg.click('#designEToggle'); await pg.fill('#designText', 'thème sombre'); await pg.waitForTimeout(100);
    check('Design: the launcher command is /pilot-design <text>', (await text(pg, '#designCmd')) === '/pilot-design thème sombre');
    // Wiki: functional-frame and personas-flows runs
    await tab(pg, 'Wiki');
    const wt = await text(pg, `#view ${ARUNS}`);
    check('Wiki: the personas-flows run (waiting for a human, answered on GitHub) and the failed functional-frame run, at the top', (await pg.locator(`#view ${ARUNS} .row`).count()) === 2 && /#33 /.test(wt) && /#34 /.test(wt) && /Personas et user flows/.test(wt) && /Cadre fonctionnel/.test(wt) && /attend un humain/.test(await rowsOf(33).textContent()) && /échoué/.test(await rowsOf(34).textContent()) && /Répondre sur GitHub/.test((await cmdsOf(33)).join()));
    await rowsOf(33).locator('button:has-text("Workflow")').click(); await pg.waitForTimeout(150);
    check('Wiki: the waiting run says what it awaits at its gate', /Attendu : décision humaine à ce gate/.test(await rowsOf(33).locator('li.cur').textContent()));
    const wikiCmds = (await pg.$$eval('#view a.btn', (as) => as.map((a) => decodeURIComponent((a.href.split('?q=')[1] || '').split('&repo=')[0])))).filter(Boolean);
    check('Wiki: launchers write /pilot-wiki (question, --lint), /pilot-wiki --edit|--remove <id> and /pilot-flow --edit|--remove <id>', ['/pilot-wiki', '/pilot-wiki --lint'].every((c) => wikiCmds.includes(c)) && wikiCmds.some((c) => /^\/pilot-wiki --edit [a-z0-9-]+ $/.test(c)) && wikiCmds.some((c) => /^\/pilot-wiki --remove [a-z0-9-]+$/.test(c)) && wikiCmds.some((c) => /^\/pilot-flow --edit [a-z0-9-]+ $/.test(c)) && wikiCmds.some((c) => /^\/pilot-flow --remove [a-z0-9-]+$/.test(c)) && !wikiCmds.some((c) => /--bootstrap/.test(c)), JSON.stringify(wikiCmds.filter((c) => /flow/.test(c))));
    await pg.click('#view details.foldcard summary'); await pg.fill('#flowNewText', 'Léa, 16 ans'); await pg.waitForTimeout(100);
    check('Wiki: new persona writes /pilot-flow --new persona <text>, new flow --new flow', /\/pilot-flow --new persona Léa, 16 ans/.test(await text(pg, '#view details.foldcard')));
    await pg.click('#view details.foldcard button:has-text("Parcours")'); await pg.waitForTimeout(100);
    check('Wiki: a flow request writes /pilot-flow --new flow <text>', /\/pilot-flow --new flow Léa, 16 ans/.test(await text(pg, '#view details.foldcard')));
    // Prototypes
    await tab(pg, 'Prototypes');
    check('Prototypes: the proto run at the top, resumable, with its Workflow button', /#35 /.test(await text(pg, `#view ${ARUNS}`)) && /Prototype/.test(await text(pg, `#view ${ARUNS}`)) && (await rowsOf(35).locator('button:has-text("Workflow")').count()) === 1);
    await pg.click('#protoNToggle'); await pg.fill('#protoText', 'choisir'); await pg.waitForTimeout(100);
    check('Prototypes: the launcher writes /pilot-proto <idea>', (await text(pg, '#protoCmd')) === '/pilot-proto choisir');
    check('admin runs: no page errors', pg.errors.length === 0, pg.errors.join('|'));
    await pg.close();
    // a done run, or none, leaves the tab as it was
    pg = await open({ preload: [Object.assign({}, ADM, { issues: ADM.issues.filter((i) => i.n !== 31) })], events: [AR[5]], architecture: [ARCH] });
    await tab(pg, 'Architecture');
    check('Architecture: no run in progress, no runs section', (await pg.locator(`#view ${ARUNS}`).count()) === 0);
    await pg.close();
    // the one-place launcher
    pg = await open({ preload: [ADM], events: AR, wiki: [WIKI] });
    await tab(pg, 'Travail');
    check('admin launcher: folded by default, one kind per admin workflow whose module is on', await pg.$eval('#adminBody', (e) => e.hidden));
    await pg.click('#adminToggle');
    const kinds = () => pg.$$eval('#adminSeg button', (b) => b.map((x) => x.textContent));
    check('admin launcher: with the five modules on, six kinds (technical rule, wiki entry, design system, persona, flow, prototype)', JSON.stringify(await kinds()) === JSON.stringify(['Règle technique', 'Entrée du wiki', 'Design system', 'Persona', 'Parcours', 'Prototype']), JSON.stringify(await kinds()));
    const aCmd = () => text(pg, '#adminCmd');
    const aHref = async () => decodeURIComponent((await pg.$eval('#adminOpen', (a) => a.getAttribute('href') || '')).split('?q=')[1].split('&repo=')[0]);
    check('admin launcher: no link while the text is empty', (await pg.$eval('#adminOpen', (a) => a.getAttribute('aria-disabled'))) === 'true' && (await aCmd()) === '/pilot-architecture --guideline …');
    await pg.fill('#adminText', 'ma\ndemande'); await pg.waitForTimeout(100);
    for (const [label, cmd] of [['Règle technique', '/pilot-architecture --guideline ma demande'], ['Entrée du wiki', '/pilot-wiki --edit ma demande'], ['Design system', '/pilot-design ma demande'], ['Persona', '/pilot-flow --new persona ma demande'], ['Parcours', '/pilot-flow --new flow ma demande'], ['Prototype', '/pilot-proto ma demande']]) {
      await pg.click('#adminSeg >> text=' + label); await pg.waitForTimeout(80);
      check('admin launcher: ' + label + ' writes ' + cmd, (await aCmd()) === cmd && (await aHref()) === cmd, await aCmd());
    }
    for (const [mods, wfs, expect] of [[{ wiki: true, architecture: false, design: false, proto: false }, null, ['Entrée du wiki', 'Persona', 'Parcours']], [{ wiki: false, architecture: true, design: true, proto: true }, ['technical-frame', 'proto'], ['Règle technique', 'Prototype']]]) {
      const pn = await open({ preload: [Object.assign({}, ADM, { modules: Object.assign({ dashboard: true }, mods), workflows: wfs || ADM.workflows })] });
      await tab(pn, 'Travail'); await pn.click('#adminToggle');
      check('admin launcher: only the kinds whose workflow is in the snapshot and whose module is on', JSON.stringify(await pn.$$eval('#adminSeg button', (b) => b.map((x) => x.textContent))) === JSON.stringify(expect), JSON.stringify(await pn.$$eval('#adminSeg button', (b) => b.map((x) => x.textContent))));
      await pn.close();
    }
    const pnone = await open({ preload: [Object.assign({}, ADM, { modules: { dashboard: true, wiki: false, architecture: false, design: false, proto: false } })] });
    await tab(pnone, 'Travail');
    check('admin launcher: hidden when no admin module is on', await pnone.$eval('#admin', (e) => e.hidden));
    await pnone.close();
    check('admin launcher: no page errors', pg.errors.length === 0, pg.errors.join('|'));
    await pg.close(); }

  // ---- language: English shows no French left, French stays, the choice sticks and follows the project ----
  {
    const FR_WORDS = /[éèêàùçôîï]|\b(le|la|les|des|du|une|pour|avec|sur|dans|est|vous|votre|ou|ne|pas|il y a|aucun|aucune)\b/i;
    const leftovers = async (pg, routes) => {
      const out = [];
      for (const r of routes) {
        await pg.evaluate((x) => { location.hash = x; }, r); await pg.waitForTimeout(150);
        const t = await pg.evaluate(() => {
          const bits = [document.body.innerText];
          document.querySelectorAll('[title],[aria-label],[placeholder]').forEach((e) => ['title', 'aria-label', 'placeholder'].forEach((a) => { if (e.getAttribute(a)) bits.push(e.getAttribute(a)); }));
          return bits.join('\n');
        });
        const own = t.split('\n').filter((l) => FR_WORDS.test(l) && !/Ticket|Layering|Catalog|Autre projet|Jonas|myavimobility|\bProto\b|du proto|Trop complexe|Piège|Pas de blanc/.test(l));
        if (own.length) out.push('#' + r + ': ' + own.slice(0, 4).join(' ¦ '));
      }
      return out;
    };
    const EN6 = snapshot(V6.issues.map((i) => Object.assign({}, i, { t: (i.l.some((l) => l.startsWith('run:')) ? 'run:proto ' : '') + 'Item ' + i.n })), 120); EN6.workflowSteps = WFSTEPS;
    const full = { preload: [EN6], design: [DESIGN], wiki: [WIKI], architecture: [ARCH], protos: PROTOS, protoHtml: PHTML,
      events: PEVENTS.concat([run({ n: 16, loops: { check: 1 } }), run({ n: 40, workflow: 'need', state: 'waiting-human' }), run({ n: 41, workflow: 'accept', state: 'failed' }), run({ n: 13, workflow: 'plan', step: 'ask', state: 'waiting-human' })]) };
    let page = await open(Object.assign({ lang: 'en' }, full));
    const left = await leftovers(page, ROUTES.concat(['wiki', 'architecture', 'architecture/guidelines']));
    check('language: English shows no French in any tab', left.length === 0, left.join('\n   '));
    await page.close();
    page = await open(Object.assign({ lang: 'en', view: 'board' }, full));
    const lb = await leftovers(page, ['file']);
    check('language: English shows no French on the board', lb.length === 0, lb.join('\n   '));
    await page.evaluate(() => { location.hash = 'file'; }); await page.waitForTimeout(150);
    await page.click('#adminToggle');
    const wfb = page.locator('#view section[aria-label="Runs under way"] button[aria-expanded=false]:has-text("Workflow")');
    for (let guard = 0; guard < 10 && (await wfb.count()) > 0; guard++) { await wfb.first().click(); await page.waitForTimeout(80); }
    const lt = await leftovers(page, ['file']);
    check('language: English shows no French with a timeline and the admin launcher open', lt.length === 0 && (await page.locator('#view .tl').count()) > 0 && /To frame/.test(await text(page, '#view .board')) && /Awaited: human answer to the question asked/.test(await text(page, '#view')), lt.join('\n   ') + ' ' + (await page.locator('#view .tl').count()));
    await page.evaluate(() => { location.hash = 'aide/agents'; }); await page.waitForTimeout(150);
    check('language: English page is marked lang=en and the button says so', (await page.$eval('html', (e) => e.lang)) === 'en' && (await page.$eval('#langSeg button[aria-pressed=true]', (b) => b.textContent)) === 'EN');
    check('language: page errors', page.errors.length === 0, page.errors.join('|'));
    await page.evaluate(() => { location.hash = 'file'; }); await page.waitForTimeout(150);
    await page.click('#ideaToggle'); await page.fill('#ideaText', 'ma note');
    await page.evaluate(() => { location.hash = 'aide/agents'; }); await page.waitForTimeout(150);
    await page.click('#langSeg button[lang=fr]'); await page.waitForTimeout(200);
    check('language: switching to French translates back (tabs, form, footer) and keeps what was typed',
          /Travail/.test(await text(page, '#tabs')) && /Nouvelle demande/.test(await text(page, '#idea')) && /déployé le/.test(await text(page, '#version')) && (await page.inputValue('#ideaText')) === 'ma note');
    check('language: the choice is remembered', (await page.evaluate(() => localStorage.getItem('cp.lang'))) === 'fr');
    await page.close();
    page = await open({ lang: null, preload: [Object.assign({}, BASE, { language: 'fr' })] });
    check('language: with no choice yet the page follows the project language (fr)', /Travail/.test(await text(page, '#tabs')));
    await page.close();
    page = await open({ lang: null, preload: [Object.assign({}, BASE, { language: 'en' })] });
    check('language: and English when the project is English, or says nothing', /Work/.test(await text(page, '#tabs')));
    await page.close();
    page = await open({ lang: 'en', preload: [Object.assign({}, BASE, { language: 'fr' })] });
    check('language: a reader\'s own choice wins over the project language', /Work/.test(await text(page, '#tabs')));
    await page.close();
    const keys = fs.readFileSync(TEMPLATE, 'utf8');
    const stale = Object.keys(JSON.parse(keys.match(/var EN=(\{[\s\S]*?\n\});/)[1])).filter((k) => keys.split(k).length < 3);
    check('language: every English key is a French text the page really contains', stale.length === 0, stale.join(' | '));
  }

  // ---- renderer: the project name is HTML-escaped ----
  const escaped = render('A<b>"x"&y', 'o/r', path.join(TMP, 'escaped.html'));
  page = await browser.newPage(); await page.goto(escaped);
  check('renderer escapes the project name', (await page.textContent('h1')) === 'Cockpit A<b>"x"&y' && (await page.$('h1 b')) === null);
  await page.close();

  await browser.close();
  console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
  process.exit(results.every(Boolean) ? 0 : 1);
})();
