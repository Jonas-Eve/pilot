# PILOT Wiki — design proposal

Status: **proposal, nothing implemented**. Human-only document: no skill or agent reads it,
and it is not copied into consuming projects. It lives outside `assets/` on purpose.
Once validated, its contract moves into `assets/docs/` (see §9) and this file is removed.

## 1. Goal

Tickets describe deltas, prototypes are mockups, specs are throwaway. Nothing says what the
product does **today**, or what is promised and not yet built. The wiki is that source of
truth, for agents and humans, as markdown files in the consuming project's repo.

## 2. Principles

1. **The wiki is right, the code conforms.** A divergence is either a bug (the code is wrong)
   or a decision (the wiki must change) — never silently both.
2. **Only a PR changes the wiki.** No commit to `main` outside a PR. A code PR carries its own
   wiki change, so `main` and every branch stay internally coherent, and a PR closed without
   merge leaves no trace.
3. **Durable states are written, in-flight states are derived.** The files hold only what a
   merged PR can make true. Everything else is computed from ticket labels at read time.
4. **Wiki changes ride existing human checkpoints.** Discovery's brief validation, Spec's
   split validation, the PR review, QA. No new approval step.
5. **Verification is a measurement, not a signature.** `lint` compares and stamps; a human
   only arbitrates a drift.
6. **The wiki says *what*, not *how*.** Behavior, rules, vocabulary. Technical
   specs stay in tickets — duplicating them would recreate the drift the wiki prevents.

## 3. Layout

- Root: `wiki/` in the **project** repo. Project-owned: `/pilot-update` never touches it.
  With the module on, its absence is what `doctor` reports (§6).
- Functional only, organized by **functional domain**: one folder per product area
  (`search/`, `export/`…), one markdown file per entry. Domains come from the project's epics.
  Architecture decisions are out of scope here: they will be handled by a reworked
  `/pilot-init-archi`.
- The bundle follows **OKF** (Open Knowledge Format, Google Cloud): one concept per file, a YAML
  frontmatter whose only required key is `type`, `index.md` and `log.md` reserved. PILOT's own keys live
  under `pilot:`; `log.md` is not used (git is the history).
- An `index.md` per folder lists its entries with their one-sentence `description`, so an agent
  opens only what it needs. `pilot.py` writes them (`wiki reindex`, run by every `add`/`set`/`remove`)
  and `wiki lint` flags a stale one; the root one carries `okf_version`. A conflict on an index
  between two PRs is resolved by regenerating it.

### Entry format

One entry = one file `wiki/<domain>/<id>.md`, the file name being the id:

```markdown
---
type: Behavior
title: Filter results by wheelchair accessibility
description: The user can filter search results to places with step-free access.
status: draft
verified:
  by: process:pilot-wiki
  at: 2026-11-08T12:36:44Z
pilot:
  status: specified
  tickets: [12, 15]
  verifiedCommit: abc123
---

The user can filter search results to places with step-free access. …
```

`status` (OKF: `draft`, `stable`, `deprecated`) is derived by the script from `pilot.status`
(`proposed` and `specified` → `draft`, `implemented` → `stable`); `verified` is OKF's own provenance key,
written only by a lint or an init, with the commit in `pilot.verifiedCommit`. Other keys are kept as
they are. `pilot.py wiki` reads the YAML subset it writes (scalars, `[a, b]`, one nested block); a
frontmatter outside it is reported by `lint` and never rewritten. An entry belongs to the tickets it
lists: that list is what makes ownership and conflicts decidable.

## 4. Statuses

| Kind | Status | Meaning | Source |
|---|---|---|---|
| durable (in the file) | `proposed` | Discovery validated it, not specified | wiki PR from Discovery |
| durable | `specified` | Spec validated it, ready for or in dev | wiki PR from Spec |
| durable | `implemented` | merged in code | the code PR that completes it |
| durable | `deprecated` | being or already retired | wiki PR from a story that removes it |
| derived | `in-dev` | a listed ticket is `status:in-dev` | labels |
| derived | `in-review` | a listed PR is `review-ready`/`in-review`/`changes-requested` | labels |
| derived | `in-qa` | the story is `status:qa`/`in-qa` | labels |
| derived | `verified` | `implemented`, stamped by a lint, and its story closed after QA | labels + stamp |

Reading shows file status plus the most advanced live overlay of the entry's open tickets
(e.g. `specified · in-review (PR #42)`). A file never says `in-dev`.

An entry covered by several tasks flips to `implemented` in the PR of the **last** task
that completes it; before that it stays `specified`.

## 5. Flow per phase

| Phase | Reads | Writes (always via PR) |
|---|---|---|
| 1 Discovery | entries touching the idea: already exists? contradicts? | small docs-only PR: new/changed entries as `proposed`, merged by the human who validates the brief |
| 2 Spec | entries of the story | same, entries → `specified` (and `deprecated` where the story retires behavior); a `wont-do` ticket removes its `proposed` entries |
| 3 Dev | the entries its ticket lists | its own code PR flips them to `implemented`. A dev who finds the wiki wrong or unfollowable does **not** edit it: `needs-human`, existing flow |
| 4 Review | the PR's wiki diff | tech lead (spec conformance): wiki diff matches the code; PM: entries match the acceptance criteria. A behavior change with no wiki diff is a blocking finding |
| 5 QA | the story's entries | nothing: `verified` is derived |

`type:tech`, `type:e2e` tasks and `type:bug` fixes change no entry unless the wiki was
underspecified (then it is a normal wiki edit in that PR).

## 6. `/pilot-wiki`

- `/pilot-wiki <question>` (or no flag) — answers from the wiki with citations (page, entry
  id, derived status). No code reading beyond what the answer needs; says so when the wiki
  does not cover the question.
- `/pilot-wiki --lint [domain|entry]` — see below.
- `/pilot-wiki --bootstrap [domain]` — drafts the wiki from what the project has: entries deduced by
  crossing intent (closed tickets, accepted prototypes) with reality (the code). Turning the module on is
  separate: any `/pilot-wiki` run proposes it first, `/pilot-init` asks for it on a new project and
  `/pilot-update` offers it on an existing one. See "Bootstrap" below.

The wiki is an optional module: `.pilot/state.json` carries `"modules": {"wiki": true}` (`pilot.py module
list|enable|disable`), asked by `/pilot-init` unless `--wiki`/`--no-wiki` is given, turned on by
`/pilot-wiki` on an existing project. A project without it behaves as before; with it on,
`pilot.py doctor` also requires `wiki/`.

Without the skill: a `PILOT:INTRO` block in the project's `CLAUDE.md` tells any agent to
consult `wiki/` (via `pilot.py wiki index`) before answering about the product.

### Lint

Persona: tech lead (it already judges conformance), PM consulted for functional entries.

1. **Mechanical** (`pilot.py wiki lint`, no LLM): unparsable entry lines, duplicate ids,
   entries whose tickets are all closed while status is `proposed`/`specified` (orphaned
   promise), `implemented` entries with no merged PR among their tickets.
2. **Judgment** (agent): for each `implemented`/`verified` entry, compare wiki to code. Verdict
   `ok` | `drift` | `unverifiable`. `proposed`/`specified` are never compared to code.
   Behavior present in code and absent from the wiki is reported as advisory only.
3. **Stamp**: `ok` entries get `verifiedAt` + `verifiedCommit`. Drifted entries keep their
   old stamp, so staleness stays visible.
4. **Drift resolution** — the caller arbitrates, per drift:
   - code is wrong → `type:bug` ticket through the shared bug mechanism; wiki untouched;
   - wiki must change → a behavior change goes back through Discovery; a pure correction is
     edited in the lint PR after the human confirms;
   - undocumented behavior → entry added, or flagged for removal from the code.
5. Output: **one PR per run** bundling stamps and resolved corrections.

Pair: the human arbitrates live. `--auto`: every drift is listed under "To arbitrate" in
the run's PR and stays unstamped, nothing is decided without a human.

### Bootstrap

On an existing project, one PR **per domain** (one folder of `wiki/`), never one huge PR.
For each behavior the agent crosses the two sources and triages it:

| Case | Treatment |
|---|---|
| **Convergent**: tickets say X, code does X | `implemented` entry written directly, stamped (`verifiedAt` + `verifiedCommit`): the crossing is already a verification |
| **Divergent**: tickets say X, code does Y | the human arbitrates: wiki says X (the code is a bug, `type:bug`) or Y (intent changed) |
| **Code only**: behavior without a ticket | entry created unstamped, flagged "undocumented" |
| **Tickets only**: closed ticket, no trace in code | gap to arbitrate: never delivered, or since removed |

Tickets contradicting each other over time: the most recent wins; if unclear, treated as
divergent. Each entry cites its two proofs (the ticket and the file or function), so a
human can spot-check in seconds. The PR description lists divergences first, then
summarizes the convergent entries (count, examples). A human merges: init never merges
itself.

Pair: the human arbitrates divergences live. `--auto`: divergences are listed under "To
arbitrate" in the PR and their entries stay unstamped; nothing is decided.

## 7. `pilot.py wiki`

Deterministic, like the rest of the script. Offline (no GitHub call): `index [--ticket N]` (entries,
descriptions, statuses, stamps; `--ticket` answers "which entries does my ticket list?"), `add <domain>/<id>.md`
(create an entry), `set` (the only writer of the frontmatter afterwards: status, tickets, title, description,
`--stamp COMMIT`, `--clear-stamp`), `remove` (a `proposed` entry only), `reindex` (the folder `index.md`
files), and `migrate` (a wiki in the earlier multi-entry page format → one OKF file per entry), so agents
never hand-edit a frontmatter or an index. With GitHub: `show <id>` (entry text plus derived overlay),
`status [id...]` (derived overlay from the entries' tickets), `lint` (the mechanical checks of §6, plus a
stale index; exit 1 on findings) and `snapshot` (the dashboard's document). Derived statuses are never
accepted by `add`/`set`. Judgment (wording, comparing to code, arbitrating drift) never lives in it.
Offline tests in `scripts/test_pilot.py` (`WikiTests`).

## 8. State combinations checked

- PR closed without merge: wiki unchanged — correct.
- `changes-requested`: the wiki diff is reclaimed with the code, same PR.
- Two open PRs on the same entry: second rebases; conflict resolution goes to the entry's
  ticket owner, never auto-merged.
- Ticket `wont-do` after Discovery: `proposed` entries removed by a wiki PR.
- Story re-scoped after QA: entries re-enter via Discovery/Spec as `proposed`/`specified`,
  previous `implemented` text kept until the new PR merges.
- Entry `implemented` but its ticket reopened: lint's mechanical check flags it.
- Wiki written while a PR is open: only that PR's own entries — `main` never says
  `implemented` before the code is there.

## 9. Delivery

The wiki is an optional module, so every step is backward compatible and a minor release; `main` is
never half-migrated:

1. `pilot.py wiki` (index, show, status, lint, add, set) and its tests — done, 2.10.0.
2. `/pilot-wiki` (query, `--lint`, `--bootstrap`) and the link/task docs — done, 2.11.0.
3. Discovery and Spec wiki PRs, Dev flips to `implemented` — done.
4. Review and QA criteria, and the dashboard "Wiki" tab (read-only, by functional domain; `pilot.py wiki snapshot`, pushed by `/pilot-dashboard`) — done.
5. The module switch (`modules.wiki` in `state.json`, `pilot.py module`), `doctor` checking `wiki/` only
   when it is on, `/pilot-init` asking (or `--wiki`/`--no-wiki`), `/pilot-update` offering the module and `--bootstrap` — done
   (steps 4 and 5 share one PR: a single bump, 2.13.0).

Content placement (re-run the three-tier test with `grep` at implementation time):
contract and format in `assets/docs/pilot-link-wiki.md` (read by every phase that touches
it, whole file injected); `pilot-process.md` gets only a pointer and the "only a PR changes
the wiki" rule; one task doc per duty (`pilot-task-wiki-lint.md`, `pilot-task-wiki-bootstrap.md`…); persona
files unchanged except their duty lists.

## 10. Known limits

- An ingestion error now outranks the code: this relies on the human checkpoints of §2.4.
  For an entry never stamped, lint presents a drift as "the entry is probably wrong" first;
  the human still arbitrates.
- Sources that agree do not guarantee truth (ticket and code can both describe a behavior
  the product has since dropped): init's convergent entries still reach `main` only through
  a human-merged PR.
- Lint's code comparison is only as good as the agent's reading; `unverifiable` is an
  honest verdict and leaves the entry unstamped.
