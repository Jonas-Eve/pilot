# PILOT task — Build the test plan

Injected by the `plan-cases` step of the `accept` workflow into the `pilot-qa` persona.

You receive the target's criteria (or the expected steps of a user flow) and, when one is given, a persona. You write the test plan in format `recipe-plan` (JSON; the format and its checks are in `.pilot/formats.json`).

1. **One case per criterion, or per step of the flow.** No criterion without a case, no case without a source. `source` is the id of the criterion or step (`<entry>#C3`, `<entry>#P2`), copied exactly; `target` is the target's id.
2. **`expected` is observable.** What a person sees or can verify on the deployed environment, in the words of the criterion's `then` (or the step's `result`): a displayed text, a state, a navigation, a visible record. Never an internal state, never a code path, never a word of the format's ambiguous list.
3. **A case expresses its criterion, no more and no less.** Do not add a check the criterion does not state, do not drop part of its `then`. A criterion that cannot be observed is not given an invented expected: put it in a `QUESTION:` with the criterion's id.
4. **Persona.** When one is given, set `persona` and write, per case, `how`: the way that persona plays it (device, viewport, keyboard only, zoom, screen reader through the accessibility tree, language, pace), taken from the persona's own document. `how` changes the way of playing, never `expected`. Without a persona, omit `how`.
5. **Case ids** are `K1`, `K2`… in the criteria's order. One precondition (an account, data) shared by cases is stated in the first case's `how` and not repeated.
6. **A criterion marked as verified by `human` or `judgment`** still gets its case; do not decide who runs it.

Never run a case, never edit a criterion or a flow, never reorder or merge two criteria into one case.

Return the plan's path and the `ASSUMPTION:` lines (a persona detail you had to choose, an unstated precondition).
