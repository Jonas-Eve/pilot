# PILOT task — Correct a wiki entry

Injected by `.claude/skills/pilot-wiki/SKILL.md` (`--edit`) into the `pilot-pm` persona's prompt, together with
`.pilot/pilot-link-wiki.md`.

Write in the language the prompt names (English when it names none).

You receive one entry (status, tickets, text) and the change a human asks for. First decide what the change is:

- `correction` — wording, precision, a missing detail the entry already implies, a typo, vocabulary. After it, the
  product does exactly what the entry already promised or does today; nobody would have to change the code.
- `behavior-change` — after it, the product would do something different: a new behavior, a removed one, another
  rule, another threshold. This is not yours to write: say in `reason`, in one sentence, what would change.

For a `correction`, return the entry as it should read, nothing more changed than the request says: the present
tense, what the product does and never how, no ticket vocabulary. Where the request is ambiguous, put the question
in `questions` instead of choosing. A request that mixes a correction and a behavior change is a `behavior-change`.

Return one JSON object, nothing else:

```json
{"verdict": "correction|behavior-change", "reason": "", "title": "", "description": "", "body": "", "questions": [""]}
```

`title`, `description` and `body` are empty for a `behavior-change`.
