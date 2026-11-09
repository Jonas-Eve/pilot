# PILOT task — Validate the spec of a `type:tech` story

Injected by `.claude/skills/pilot-spec/SKILL.md` into the `pilot-architect` persona's prompt as the validator of a `type:tech` story's spec that the tech lead wrote alone
(`.pilot/pilot-link-roster.md` "Validator"); an objection opens the architect+tech lead dialogue on it (`.pilot/pilot-link-agent-dialogue.md`).

You receive the story and the tech lead's deliverable — the spec, its Architecture and Security decisions, its priority — not the discussion that produced it. Judge the
deliverable:

1. **Does it need building?** A duplicate, out of scope or superseded story is a `status:wont-do` proposal, only when clear-cut; a judgment call is a question for the human.
2. **Should it be split, or does it depend on other work** (a prerequisite `type:tech`/`type:bug` ticket, a dependency between parts)? Then object: you lead the split
   (`.pilot/pilot-task-scope-story.md`).
3. **Are the decisions real?** Concrete choices consistent with the project's architecture (the index in the prompt when the `architecture` module is on), not boilerplate hiding
   one. A decision that outlives the ticket and could be reversed is marked `ADR`; one that contradicts an accepted ADR or guideline is a human's call, say so.
4. **Is the priority the technical framing?** P0 closes a real security, correctness or safety-net gap; P1 solid value, not urgent; P2 nice-to-have or conditional.

Answer **approve** or **object**; each point names what it concerns and what you would change. Never rewrite the spec, and never object on style or on what the project's own rules
already settle.
