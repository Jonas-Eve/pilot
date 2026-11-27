# PILOT task — Write the provisional documentation of an express

Injected by the `write` step of the express workflow into `pilot-pm` (criteria and journal) and, only when a technical decision is taken, `pilot-architect` (the ADR),
one `Agent` call per persona. The change ships before its documentation is validated; everything you write is provisional.

You receive the express intention (the fix or the small change), the audit's delta, the proposed scope and, on later turns, the human's answer.

PM:
- Find the need entry the change belongs to (cite its id); create one in the `need-entry` format only if none covers it.
- If the change restores a behavior an existing criterion already describes, write no criterion and say so in the Journal line. Otherwise add or modify
  only the criteria the change needs: `when`, `then` (observable, decidable), `by`, `source`. A modified criterion keeps its id.
- Set `pilot.status: provisional` on every entry you touch, and only that. Never change the status of an entry to `specified` or `implemented`.
- Add one Journal line J<n>: date, origin `express`, the decision, the alternatives discarded, the reason. Never edit an existing line.
- Scope: vocabulary terms only, from the proposed scope.

Architect:
- Write a local ADR in the `adr-local` format, `pilot.status: provisional`, only if the change takes a technical decision (a new dependency, a data shape, a
  boundary). One decision D<n> per choice, `covers` the criteria it serves, with the reason. A change that follows existing decisions writes no ADR.
- Never contradict an accepted ADR or guideline: name it in an `ASSUMPTION:` and keep the change inside it.

Both:
- Every point where you took a default is an `ASSUMPTION:`; they are recorded for the Recette. A `QUESTION:` only when two readings lead to different behavior for
  the user or different cost.
- Keep it minimal: the documentation of the change, not of what surrounds it.

Never: write a ticket, code or a test; document a behavior the change does not touch; present a provisional text as validated.
