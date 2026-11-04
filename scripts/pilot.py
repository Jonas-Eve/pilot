#!/usr/bin/env python3
"""PILOT's deterministic ticket mechanics (assets/docs/pilot-process.md §3-§4), as a CLI.

  pilot.py pool    <spec|dev|review|qa> [--limit N]
  pilot.py resolve <phase> <issue> [--resume]
  pilot.py claim   <phase> <issue> --mode fresh|reclaim|resume-orphaned|resume-cleared|rescope
  pilot.py set     <issue> [--status S] [--assign-me|--unassign] [--add L]... [--remove L]... [--close]
  pilot.py flag    <issue> --comment TEXT      # needs-human + the mandatory why/what's-needed comment
  pilot.py unflag  <issue> --comment TEXT      # resolution comment, then needs-human removed
  pilot.py doctor  [--verbose]                 # preflight: can the commands above work here?

Every command takes `--repo owner/repo` (default: the git remote of the current directory) and
prints one JSON object on stdout. Exit codes: 0 done / answered, 1 refused by a precondition
(JSON says why), 2 GitHub or usage failure.

Judgment never lives here: which agent to call, what a story/spec/review says, and pair
dialogue stay with the skills. Requires the `gh` CLI and Python 3.
"""
import argparse
import json
import re
import subprocess
import sys

# phase -> statuses and which §4 rules apply to an explicitly-given ticket
PHASES = {
    "spec": {"fresh": "status:backlog", "inprog": "status:in-spec", "reclaim": None,
             "gate": False, "containers": {"epic"},
             "resumable": {"status:in-spec", "status:draft"}},
    "dev": {"fresh": "status:dev-ready", "inprog": "status:in-dev",
            "reclaim": "status:changes-requested", "gate": True, "containers": {"epic", "split"},
            "resumable": {"status:in-dev"}},
    "review": {"fresh": "status:review-ready", "inprog": "status:in-review", "reclaim": None,
               "gate": False, "containers": {"epic", "split"}, "resumable": {"status:in-review"}},
    "qa": {"fresh": "status:qa", "inprog": "status:in-qa", "reclaim": None,
           "gate": True, "containers": set(), "resumable": {"status:in-qa"}},
}
STATUSES = {
    "draft", "backlog", "in-spec", "dev-ready", "in-dev", "review-ready", "in-review",
    "changes-requested", "approved", "wont-do", "split", "qa", "in-qa", "done",
}
RESCOPABLE = ("status:qa", "status:in-qa", "status:split")  # spec re-scopes these in place
REQUIRED_LABELS = (
    {"type:feature", "type:tech", "type:bug", "type:e2e", "level:epic", "level:story", "level:task",
     "priority:P0", "priority:P1", "priority:P2", "needs-human", "on-hold", "can-resume"}
    | {f"status:{name}" for name in STATUSES}
)
PRIORITY = {"priority:P0": 0, "priority:P1": 1, "priority:P2": 2}
NO_PRIORITY = 9
FLAGS = ("needs-human", "on-hold")
DEPENDS_RE = re.compile(r"Depends on #(\d+)")
BLOCKS_RE = re.compile(r"Blocks #(\d+)")
REMOTE_RE = re.compile(r"(?:github\.com[:/]|/git/)([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


class GhError(Exception):
    pass


class GhClient:
    def __init__(self, repo):
        self.repo = repo
        self._me = None

    def _run(self, path, params=None, paginate=False, method="GET", body=None):
        cmd = ["gh", "api", "-X", method, path]
        if paginate:
            cmd.append("--paginate")
        if body is not None:
            cmd += ["--input", "-"]
        for key, value in (params or {}).items():
            cmd += ["-f", f"{key}={value}"]
        proc = subprocess.run(
            cmd, input=json.dumps(body) if body is not None else None,
            capture_output=True, text=True,
        )
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
        text = self._run(f"repos/{self.repo}/issues",
                         {"state": "open", "labels": label, "per_page": 100}, paginate=True)
        return [i for i in self._decode(text) if "pull_request" not in i]

    def get_issue(self, number):
        """The raw issue (a PR carries a `pull_request` key), or None when it doesn't exist."""
        try:
            return json.loads(self._run(f"repos/{self.repo}/issues/{number}"))
        except GhError as err:
            if "404" in str(err) or "Not Found" in str(err):
                return None
            raise

    def is_open(self, number):
        """True/False, or None when the issue can't be read."""
        try:
            issue = self.get_issue(number)
        except (GhError, ValueError):
            return None
        return None if issue is None else issue.get("state") == "open"

    def comments(self, number):
        text = self._run(f"repos/{self.repo}/issues/{number}/comments",
                         {"per_page": 100}, paginate=True)
        return [c.get("body") or "" for c in self._decode(text)]

    def sub_issues(self, number):
        text = self._run(f"repos/{self.repo}/issues/{number}/sub_issues",
                         {"per_page": 100}, paginate=True)
        return self._decode(text)

    def repo_info(self):
        return json.loads(self._run(f"repos/{self.repo}"))

    def label_names(self):
        text = self._run(f"repos/{self.repo}/labels", {"per_page": 100}, paginate=True)
        return {l["name"] for l in self._decode(text)}

    def me(self):
        if self._me is None:
            self._me = json.loads(self._run("user"))["login"]
        return self._me

    def patch_issue(self, number, body):
        return json.loads(self._run(f"repos/{self.repo}/issues/{number}", method="PATCH", body=body))

    def post_comment(self, number, text):
        self._run(f"repos/{self.repo}/issues/{number}/comments", method="POST", body={"body": text})


def normalize(raw):
    return {
        "number": raw["number"],
        "title": raw.get("title", ""),
        "state": raw.get("state", "open"),
        "labels": {(l["name"] if isinstance(l, dict) else l) for l in raw.get("labels", [])},
        "assignees": [a["login"] for a in raw.get("assignees", [])],
        "body": raw.get("body") or "",
        "created_at": raw.get("created_at", ""),
        "is_pr": "pull_request" in raw,
    }


def status_of(labels):
    return next((l for l in sorted(labels) if l.startswith("status:")), "")


def priority_rank(labels):
    return min((PRIORITY[l] for l in labels if l in PRIORITY), default=NO_PRIORITY)


def public(issue, **extra):
    prio = next((l for l in sorted(issue["labels"]) if l in PRIORITY), "")
    out = {"number": issue["number"], "title": issue["title"],
           "status": status_of(issue["labels"]), "priority": prio}
    out.update(extra)
    return out


class Refused(Exception):
    """A precondition failed: the JSON payload explains, exit status 1."""

    def __init__(self, payload):
        super().__init__(payload.get("reason", "refused"))
        self.payload = payload


class Machine:
    def __init__(self, gh):
        self.gh = gh
        self._open = {}

    # ---- shared checks -------------------------------------------------------------------
    def open_state(self, number):
        if number not in self._open:
            self._open[number] = self.gh.is_open(number)
        return self._open[number]

    def blocking_dependencies(self, issue):
        """Open (or unreadable) 'Depends on #N' references in the issue body."""
        return [n for n in sorted({int(m) for m in DEPENDS_RE.findall(issue["body"])})
                if self.open_state(n) is not False]

    def blocks_open_ticket(self, issue):
        """True when a 'Blocks #M' comment on this issue points at a still-open M."""
        for body in self.gh.comments(issue["number"]):
            for m in BLOCKS_RE.findall(body):
                if self.open_state(int(m)) is True:
                    return True
        return False

    # ---- pool ----------------------------------------------------------------------------
    def pool(self, phase, limit, only=None):
        cfg = PHASES[phase]
        candidates, excluded = [], []

        def reject(issue, reason, **extra):
            excluded.append(public(issue, reason=reason, **extra))

        def consider(issue, pool):
            for flag in FLAGS:
                if flag in issue["labels"]:
                    return reject(issue, flag)
            deps = self.blocking_dependencies(issue)
            if deps:
                return reject(issue, "depends-on-open", depends_on=deps)
            candidates.append(dict(issue, pool=pool))

        def raw_issues(label):
            return [i for i in self.gh.issues_with_label(label) if only is None or i["number"] in only]

        for raw in raw_issues(cfg["fresh"]):
            issue = normalize(raw)
            if issue["assignees"]:
                reject(issue, "assigned")
            else:
                consider(issue, "fresh")
        for raw in raw_issues(cfg["inprog"]):
            issue = normalize(raw)
            if "can-resume" in issue["labels"]:
                consider(issue, "resumable")
            else:
                reject(issue, "in-progress-without-can-resume")
        if cfg["reclaim"]:
            for raw in raw_issues(cfg["reclaim"]):
                consider(normalize(raw), "reclaimable")

        candidates.sort(key=lambda c: (priority_rank(c["labels"]), c["created_at"]))
        if candidates:
            top = priority_rank(candidates[0]["labels"])
            tier = [c for c in candidates if priority_rank(c["labels"]) == top]
            for c in tier:
                c["blocks"] = self.blocks_open_ticket(c)
            tier.sort(key=lambda c: (not c["blocks"], c["created_at"]))
            candidates = tier + [c for c in candidates if priority_rank(c["labels"]) != top]

        shown = [public(c, pool=c["pool"], created_at=c["created_at"],
                        blocks_open_ticket=c.get("blocks")) for c in candidates]
        return {"pick": shown[0] if shown else None, "candidates": shown[:limit],
                "candidate_count": len(shown),
                "excluded": sorted(excluded, key=lambda e: e["number"])}

    # ---- resolve -------------------------------------------------------------------------
    def open_tree(self, number):
        """Open tickets under an Epic/split story, at most two hops (epic -> story -> task)."""
        found = []
        for child in self.gh.sub_issues(number):
            if child.get("state") != "open":
                continue
            found.append(child["number"])
            labels = normalize(child)["labels"]
            if "status:split" in labels:
                found += [g["number"] for g in self.gh.sub_issues(child["number"])
                          if g.get("state") == "open"]
        return found

    def resolve(self, phase, number, resume=False):
        cfg = PHASES[phase]
        raw = self.gh.get_issue(number)
        if raw is None:
            return {"action": "stop", "reason": "not-found", "issue": number}
        issue = normalize(raw)
        labels, status = issue["labels"], status_of(issue["labels"])
        base = {"issue": number, "status": status}
        if issue["state"] != "open":
            return {"action": "stop", "reason": "closed", **base}
        if issue["is_pr"]:
            return {"action": "manual", "reason": "pr-number", **base}
        if not resume:
            kind = ("epic" if "level:epic" in labels else
                    "split" if "level:story" in labels and status == "status:split" else None)
            if kind in cfg["containers"]:
                tree = self.open_tree(number)
                if tree:
                    found = self.pool(phase, 5, only=set(tree))
                    return {"action": "descend", "via": number, "pick": found["pick"],
                            "candidate_count": found["candidate_count"]}
                if phase == "spec" and kind == "epic":
                    return {"action": "stop", "reason": "epic-without-open-subissues", **base}
        if phase == "spec" and not resume and status in RESCOPABLE:
            return {"action": "rescope", **base}
        flags = sorted(f for f in FLAGS if f in labels)
        assigned = issue["assignees"]
        if resume:
            if status in cfg["resumable"] and assigned and not flags:
                return {"action": "resume-orphaned", **base}
            return {"action": "stop", "reason": "resume-mismatch", "flags": flags,
                    "assignees": assigned, **base}
        if flags:
            return {"action": "stop", "reason": "flagged", "flags": flags, **base}
        if status == cfg["inprog"]:
            if "can-resume" in labels:
                return {"action": "resume-cleared", **base}
            if assigned:
                return {"action": "ask-resume", "assignees": assigned, **base}
            return {"action": "stop", "reason": "in-progress-unassigned", **base}
        if cfg["reclaim"] and status == cfg["reclaim"]:
            return {"action": "reclaim", **base}
        if status == cfg["fresh"]:
            if assigned:
                return {"action": "stop", "reason": "assigned", "assignees": assigned, **base}
            if cfg["gate"]:
                deps = self.blocking_dependencies(issue)
                if deps:
                    return {"action": "stop", "reason": "depends-on-open", "depends_on": deps, **base}
            return {"action": "claim-fresh", **base}
        return {"action": "stop", "reason": "wrong-status", **base}

    # ---- preflight -----------------------------------------------------------------------
    def doctor(self):
        """Cheap checks that the other commands can work here; changes nothing.

        Cannot prove a write will be allowed (a session may restrict writes that the GitHub
        account itself could make); it checks what the account and the repo say.
        """
        checks = []

        def check(name, ok, detail=""):
            checks.append({"name": name, "ok": bool(ok), "detail": detail})
            return bool(ok)

        check("python>=3.8", sys.version_info >= (3, 8), sys.version.split()[0])
        login = None
        try:
            login = self.gh.me()
            check("github-api", True, f"authenticated as {login}")
        except (GhError, ValueError, FileNotFoundError, KeyError) as err:
            check("github-api", False, str(err) or "gh CLI not found or not authenticated")
        if login:
            try:
                info = self.gh.repo_info()
                check("repo-readable", True, info.get("full_name", ""))
                perms = info.get("permissions") or {}
                check("repo-write-permission", perms.get("push") or perms.get("admin"),
                      "the account can push (a session may still restrict writes)"
                      if perms.get("push") or perms.get("admin")
                      else "read-only access: claim/set/flag would be refused")
                missing = sorted(REQUIRED_LABELS - self.gh.label_names())
                check("pilot-labels", not missing,
                      "all present" if not missing else
                      f"{len(missing)} missing (run /pilot-update): " + ", ".join(missing[:6])
                      + ("…" if len(missing) > 6 else ""))
            except (GhError, ValueError) as err:
                check("repo-readable", False, str(err))
        failed = [c for c in checks if not c["ok"]]
        return {"ok": not failed, "login": login, "failed": failed, "checks": checks}

    # ---- writes --------------------------------------------------------------------------
    def _write(self, number, labels, assignees=None, extra=None):
        body = {"labels": sorted(labels)}
        if assignees is not None:
            body["assignees"] = assignees
        body.update(extra or {})
        return normalize(self.gh.patch_issue(number, body))

    def claim(self, phase, number, mode):
        cfg = PHASES[phase]
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"claimed": False, "reason": "not-found", "issue": number})
        issue = normalize(raw)
        labels, status = set(issue["labels"]), status_of(issue["labels"])
        me = self.gh.me()

        def refuse(reason, **extra):
            raise Refused({"claimed": False, "reason": reason, "issue": number, "status": status,
                           "assignees": issue["assignees"], **extra})

        if issue["state"] != "open":
            refuse("closed")
        new_assignees = [me]
        if mode == "fresh":
            if status != cfg["fresh"] or issue["assignees"]:
                refuse("not-claimable", expected=cfg["fresh"])
            labels = labels - {cfg["fresh"]} | {cfg["inprog"]}
        elif mode == "reclaim":
            if not cfg["reclaim"] or status != cfg["reclaim"]:
                refuse("not-claimable", expected=cfg["reclaim"])
            labels = labels - {cfg["reclaim"]} | {cfg["inprog"]}
        elif mode == "resume-orphaned":
            if status not in cfg["resumable"] or not issue["assignees"]:
                refuse("not-claimable", expected=sorted(cfg["resumable"]))
        elif mode == "resume-cleared":
            if status != cfg["inprog"] or "can-resume" not in labels:
                refuse("not-claimable", expected=cfg["inprog"] + " + can-resume")
            new_assignees = None  # already claimed: only the one-time signal is consumed
        elif mode == "rescope":
            if phase != "spec" or status not in RESCOPABLE:
                refuse("not-claimable", expected="status:qa, status:in-qa or status:split (spec only)")
            labels = {l for l in labels if not l.startswith("status:")} | {cfg["inprog"]}
        else:
            refuse("unknown-mode")
        if any(f in labels for f in FLAGS):
            refuse("flagged", flags=sorted(f for f in FLAGS if f in labels))
        labels.discard("can-resume")
        self._write(number, labels, new_assignees)
        after = normalize(self.gh.get_issue(number))
        if new_assignees is not None and after["assignees"] != new_assignees:
            raise Refused({"claimed": False, "reason": "lost-race", "issue": number,
                           "assignees": after["assignees"]})
        return {"claimed": True, "mode": mode, "issue": number, "assignee": me,
                "status": status_of(after["labels"]), "labels": sorted(after["labels"])}

    def set(self, number, status=None, assign=None, add=(), remove=(), close=False):
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        labels = set(normalize(raw)["labels"])
        if status is not None:
            name = status[len("status:"):] if status.startswith("status:") else status
            if name != "none" and name not in STATUSES:
                raise Refused({"ok": False, "reason": "unknown-status", "status": status,
                               "allowed": sorted(STATUSES)})
            labels = {l for l in labels if not l.startswith("status:")}
            if name != "none":
                labels.add(f"status:{name}")
        labels |= set(add)
        labels -= set(remove)
        assignees = [self.gh.me()] if assign == "me" else [] if assign == "none" else None
        extra = {"state": "closed", "state_reason": "completed"} if close else None
        after = self._write(number, labels, assignees, extra)
        return {"ok": True, "issue": number, "status": status_of(after["labels"]),
                "labels": sorted(after["labels"]), "assignees": after["assignees"],
                "state": after["state"]}

    def flag(self, number, comment):
        if not comment.strip():
            raise Refused({"ok": False, "reason": "comment-required"})
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        labels = normalize(raw)["labels"]
        self.gh.post_comment(number, comment)  # comment first: a flag never exists without one
        self._write(number, labels | {"needs-human"})
        return {"ok": True, "issue": number, "flagged": True}

    def unflag(self, number, comment):
        if not comment.strip():
            raise Refused({"ok": False, "reason": "comment-required"})
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        labels = normalize(raw)["labels"]
        self.gh.post_comment(number, comment)  # the resolution is always on the record first
        self._write(number, labels - {"needs-human"})
        return {"ok": True, "issue": number, "flagged": False}


def repo_from_remote(url):
    match = REMOTE_RE.search(url.strip())
    return f"{match.group(1)}/{match.group(2)}" if match else None


def resolve_repo():
    """owner/repo of the current directory, from the git remote.

    `gh repo view` is avoided: it uses GraphQL, which Claude Code sessions block.
    """
    proc = subprocess.run(["git", "config", "--get", "remote.origin.url"],
                          capture_output=True, text=True)
    repo = repo_from_remote(proc.stdout) if proc.returncode == 0 else None
    if not repo:
        raise GhError("cannot resolve the repository from remote.origin.url; pass --repo owner/repo")
    return repo


def build_parser():
    parser = argparse.ArgumentParser(prog="pilot.py", description=__doc__.split("\n")[0])
    parser.add_argument("--repo", help="owner/repo (default: git remote of the current directory)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="cmd", required=True)
    _add = sub.add_parser
    sub.add_parser = lambda *a, **k: _add(*a, parents=[common], **k)
    phases = sorted(PHASES)
    p = sub.add_parser("pool")
    p.add_argument("phase", choices=phases)
    p.add_argument("--limit", type=int, default=5)
    p = sub.add_parser("resolve")
    p.add_argument("phase", choices=phases)
    p.add_argument("issue", type=int)
    p.add_argument("--resume", action="store_true")
    p = sub.add_parser("claim")
    p.add_argument("phase", choices=phases)
    p.add_argument("issue", type=int)
    p.add_argument("--mode", required=True,
                   choices=["fresh", "reclaim", "resume-orphaned", "resume-cleared", "rescope"])
    p = sub.add_parser("set")
    p.add_argument("issue", type=int)
    p.add_argument("--status", help="a status name (e.g. review-ready) or 'none'")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--assign-me", action="store_true")
    group.add_argument("--unassign", action="store_true")
    p.add_argument("--add", action="append", default=[])
    p.add_argument("--remove", action="append", default=[])
    p.add_argument("--close", action="store_true")
    p = sub.add_parser("doctor")
    p.add_argument("--verbose", action="store_true", help="list every check, not only failures")
    for name in ("flag", "unflag"):
        p = sub.add_parser(name)
        p.add_argument("issue", type=int)
        p.add_argument("--comment", required=True)
    return parser


def run(args, gh):
    machine = Machine(gh)
    if args.cmd == "pool":
        return {"phase": args.phase, **machine.pool(args.phase, args.limit)}
    if args.cmd == "resolve":
        return machine.resolve(args.phase, args.issue, args.resume)
    if args.cmd == "claim":
        return machine.claim(args.phase, args.issue, args.mode)
    if args.cmd == "set":
        assign = "me" if args.assign_me else "none" if args.unassign else None
        return machine.set(args.issue, args.status, assign, args.add, args.remove, args.close)
    if args.cmd == "doctor":
        report = machine.doctor()
        if not args.verbose:
            report.pop("checks")
        return report
    if args.cmd == "flag":
        return machine.flag(args.issue, args.comment)
    return machine.unflag(args.issue, args.comment)


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        repo = args.repo or resolve_repo()
        result = run(args, GhClient(repo))
    except Refused as refusal:
        print(json.dumps(refusal.payload, ensure_ascii=False))
        return 1
    except (GhError, FileNotFoundError, ValueError) as err:
        print(json.dumps({"error": str(err) or "gh CLI not found"}))
        return 2
    print(json.dumps({"repo": repo, **result}, ensure_ascii=False))
    return 1 if result.get("ok") is False and args.cmd == "doctor" else 0


if __name__ == "__main__":
    sys.exit(main())
