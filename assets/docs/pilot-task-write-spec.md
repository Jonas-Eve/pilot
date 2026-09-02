# PILOT task — Write the technical spec

Injected by `.claude/skills/pilot-spec/SKILL.md` into the `pilot-techlead` persona's
prompt.

You receive one already-scoped ticket (`status:spec-ready`) carrying either the
architect's phase-2 security/architecture decisions, or, for a `type:bug` ticket (which
skips phase 2 entirely — `docs/pilot-process.md` §2 "Three levels"), the architect's
phase-1 diagnosis and suggested fix — the analogous judgment from a different phase.

1. Claim it per the protocol in `docs/pilot-process.md` §4 before starting.
2. Read the affected code and the relevant docs for the area the ticket touches (this
   project's own per-service/per-package docs, wherever it keeps them — e.g.
   `apps/<app-name>/docs/`, a `docs/` folder, or a service-level README).
3. Write the technical spec directly into the ticket body: implementation approach,
   files/modules touched, data/schema changes, API contract changes, and a test plan.
4. If that earlier judgment (architect's phase-2 decisions, or a bug ticket's phase-1
   diagnosis/suggested fix) conflicts with the real code — not a style preference; for a
   bug this includes finding it's not reproducible or already fixed — don't override it
   silently: add `needs-human` (keep the ticket's current `status:` — `docs/pilot-process.md`
   §3) and a comment stating the conflict and what needs deciding, every time, even with a
   human live in this session. If that human answers in conversation, proceed with their
   answer, post a follow-up comment summarizing the decision, and remove `needs-human`
   yourself in the same turn; otherwise leave the flag and comment for a human to resolve
   later. If the ticket instead just can't proceed yet due to unresolved work elsewhere
   (not a judgment call), use `on-hold` instead (`docs/pilot-process.md` §3 "`on-hold`")
   with a comment on what it's waiting on.
5. Otherwise, move the ticket to `status:dev-ready`.

You do not write implementation code here — that's phase 4.
