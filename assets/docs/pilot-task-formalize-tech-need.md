# PILOT task — Formalize a standalone raw `type:tech` need

Injected by `.claude/skills/pilot-spec/SKILL.md` into the `pilot-architect` persona's
prompt, for its own no-ticket entry, when the raw need auto-detects (or is declared via
`--tech`) as a standalone technical need with no product framing. You're working alone
here, not in dialogue — this is a classification/drafting step, not the split/spec
dialogue with the tech lead that follows once this ticket exists
(`.pilot/pilot-link-agent-dialogue.md`).

You receive a raw technical need in free text (possibly with a rough back-and-forth
already had with the human) — infra, CI, security hardening, deployment, migration,
performance/optimization work with no product framing. If the need actually reads as a
product idea instead, say so and point at `/pilot-discovery` rather than drafting it here
— this entry is only for something with no PM angle at all. Turn it into a
well-formed `type:tech` GitHub issue, with your own initial `priority:P0/P1/P2`
(`.pilot/pilot-process.md` §3 — the technical framing: security/correctness/safety-net);
deciding whether it needs splitting into dev-sized tasks is a separate, later step in the
same skill invocation, once this ticket is drafted and approved.

1. Write the story's issue body: what the need actually is and why, concrete enough
   that the split/spec pass that follows can work it without re-litigating what you meant.
2. **Standalone, never grouped under an Epic** — there is no `type:tech` epic
   (`.pilot/pilot-process.md` §2 "Three levels"); a need that genuinely can't be delivered
   as one story is rare enough here that it's not worth an epic mechanism of its own —
   create each as its own standalone `level:story` instead, cross-referenced with a plain
   "Related: #N" note in each one's body if you do split it this way. If the need is tied
   to a product effort instead (it belongs alongside a `type:feature` story), it isn't
   standalone — point at `/pilot-discovery` instead, where the PM+architect dialogue can
   group it under that effort's own Epic.
3. Label each story `type:tech`, `level:story`, `status:draft` (this skill's own no-ticket
   entry drafts it live with a human before finalizing, same as Discovery does), its own
   initial `priority:P0/P1/P2` (above), assigned to this session. If you created more than
   one (step 2's rare case), the skill continues splitting/speccing only the primary one
   in this same run — the others still get drafted and approved right here, but land on
   `status:backlog` for a later run, same as any other standalone tech story
   (`pilot-spec/SKILL.md` step 1a).
