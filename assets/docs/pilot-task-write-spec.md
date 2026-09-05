# PILOT task — Write the technical spec

Injected by `.claude/skills/pilot-spec/SKILL.md` into the `pilot-techlead` persona's
prompt.

You receive one already-scoped ticket (`status:spec-ready`) carrying either the
architect's phase-2 security/architecture decisions, or, for a `type:bug` ticket (which
skips phase 2 entirely — `.pilot/pilot-process.md` §2 "Three levels"), the architect's
phase-1 diagnosis and suggested fix — the analogous judgment from a different phase.

1. Claim it per the protocol in `.pilot/pilot-process.md` §4 before starting.
2. Read the affected code — your own identity's project-doc habit already covers the
   conventions/README side of grounding yourself in the area the ticket touches.
3. Write the technical spec directly into the ticket body: implementation approach,
   files/modules touched, data/schema changes, API contract changes, and a test plan. If
   the ticket carries a UI/UX description, the implementation approach must account for
   it — components/screens touched, how they map to what's described.
4. If that earlier judgment (architect's phase-2 decisions, or a bug ticket's phase-1
   diagnosis/suggested fix) conflicts with the real code — not a style preference; for a
   bug this includes finding it's not reproducible or already fixed — don't override it
   silently: add `needs-human` (keep the ticket's current `status:` — `.pilot/pilot-process.md`
   §3) and a comment stating the conflict and what needs deciding, every time, even with a
   human live in this session. If that human answers in conversation, proceed with their
   answer, post a follow-up comment summarizing the decision, and remove `needs-human`
   yourself in the same turn; otherwise leave the flag and comment for a human to resolve
   later. If the ticket instead just can't proceed yet due to unresolved work elsewhere
   (not a judgment call), use `on-hold` instead (`.pilot/pilot-process.md` §3 "`on-hold`")
   with a comment on what it's waiting on.
5. Otherwise, move the ticket to `status:dev-ready`.

You do not write implementation code here — that's phase 4.

**Reconciling an ensemble (`--multi`, `.pilot/pilot-link-multi-consensus.md`)**: sometimes
you're given N other instances' full specs for this same ticket instead of being asked to
write one yourself — compare them, never draft your own. Decide whether they
substantively agree on the technical approach (implementation approach, files/modules
touched, data/schema/API contract changes, test plan) and on whether a blocking conflict
with the architect's decisions exists — surface differences in wording don't count. Agree
→ name which one instance's spec to adopt verbatim. Genuinely diverge → report exactly
which point(s) and quote each differing instance's position, without picking a winner
yourself.
