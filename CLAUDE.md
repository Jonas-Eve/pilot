# CLAUDE CODE GUIDE & DIRECTIVES — `pilot` REPO

## 0. REPLYING TO THE USER
Reply in the user's language, as concisely as possible without omitting information: lead with the outcome, then only what the user must know or decide (what changed, what is unverified, what is theirs to do). No recap of the steps taken, no restating the question, no filler, no list where one sentence does. Details go in the PR or the docs, not in the reply.

## 1. WHAT THIS REPO IS
This repo packages PILOT — a set of **workflows** where the human decides (through documents in a formatted intermediate language), agents execute and code checks —
for reuse across projects, as a **plain repo consuming projects clone and copy from**, not a Claude Code plugin. A plugin was tried first, but plugin installation turned out
to be local to whichever machine/container runs it and never reached Claude Code on the web or the mobile app, so the distribution model is deliberately "clone this repo,
copy its `.claude/skills/`/`.claude/agents/` into your project's own `.claude/`" — the same mechanism as any other project-local skill, identical on every surface. This repo is
not itself an application, but it has a vision (`wiki/product/vision.md`, read first by the PM and designer personas).

The canonical spec of what every workflow shares is `assets/docs/pilot-process.md`: where objects live, statuses and flags, the run, claim and resume, isolation, events, modules.
Read it before changing a skill, an agent, a label or `scripts/pilot.py`; those files must never drift from it. It is genericized on purpose (no reference to a consuming project).

A workflow is data: `assets/workflows/<id>.json` (steps, kinds, personas, task docs, checks, judges, where a failure goes, a contract of statuses). Its skill runs it as
`assets/docs/pilot-link-runner.md` says: `pilot.py` serves one step at a time, an agent call gets only its persona, its task doc, `pilot-link-agent-contract.md` and the typed documents
of the step, and `pilot.py run advance` decides the next step from the data. The formats of the documents the checks validate are `assets/formats.json`.

## 2. STRUCTURE
- `.pilot/`, `.github/`, `wiki/`, `architecture/` — this repo runs PILOT on itself (modules `dashboard`, `wiki`, `architecture`). `.pilot/` and `.github/workflows/pilot-status-on-merge.yml` are
  verbatim copies of `scripts/pilot.py`, `scripts/pilot_checks.py`, `assets/`, PILOT-owned like in any project: never edited here, synced from the published `main` by `/pilot-update`, so they lag a change until it
  is merged and synced. The sources stay `assets/`, `scripts/` and `.claude/`; `scripts/test_pilot.py` runs from an empty directory so the repo's own `.pilot/state.json` never changes what it sees.
- `assets/workflows/*.json` — the eleven workflows, copied into a project as `.pilot/workflows/`. A workflow may `include` another's steps (the express runs the build's). `pilot.py workflow check` validates them.
- `assets/formats.json` — the document formats the checks validate (copied as `.pilot/formats.json`).
- `.claude/skills/<name>/SKILL.md` — one per slash command, copied verbatim into a project's `.claude/skills/`; all fifteen carry the `pilot-` prefix a project-local skill needs. The six run workflows
  `pilot-need`, `pilot-plan`, `pilot-build`, `pilot-accept`, `pilot-report`, `pilot-express`; the five module skills run an admin workflow and keep their other modes: `pilot-architecture` (technical frame),
  `pilot-wiki` (functional frame), `pilot-design` (design system), `pilot-proto` (prototype), `pilot-flow` (personas and user flows); `pilot-init`, `pilot-update`, `pilot-dashboard`, `pilot-help` maintain and
  explain the rest. `pilot-help` is read-only: it lists, explains, turns a goal into the exact command, or names the persona responsible.
- `.claude/agents/<name>.md` — the seven personas (`pilot-pm`, `pilot-architect`, `pilot-techlead`, `pilot-dev`, `pilot-e2e`, `pilot-qa`, `pilot-designer`). Each carries only its identity; its duties are the task docs
  the workflow data gives it (`python3 scripts/lint_pilot.py` checks that its list matches). A persona is lead (it understands the need), validator (another persona that receives the deliverable alone) or reviewer, by workflow.
  The judge has no persona.
- `assets/docs/pilot-process.md` — the generic spec (§1 of this file). `pilot-link-<topic>.md` — a doc read by two or more, not all, skills: `runner` (running any workflow), `agent-contract` (what an agent call
  returns; injected whole into every agent call), `knowledge`, `wiki`, `architecture`, `dashboard`. `pilot-task-<duty>.md` — one persona's instructions for one duty, injected by the runner into the agent call; never read by the persona itself.
- `assets/templates/*.tmpl` — doc skeletons `/pilot-init` renders. `pilot-intro-*`, `pilot-maintenance-claude`, `pilot-architecture-*`, `pilot-commands-*` are canonical marked-block contents (`PILOT:INTRO`, `PILOT:MAINTENANCE`,
  `PILOT:ARCHITECTURE`, `PILOT:COMMANDS`) embedded in `CLAUDE.md.tmpl`/`README.md.tmpl` and re-synced by `/pilot-update` without touching the rest of the project's files. **Any PILOT-specific sentence in
  `CLAUDE.md.tmpl`/`README.md.tmpl` belongs inside a `PILOT:<name>` marker with a matching canonical snippet — never bare in the template.** `pilot-dashboard.html.tmpl` is the page `/pilot-dashboard` renders and publishes as one
  private Artifact per project; checked by `scripts/test_dashboard.js`. While developing the page, publish it to the demo artifact "Cockpit pilot (démo)" (fake data from `scripts/demo_snapshot.py`), never to a real project's dashboard.
- `assets/github/` — the merge workflow (`pilot.py ticket merged` for a PR a human merges) and the PR template, copied into a project.
- `scripts/pilot.py` + `scripts/pilot_checks.py` — PILOT's deterministic mechanics as a CLI, **the reference for them**, copied as `.pilot/pilot.py` and `.pilot/pilot_checks.py`. `pilot_checks.py` holds the code checks
  of the workflows' `check` steps and the format validators. Commands: `workflow` (list, show, one step, check), `contract`, `pool`/`resolve`/`claim`/`set`/`flag`/`unflag`, `run` (start, show, note, advance, resume, end), `check`,
  `judge`, `ticket` (create, close-forming, drop, merged), `derive`, `pr` (open, ci, merge), `labels` (sync, migrate), `config`, `doctor`, `module`, `snapshot`, `event`, `proto-pack`, `flow`, `wiki`, `arch`. Every command prints
  one JSON object. Judgment never lives in it: which agent to call, what a document says. `pilot-process.md` keeps the contract; an exact condition is changed in the script and `scripts/test_pilot.py`
  (`python3 -m unittest scripts/test_pilot.py`) first, then the contract text if it no longer matches.
- `scripts/lint_pilot.py` — maintainers' coherence linter, never copied into a project: doc references, orphan docs, the workflow data against the files it names (task docs, personas, a skill per workflow), persona duty lists derived from the
  workflows, label vocabulary and `pilot.py` commands cited against `pilot.py`, quoted section titles, counts in words, `argument-hint` flags, template markers, size of the LLM-read files. Runs in CI with `test_lint_pilot.py` and `test_pilot.py`
  (`.github/workflows/lint-pilot.yml`); run it after any edit of the families §3's cross-reference check names.
- `.claude/settings.json` + `scripts/hooks/repo_hook.py` — maintainers' hooks, never copied: refuse an edit of a PILOT-owned copy, run `lint_pilot.py` after an edit of a file it covers, and refuse a PR creation while the diff
  touches what projects copy and no maintainer review of that exact diff returned `VERDICT: PASS` (`docs/maintainer-review.md`; why none ships to projects: `docs/hooks-findings.md`).

Within a skill file, reference this repo's own assets via a fresh clone of `https://github.com/Jonas-Eve/pilot` into a scratch directory (`$PILOT_SRC`) — never a fixed path.

## 3. CHANGE DISCIPLINE
- **Deterministic first — code over prose:** whatever can be decided by code (a script, a check, a test, a linter, a hook) is, and the prose that explained it leaves the LLM-read files. A rule written in a `SKILL.md` or task doc that a
  command could compute or check is a candidate to move: into `scripts/pilot.py`/`pilot_checks.py` (and tests) for ticket and document mechanics, into `lint_pilot.py` for this repo's coherence, into this repo's hooks for a constraint
  on what the model does here. Prose keeps only judgment. A judge asks only what no code check can. The test of a new rule: could a check fail on it? Then write the check.
- **Mechanism vs. wording:** the workflow data, the statuses and labels, the claim protocol and the formats are the actual product. A mechanism change affects every project that copied from this repo: don't change it casually.
- **No duplication, token discipline:** every fact lives once. `.claude/skills/*/SKILL.md`, `.claude/agents/*.md` and every `assets/docs/pilot-*.md` load into an agent's context on every run they take part in — keep them essential-only:
  no meta-commentary, platform-quirk explanations, maintainer rationale or history. What only a human needs goes in a doc no skill or agent reads (this file, `docs/`). `workflow show --step` serves one step; never make an agent read a whole workflow.
- **Three tiers — generic, link, or single-skill:** generic — needed by every workflow (where objects live, statuses, claim, isolation) — goes in `pilot-process.md` only. Link — needed by two or more but not all skills/agents — goes in its own
  `pilot-link-<topic>.md`. Single-skill — everything else — stays in that skill's `SKILL.md`. Tool names and API-call detail belong in the owning `SKILL.md` regardless of tier. `grep` which other files would need to cite new content *before* deciding where it goes.
- **A workflow documents only its contract:** where it comes from, what it does, where it goes — the statuses and artifacts it consumes and produces (`pilot.py contract <workflow>`), never the workflows around it. What links two workflows is a link doc or a
  status. A link doc's content is identical for every consumer; a per-duty delta stays in that duty's task doc. Inject a link doc whole into an `Agent` call, never "only section X".
- **Persona files carry identity only; duties are task docs:** `.claude/agents/pilot-*.md` holds the stable trait every duty of the persona shares and ends with the list of its task docs (derived from the workflow data and checked by the linter).
  A new duty is a task doc, a `task` on a workflow step, and nothing in the persona file but that list. A task doc never assumes this invocation remembers an earlier one: write "the recorded decisions", never "the decisions you recorded" —
  that is a trait of the persona and lives once in the identity file. When editing a persona or one of its task docs, skim the others for a principle that should apply everywhere.
- **Cross-reference check:** `assets/docs/pilot-process.md`, every `pilot-link-*.md` and `pilot-task-*.md`, every `SKILL.md`, every agent file, `assets/workflows/*.json`, `assets/formats.json` and the PILOT mentions in this file and `README.md` are tightly
  cross-referenced. After editing any, run `python3 scripts/lint_pilot.py` and `grep` the exact term you changed across the family.
- **Coherence check beyond the grep:** before calling a mechanism change done, walk the state combinations it touches (a ticket assigned but unlabeled, a run waiting while its issue is flagged, both flags at once) and confirm each is handled,
  against the *whole* file the change lands in, not only the new content. Then re-run the three-tiers test on what the change turned into.
- **Renaming or removing a skill, agent or doc:** `/pilot-update` diffs a project's copies against this repo and deletes what no longer exists upstream — keep `.claude/` and `assets/` accurate and it reconciles.
- **PILOT never leaves unmarked content in a hybrid file:** a sentence only PILOT can keep accurate (a command name, a path under its control) lives inside a `<!-- PILOT:<name>:START -->`/`END` marker with a canonical snippet in `assets/templates/`.

## 4. GIT WORKFLOW
- **Version Every Change Projects Would Copy (`VERSION`, SemVer):** `VERSION` holds PILOT's
  `MAJOR.MINOR.PATCH`; `/pilot-init` and `/pilot-update` record it in the project's
  `.pilot/state.json` (`pilotVersion`) and the dashboard footer shows it. A PR that changes
  anything a project copies (skills, agents, `assets/docs`, `scripts/pilot.py`, `scripts/pilot_checks.py`, the
  dashboard template) bumps it once, in the PR itself: **patch** for a fix or wording that
  changes no mechanism, **minor** for a backward-compatible capability (a new skill, flag,
  command or dashboard feature), **major** for a mechanism change that makes a project act
  (a renamed label or status, a changed claim protocol or state machine). A PR touching none
  of those (this file, tests alone, demo data) leaves it alone. `scripts/test_pilot.py`
  (`VersionBumpTests`) fails a branch that changed what projects copy without raising
  `VERSION` above `origin/main`'s — it checks that it went up, not that the level is right.
- **Commit Freely On A Work Branch, Never On `main`:** on a short-lived work branch,
  committing and pushing completed work is authorized by default. On `main`, never
  commit or push without the user explicitly asking in the current task.
- **Amend, Don't Stack, Within The Same Not-Yet-Merged Context:** if a new commit only
  fixes or completes the change the immediately preceding, not-yet-merged commit made,
  amend that commit instead of stacking a separate one. Once merged into `main`, or once
  another branch depends on it, it's shared history — never amend or force-push it.
- **Keep A Work Branch Current By Rebasing, Never By Merging `main` In:** bring a work branch up to date
  with `git rebase origin/main`, then push it with `--force-with-lease` (the branch is yours alone, and a
  branch that only carries already-merged history is restarted from `main` the same way), so its history stays
  linear and every commit stays meaningful. Never create a merge commit, on a branch or on `main`.
- **Review A PILOT Change Before Opening Its PR:** a branch that touches what projects copy gets the maintainer review
  (`docs/maintainer-review.md`) from an agent that did not write it, run in the foreground (the hook reads its answer): fix every finding and run it again until it returns
  `VERDICT: PASS` on the current diff. The hook refuses the PR's creation until then.
- **Trunk-Based Development:** `main` is the single trunk; short-lived branches merge
  back quickly, no long-lived feature branches.
- **Conventional Commits:** `type(scope): description` (e.g.
  `feat(skills): add architecture scaffold for Expo mobile`). `scope` is typically the
  affected top-level dir (`skills`, `agents`, `scripts`, `docs`) or omitted for
  repo-wide changes.
- **Squash Merge By Default, Rebase Merge For Deliberately Separate Commits:** squash a PR
  into `main` as one commit unless it carries multiple commits that are each independently
  meaningful on purpose (not fixups of an earlier commit in the same PR — those should have
  been amended per the rule above) — rebase-merge those instead, to keep them distinct in
  `main`'s history. Never force-push `main`, and never a merge commit either way.
