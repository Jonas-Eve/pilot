# PILOT link — the project's architecture

Read by `pilot-architecture` and by the persona calls it makes (`pilot-task-architecture-bootstrap.md`,
`pilot-task-architecture-adr.md`), when the project's `architecture` module is enabled. It is the project's
source of truth for how the product is built and why. **A guideline or an ADR is a rule: when the code disagrees,
the entry is right** and a human arbitrates, never silently. **A reference entry states what the code is today: when
the code disagrees, the code is right** and the entry is corrected.

**Where and what.** An OKF bundle (Open Knowledge Format) under `architecture/` at the project root
(project-owned, never touched by `/pilot-update`), read like the wiki through the commands of
`.pilot/pilot-link-knowledge.md` (`python3 .pilot/pilot.py arch …`).

- `overview.md` — the apps or services, each one's purpose and stack, how they relate, the per-app commands.
- `guidelines/<id>.md` — a technical rule AIs and developers must respect (layering, testing, security, naming,
  dependencies), stated as a rule, one per file.
- `reference/<id>.md` — how the code is built today, one subject per file: the stack and its versions, the data
  model, the folder structure, the commands, the integrations. A statement of fact, short and exact (names, versions,
  tables, paths), never a rule and never a reason. It changes with the code.
- `adr/<NNNN-title>.md` — an architecture decision record: context, decision, alternatives rejected,
  consequences. The number is the next free one across the whole bundle (`arch next-number`); the file name is the id and
  never changes.
- `runbooks/<id>.md` — how to operate the product: deploy, provision, onboard a client. Procedures step by step, with
  the commands and the values to check. Read on demand when the task is to operate, **never carried in a phase's prompt**
  (`index --active` leaves them out; `search` and `show` find them).
- `apps/<app>/` — only in a monorepo, and only when a rule or a decision belongs to one app: `<app>-overview.md`,
  `guidelines/<id>.md`, `adr/<NNNN-title>.md`, `runbooks/<id>.md` under it. Everything transversal stays at the root. An id (the file name) is unique across
  the whole bundle.

**Where a decision sits.** The wiki says *what* the product does; a guideline says *what to do or not do* when building
(clean architecture, factoring, testing, security, naming: stable rules, imperative, each one checkable by a reviewer);
a reference entry says *how the code works today*; an ADR says *why* a choice was made. A decision is an ADR when it
outlives a ticket and someone could be tempted to reverse it. A version number or a table layout is a fact: it goes in
a reference entry, and the ADR only gives the reason for the choice behind it. A guideline names its ADR in one line
when there is one; it carries no reasoning of its own. A rule a tool can enforce (a lint rule, an architecture test)
is enforced there and the guideline points to it. When a product rule forced an ADR, it cites the wiki entry; a wiki
entry never carries the reasoning.

**Reference entries stay true.** `/pilot-architecture --verify` checks them against the code at a commit and stamps
the ones that hold (`arch set <id> --stamp <commit>`); one that does not is corrected to what the code does, after
the human has seen the difference. A PR that changes what a reference entry states updates the entry in the same PR,
and clears its stamp (`--clear-stamp`).

**Statuses.** `pilot.status` is `proposed`, `accepted`, `deprecated` or `superseded` (OKF `status`: `draft`,
`stable`, `deprecated`, `deprecated`). An accepted ADR is never edited: a later one supersedes it
(`arch supersede <new> <old>` sets both sides). Create and change entries only with `python3 .pilot/pilot.py arch
add|set|remove|supersede`, never by hand; the prose below the frontmatter is the only hand-edited part. Only an
`accepted` entry is in force: `index --active`, which a phase prompt carries, leaves out `proposed`, `deprecated` and
`superseded` entries (`search` and `show` still find them).

**Only a PR changes the architecture.** Changes go on a branch and reach `main` through a PR a human merges;
nothing is committed to `main` directly. A PR that breaks a guideline is a `change`; one that needs to break it
is a `decision`: it carries the ADR (or the guideline's own edit) that says why.
