#!/usr/bin/env python3
"""Read-only candidate selection for a PILOT phase (assets/docs/pilot-process.md §4
"Picking the next ticket when none is specified" and "Blocked-by dependencies").

Usage:
  scripts/pilot-pool.py <spec|dev|review|qa> [--repo owner/repo] [--limit N]

Prints one JSON object on stdout:
  {"phase", "repo", "pick": <candidate|null>, "candidates": [...], "excluded": [...]}

Never writes to GitHub: claiming and label changes stay with the calling skill.
Requires the `gh` CLI (same prerequisite as scripts/setup-github-labels.sh) and Python 3.
Exit codes: 0 ok (pick may be null), 2 GitHub/gh failure (JSON error on stdout).
"""
import argparse
import json
import re
import subprocess
import sys

# phase -> (fresh status, in-progress status, reclaim status or None)
PHASES = {
    "spec": ("status:backlog", "status:in-spec", None),
    "dev": ("status:dev-ready", "status:in-dev", "status:changes-requested"),
    "review": ("status:review-ready", "status:in-review", None),
    "qa": ("status:qa", "status:in-qa", None),
}
PRIORITY = {"priority:P0": 0, "priority:P1": 1, "priority:P2": 2}
NO_PRIORITY = 9
DEPENDS_RE = re.compile(r"Depends on #(\d+)")
BLOCKS_RE = re.compile(r"Blocks #(\d+)")


class GhError(Exception):
    pass


class GhClient:
    def __init__(self, repo):
        self.repo = repo

    def _run(self, path, params=None, paginate=False):
        cmd = ["gh", "api", "-X", "GET", path]
        if paginate:
            cmd.append("--paginate")
        for key, value in (params or {}).items():
            cmd += ["-f", f"{key}={value}"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise GhError((proc.stderr or proc.stdout).strip())
        return proc.stdout

    @staticmethod
    def _decode(text):
        """`gh api --paginate` prints one JSON array per page, back to back."""
        decoder, pos, out = json.JSONDecoder(), 0, []
        while pos < len(text):
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if pos >= len(text):
                break
            value, pos = decoder.raw_decode(text, pos)
            out.extend(value) if isinstance(value, list) else out.append(value)
        return out

    def issues_with_label(self, label):
        text = self._run(
            f"repos/{self.repo}/issues",
            {"state": "open", "labels": label, "per_page": 100},
            paginate=True,
        )
        return [i for i in self._decode(text) if "pull_request" not in i]

    def is_open(self, number):
        """True/False, or None when the issue can't be read."""
        try:
            data = json.loads(self._run(f"repos/{self.repo}/issues/{number}"))
        except (GhError, ValueError):
            return None
        return data.get("state") == "open"

    def comments(self, number):
        text = self._run(
            f"repos/{self.repo}/issues/{number}/comments", {"per_page": 100}, paginate=True
        )
        return [c.get("body") or "" for c in self._decode(text)]


def normalize(raw):
    return {
        "number": raw["number"],
        "title": raw.get("title", ""),
        "labels": {(l["name"] if isinstance(l, dict) else l) for l in raw.get("labels", [])},
        "assignees": [a["login"] for a in raw.get("assignees", [])],
        "body": raw.get("body") or "",
        "created_at": raw.get("created_at", ""),
    }


def priority_rank(labels):
    return min((PRIORITY[l] for l in labels if l in PRIORITY), default=NO_PRIORITY)


def public(issue, **extra):
    status = next((l for l in sorted(issue["labels"]) if l.startswith("status:")), "")
    prio = next((l for l in sorted(issue["labels"]) if l in PRIORITY), "")
    out = {"number": issue["number"], "title": issue["title"], "status": status, "priority": prio}
    out.update(extra)
    return out


class Select:
    def __init__(self, gh):
        self.gh = gh
        self._open = {}

    def open_state(self, number):
        if number not in self._open:
            self._open[number] = self.gh.is_open(number)
        return self._open[number]

    def blocking_dependencies(self, issue):
        """Open (or unreadable) 'Depends on #N' references in the issue body."""
        blocked = []
        for n in sorted({int(m) for m in DEPENDS_RE.findall(issue["body"])}):
            if self.open_state(n) is not False:
                blocked.append(n)
        return blocked

    def blocks_open_ticket(self, issue):
        """True when a 'Blocks #M' comment on this issue points at a still-open M."""
        for body in self.gh.comments(issue["number"]):
            for m in BLOCKS_RE.findall(body):
                if self.open_state(int(m)) is True:
                    return True
        return False

    def run(self, phase, limit):
        fresh, in_progress, reclaim = PHASES[phase]
        candidates, excluded = [], []

        def reject(issue, reason, **extra):
            excluded.append(public(issue, reason=reason, **extra))

        def consider(issue, pool):
            for flag in ("needs-human", "on-hold"):
                if flag in issue["labels"]:
                    return reject(issue, flag)
            deps = self.blocking_dependencies(issue)
            if deps:
                return reject(issue, "depends-on-open", depends_on=deps)
            candidates.append(dict(issue, pool=pool))

        for raw in self.gh.issues_with_label(fresh):
            issue = normalize(raw)
            if issue["assignees"]:
                reject(issue, "assigned")
            else:
                consider(issue, "fresh")
        for raw in self.gh.issues_with_label(in_progress):
            issue = normalize(raw)
            if "can-resume" in issue["labels"]:
                consider(issue, "resumable")
            else:
                reject(issue, "in-progress-without-can-resume")
        if reclaim:
            for raw in self.gh.issues_with_label(reclaim):
                consider(normalize(raw), "reclaimable")

        candidates.sort(key=lambda c: (priority_rank(c["labels"]), c["created_at"]))
        if candidates:
            top = priority_rank(candidates[0]["labels"])
            tier = [c for c in candidates if priority_rank(c["labels"]) == top]
            for c in tier:
                c["blocks"] = self.blocks_open_ticket(c)
            tier.sort(key=lambda c: (not c["blocks"], c["created_at"]))
            candidates = tier + [c for c in candidates if priority_rank(c["labels"]) != top]

        shown = [
            public(c, pool=c["pool"], created_at=c["created_at"], blocks_open_ticket=c.get("blocks"))
            for c in candidates
        ]
        return {
            "pick": shown[0] if shown else None,
            "candidates": shown[:limit],
            "candidate_count": len(shown),
            "excluded": sorted(excluded, key=lambda e: e["number"]),
        }


REMOTE_RE = re.compile(r"(?:github\.com[:/]|/git/)([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def repo_from_remote(url):
    match = REMOTE_RE.search(url.strip())
    return f"{match.group(1)}/{match.group(2)}" if match else None


def resolve_repo():
    """owner/repo of the current directory, from the git remote.

    `gh repo view` is avoided: it uses GraphQL, which Claude Code sessions block.
    """
    proc = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True
    )
    repo = repo_from_remote(proc.stdout) if proc.returncode == 0 else None
    if not repo:
        raise GhError("cannot resolve the repository from remote.origin.url; pass --repo owner/repo")
    return repo


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("phase", choices=sorted(PHASES))
    parser.add_argument("--repo", help="owner/repo (default: repo of the current directory)")
    parser.add_argument("--limit", type=int, default=5, help="max candidates listed (default 5)")
    args = parser.parse_args(argv)
    try:
        repo = args.repo or resolve_repo()
        result = Select(GhClient(repo)).run(args.phase, args.limit)
    except (GhError, FileNotFoundError) as err:
        print(json.dumps({"phase": args.phase, "error": str(err) or "gh CLI not found"}))
        return 2
    print(json.dumps({"phase": args.phase, "repo": repo, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
