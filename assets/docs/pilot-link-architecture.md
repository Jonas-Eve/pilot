# PILOT link — the project's architecture

Read by `pilot-architecture` (consultation), by the persona calls of the `technical-frame` workflow (`pilot-task-write-technical-frame.md`) and by the plan workflow that writes local ADRs, when the project's
`architecture` module is enabled. It is the project's source of truth for how the product is built and why: **when an entry and the code disagree, a human arbitrates, never silently**,
whichever of the two is wrong.

**Where and what.** An OKF bundle (Open Knowledge Format) under `architecture/` at the project root (project-owned, never touched by `/pilot-update`), read like the wiki through the
commands of `.pilot/pilot-link-knowledge.md` (`python3 .pilot/pilot.py arch …`).

- `overview.md` — the apps or services, each one's purpose and stack, how they relate, the per-app commands.
- `guidelines/<id>.md` — a technical rule AIs and developers must respect (layering, testing, security, naming, dependencies), stated as a rule, one per file.
- `reference/<id>.md` — how the code is built today, one subject per file: stack and versions, data model, folder structure, commands, integrations. A statement of fact, short and exact,
  never a rule and never a reason. It changes with the code.
- `adr/<NNNN-title>.md` — a local ADR (format `adr-local`, `.pilot/formats.json`): a decision made while planning a story or epic. The number is the next free one across the whole bundle
  (`arch next-number`); the file name is the id and never changes. There is no global ADR.
- `runbooks/<id>.md` — how to operate the product (deploy, provision, onboard a client), step by step. Read on demand, **never carried in a prompt** (`index --active` leaves them out;
  `search` and `show` find them).
- `apps/<app>/` — only in a monorepo, for a rule or decision that belongs to one app: `<app>-overview.md`, `guidelines/`, `adr/`, `runbooks/` under it. Everything transversal stays at the root.
  An id is unique across the whole bundle.

**Where a decision sits.** The wiki says *what* the product does; a guideline says *what to do or not do* when building (stable, imperative, checkable by a reviewer); a reference entry says
*how the code works today*; an ADR says *why* a choice was made. A decision is an ADR when it outlives a ticket and someone could be tempted to reverse it. A version number or table layout is a
fact: it goes in a reference entry, the ADR gives only the reason. A guideline names its ADR in one line and carries no reasoning. A rule a tool can enforce is enforced there and the guideline
points to it. An ADR forced by a product rule cites the wiki entry; a wiki entry never carries the reasoning.

**A divergence between an entry and the code** is never settled by an agent: put it to the human when one is live, else flag `needs-human` quoting both. The human decides that the code is wrong
(a correction ticket), the entry is out of date (corrected through the `technical-frame` workflow), or the code must change on purpose (a technical need stated to the plan workflow). A divergence on
a guideline is first read as a violation by the code; on an accepted ADR, a decision that no longer holds is replaced by a new ADR that supersedes it, never edited.

**Statuses.** `pilot.status` is `proposed`, `accepted` or `superseded` (OKF `status`: `draft`, `stable`, `deprecated`), the stable ones only. An accepted ADR is never edited nor deleted: a later one
supersedes it (`arch supersede <new> <old>` sets both sides). Any other retired entry is deleted (`arch remove`, refused while another entry cites it; the root `overview.md` never), never kept as
`deprecated`. Create and change entries only with `python3 .pilot/pilot.py arch add|set|remove|supersede`, never by hand; the prose below the frontmatter is the only hand-edited part. Only an
`accepted` entry is in force: `index --active`, which a prompt carries, leaves out `proposed` and `superseded` entries (`search` and `show` still find them).

**Only a docs PR changes the architecture.** The workflow that changes an entry ends with one docs PR, opened and merged by script once its gate has passed; nothing is committed to `main`
directly. A code PR that breaks a guideline is a `change`; one that needs to break it carries the ADR (or the guideline's edit) that says why.
