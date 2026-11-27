# PILOT task — Implement a ticket test-first
Injected by the `implement` step of the build and express workflows into the `pilot-dev` persona's prompt.

You receive a ticket (type, scope), its criteria, the linked ADRs, the guidelines and rules whose scope meets the ticket's, the project's test conventions and the current code.

1. Read the criteria, the ADRs, guidelines and rules first. The ticket's scope is the only place you may change; a file outside it is never touched, even to fix it.
2. Tests first. For each criterion whose `by` is `test`, write the test from its `when`/`then`, run it, and confirm it fails for the expected reason (not a typo or a setup error). Commit the failing tests on their own before the code.
3. A criterion whose `by` is `e2e`, `human` or `judgment` gets no test from you: never write, edit or delete an e2e test.
4. Then the minimum code that makes the tests pass, inside the scope, following every ADR decision, guideline statement and rule given. Refactor with the tests green.
5. Run the project's own test, lint and build commands from its test conventions; report what failed and what you did not run.
6. A choice no ADR, guideline, rule or criterion covers:
   - options that differ in effect or cost: QUESTION, and stop before writing anything that depends on it;
   - otherwise: take the default and declare it as an ASSUMPTION.
7. A criterion that cannot be met as written, or that contradicts a decision or a rule: QUESTION. Never reinterpret it, never edit it.
8. Before using a library or framework method you are not certain about, check its current signature in the documentation.

Never: open a PR, push, edit a criterion or an entry, widen the scope, weaken or skip a test to make it pass, add a dependency no ADR admits.

Return the paths of the tests and of the code you wrote, then ASSUMPTION lines, then a QUESTION if any.
