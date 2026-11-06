---
name: pilot-dashboard
description: "Publishes — or updates — the project's PILOT dashboard: one private Claude Artifact per project, with its own data, showing tickets by phase, each person's queue by role, the PILOT sessions working right now, and the project's design system and brand charter (written by /pilot-design) and its prototypes (written by /pilot-proto), both left untouched by --refresh. Renders the project's name and GitHub repo into a template from github.com/Jonas-Eve/pilot, publishes it, records its address in .pilot/state.json (dashboardUrl), and seeds its ticket snapshot. Run again, or let /pilot-update run it, to republish the latest template at the same address — the data is kept. --refresh re-reads the tickets into the snapshot and prunes obsolete events. Run only when asked (by the human, /pilot-init or /pilot-update): it publishes a page. Needs the Artifact tool, which not every surface has."
argument-hint: "[--refresh]"
---

# PILOT dashboard — `pilot-dashboard`

Not one of the five phases. One private Artifact per project; `.pilot/state.json` holds its
address. The phase skills push live events to it (`.pilot/pilot-link-dashboard.md`).

## Source

Reuse `$PILOT_SRC` when `/pilot-init` or `/pilot-update` already cloned it; otherwise clone
`https://github.com/Jonas-Eve/pilot` fresh into a scratch directory. The page is
`$PILOT_SRC/assets/templates/pilot-dashboard.html.tmpl`.

## Steps

1. **Preconditions.** `.pilot/state.json` exists with `pilotInitialized: true`, else stop and
   point at `/pilot-init`. The `Artifact` tool must be available, else say so and stop —
   nothing else in PILOT depends on the dashboard.
2. **Render.** Project name = `projectName` from `state.json`, HTML-escaped (`& < > " '`).
   Repo = `owner/repo` from `git config --get remote.origin.url`; it must match
   `[\w.-]+/[\w.-]+`, else stop and ask the human. Replace `{{PROJECT_NAME}}` and `{{REPO}}`
   and `{{PILOT_VERSION}}` (the contents of `$PILOT_SRC/VERSION`, shown in the page's footer) in
   the template, write the result to a temporary file, check that `{{DEPLOYED_AT}}` is the only
   `{{` left, and take its `sha256sum` — the hash is of that file, `{{DEPLOYED_AT}}` still in
   place, so the deployment date never makes two identical renders differ.
3. **Publish** (skipped by `--refresh` when the hash is unchanged). Before each publish, set the
   deployment time `now` (UTC ISO 8601, e.g. `date -u +%Y-%m-%dT%H:%M:%SZ`) and publish a copy of
   the rendered file with `{{DEPLOYED_AT}}` replaced by it (shown in the page's footer next to the
   version); the copy's hash is never the one recorded:
   - No `dashboardUrl` → ask the human to confirm creating a private artifact named
     "Cockpit <project name>", then publish the file with `icon: "board"`, a one-sentence
     `description`, and the capabilities below.
   - `dashboardUrl` set and the hash equals `dashboardHash` → nothing to publish; say so.
   - `dashboardUrl` set and the hash differs → `Artifact` `read` that URL, then publish the
     file to that `url` (same address, data kept) with the capabilities below. If it can't be
     read, or the read says the current user can't edit it (only its owner or an editor can
     republish), stop and say so — never create a second artifact for the project.

   Capabilities, always the full set and nothing else (no connector): `db` with rules
   `snapshots` (read `view`, write `admin`), `design`, `protos`, `protoHtml`, `events` and `activity` (read `view`, write
   `interact`).
4. **Snapshot** (after a first publish, and for `--refresh`). `python3 .pilot/pilot.py
   snapshot --out <temp file>`, then `ArtifactData` `set` on `snapshots/<owner>__<repo>` with
   that `file_path` (`get` it first and pass `if_version` if it already exists).
5. **Prune** (with step 4). `events` documents whose `at` is older than the snapshot's `at`
   are obsolete, and so are `activity` documents whose `lastBeat` is over 24 h old: list the
   collections (read them into the conversation: `out_dir` is refused for documents others may
   have written), then `delete` them in `batch`es of 50 (`if_version` each).
6. **Record**, only when step 3 published. Write `dashboardUrl`, `dashboardHash` and
   `dashboardSyncedAt` (the deployment time `now` of step 3: when the dashboard's current
   version went live, not when its data was last refreshed — that is the snapshot's `at`)
   into `.pilot/state.json`, leaving every other field alone. A `--refresh` that published
   nothing writes nothing there, so it never leaves a change to commit.
7. **Report.** The address; created, updated or unchanged; the snapshot's ticket count. The
   page is private until shared from the artifact's Share menu — people whose sessions should
   push events or edit the design system need the Contributor level. The page only reads the project's own data: a ticket
   changed by hand on GitHub shows up at the next `--refresh`, so say how often to run it
   (a scheduled task works).
