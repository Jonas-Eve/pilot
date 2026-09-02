# CLAUDE CODE GUIDE & DIRECTIVES — `pilot` REPO

## 1. WHAT THIS REPO IS
This repo packages PILOT — a 6-phase ticket-process framework — for reuse across
projects, as a **plain repo consuming projects clone and copy from**, not a Claude Code
plugin. A plugin was tried first, but plugin installation turned out to be local to
whichever machine/container runs it (a Codespace, a local CLI) and never reached Claude
Code on the web or the mobile app, so the distribution model here is deliberately just
"clone this repo, copy its `.claude/skills/`/`.claude/agents/` into your project's own
`.claude/`" — same paths on both sides, the same mechanism as any other project-local
skill, which works identically on every surface. This repo is not itself an application;
there is no "functional scope" here beyond its own content.

The canonical, always-up-to-date spec for the process this repo implements lives at
`assets/docs/pilot-process.md`. Read it before changing any skill, agent, or label —
those files must never drift from what it describes. It is genericized on purpose (no
references to any one consuming project); when porting a change from a project that
forked PILOT, strip project-specific details the same way.

## 2. STRUCTURE
- `.claude/skills/<name>/SKILL.md` — one per slash command, copied verbatim into a
  consuming project's `.claude/skills/<name>/SKILL.md` by `/pilot-init` (and kept in
  sync by `/pilot-update`) — same path on both sides. All ten carry the `pilot-`
  prefix a project-local skill needs to avoid colliding with the project's own — there's
  no plugin namespace to rely on instead. `pilot-init`, `pilot-init-archi`,
  `pilot-update` are this repo's own bootstrap/maintenance commands; `pilot-story`,
  `pilot-scope`, `pilot-spec`, `pilot-dev`, `pilot-review`, `pilot-qa` are the six PILOT
  phases; `pilot-auto` is a dispatcher over the four auto-capable phase sweeps (review,
  dev, spec, scope) — not itself a phase, adds nothing to `pilot-process.md`'s state
  machine (see that skill's own file for its mechanics).
- `.claude/agents/<name>.md` — the six personas (`pilot-pm`, `pilot-architect`,
  `pilot-techlead`, `pilot-dev`, `pilot-e2e`, `pilot-qa`) the phase skills delegate to via
  the `Agent` tool, copied into a consuming project's `.claude/agents/` the same way.
- `assets/docs/pilot-process.md` — canonical process spec, copied verbatim into a
  consuming project as `docs/pilot-process.md` by `/pilot-init` and re-synced by
  `/pilot-update`. Contains only what a skill or agent needs to operate — no purely
  illustrative material (a diagram, a worked example) belongs here.
- `assets/docs/pilot-process-visual.md` — a purely human-facing companion to the above
  (currently a sequence diagram), synced the same way, for a human getting oriented; no
  skill or agent reads it. Anything added to help a human understand the process, rather
  than something a skill/agent needs to run it, goes here instead of bloating
  `pilot-process.md`.
- `assets/templates/*.tmpl` — doc skeletons `/pilot-init` renders with `{{PLACEHOLDER}}`
  substitution. `pilot-intro-claude.md.tmpl` / `pilot-intro-readme.md.tmpl` and
  `pilot-maintenance-claude.md.tmpl` are canonical marked-block contents (`PILOT:INTRO`,
  `PILOT:MAINTENANCE`), embedded inside `CLAUDE.md.tmpl`/`README.md.tmpl` at init time
  and re-synced by `/pilot-update` from those same files without touching the rest of
  the consuming project's `CLAUDE.md`/`README.md`. **Any PILOT-specific sentence in
  `CLAUDE.md.tmpl`/`README.md.tmpl` belongs inside a `PILOT:<name>` marker with a
  matching canonical snippet here — never bare in the template** — that's what keeps a
  consuming project's own prose free of content only PILOT can keep current (see
  §3 below).
- `scripts/setup-github-labels.sh` — idempotent GitHub label provisioning, run by both
  `/pilot-init` and `/pilot-update`; also bumps the calling project's own
  `.pilot/state.json` (`lastLabelsSyncAt`) itself when run from that project's root, if
  the file already exists there.

Within a skill file, reference this repo's own assets via a fresh clone of
`https://github.com/Jonas-Eve/pilot` into a scratch directory (called `$PILOT_SRC` in
the skill files) — never a fixed path, there is no installed location.

## 3. CHANGE DISCIPLINE
- **Mechanism vs. wording:** the phase names, label taxonomy, claim protocol, and
  skill-to-agent mapping in `assets/docs/pilot-process.md` are the actual product. Don't
  change them casually; a mechanism change here affects every project that has copied
  from this repo, not just one.
- **Token discipline — LLM-read files stay essential-only:** `.claude/skills/*/SKILL.md`,
  `.claude/agents/*.md`, and `assets/docs/pilot-process.md` load into an agent's context on
  every run they take part in — keep them to only what a skill or agent needs to operate
  correctly. No meta-commentary, platform-quirk explanations, maintainer rationale, or
  historical notes about why something is the way it is. If something is worth writing down
  for a human but doesn't change what an agent does, it belongs in a doc no skill or agent
  reads instead, never padded into the file an LLM actually loads — `assets/docs/pilot-process-visual.md`
  is the existing example for `pilot-process.md` (§2), but nothing requires reusing it or any
  other existing doc: pick whichever already-existing human-only doc actually fits the
  information, or create a new one next to the skill/agent/doc it explains, whichever the
  content itself calls for.
- **Cross-reference check:** `assets/docs/pilot-process.md`, every `.claude/skills/*/SKILL.md`,
  every `.claude/agents/pilot-*.md`, and the PILOT mentions in this file and `README.md` are
  tightly cross-referenced. After editing any of them, `grep` the exact term(s) you
  changed (a renamed label, a moved section heading) across that whole family and fix
  what turns up, rather than re-reading every file end to end.
- **Renaming or removing a skill/agent:** `/pilot-update` handles this by diffing a
  project's locally-copied skills/agents against this repo's current `.claude/skills/`/
  `.claude/agents/` and flagging anything that no longer matches anything upstream as
  orphaned (see `.claude/skills/pilot-update/SKILL.md`) — there's no separate
  version/rename log to maintain here, just keep this repo's own `.claude/skills/`/
  `.claude/agents/` accurate and `/pilot-update` will reconcile a project's copy against
  it next time it runs.
- **PILOT never leaves unmarked content in a hybrid file:** `CLAUDE.md`/`README.md` in a
  consuming project are otherwise project-owned, so any sentence only PILOT can keep
  accurate (a command name, a file path under its control) must live inside a
  `<!-- PILOT:<name>:START -->`/`END` marker with a matching canonical snippet in
  `assets/templates/`, never as bare prose in `CLAUDE.md.tmpl`/`README.md.tmpl` — a bare
  mention there goes stale the moment something renames and `/pilot-update` has no marker
  telling it where to fix it. A project's own files that happen to reference a PILOT
  command by choice (a PR template, an unrelated skill) are a different case — that's the
  project's own doc-maintenance burden, not a gap in this rule.

## 4. GIT WORKFLOW
- **Commit Freely On A Work Branch, Never On `main`:** on a short-lived work branch,
  committing and pushing completed work is authorized by default. On `main`, never
  commit or push without the user explicitly asking in the current task.
- **Amend, Don't Stack, Within The Same Not-Yet-Merged Context:** if a new commit only
  fixes or completes the change the immediately preceding, not-yet-merged commit made,
  amend that commit instead of stacking a separate one. Once merged into `main`, or once
  another branch depends on it, it's shared history — never amend or force-push it.
- **Trunk-Based Development:** `main` is the single trunk; short-lived branches merge
  back quickly, no long-lived feature branches.
- **Conventional Commits:** `type(scope): description` (e.g.
  `feat(skills): add pilot-init-archi scaffold for Expo mobile`). `scope` is typically the
  affected top-level dir (`skills`, `agents`, `scripts`, `docs`) or omitted for
  repo-wide changes.
- **Rebase Merge Only:** PRs merge into `main` via rebase merge, keeping history linear.
  Never force-push `main`.
