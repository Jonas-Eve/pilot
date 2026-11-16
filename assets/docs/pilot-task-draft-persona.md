# PILOT task — Draft a user persona

Injected by `.claude/skills/pilot-flow/SKILL.md` (`--new persona`) into the `pilot-designer` persona's prompt, with `.pilot/pilot-link-wiki.md` in full.

Write every title, description and body in the language the prompt names (English when it names none).

You receive a human's description of an end user, the product's vision, and the personas that already exist (id, title, description). A human is live: this is a draft to refine together.

1. **A persona is a kind of user to test as**, not a marketing segment and not a real person. Say who they are, what they come to do with the product, and the constraints a test must reproduce: the device and viewport, the assistive
   technology or its equivalent (keyboard only, zoom, screen reader, voice), the language, their ease with digital tools, and what makes them give up. Keep only what changes what a tester does or sees.
2. **One line for the test account**: `Test account: <short label>` (or `Test account: none` when the persona needs no login). A label only: never a login, password, token or any secret.
3. **Reuse before adding.** If an existing persona already covers the description, return it as an `update` of that id with the change, not a near-duplicate.
4. **Do not invent.** What the description and the vision do not say, ask under `questions`; do not fill it with plausible detail.
5. The id is lowercase letters, digits and dashes, short and stable (`marie-senior`). One persona is at most 400 words.

Return one JSON object, nothing else:

```json
{"action": "add|update", "id": "", "title": "", "description": "", "body": "", "questions": [""]}
```

`description` is one sentence (the entry's line in the index), `body` the prose only, including the `Test account:` line.
