# PILOT task — Draft one domain of the wiki from tickets and code

Injected by `.claude/skills/pilot-wiki/SKILL.md` (`--init`) into the `pilot-techlead` persona's
prompt, once per domain, together with `.pilot/pilot-link-wiki.md`.

You receive a domain (a functional area of the product, a folder of `wiki/`, e.g. `search/`), the closed tickets and accepted
prototypes that belong to it (title, body, comments) and where its code lives. Cross two
independent sources for every behavior of the domain: **intent** (the tickets and prototypes) and
**reality** (the code, read and run where cheap). Triage each behavior:

- `convergent` — intent and code agree.
- `divergent` — they disagree (intent says X, code does Y).
- `code-only` — the code does it, no ticket mentions it.
- `tickets-only` — a ticket promises it, the code has no trace of it.

Tickets that contradict each other over time: the most recent one wins; when that is not clear,
the behavior is `divergent`. State each behavior as the product's rule in the present tense, in
one short paragraph — what, never how. Pick a stable, lowercase, dash-separated id (the file name) and write a one-sentence `description`.

Every entry cites its two proofs: the ticket(s) and the `path:line` it found (or "none" for the
missing side). For `divergent`, write the two readings and the question the human must settle.

Return one JSON object, nothing else:

```json
{"domain": "",
 "entries": [{"id": "", "title": "", "path": "<domain>/<id>.md", "description": "", "body": "",
              "triage": "convergent|divergent|code-only|tickets-only",
              "tickets": [0], "ticketProof": "", "codeProof": "", "question": ""}]}
```
