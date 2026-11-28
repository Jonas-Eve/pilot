---
name: pilot-wiki
description: "Answers a question about what the product does and what is promised, from the project's wiki (wiki/ at the project root, .pilot/pilot-link-wiki.md): a question in free text → answer with citations (path, status), and says when the wiki does not cover it. Read-only: it changes nothing and takes no flag. To change the wiki: /pilot-functional-frame (vocabulary, shared rules), /pilot-need (behaviors), /pilot-persona, /pilot-user-flow."
argument-hint: "<question>"
disable-model-invocation: true
---

# PILOT wiki — `pilot-wiki`

Read `.pilot/pilot-link-knowledge.md` (how to read the bundle) and `.pilot/pilot-link-wiki.md` (entry format, statuses) first. Consultation only: it reads through
`python3 .pilot/pilot.py wiki index|search|describe|show|status`, writes nothing, claims no ticket, changes no label.

`python3 .pilot/pilot.py module list` tells whether the `wiki` module is on. Off, or `wiki/` missing: say so, point at `/pilot-functional-frame` (it turns the module on), and stop.

1. Read per `.pilot/pilot-link-knowledge.md`: `wiki index --depth 1`, then `wiki search` or a folder, then `wiki show` only those that bear on the question.
2. Answer from them, citing each as its `path` with its `display` status. A `proposed`/`specified` entry is a promise, not behavior: say so.
   Where the wiki is silent, say it is not covered; do not fill the gap from the code.
3. A request to add, change or remove an entry is not answered here: name the skill above that does it.
