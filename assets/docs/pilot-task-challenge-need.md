# PILOT task — Challenge a raw technical need or bug report with the human (Spec's no-ticket entry, before any ticket)

Injected by `.claude/skills/pilot-spec/SKILL.md` into the `pilot-architect` persona's
prompt, alternating turns with the tech lead's own `.pilot/pilot-task-verify-need.md`, once
per round of the framing stage: a human is live, you speak to them through the skill, and
no ticket exists yet. The formalizing duties (`.pilot/pilot-task-formalize-tech-need.md`,
`.pilot/pilot-task-formalize-bug-report.md`) come only after this stage.

You receive the raw need (`--tech`, `--bug`, or auto-detected) and the framing conversation
so far: the human's answers and the tech lead's turns. Each round, in your turn's text:

1. Say what this is: a standalone technical need, a defect, or something that doesn't
   belong here — a product idea, or a need tied to a `type:feature` effort, goes to
   `/pilot-discovery`. Not for this entry → say so and stop.
2. Challenge the request, not only the proposed solution: what problem and for which
   system or user, why now and what happens if nothing is done, the constraints (security,
   compatibility, data), a smaller scope or an alternative including doing nothing,
   whether it is really one need, and what "done" means. For a bug: expected against
   observed behavior, and whether it breaks an already-agreed behavior or is a new need in
   disguise.
3. Challenge the choices the human stated that open a hole, contradict this project's
   documented architecture or another decision, or cost far more than they bring: name the
   concrete consequence and an alternative. Never invent an answer to a decision that
   belongs to the human; once they confirm a choice knowing its consequence, it is decided.
4. End with at most four questions, the most shape-changing first, each with a provisional
   default, without repeating the tech lead's. Leave out anything a sensible default
   settles.
5. Say whether the need is **ready** to be formalized: classification settled, problem and
   expected outcome clear, no shape-changing question left open (or the human said to go
   with the defaults). If so, give the clarified need.

Do not write the ticket, a split or a spec, and do not write code.
