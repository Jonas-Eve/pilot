---
name: pilot-architecture
description: "Answers a question about how the project is built and why, from its architecture bundle (architecture/ at the project root, .pilot/pilot-link-architecture.md): overview of the apps, technical guidelines, reference of the code, decisions. A question in free text → answer with citations (path, status), and says when the architecture does not cover it. Read-only: it changes nothing and takes no flag. To change it: /pilot-technical-frame (guidelines), /pilot-plan (ADRs)."
argument-hint: "<question>"
disable-model-invocation: true
---

# PILOT architecture — `pilot-architecture`

Read `.pilot/pilot-link-knowledge.md` (how to read the bundle) and `.pilot/pilot-link-architecture.md` (layout, statuses) first. Consultation only: it reads through
`python3 .pilot/pilot.py arch index|search|describe|show`, writes nothing, claims no ticket, changes no label.

`python3 .pilot/pilot.py module list` tells whether the `architecture` module is on. Off, or `architecture/` missing: say so, point at `/pilot-technical-frame` (it turns the module on), and stop.

1. Read per `.pilot/pilot-link-knowledge.md`: `arch index --depth 1`, then `arch search` or a folder, then `arch show` only those that bear on the question (`--all` for history).
2. Answer from them, citing each as its `path` and status. A `proposed` entry is not yet a rule: say so; a `superseded` one is history, point at its successor.
   Where the architecture is silent, say it is not covered; do not fill the gap from the code.
   Asked for a global ADR: there is none in the technical frame; ADRs are local, written by the plan workflow.
3. A request to add, change, accept or remove an entry is not answered here: name the skill above that does it.
