# PILOT task — Validate a deliverable
Injected by every `validate` step into the persona that is not the lead (architect, techlead, pm or dev, as the step says).

You receive the deliverable alone and the documents the step lists, never the discussion or the producer's reasoning. Find what neither code nor the judge sees: code already checks format, citations, size and cycles; the judge already answers closed questions. Do not repeat them, do not assert that a check passed.

Look for, by kind of deliverable:
- a need: a criterion that a different reading would satisfy while missing the intent; a case the criteria leave open (error, empty, concurrent, first use); two criteria that cannot both hold; a source that does not support the criterion citing it.
- a frame (guidelines, functional rules): a statement that contradicts an ADR, another statement or the code as it is; a `by: rule` statement no tool could check, or a `by: judgment` one a rule could; an example that does not illustrate its statement; a scope too wide or too narrow for the reason given.
- a plan: a task that cannot be built without another it does not depend on; a criterion or decision no task carries, or carried twice; a task whose scope overlaps another's; a reads list missing what the task needs.
- an implementation: a deviation from an ADR or guideline, a case left uncovered, duplication, a readability problem a maintainer would trip on, a declared assumption that hides a real choice.
- a design system: a token pair that fails contrast, a component state missing for its use, a component using a value that is not a token, a name that two components could share.
- a prototype: a path through the need that the mockup cannot take, a state a person will reach and cannot see, an element the need does not ask for.

Rules:
1. Every defect cites its source (an entry id, `#C`/`#D`/`#E` id, a path and line, a token). Without one it is dropped.
2. A defect states what goes wrong for a person or a maintainer, not a preference.
3. Say what you did not check rather than assume; never invent a reference.
4. Change nothing; do not propose a rewrite beyond the one line a defect needs.

Return `DEFECT:` lines or `NO DEFECT`.
