# PILOT link — the project's wiki

Read by `pilot-wiki` and by the persona calls it makes (`pilot-task-wiki-lint.md`,
`pilot-task-wiki-bootstrap.md`), and by `pilot-discovery`, `pilot-spec` and `pilot-dev`
(`pilot-task-wiki-entries.md`), `pilot-review` and `pilot-qa`, when the project's `wiki` module is enabled.
The wiki is the project's source of truth for what the product does and what is promised: **when the wiki
and the code disagree, the wiki is right** and the divergence is arbitrated by a human, never settled
silently.

**Where and what.** An OKF bundle (Open Knowledge Format) under `wiki/` at the project root (project-owned,
never touched by `/pilot-update`): one markdown file per entry, `wiki/<domain>/<id>.md`, one folder per
functional domain (`wiki/search/`), and an `index.md` in each folder listing its entries with their
one-sentence description, read through the commands of `.pilot/pilot-link-knowledge.md`. Functional only (architecture decisions live elsewhere): it says *what* — behavior, rules,
vocabulary — never *how*; technical specs stay in tickets.

**Entries.** The file name is the entry's id (lowercase letters, digits and dashes; it never changes once
merged). A YAML frontmatter, then the prose — what the product does, in the present tense:

```markdown
---
type: Behavior
title: Filter by accessibility
description: One sentence, shown in the folder's index.
status: draft
pilot:
  status: specified
  tickets: [12, 15]
---

Prose.
```

`pilot.tickets` lists the tickets that own the entry (the `type:feature` story too). Create an entry with
`python3 .pilot/pilot.py wiki add <domain>/<id>.md --title … --description … --status … --ticket …`, change
its frontmatter only with `wiki set`, remove one with `wiki remove` — never by hand: the script
keeps the OKF `status` in step with `pilot.status` and the folder `index.md` files current (`wiki reindex`),
and leaves any other key as it is. The prose below the frontmatter is edited by hand when an entry's behavior
changes. A pure correction (wording, precision) keeps the entry's status and tickets and goes through
`/pilot-wiki --edit`; a change of behavior goes back through `/pilot-discovery`, never an edit. A stamped entry whose text changed has its stamp cleared (`wiki set --clear-stamp`).

**Statuses.** `pilot.status` is `proposed` (validated in Discovery), `specified` (validated in Spec),
or `implemented` (merged in code); the OKF `status` is `draft`, `draft`, `stable` accordingly. A retired entry is deleted
(`wiki remove`, refused while another entry cites it), never kept as `deprecated`; an entry still `deprecated` from an earlier version is read and `lint` warns. `in-dev`, `in-review`, `in-qa` and `verified` are derived
(`wiki status`/`wiki show`), never written: the first three from the tickets' labels, `verified` for an `implemented` entry that carries a
stamp and whose feature story is done. The stamp — `verified` (who, when) and `pilot.verifiedCommit` — verifies an entry against the code and is written
(`wiki set --stamp <commit>`) only on an `implemented` entry: by the Dev PR that moves it to `implemented`, after checking the behavior holds
(`.pilot/pilot-task-implement.md` step 6a), confirmed by Review (a stamp stays valid while only files under `wiki/` changed since its commit); by a manual `/pilot-wiki --lint`; or by an init that found tickets and code in agreement.
A PR stamps no other entry. Editing an entry's text clears its stamp.

**The vision.** One entry of `type: Vision` (id `vision`, no status and no ticket: it promises no behavior; create it with
`wiki add <domain>/vision.md --type Vision …`) says what the product is, for whom
and by which principles — never a behavior to deliver. It is the vision `pilot-pm` and `pilot-designer`
read first. It is created when the wiki is initialised (`/pilot-init`, or `/pilot-wiki` turning the module on), from the vision
the human gives. No code verifies it: it is never stamped and `--lint` leaves it out. It changes in the PR of the ticket that
changes the product's direction, with the wording the human confirmed, never silently.

**Personas and user flows.** Two folders are not functional domains: `wiki/persona/` (`type: Persona`, one end user's profile: who they are, their constraints, their test account's label) and `wiki/user-flow/`
(`type: UserFlow`, one journey: its goal, the personas it is for, numbered steps each with the expected outcome), tested by `/pilot-flow`. They are never stamped (a run of the flow, not the code, is what checks one), and `--lint`
and `--bootstrap` leave them out. A retired one is deleted (`wiki remove`), refused while a flow's `Personas:` line or another entry cites it. A persona carries no status; it is written by a human or `/pilot-flow --new persona`, no ticket, never by a story. A flow written by hand (or `/pilot-flow --new flow`) is `implemented`
with no ticket; one a story creates or changes follows the story's entries (`proposed`, `specified`, and `implemented` by the Dev PR that completes it, like any entry: `.pilot/pilot-task-implement.md` step 6a; the story as its ticket), and `/pilot-flow` runs only an `implemented` one. A flow's `verified` is derived by the dashboard, not written in the file: its last run passed and the flow and each persona that played are unchanged since (the hashes of the `flowRuns` document).

**Only a PR changes the wiki.** Wiki changes go on a branch and reach `main` through a PR a human merges,
the `index.md` files included; nothing is committed to `main` directly.

**A divergence between an entry and the code** is resolved by a human, one of:
- the code is wrong: a `type:bug` ticket (`/pilot-spec --bug "<description>"`), wiki untouched;
- the wiki must change: a behavior change goes back through `/pilot-discovery`; a pure
  correction is edited in the same PR once the human confirms;
- behavior present in the code and absent from the wiki: an entry is added, or the code's
  behavior is questioned.

An entry never stamped has not been checked against anything: a divergence on it is first read as "the
entry is probably wrong", the human still decides.
