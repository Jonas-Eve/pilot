# Maintainer review of a change to PILOT

Human and agent document for the maintainers of this repo: not read by any skill or agent of a project, not copied
into one. A PR that touches what projects copy gets this review before it is opened, from an isolated agent that did not
write the change. The gate is `scripts/hooks/repo_hook.py` (`pr-gate`, `review-track`): `create_pull_request` is refused
until a review of the current diff returned `VERDICT: PASS`.

## How to run it

Spawn one agent (any read-only capable type) with this prompt, and nothing that argues for the change:

> Read `docs/maintainer-review.md` and `CLAUDE.md` §3-§4, then review the diff `git diff $(git merge-base HEAD origin/main)`
> plus untracked files, as that document says. Read-only: change nothing. Reply in its output format.

Fix every finding, commit, and run it again: the verdict counts only for the diff it saw.

## What the reviewer does

Start from the diff and the repo as it is. For every changed term (label, status, flag, command, file name, heading), `grep`
the family CLAUDE.md §3 names (process doc, link and task docs, skills, agents, `pilot.py`, templates, README, CLAUDE.md)
and read what turns up. Then:

### 1. Coherence (what `lint_pilot.py` cannot see)
- **Contradiction:** a rule the change adds or edits against the rest of the *whole* file it lands in, and against the rule in
  every other file that states the same thing. Quote both sides.
- **Tier:** each addition at the right level (generic → `pilot-process.md`, some phases → a link doc, one phase → its
  `SKILL.md`; a persona's duty → a task doc, never the persona file). A paragraph describing a neighbouring phase or the chain
  is in the wrong place.
- **State space:** a change to a status, flag, label, claim or pool rule: list the ticket shapes it touches (status × assignee ×
  `needs-human`/`on-hold`/`can-resume` × type × level, with and without the optional modules) and name any shape no rule handles
  or two rules handle oppositely.
- **Persona consistency:** a principle changed in one task doc of a persona that its other task docs do not follow.
- **Token discipline:** meta-commentary, maintainer rationale or history in a file an agent loads.
- **Deterministic first:** a rule added in prose that a command, a test, the linter or a hook could check.

### 2. Completeness (the holes)
- **Version:** any file projects copy changed (`.claude/skills/`, `.claude/agents/`, `assets/`, `scripts/pilot.py`,
  `scripts/pilot_hook.py`, `scripts/setup-github-labels.sh`) → `VERSION` raised, at the right level (CLAUDE.md §4: patch / minor / major).
- **A new or renamed label, status, flag, command, module or skill → every place that names it:** `pilot-process.md`,
  `pilot.py` docstring and `--help`, the CLAUDE.md §2 `pilot.py` paragraph, `pilot-help`, `/pilot-init` and `/pilot-update`,
  the dashboard "i" page (`HOW_PHASES`, `HOW_TABS`, `vHow*`, `AGENTS`, `ROSTER`) and `scripts/test_dashboard.js`,
  `scripts/demo_snapshot.py`, the canonical template snippets, README, counts written in words ("fifteen skills").
- **A behaviour change in `pilot.py`** → a test in `scripts/test_pilot.py` that fails without it, and the contract text in
  `pilot-process.md` if it no longer matches.
- **A new skill, agent or doc** → listed where CLAUDE.md §2 lists its kind, a persona's duties paragraph updated, a
  `/pilot-update` effect (copy, or delete if it replaces a retired file).
- **A rule now enforced by code or a hook** → the prose that stated it removed, unless the enforcing module is opt-in (then
  say which).
- **The PR itself:** its description says what changed, what is unverified and what the human must do; the template's
  headings are filled.
- Anything the change implies and does not do (a flag documented but not parsed, a skill step that calls a command with a flag
  the command lacks, a doc promising a behaviour the script does not have).

Run `python3 scripts/lint_pilot.py` and the two test suites first; report only what they cannot.

## Output format

First line, exactly one of `VERDICT: PASS` or `VERDICT: FINDINGS`. Then, for FINDINGS, one entry per finding: the file and
line, the rule above it breaks, what is wrong or missing in one sentence, the concrete fix. No praise, no summary of the diff,
no finding you could not point at a line for. `PASS` only when nothing in either part holds.
