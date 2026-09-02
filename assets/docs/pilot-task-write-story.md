# PILOT task — Write a `type:feature` story

Injected by `.claude/skills/pilot-story/SKILL.md` into the `pilot-pm` persona's prompt.

You receive a raw idea in free text (possibly after back-and-forth with the human). Turn
it into a well-formed `type:feature` GitHub issue — not code, architecture, or
dependency/splitting decisions; that's phase 2's job.

1. Check this project's functional-scope doc, if any, to confirm the idea is in scope.
   Clearly out of scope → say so and stop, nothing created. Genuinely unsure (not clearly
   out) with a human live in this session → ask directly instead of declining — the one
   point in phase 1 where this applies, since no ticket exists yet for a `needs-human`
   label to attach to (unlike phases 2-4, `docs/pilot-process.md` §3 "needs-human — an
   orthogonal flag"). No human available → say you're unsure and stop, same as
   out-of-scope. No functional-scope doc at all → judge from the project's
   README/CLAUDE.md and existing issues, leaning toward asking over guessing when
   genuinely unclear.
2. Decide whether the idea fits in **one** story or genuinely needs **several** — don't
   force a sprawling single story to avoid the extra step. If several:
   - Reuse an existing open `level:epic` + `type:feature` issue that already fits this
     idea by theme (new stories become its sub-issues) rather than duplicating an Epic.
   - Otherwise create a new Epic (`level:epic` + `type:feature`, no `status:` label,
     open, unassigned) titled/described at the theme level, not story level.
3. Write each story's issue body as a standard user story:
   - "As a ... I want ... so that ..." (or the equivalent in whatever language the idea
     was given in — match it).
   - Acceptance criteria as a checklist — concrete, testable statements, not vague goals.
   - Explicit out-of-scope notes for anything adjacent you're deliberately not including.
4. Do not decompose into technical tasks, decide architecture, or record dependencies —
   that's the architect's job in phase 2. Do not write or suggest code. An Epic is a
   different kind of grouping than a task split (`docs/pilot-process.md` §2) — don't
   conflate them.
5. Set the story's initial `priority:P0/P1/P2` (`docs/pilot-process.md` §3) — business
   value/urgency to the user, not a technical-risk call (that's the architect's framing
   for `type:tech`/`type:bug`). The architect may still revise it per task in phase 2
   once the split is known.
6. Label each story `type:feature`, `level:story`, `status:backlog`, the priority from
   step 5, unassigned. If created under an Epic, link it as that Epic's sub-issue.
