# PILOT task — Consolidate the runs of a user flow

Injected by `.claude/skills/pilot-flow/SKILL.md` into one `pilot-qa` call, alongside `.pilot/pilot-link-bug-tickets.md` in full.

You receive a user flow and the results of each persona's run (the JSON of `.pilot/pilot-task-flow-run.md`). Each persona ran alone: nobody has compared them.

1. **Group the failures by root cause**, across personas: the same step failing for two personas for one reason is one finding, a step failing for one persona only because of their constraints (zoom, keyboard,
   language) is its own finding naming that persona.
2. **Classify each finding** (`.pilot/pilot-link-bug-tickets.md`). A genuine defect against what the flow or the wiki states → originate one `type:bug` ticket per root cause as that doc says, `status:backlog`: its title names
   the flow and the step, its body the personas affected, the steps to reproduce (the persona's constraints included) and what was observed. There is no discovering ticket: nothing to link back to, nothing to unclaim.
   Anything else (a product question, an edge nobody settled, a flow that no longer matches the product) is not a bug: report it for a human to raise via Discovery. An exact duplicate of an open bug ticket: create nothing, name it.
3. **Friction** is never a ticket. Keep each one with its persona and step, merged when several personas met the same one.
4. A persona whose session did not start, and every `untestable` step, are reported as such, never counted as passed.

You never write application code, claim or label a ticket, or write to the wiki.

Return one JSON object, nothing else:

```json
{"bugs": [{"ticket": 0, "title": "", "personas": [], "steps": []}],
 "not_bugs": [{"finding": "", "personas": [], "steps": []}],
 "friction": [{"persona": "", "step": 1, "observed": ""}],
 "not_run": [{"persona": "", "step": 0, "why": ""}]}
```
