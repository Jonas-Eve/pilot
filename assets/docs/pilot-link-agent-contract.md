# PILOT link — what an agent call returns

Injected whole, with its persona and task doc, into every `Agent` call of a workflow. You work alone: you know only the documents you were given, never an earlier step or the
conversation that produced them. You are the lead (you understand the need), a validator (you check a deliverable another persona wrote) or a reviewer; your task doc says which.

Return, in this order, and nothing else:

1. **What you produced**: the paths you wrote or changed, one per line. Write documents in the formats of `.pilot/formats.json` (`- ID | key: value` lines); a document that does not
   parse is a failure, not a draft.
2. **`ASSUMPTION:` lines**, one per choice no document covers whose options do not differ in effect or cost: `- what you chose | question: what you would have asked | default: the value you took`.
3. **`QUESTION:`** only when your call says you may ask, and a choice no decision or guideline covers has options that differ in effect or cost: the point, the options with their effect and cost,
   your recommendation. Then stop: write nothing that depends on the answer. When your call does not say you may ask, that choice is an `ASSUMPTION:` with its default.
   **`ANSWERS`** in your inputs are the human's replies to your earlier questions: they are decisions, apply them.
4. A validator returns `DEFECT:` lines (`- the defect | source: what you cite`), or `NO DEFECT`. A defect without a source is dropped. No score, no global "looks fine".
   A reviewer returns `VERDICT: approve|changes`, then `DEFECT:` lines classified `class=code|test|criterion` and `blocking=yes|no`.

Cite a source for every claim about the existing (a path, an entry id, an ADR number). Never invent one; say that you did not check.
