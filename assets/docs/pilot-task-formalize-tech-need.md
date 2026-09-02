# PILOT task — Formalize a raw `type:tech` need

Injected by `.claude/skills/pilot-story/SKILL.md` into the `pilot-architect` persona's
prompt, when the raw need auto-detects (or is declared via `--tech`) as technical.

You receive a raw technical need in free text (possibly with a rough back-and-forth
already had with the human) — infra, CI, security hardening, deployment, migration,
performance/optimization work with no product framing. Turn it into one or more
well-formed `type:tech` GitHub issues, each with your own initial `priority:P0/P1/P2`
(`docs/pilot-process.md` §3 — the technical framing: security/correctness/safety-net);
deciding whether it needs splitting or recording dependencies is still phase 2's job,
later and separately.

1. Decide if the need fits **one** story or genuinely needs **several** (e.g.
   "CI"/"optimization" needs often do) — don't force one sprawling story to avoid the
   split.
2. If several: reuse an existing open `level:epic` + `type:tech` issue that fits by
   theme (new stories become its sub-issues), else create a new tech Epic
   (`level:epic` + `type:tech`, no `status:` label, open, unassigned) — same as the PM
   does for `type:feature` (`docs/pilot-process.md` §2).
3. Write each story's issue body: what the need actually is and why, concrete enough
   that phase 2 can scope it without re-litigating what you meant.
4. Label each story `type:tech`, `level:story`, `status:backlog`, its own initial
   `priority:P0/P1/P2` (above), unassigned. If created under an Epic, link it as that
   Epic's sub-issue.
