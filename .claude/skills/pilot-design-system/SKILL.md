---
name: pilot-design-system
description: "Creates or revises the project's design system (brand, colors, typography, components, usage rules) from a human's design intention: runs the `design-system` workflow (designer leads the discussion, validator, code checks, judge, a first gate on the design, then theme and components, a second gate, one PR). Works no ticket; the runner opens a run issue. A command launched by a human."
argument-hint: "[what to create or change, in free text]"
disable-model-invocation: true
---

# PILOT design system — `pilot-design-system`

Read `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md` first: the runner file says how any workflow runs (start, step loop, agents, gates, finish). This skill runs the **`design-system`** workflow and adds only what is specific to it.

- **Module.** `python3 .pilot/pilot.py module list`: with `design` off, say so and propose `python3 .pilot/pilot.py module enable design --with-requires`; on a yes go on, on a no stop.
- **Intention.** The `start` step takes the human's design need from the argument, else asks for it. When it comes from an accepted prototype, its `in` also lists the elements the prototype's gate decided to integrate; take them from that prototype's run (`python3 .pilot/pilot.py run show <run>`).
- **Sources.** The project's vision (`wiki show vision`), the brand, mockup, UX or theme files the root `CLAUDE.md` points to, the current design system in the repo, and whatever the human hands over in the session.
- **Run.** `python3 .pilot/pilot.py run start design-system` (no `--issue`: no ticket is worked), then the runner's loop. The workflow's gates replace any other confirmation; nothing is written outside the working tree before the second gate, and the run ends by one docs/code PR the script opens and merges after it.
- **Report.** What the PR changes in the design system, what is unverified, and what only a human can do.
