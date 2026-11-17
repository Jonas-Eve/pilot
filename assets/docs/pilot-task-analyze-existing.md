# PILOT task — Analyze the existing

Injected by `/pilot-discovery`, `/pilot-spec`, `/pilot-dev`, `/pilot-design` and `/pilot-proto` into the prompt of the persona that opens a discussion (the PM in Discovery and `/pilot-proto`, the architect for Spec's
no-ticket entry, the tech lead for a story or a bug, the dev in Dev, the designer in `/pilot-design`), with `.pilot/pilot-link-existing-analysis.md` in full, before that persona proposes anything.

You receive the input (a raw idea, a need, or the ticket), and, when one exists, the analysis already written.

1. Read what the input touches, from the sources the link doc lists. Search before reading whole files; stop when the input's own points are covered.
2. Write the analysis in the link doc's three sections, every statement with its source.
3. An existing analysis is extended, never rewritten: return only the delta the new input needs.
4. Do not propose, decide or draft anything: this turn tells the human and the other personas exactly what exists, nothing more.

Return the analysis text only.
