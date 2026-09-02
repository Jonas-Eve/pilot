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

At runtime, a phase skill reads up to three layers, not just its own file:
`pilot-process.md` for the generic mechanics every phase shares (labels, claim protocol,
pair/`--auto`), whichever `pilot-link-<topic>.md` doc(s) it's named in for coordinating
with the specific other skills/agents it hands off to or reads from, and its own
`SKILL.md` for its own orchestration mechanics. §3 below ("Three tiers") is the mirror
image of this for writing new content — decide the tier, then add it to the matching
layer instead of the file you happen to already be editing.

The actual judgment work happens in an isolated `Agent` call to one of the six personas
(`.claude/agents/pilot-*.md`). Each of those carries only that persona's stable
identity — never any duty's specific instructions, even for a persona with several
duties (the architect formalizes, scopes, *and* reviews). What to actually do arrives in
the prompt: the calling skill reads the matching `assets/docs/pilot-task-<duty>.md` and
passes its content as part of the `Agent` call, so a persona never carries — or loads —
instructions for a duty it isn't performing right now. §3 below ("Task docs") covers
when new persona-facing content belongs in one of these instead of the persona file
itself.

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
  Each file carries only that persona's identity (who it is, what judgment it brings) —
  never a duty's mechanics, even for a persona with several duties. Duty instructions
  live in `assets/docs/pilot-task-<duty>.md` instead (below), injected into the `Agent`
  call's prompt by whichever skill owns that duty.
- `assets/docs/pilot-process.md` — canonical process spec, copied verbatim into a
  consuming project as `docs/pilot-process.md` by `/pilot-init` and re-synced by
  `/pilot-update`. Contains only what a skill or agent needs to operate — no purely
  illustrative material (a diagram, a worked example) belongs here.
- `assets/docs/pilot-process-companion.md` — a purely human-facing companion to the above
  (currently a sequence diagram), synced the same way, for a human getting oriented; no
  skill or agent reads it. Anything added to help a human understand the process, rather
  than something a skill/agent needs to run it, goes here instead of bloating
  `pilot-process.md`.
- `assets/docs/pilot-link-<topic>.md` — a cross-skill link doc: operational like
  `pilot-process.md` itself (a skill/agent reads it to run), but scoped to the specific
  two-or-more skills/agents it names rather than all of them — the opposite of a
  companion, which is human-only and read by none. Copied verbatim into a consuming
  project as `docs/pilot-link-<topic>.md` the same way as `pilot-process.md`. Holds
  content that connects a subset of skills (e.g. how phase 5's reviewers and phase 4's
  reclaim need to agree on something) — see §3 below for when content belongs here
  instead of `pilot-process.md` or a single `SKILL.md`.
- `assets/docs/pilot-task-<duty>.md` — one persona's instructions for one specific duty
  (e.g. the architect scoping a story, vs. the architect reviewing a PR) — never read by
  the persona itself via its own `Read`, but injected into the `Agent` call's prompt by
  the one skill that owns that duty. Copied verbatim into a consuming project as
  `docs/pilot-task-<duty>.md` the same way as `pilot-process.md`. This is what keeps
  `.claude/agents/pilot-*.md` down to pure identity: a persona with several duties (the
  architect, the PM, the tech lead) gets one task doc per duty, never all of them bundled
  into the persona file where every invocation would load them regardless of relevance.
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
  `.claude/agents/*.md`, `assets/docs/pilot-process.md`, every `pilot-link-*.md`, and
  every `pilot-task-*.md` load into an agent's context on every run they take part in —
  keep them to only what a skill or agent needs to operate correctly. No meta-commentary,
  platform-quirk explanations, maintainer rationale, or
  historical notes about why something is the way it is. If something is worth writing down
  for a human but doesn't change what an agent does, it belongs in a doc no skill or agent
  reads instead, never padded into the file an LLM actually loads — `assets/docs/pilot-process-companion.md`
  is the existing example for `pilot-process.md` (§2), but nothing requires reusing it or any
  other existing doc: pick whichever already-existing human-only doc actually fits the
  information, or create a new one next to the skill/agent/doc it explains, whichever the
  content itself calls for. Renaming or retiring one of these human-only docs is a rename
  like any other — `/pilot-update` must actually delete the old file in an already-initialized
  project, not just add the new one (see its own `SKILL.md`).
- **Three tiers, not two — generic, link, or single-skill:** before adding anything
  anywhere, decide which of three tiers it actually belongs to. Generic — genuinely needed
  by *every* phase skill/agent (the label taxonomy, claim protocol, state-machine
  transitions, the pair/`--auto` contract) — goes in `pilot-process.md`, and only there.
  Link — needed by *two or more but not all* skills/agents to coordinate with each other
  (e.g. how phase 5's submitted review and phase 4's reclaim must read the same tags) —
  goes in its own `assets/docs/pilot-link-<topic>.md` (§2), never bloating
  `pilot-process.md` with something most phases never read. Single-skill — everything else,
  including how one specific phase claims, what it does mid-run, and how it wraps up, even
  when that phase is the one you're currently changing — stays in that skill's own
  `SKILL.md`, never promoted up a tier just because it's the thing you're focused on right
  now. `grep` for which other files would actually need to cite it (the check below
  already asks you to grep after editing — run it *before* deciding where new content
  goes, not just after): zero others → single-skill; some but not all → a link doc; all
  six phases → `pilot-process.md`. Tool names and API-call-level detail belong in the
  owning `SKILL.md` regardless of tier, never in `pilot-process.md` or a link doc.
- **Persona files carry only identity; duty instructions are task docs:** this tiering
  decides where a *skill's own* content goes — a persona's content is a different split
  again. `.claude/agents/pilot-*.md` holds only the stable trait every one of that
  persona's duties shares (what kind of judgment it brings); it's loaded in full on
  *every* invocation of that persona, so anything specific to one duty (how to scope,
  how to review, how to write a spec) never belongs there, even for a persona with only
  one duty today — put it in `assets/docs/pilot-task-<duty>.md` instead (§2), read and
  injected into the `Agent` call's prompt by the one skill that owns that duty. Adding a
  new duty to an existing persona (a new phase that also calls the architect, say) means
  a new task doc, a new citation in the calling skill, and a new entry in the persona
  file's own duties list (below) — never a new section appended to the persona file
  itself.
- **Keep a persona's judgment consistent across its split files:** splitting a
  multi-duty persona into an identity plus several task docs removes the "same file,
  scroll up to see the other duty" safety net that used to make an accidental
  contradiction between duties easy to spot. Nothing greppable catches a *judgment*
  drift (the same heuristic phrased subtly differently in two task docs) the way the
  check below catches a renamed term, so each `.claude/agents/pilot-*.md` ends with a
  one-line list of its own task doc(s) precisely so this stays checkable by hand: when
  editing that identity or any one of its task docs, skim the others in the list too for
  a principle that should apply everywhere but doesn't yet, or was rephrased
  inconsistently. Keep that list itself in sync with the previous bullet's rule.
- **Cross-reference check:** `assets/docs/pilot-process.md`, every `assets/docs/pilot-link-*.md`,
  `pilot-process-*.md`, and `pilot-task-*.md`, every `.claude/skills/*/SKILL.md`, every
  `.claude/agents/pilot-*.md`, and the PILOT mentions in this file and `README.md` are
  tightly cross-referenced. After editing any of them, `grep` the exact term(s) you
  changed (a renamed label, a moved section heading, a link/task doc's filename) across
  that whole family and fix what turns up, rather than re-reading every file end to end.
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
- **Squash Merge By Default, Rebase Merge For Deliberately Separate Commits:** squash a PR
  into `main` as one commit unless it carries multiple commits that are each independently
  meaningful on purpose (not fixups of an earlier commit in the same PR — those should have
  been amended per the rule above) — rebase-merge those instead, to keep them distinct in
  `main`'s history. Never force-push `main`, and never a merge commit either way.
