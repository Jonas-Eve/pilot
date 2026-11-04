# PILOT task — Verify a raw technical need or bug report against the real code (Spec's no-ticket entry, before any ticket)

Injected by `.claude/skills/pilot-spec/SKILL.md` into the `pilot-techlead` persona's
prompt, alternating turns with the architect's own `.pilot/pilot-task-challenge-need.md`
(`.pilot/pilot-link-agent-dialogue.md`), inside each round of the framing stage: a human is
live, but the architect is the one who speaks to them — you talk to the architect, and no
ticket exists yet.

You receive the raw need (`--tech`, `--bug`, or auto-detected) and the framing conversation
so far: the human's answers and the architect's turns. Each round, in your turn's text:

1. Check the claims against the real project instead of taking them on trust: does what the
   need describes exist as described, where does it live, what does it touch. For a bug,
   try to reproduce or localize it — say what you ran and what happened, and how confident
   you are. Run only read-only or validation commands; change nothing.
2. Judge feasibility and size: could it be done as worded, hidden dependencies, how it
   would be tested, obvious blockers. Say if it is really bigger than it reads (several
   stories), or smaller (already done, or a duplicate of an open ticket — check the open
   issues).
3. End with what the human must decide, for the architect to put to them: at most four
   questions, the most shape-changing first, each with a provisional default, without
   repeating the architect's.
4. Say whether, from the code's side, the need is **ready** to be formalized.

Do not write the ticket, a split or a spec, and do not write code.
