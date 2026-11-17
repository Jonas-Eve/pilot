# PILOT link — the project's architecture

Read by `pilot-architecture` and by the persona calls it makes (`pilot-task-architecture-bootstrap.md`,
`pilot-task-architecture-adr.md`), when the project's `architecture` module is enabled. It is the project's
source of truth for how the product is built and why: **when an entry and the code disagree, a human arbitrates,
never silently** (below), whichever of the two is wrong.

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
the ones that hold (`arch set <id> --stamp <commit>`). A PR that changes what a reference entry states updates the
entry in the same PR, and clears its stamp (`--clear-stamp`).

**A divergence between a reference entry and the code** is resolved by a human, one of: the code is wrong (a
`type:bug` ticket, `/pilot-spec --bug "<description>"`, entry untouched); the entry is wrong or out of date (it is
corrected in the same PR once the human confirms); the code must change on purpose (a `/pilot-spec --tech` ticket,
entry untouched). An entry never stamped has not been checked against anything: a divergence on it is first read as
a wrong or stale entry, with the reason.

**Statuses.** `pilot.status` is `proposed`, `accepted` or `superseded` (OKF `status`: `draft`,
`stable`, `deprecated`). An accepted ADR is never edited and never deleted: a later one supersedes it, the old one stays as the history of the
decision (`arch supersede <new> <old>` sets both sides). Any other retired entry — a guideline, a reference, a runbook, a `proposed` ADR — is deleted (`arch remove`, refused while another entry
cites it; the root `overview.md` never), never kept as `deprecated`. Create and change entries only with `python3 .pilot/pilot.py arch
add|set|remove|supersede`, never by hand; the prose below the frontmatter is the only hand-edited part. Only an
`accepted` entry is in force: `index --active`, which a phase prompt carries, leaves out `proposed` and
`superseded` entries (`search` and `show` still find them).

**Only a PR changes the architecture.** Changes go on a branch and reach `main` through a PR a human merges;
nothing is committed to `main` directly. A PR that breaks a guideline is a `change`; one that needs to break it
is a `decision`: it carries the ADR (or the guideline's own edit) that says why.
