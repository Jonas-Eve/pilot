# PILOT link — the project's wiki

Read by `pilot-wiki`, by the persona calls of its `functional-frame` workflow (`pilot-task-write-functional-frame.md`), and by the workflows that read or write the wiki (`pilot-need`,
`pilot-plan`, `pilot-build`, `pilot-accept`, `pilot-express`, `pilot-flow`), when the project's `wiki` module is enabled. The wiki is the project's source of truth for what the product does and
what is promised: **when the wiki and the code disagree, the wiki is right** and a human arbitrates the divergence, never silently.

**Where and what.** An OKF bundle (Open Knowledge Format) under `wiki/` at the project root (project-owned, never touched by `/pilot-update`): one markdown file per entry,
`wiki/<domain>/<id>.md`, one folder per functional domain, and an `index.md` in each folder listing its entries with their one-sentence description, read through the commands of
`.pilot/pilot-link-knowledge.md`. Functional only: *what* — behavior, rules, vocabulary — never *how*; technical decisions are in `architecture/`.

**Entries.** The file name is the entry's id (lowercase letters, digits, dashes; it never changes once merged). A YAML frontmatter, then the body:

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
```

- A **need entry** (`type: Behavior`) has the sections of format `need-entry` (Need, Criteria, Outside, Journal); a **frame entry** (the vocabulary, the rules shared by several behaviors)
  those of `frame`; the persona, user-flow and vocabulary entries those of their own formats (`.pilot/formats.json`). The sections are never restated here, and the need workflow's checks validate them.
- `pilot.tickets` lists the tickets that own the entry. Create an entry with `python3 .pilot/pilot.py wiki add <domain>/<id>.md --title … --description … --status … --ticket …`, change its
  frontmatter only with `wiki set`, remove one with `wiki remove` — never by hand: the script keeps the OKF `status` in step with `pilot.status` and the folder `index.md` files current
  (`wiki reindex`).

**Statuses.** The file holds stable statuses only: `proposed` (validated at the need workflow's first gate), `specified` (its story validated at the second gate), `implemented` (merged in code); the
OKF `status` is `draft`, `draft`, `stable`; `provisional` is a document written by the express workflow, still open to change. An in-flight state (rework, building, reviewing, merged awaiting
recette, recetted, in gap) is derived from tickets, runs and records (`wiki status`, `wiki show`), never written. A retired entry is deleted (`wiki remove`, refused while another entry cites
it), never kept as `deprecated`.

**Who changes what.** A change of behavior goes through the need workflow (`/pilot-need`), never a hand edit; a pure correction (wording, precision) of a frame entry goes through
`/pilot-wiki --edit`. A document reaches `main` by the docs PR its workflow ends with, opened and merged by script after its gate; nothing is committed to `main` directly.

**The vision.** One entry of `type: Vision` (id `vision`, no status, no ticket: it promises no behavior; `wiki add <domain>/vision.md --type Vision …`) says what the product is, for whom and by
which principles. It is the vision `pilot-pm` and `pilot-designer` read first, created when the wiki is initialised from the vision the human gives, and changed only with the wording the human
confirmed.

**Personas and user flows.** Two folders are not functional domains: `wiki/persona/` (`type: Persona`: who the end user is, their constraints, their test account's label) and `wiki/user-flow/`
(`type: UserFlow`: one journey, its goal, its personas, numbered steps each with the expected outcome). They are written by a human or `/pilot-flow --new`, with no ticket unless a story creates or
changes a flow (then it follows that story's entries); a persona carries no status. A retired one is deleted (`wiki remove`), refused while a flow's `Personas:` line or another entry cites it.
Running a flow as personas is the accept workflow (`/pilot-accept <user-flow id>`). Never any credential or secret in an entry.

**A divergence between an entry and the code** is resolved by a human, one of: the code is wrong (a correction ticket made by a Recette, or a report); the wiki must change (a change of behavior
goes back through `/pilot-need`, a pure correction through `/pilot-wiki --edit`); behavior present in the code and absent from the wiki (an entry is added by `/pilot-need`, or the code's
behavior is questioned).
