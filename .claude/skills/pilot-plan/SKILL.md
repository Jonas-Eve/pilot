---
name: pilot-plan
description: "Runs the plan workflow: a ready epic or story becomes local ADRs and tickets ready to build — the story as it is, or split into tasks only when the code checks say it does not fit. Also takes a technical need stated directly by human T. Human T decides at one gate."
argument-hint: "[<epic or story issue>] | \"<technical need>\" | --resume <issue>"
---

# PILOT — plan

Read `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md`, then run workflow `plan`. The leads are the architect (ADRs, scopes) and the tech lead (the split), in dialogue; the validator is the PM for a story, the dev for a technical need.

**Target.** The number given, else `pilot.py pool plan`. `pilot.py claim plan <issue> --mode fresh` before any work (it moves the epic or story to `planning`). A technical need ("entry 2") has no ticket: the runner creates its `run` issue.

**Specific.** The orientation step is mandatory: the human gives one or says "no orientation"; silence is not an answer. The plan checks need the entries' paths, the ADR paths, the project's size threshold (`pilot.py config get threshold`) and the tickets' read sizes (count the bytes of the files each ticket's `reads` lists). The end creates the tasks (`pilot.py ticket create --level task`, under the story) or, for an unsplit story, sets it `ready`, then the epic and story statuses (`pilot.py derive`), the entries' `specified` and the ADRs' `accepted` in the docs PR.
