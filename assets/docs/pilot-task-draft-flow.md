# PILOT task — Draft a user flow

Injected by `.claude/skills/pilot-flow/SKILL.md` (`--new flow`) into the `pilot-qa` persona's prompt, with `.pilot/pilot-link-wiki.md` in full.

Write every title, description and body in the language the prompt names (English when it names none).

You receive a human's description of a journey, the product's vision, the personas that exist (id, title, description) and the behaviors of the wiki the journey touches. A human is live: this is a draft to refine together.

1. **A flow is one journey, tested end to end in a browser**: its goal, then numbered steps in order, each one `do → expect`, one action and one observable outcome per step. A step a tester cannot check from the browser is
   not a step.
2. **Ground every expectation in the wiki.** An expected outcome comes from a behavior the wiki states; cite it by id in the step. A step the wiki is silent on goes under `gaps` with the question for the human, never into the
   steps as an assumed behavior.
3. **The body carries two header lines**: `Personas: <id>, <id>` (only ids from the personas you received; none fits → say so under `questions`, never invent an id) and, when the journey does not start at the home page,
   `Start: <path or screen>`. Then the goal, then the steps.
4. **Reuse before adding.** An existing flow that covers the journey is an `update` of that id, not a near-duplicate.
5. The id is lowercase letters, digits and dashes (`find-a-place`). One flow is at most 800 words.

Return one JSON object, nothing else:

```json
{"action": "add|update", "id": "", "title": "", "description": "", "body": "", "gaps": [{"step": 0, "question": ""}], "questions": [""]}
```

`description` is one sentence (the entry's line in the index), `body` the prose only, headers included.
