# PILOT link — pushing live events to the project's dashboard

Read by `pilot-spec`, `pilot-dev`, `pilot-review`, `pilot-qa`, and `pilot-dashboard` (which
publishes the page that reads these documents). Best-effort only: GitHub labels stay the
source of truth, and a push that fails or is skipped never blocks, delays or changes a phase.

**When.** `.pilot/state.json` has `dashboardUrl` and the tool that writes to the dashboard's
database is available. Otherwise skip everything below, silently. Decide once per session.

**What to push** (to the dashboard at `dashboardUrl`):
- Every `event` returned by `.pilot/pilot.py claim|set|flag|unflag`: a new document in the
  `events` collection, id `<epoch milliseconds>-<issue number>`, body = the event object as
  returned. Always a new document, never an update.
- After a successful `claim`: its `activity` object as a document in the `activity`
  collection, id = its `id`, with two fields added: `auto` (`true` when this run is `--auto`,
  else `false`) and `lastBeat` (now, UTC ISO 8601, e.g. `date -u +%Y-%m-%dT%H:%M:%SZ`). Keep
  the version each write returns.
- Refresh `lastBeat` — an update pinned to the last version you got — after each `Agent` call
  returns.
- When the run ends — done, stopped, or `needs-human` — delete that activity document
  (pinned to the last version).

Never read the dashboard back, never retry a failed push, and mention a failure only in the
phase's final report.
