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
one-sentence description — read it, or `python3 .pilot/pilot.py wiki index`, to find what to open, then open
only that. Functional only (architecture decisions live elsewhere): it says *what* — behavior, rules,
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
its frontmatter only with `wiki set`, remove a `proposed` one with `wiki remove` — never by hand: the script
keeps the OKF `status` in step with `pilot.status` and the folder `index.md` files current (`wiki reindex`),
and leaves any other key as it is. The prose below the frontmatter is edited by hand when an entry's behavior
changes.

**Statuses.** `pilot.status` is `proposed` (validated in Discovery), `specified` (validated in Spec),
`implemented` (merged in code) or `deprecated`; the OKF `status` is `draft`, `draft`, `stable`, `deprecated`
accordingly. `in-dev`, `in-review`, `in-qa` and `verified` are derived (`wiki status`/`wiki show`), never
written: the first three from the tickets' labels, `verified` for an `implemented` entry that carries a lint
stamp and whose feature story is done. The stamp — `verified` (who, when) and `pilot.verifiedCommit` — is
written only by a lint that found the entry conforming (`wiki set --stamp <commit>`), or by an init that
found tickets and code in agreement.

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
