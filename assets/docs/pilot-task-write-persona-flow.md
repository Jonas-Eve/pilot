# PILOT task — Write a persona or a user flow

Injected by the `write` step of the personas-flows workflow: into `pilot-designer` for a persona, into `pilot-qa` for a user flow. Take only the part for your persona.

You receive the human's intention, the audit's delta and the proposed scope.

Designer, a persona (`persona` format):
- Describe a person, not a segment: goals, skills, constraints, vocabulary, context of use, and the `Usage` lines U1, U2… that say how this person uses the product (device,
  input mode, assistive technology, accessibility needs). One fact per line.
- Never prescribe behavior ("the persona clicks…") or a feature, and never write a trait that cannot be observed when playing the persona. Take facts from the
  intention; mark each guess in an `ASSUMPTION:`. No stereotype beyond what the human said.
- Reuse an existing persona when one fits; write a new one only when none does.

QA, a user flow (`user-flow` format):
- Steps P1, P2…: `step` is what the persona does, `result` is what they observe afterwards, concrete and decidable. Set `pilot.personas` to the personas that play it and
  `pilot.scope` with vocabulary terms. A flow plays as a persona: a step the persona cannot take is a defect of the flow.
- `source` of a step is the criterion `entry#C<n>` that already describes the result; read the entries to find it, cite only one that exists. A step no criterion covers is
  `to-create`, and gets a Candidates line K<n> (`from` the step, `request` a one-sentence need, `state: candidate`).
- Never write an expected result that is not visible to the persona, nor a step that depends on an implementation detail.
- If the flow exists, edit only what the intention changes and add a Journal line J<n> (date, origin, decision, alternatives discarded, reason); never edit an existing
  line, step id or candidate id.
- Missing persona for the flow: say it in a `QUESTION:` only if no existing persona could play it; otherwise reuse one.

Never: write a criterion, a test script or a ticket; ask about wording or order (take a default and record an `ASSUMPTION:`).
