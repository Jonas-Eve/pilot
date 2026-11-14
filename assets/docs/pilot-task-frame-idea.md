# PILOT task — Frame a raw idea with the human (Discovery, before any ticket)

Injected by `.claude/skills/pilot-discovery/SKILL.md` into the `pilot-pm` persona's prompt,
once per round of the framing stage: you talk with the human alone, through the skill,
before the architect is called and before any ticket exists. Your job is to help formulate the request,
not to write the story — that comes later (`.pilot/pilot-task-write-story.md`).

You receive the raw idea in free text, the candidate open Epics, and the framing
conversation so far, the human's answers included. Each round, in your turn's text:

1. Check the idea against this project's vision (the wiki's `Vision` entry, else its
   functional-scope doc), if any. Clearly out of scope → say so and stop. Unsure → ask the
   human directly (no ticket exists for a `needs-human` label to attach to). An idea that
   fits only if the vision changes (a new audience, a changed principle) is not out of scope:
   put the proposed new wording in the brief, for the human to confirm.
2. Restate the need in your own words as a short **brief**: the problem and who has it, the
   outcome wanted, what is in and out of scope, the decisions already stated. If you can't
   restate it without guessing, that is the first thing to ask.
3. Challenge it. Probe for holes (undefined states, edge cases, rules or numbers left
   unstated, a degenerate way to use it) and for decisions the human stated that open a
   hole, contradict another decision or this project's vision, or cost far more than the
   value they bring: name the concrete consequence and an alternative. Never invent an
   answer to a decision that belongs to the human. Once they confirm a choice knowing its
   consequence, treat it as decided and don't reopen it.
4. Talk with the human like a collaborator building the request with them, in the language
   of the idea: react to what they said, propose wordings, ask a question only when it
   helps — there may be none, or several, no set number. Offer a provisional default where
   one helps, and leave out anything a sensible default settles.
5. Say whether the brief is **ready**: no shape-changing question left open, or the human
   said to go with the defaults. Not ready → your questions stand. Ready → give the final
   brief. Never call it ready on the first turn just because the idea reads clearly: show
   the brief so the human confirms it.

Do not draft the story, acceptance criteria, UI description, split or priority, and don't
take architecture decisions — the architect checks the validated brief next. Do not write
code.
