---
name: pilot-express
description: "Runs the express workflow: a simplified path to go fast — a hotfix, a core feature — for accounts allowed to use it. It writes provisional documentation, makes one story without tasks and builds it in the same workflow, so the need can still change while the work runs. The Recette stays a separate workflow."
argument-hint: "\"<request>\" [--from-report <issue>] | --resume <run issue>"
---

# PILOT — express

Read `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md`, then run workflow `express`. The human who asks stays the counterpart of every question and gate; the account must hold the express right (the platform decides, not this skill).

**Specific.** `--from-report N` starts from a blocking report qualified as a gap (its form and qualification are the request). An express refuses and says why when it would touch a frame, contradict an accepted ADR or guideline, or meet an open ticket on the same criteria: the request then goes through `/pilot-need`. Its build steps are the build workflow's, minus the e2e tests. The catch-up item is created at the end (`pilot.py ticket create --label express`, with its deadline in the body) so the provisional documents are confirmed, corrected or replaced by `/pilot-need` or `/pilot-plan`.
