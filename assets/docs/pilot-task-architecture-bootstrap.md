# PILOT task — Draft the architecture overview and guidelines from the existing project

Injected by `.claude/skills/pilot-architecture/SKILL.md` (`--bootstrap`) into the `pilot-architect` persona's
prompt, together with `.pilot/pilot-link-architecture.md`.

You receive the project's inventory (its apps; an outline of `docs/**` and of each app's `README.md`, `CLAUDE.md` and `docs/**`; the state of the
`PILOT:ARCHITECTURE`/`PILOT:COMMANDS` blocks of `CLAUDE.md` and `README.md`) and the current commit. Classify each document from its outline, then open only
those that are architecture or decision, and read the code where cheap to confirm what a document claims:

- `architecture` — how the project is built: the apps, their stack, how they relate, commands, technical rules.
- `decision` — a document that justifies a choice (why X rather than Y).
- `functional` — what the product does for its users; not yours, list it.
- `other` — a contribution guide, a runbook, user documentation; leave it.

Produce:
- `overview.md` — each app or service: purpose, stack, how it talks to the others, and its dev/test/build
  commands, as they actually are.
- `guidelines/<id>.md` — one rule per file for each technical rule the project really follows or states
  (layering, testing, security, naming, dependencies): the rule in the imperative, one short paragraph, with
  the reason only when the code or documents give one. A rule stated in the documents that the code does not
  follow is `divergent`: write it as stated and put the question for the human.

In a monorepo, a rule that holds for one app only belongs under `apps/<app>/` (`apps/<app>/guidelines/<id>.md`, and
`apps/<app>/<app>-overview.md` for that app's own overview); what holds for every app stays at the root. Ids are unique across the whole bundle.

Do not invent rules the project does not follow, and write no ADR: a decision's reasoning is recorded only when
a human gives it. Pick a stable lowercase dash-separated id and a one-sentence `description` per entry.

A `decision` document yields no ADR: list it under `decisions` with the reasoning it states, for the human to confirm. Cite for every entry the document it
came from (`source`, or "code" when you read it there).

Return one JSON object, nothing else:

```json
{"entries": [{"path": "overview.md|guidelines/<id>.md|apps/<app>/…", "title": "", "description": "", "body": "", "source": "",
              "triage": "convergent|divergent|documented-only|code-only", "proof": "", "question": ""}],
 "decisions": [{"source": "", "decision": "", "reasoning": ""}],
 "functional": [""], "ignored": [""]}
```
