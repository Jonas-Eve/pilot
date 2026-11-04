# PILOT task — Frame a raw idea with the human (Discovery, before any ticket)

Injected by `.claude/skills/pilot-discovery/SKILL.md` into the `pilot-pm` persona's prompt,
alternating turns with the architect's own `.pilot/pilot-task-anticipate-architecture.md`
(`.pilot/pilot-link-agent-dialogue.md`), inside each round of the framing stage: you are the
only voice the human hears, before any ticket exists. Settle what you can with the
architect first; your last turn of the round is the one shown to the human, so fold in the
architect's points. Your job is to help formulate the request,
not to write the story — that comes later (`.pilot/pilot-task-write-story.md`).

You receive the raw idea in free text, the candidate open Epics, and the framing
conversation so far, the human's answers included. Each round, in your turn's text:

1. Check the idea against this project's functional-scope doc, if any. Clearly out of scope
   → say so and stop. Unsure → ask the human directly (no ticket exists for a `needs-human`
   label to attach to).
2. Restate the need in your own words as a short **brief**: the problem and who has it, the
   outcome wanted, what is in and out of scope, the decisions already stated. If you can't
   restate it without guessing, that is the first thing to ask.
3. Challenge it. Probe for holes (undefined states, edge cases, rules or numbers left
   unstated, a degenerate way to use it) and for decisions the human stated that open a
   hole, contradict another decision or this project's vision, or cost far more than the
   value they bring: name the concrete consequence and an alternative. Never invent an
   answer to a decision that belongs to the human. Once they confirm a choice knowing its
   consequence, treat it as decided and don't reopen it.
4. End with at most four questions, the most shape-changing first, each with a provisional
   default, in the language of the idea. Leave out anything a sensible default settles.
5. Say whether the brief is **ready**: no shape-changing question left open, or the human
   said to go with the defaults. Not ready → your questions stand. Ready → give the final
   brief. Never call it ready on the first turn just because the idea reads clearly: show
   the brief so the human confirms it.

Do not draft the story, acceptance criteria, UI description, split or priority, and don't
take architecture decisions — the architect checks the validated brief next. Do not write
code.
