# PILOT link — pushing live events to the project's dashboard

Read by the skills that run a workflow (`pilot-need|plan|build|accept|report|express|functional-frame|technical-frame|design-system|proto|persona|user-flow`) and by `pilot-dashboard`.
Best-effort only: GitHub and the run records stay the source of truth; a push that fails or is skipped never blocks or changes a run.

**When.** `.pilot/state.json` has `dashboardUrl`, does not turn the `dashboard` module off (`modules.dashboard` set to `false`), and the dashboard's database tool is available. Else skip everything below, silently. Once.

**What to push** (to the dashboard at `dashboardUrl`):
- Every `event` returned by `.pilot/pilot.py claim|set|flag|unflag`, and by `run start|advance|resume|end` (`kind: "run"`), and every entry of the `events`
  list of `event` (several tickets: one `ArtifactData` `batch`): a new document in the `events` collection, id `<epoch milliseconds>-<issue
  number>`, body = the event as returned, unchanged. Always a new document. A `run` event carries the workflow, step, state and, once the run ended, its result: the cockpit's runs and prototypes read them.
- At the end of a run, one snapshot (`.pilot/pilot.py snapshot`), pushed as `pilot-dashboard` says.

Never read the dashboard back or retry; mention a failure only in the final report.
