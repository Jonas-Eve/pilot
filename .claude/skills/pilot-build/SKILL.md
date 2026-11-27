---
name: pilot-build
description: "Runs the build workflow on a ready ticket: the dev writes its tests first, then the code; a validator, code checks and a judge, then a review of the local diff by the PM, architect and designer where they apply, e2e tests, and finally one PR that only has to pass the CI before the script merges it. Asks a human only when a choice is covered by nothing."
argument-hint: "[<ticket issue>] | --resume <issue>"
---

# PILOT — build

Read `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md`, then run workflow `build`. No human is needed unless a question is raised.

**Target.** The number given, else `pilot.py pool build`: a story left unsplit or a task, `ready`, no `needs-human`, no open "Depends on #N". `resolve`, then `claim build <issue> --mode …` before any work.

**Specific.** The checks read the project's results: run its commands (`pilot.py config get commands.test|rules|e2e`) and write the JSON the checks list. The e2e tests run locally by script, never in CI. Open the PR only after the review, the e2e tests and every check have passed (`pilot.py pr open`); wait for the CI (`pilot.py pr ci`), then `pr merge`. After the merge: the ticket is `merged`, then `pilot.py derive <parent>`.
