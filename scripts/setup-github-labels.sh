#!/usr/bin/env bash
# Idempotently creates/updates every GitHub label the PILOT ticket process depends on
# (see assets/docs/pilot-process.md §3 for the label taxonomy this mirrors).
#
# Usage:
#   scripts/setup-github-labels.sh [owner/repo]
#
# Without an argument, operates on the repo of the current directory (as resolved by
# `gh repo view`). Requires the `gh` CLI, authenticated with a token that can manage
# labels on the target repo.
#
# Safe to re-run: each label is created if missing, or updated in place (color +
# description) if it already exists. Never deletes a label.
#
# If a `.pilot/state.json` exists in the current directory (i.e. this is being run from
# a PILOT-initialized project's own root, as pilot-init/pilot-update both do), this also
# bumps that file's `lastLabelsSyncAt` field to now, in place, leaving everything else in
# the file untouched. Run from anywhere else (no such file, or too early in pilot-init's
# own flow, before it has created one yet), this step is a silent no-op.

set -euo pipefail

REPO_ARG=()
if [[ $# -ge 1 ]]; then
  REPO_ARG=(--repo "$1")
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh CLI not found. Install it and run 'gh auth login' first." >&2
  exit 1
fi

# name|color(hex, no #)|description
LABELS=(
  "type:feature|1D76DB|PILOT: functional user story, formalized by the PM during phase 1"
  "type:tech|0E8A16|PILOT: technical need, formalized by the architect during phase 1"
  "type:bug|D93F0B|PILOT: defect in shipped code, classified by the architect; always level:task, skips phase 2"
  "type:e2e|FBCA04|PILOT: mandatory end-to-end task on every type:feature split; routes phase 4 to pilot-e2e"
  "level:epic|5319E7|PILOT: groups several level:story tickets by theme; never scoped/spec'd/built itself"
  "level:story|BFD4F2|PILOT: the root unit phase 1 produces; may stay unsplit or become status:split"
  "level:task|C2C2C2|PILOT: dev-sized unit of a status:split story, or a standalone type:bug ticket; never split further"
  "priority:P0|B60205|PILOT: highest priority, initial value at phase 1 (PM/architect), revised at phase 2"
  "priority:P1|D93F0B|PILOT: medium priority, initial value at phase 1 (PM/architect), revised at phase 2"
  "priority:P2|FBCA04|PILOT: lowest priority, initial value at phase 1 (PM/architect), revised at phase 2"
  "status:draft|C5DEF5|PILOT: phase 1 has created the ticket, awaiting final human approval in pair mode"
  "status:backlog|BFD4F2|PILOT: ticket exists, phase 2 hasn't started"
  "status:in-scope|C5DEF5|PILOT: architect has claimed it for phase 2"
  "status:spec-ready|BFD4F2|PILOT: scoped-and-not-split, or a type:bug ticket skipping phase 2 entirely; ready for phase 3"
  "status:in-spec|C5DEF5|PILOT: tech lead has claimed it for phase 3"
  "status:dev-ready|BFD4F2|PILOT: spec written, ready for phase 4"
  "status:in-dev|C5DEF5|PILOT: a dev has claimed it for phase 4"
  "status:review-ready|BFD4F2|PILOT: a PR is open, ready for phase 5 to claim"
  "status:in-review|C5DEF5|PILOT: phase 5 has claimed it and is running (or blocked)"
  "status:changes-requested|F9D0C4|PILOT: phase 5 found at least one blocking, code-level point"
  "status:approved|0E8A16|PILOT: phase 5 ran, every reviewer approved, ready to merge"
  "status:wont-do|E4E669|PILOT: concluded (phase 1 or phase 2) this ticket shouldn't be built"
  "status:split|D4C5F9|PILOT: split into tasks (mandatory for type:feature, judgment call for type:tech); tracks its tasks"
  "status:qa|FBCA04|PILOT: type:feature story whose tasks are all done; ready for phase 6 human QA"
  "status:in-qa|C5DEF5|PILOT: pilot-qa has claimed it for phase 6"
  "status:done|0E8A16|PILOT: merged, via cascade from a status:split parent's tasks, or confirmed by phase 6 QA"
  "needs-human|B60205|PILOT: a phase hit something only a human can decide; status: stays wherever it was"
  "on-hold|C2C2C2|PILOT: deliberately paused, not blocked on a question; excluded from every phase's candidate pools"
)

echo "Setting up PILOT labels on ${1:-the current repo}..."

for entry in "${LABELS[@]}"; do
  IFS='|' read -r name color description <<<"$entry"
  if gh label list "${REPO_ARG[@]}" --search "$name" --json name --jq '.[].name' 2>/dev/null | grep -qx "$name"; then
    gh label edit "$name" "${REPO_ARG[@]}" --color "$color" --description "$description"
    echo "  updated: $name"
  else
    gh label create "$name" "${REPO_ARG[@]}" --color "$color" --description "$description"
    echo "  created: $name"
  fi
done

echo "Done. ${#LABELS[@]} PILOT labels are in sync."

STATE_FILE=".pilot/state.json"
if [[ -f "$STATE_FILE" ]] && grep -q '"lastLabelsSyncAt"' "$STATE_FILE"; then
  NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if command -v perl >/dev/null 2>&1; then
    perl -pi -e 's/"lastLabelsSyncAt"\s*:\s*(null|"[^"]*")/"lastLabelsSyncAt": "'"$NOW"'"/' "$STATE_FILE"
    echo "Updated $STATE_FILE: lastLabelsSyncAt=$NOW"
  else
    echo "warning: perl not found, couldn't bump lastLabelsSyncAt in $STATE_FILE — set it to $NOW by hand." >&2
  fi
fi
