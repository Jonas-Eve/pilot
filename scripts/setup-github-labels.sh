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
  "type:bug|D93F0B|PILOT: defect in already-shipped code, formalized/originated by the architect"
  "type:epic|5319E7|PILOT: groups several type:feature/type:tech/type:bug stories by theme; never scoped/spec'd/built itself"
  "type:e2e|FBCA04|PILOT: secondary label on a sub-ticket, alongside its inherited type:; routes phase 4 to pilot-e2e"
  "priority:P0|B60205|PILOT: highest priority, set by the architect during phase 2"
  "priority:P1|D93F0B|PILOT: medium priority, set by the architect during phase 2"
  "priority:P2|FBCA04|PILOT: lowest priority, set by the architect during phase 2"
  "status:draft|C5DEF5|PILOT: phase 1 has created the ticket, awaiting final human approval in pair mode"
  "status:backlog|BFD4F2|PILOT: ticket exists, phase 2 hasn't started"
  "status:scoping|C5DEF5|PILOT: architect has claimed it for phase 2"
  "status:spec-ready|BFD4F2|PILOT: scoped, not split, ready for phase 3"
  "status:in-spec|C5DEF5|PILOT: tech lead has claimed it for phase 3"
  "status:dev-ready|BFD4F2|PILOT: spec written, ready for phase 4"
  "status:in-dev|C5DEF5|PILOT: a dev has claimed it for phase 4"
  "status:in-review|FEF2C0|PILOT: a PR is open, phase 5 is running or about to"
  "status:changes-requested|F9D0C4|PILOT: phase 5 found at least one blocking, code-level point"
  "status:approved|0E8A16|PILOT: phase 5 ran, every reviewer approved, ready to merge"
  "status:wont-do|E4E669|PILOT: architect concluded during phase 2 this ticket shouldn't be built"
  "status:split|D4C5F9|PILOT: split into sub-tickets (mandatory for type:feature, a size judgment for type:tech/type:bug); tracks its own sub-tickets"
  "status:qa|FBCA04|PILOT: type:feature story whose sub-tickets are all done; ready for phase 6 human QA"
  "status:in-qa|C5DEF5|PILOT: pilot-qa has claimed it for phase 6"
  "status:done|0E8A16|PILOT: merged, completed by cascade from a status:split parent's sub-tickets, or confirmed by phase 6 human QA"
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
