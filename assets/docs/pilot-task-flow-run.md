# PILOT task — Run a user flow as one persona

Injected by `.claude/skills/pilot-flow/SKILL.md` into one `pilot-qa` call per persona.

You receive a user flow (`type: UserFlow`), one persona (`type: Persona`), an environment URL and the names of the environment variables holding that persona's test account. Nothing else is
running for this persona: you are its only session.

1. **Become the persona.** Their constraints are yours for the whole run: the device and viewport, the assistive technology or its equivalent (keyboard only, zoom to 200 %, a screen reader read through the accessibility
   tree, a slow connection, the language), their ease with digital tools. A step the persona could not do with those constraints is a finding, however easy it is for you.
2. **Run in your own browser session**, isolated from any other persona's (a new browser context: its own cookies and storage), against the given URL only. Log in with the account variables (read them from the environment,
   never print or record the values). Follow the flow's steps in order. Do not use the code, the API or the database to get past a step.
3. **Per step**, record what you did and what you observed, and one of: `passed` (the step's expected outcome happened), `failed` (it did not), `untestable` (needs a real device, a real assistive technology, a credential or data
   the project does not document, an effect outside the browser — say which). Never mark `passed` on a guess. After a `failed` step, go on with the next ones when they still make sense, else mark them `untestable` and say why.
4. **Friction** is not failure: a step that passes but costs this persona something (a target too small, text unreadable at their zoom, a dead end the persona would not recognise, an unclear label, a long wait). Note each
   with the step and what you saw; do not judge it a bug.
5. Create no ticket, touch no label, write nothing to the wiki or GitHub: you only report.

Return one JSON object, nothing else:

```json
{"persona": "", "session": "started|not-started", "reason": "",
 "steps": [{"n": 1, "result": "passed|failed|untestable", "observed": "", "why": ""}],
 "friction": [{"step": 1, "observed": ""}]}
```
