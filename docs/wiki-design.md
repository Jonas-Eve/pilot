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
6. **The wiki says *what*, not *how*.** Behavior, rules, decisions, vocabulary. Technical
   specs stay in tickets — duplicating them would recreate the drift the wiki prevents.

## 3. Layout

- Root: `wiki/` in the **project** repo (`wikiDir` in `.pilot/state.json`). Project-owned:
  `/pilot-update` never touches it. Presence of `wikiDir` is what enables the feature.
- One markdown file per capability/topic, grouped by folder: `features/`, `flows/`,
  `architecture/`, `decisions/`, `glossary.md`.
- No committed index: `pilot.py wiki index` prints it on demand (titles, entry ids,
  statuses). A committed index is a merge-conflict magnet.

### Entry format

One entry = one `##` heading with a stable id, followed by a machine-readable line:

```markdown
## Filter results by wheelchair accessibility {#search-accessibility-filter}
<!-- wiki: status=specified tickets=#12,#15 verifiedAt= verifiedCommit= -->

The user can filter search results to places with step-free access. …
```

`pilot.py wiki` parses only that comment line; prose is free-form. An entry belongs to the
tickets it lists — that list is what makes ownership and conflicts decidable.

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
| derived | `verified` | `implemented` and its story closed after QA | labels |

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

`type:tech` tickets touch `architecture/` or `decisions/` entries when they decide
something durable; `type:e2e` tasks and `type:bug` fixes change no entry unless the
wiki was underspecified (then it is a normal wiki edit in that PR).

## 6. `/pilot-wiki`

- `/pilot-wiki <question>` (or no flag) — answers from the wiki with citations (page, entry
  id, derived status). No code reading beyond what the answer needs; says so when the wiki
  does not cover the question.
- `/pilot-wiki --lint [page|entry]` — see below.
- `/pilot-wiki --bootstrap` — first pass on an existing project: drafts pages from code,
  closed tickets and accepted prototypes as `implemented` entries with **no** `verifiedAt`,
  in one PR a human reviews. Lint then verifies progressively.

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

Pair: the human arbitrates live. `--auto`: each drift becomes `needs-human`, stays
unstamped, nothing is decided without a human.

## 7. `pilot.py wiki`

Deterministic, like the rest of the script: `index`, `show <id>` (entry + derived overlay),
`status` (overlay for given tickets), `lint` (mechanical checks above), `set-status <id>
<status>` (the only writer of the entry line, so agents never hand-edit it). Judgment
(wording, comparing to code, arbitrating drift) never lives in it. Offline tests in
`scripts/test_pilot.py`.

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

**Step 1 — opt-in, minor bump.** Projects without `wikiDir` behave exactly as today.
`/pilot-init --wiki`, `/pilot-wiki` (query, lint, bootstrap), `pilot.py wiki`, Discovery and
Spec wiki PRs, Dev flips to `implemented`, dashboard untouched.
**Step 2 — default, major bump.** Review and QA criteria become mandatory, wiki enabled by
default, dashboard "Wiki" tab (entries and statuses).

Content placement (re-run the three-tier test with `grep` at implementation time):
contract and format in `assets/docs/pilot-link-wiki.md` (read by every phase that touches
it, whole file injected); `pilot-process.md` gets only a pointer and the "only a PR changes
the wiki" rule; one task doc per duty (`pilot-task-wiki-lint.md`, bootstrap…); persona
files unchanged except their duty lists.

## 10. Known limits

- An ingestion error now outranks the code: step 1 relies on the human checkpoints of §2.4,
  and bootstrap entries stay unstamped until lint verifies them.
- Lint's code comparison is only as good as the agent's reading; `unverifiable` is an
  honest verdict and leaves the entry unstamped.
