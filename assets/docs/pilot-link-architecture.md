# PILOT link — the project's architecture

Read by `pilot-architecture` and by the persona calls it makes (`pilot-task-architecture-bootstrap.md`,
`pilot-task-architecture-adr.md`), when the project's `architecture` module is enabled. It is the project's
source of truth for how the product is built and why: **when the architecture and the code disagree, the
architecture is right**, and a human arbitrates, never silently.

**Where and what.** An OKF bundle (Open Knowledge Format) under `architecture/` at the project root
(project-owned, never touched by `/pilot-update`), read like the wiki through the commands of
`.pilot/pilot-link-knowledge.md` (`python3 .pilot/pilot.py arch …`).

- `overview.md` — the apps or services, each one's purpose and stack, how they relate, the per-app commands.
- `guidelines/<id>.md` — a technical rule AIs and developers must respect (layering, testing, security, naming,
  dependencies), stated as a rule, one per file.
- `adr/<NNNN-title>.md` — an architecture decision record: context, decision, alternatives rejected,
  consequences. The number is the next free one across the whole bundle (`arch next-number`); the file name is the id and
  never changes.
- `runbooks/<id>.md` — how to operate the product: deploy, provision, onboard a client. Procedures step by step, with
  the commands and the values to check. Read on demand when the task is to operate, **never carried in a phase's prompt**
  (`index --active` leaves them out; `search` and `show` find them).
- `apps/<app>/` — only in a monorepo, and only when a rule or a decision belongs to one app: `<app>-overview.md`,
  `guidelines/<id>.md`, `adr/<NNNN-title>.md`, `runbooks/<id>.md` under it. Everything transversal stays at the root. An id (the file name) is unique across
  the whole bundle.

**Where a decision sits.** The wiki says *what* the product does; a guideline says *how* we build; an ADR says
*why* a choice was made. A decision is an ADR when it outlives a ticket and someone could be tempted to reverse it.
When a product rule forced it, the ADR cites the wiki entry; a wiki entry never carries the reasoning.

**Statuses.** `pilot.status` is `proposed`, `accepted`, `deprecated` or `superseded` (OKF `status`: `draft`,
`stable`, `deprecated`, `deprecated`). An accepted ADR is never edited: a later one supersedes it
(`arch supersede <new> <old>` sets both sides). Create and change entries only with `python3 .pilot/pilot.py arch
add|set|remove|supersede`, never by hand; the prose below the frontmatter is the only hand-edited part.

**Only a PR changes the architecture.** Changes go on a branch and reach `main` through a PR a human merges;
nothing is committed to `main` directly. A PR that breaks a guideline is a `change`; one that needs to break it
is a `decision`: it carries the ADR (or the guideline's own edit) that says why.
