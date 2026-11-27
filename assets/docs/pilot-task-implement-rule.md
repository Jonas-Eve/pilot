# PILOT task — Implement the rules of a guideline
Injected by the `implement` step of the technical-frame workflow into the `pilot-dev` persona's prompt.

You receive a validated guideline (its source, statements, examples), the guidelines and tooling whose scope meets its own, and the project's current configuration.

1. List the statements marked `by: rule`. Each gets at least one rule: a linter rule, a test or a build constraint, using the tooling the guidelines already in force name. Statements marked `by: judgment` get nothing from you.
2. Each rule is limited to the guideline's `pilot.scope`: it never fires outside it, and the configuration states the scope explicitly.
3. Every example of the guideline becomes an automated case: a `pass` example must be accepted, a `fail` example must be rejected. Write the cases first and see the `fail` ones go undetected before the rule exists.
4. Prove detection: inject one violation of each rule into a scratch copy of the code inside the scope, confirm the rule reports it, then remove it. A rule that detects nothing is a defect, not a result.
5. Run the new rules on the existing code. A pre-existing violation is not fixed by you and the rule is not loosened to hide it: list it as an ASSUMPTION with its count and paths.
6. Put the configuration in `architecture/` and the project where the tooling expects it; each rule carries the guideline id and statement id (`<entry>#E<n>`) it implements.
7. No tool in the guidelines or project fits a statement, or two statements conflict: QUESTION. Never add a new tool or dependency on your own.

Never: edit the guideline or its statements, write a rule for a `judgment` statement, widen a scope, open a PR.

Return the paths of the rules, cases and configuration, then ASSUMPTION lines, then a QUESTION if any.
