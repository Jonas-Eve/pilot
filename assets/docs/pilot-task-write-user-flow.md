# PILOT task — Write a user flow

Injected by the `write` step of the user-flow workflow into the `pilot-qa` persona's `Agent` call.

You receive the human's intention, the audit's delta and the proposed scope. Write one user flow in the `user-flow` format.

Do:
- Steps P1, P2…: `step` is what the persona does, `result` is what they observe afterwards, concrete and decidable. Set `pilot.personas` to the personas that play it and
  `pilot.scope` with vocabulary terms. A flow plays as a persona: a step the persona cannot take is a defect of the flow.
- `source` of a step is the criterion `entry#C<n>` that already describes the result; read the entries to find it, cite only one that exists. A step no criterion covers is
  `to-create`, and gets a Candidates line K<n> (`from` the step, `request` a one-sentence need, `state: candidate`).
- Never write an expected result that is not visible to the persona, nor a step that depends on an implementation detail.
- A new flow is a file created at `user-flow/<id>.md` (`wiki add`); if the flow exists (`--edit <id>`), edit only what the intention changes, keep its id, and add a Journal line J<n>
  (date, origin, decision, alternatives discarded, reason); never edit an existing line, step id or candidate id.
- Cite only existing personas. When no existing persona could play the flow, say so in an `ASSUMPTION:` (the Persona workflow creates it first).

Never: write a criterion, a test script or a ticket; ask about wording or order (take a default and record an `ASSUMPTION:`).
