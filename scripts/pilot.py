#!/usr/bin/env python3
"""PILOT's deterministic ticket mechanics (assets/docs/pilot-process.md §3-§4), as a CLI.

  pilot.py pool    <spec|dev|review|qa> [--limit N]
  pilot.py resolve <phase> <issue> [--resume]
  pilot.py claim   <phase> <issue> --mode fresh|reclaim|resume-orphaned|resume-cleared|rescope
  pilot.py set     <issue> [--status S] [--assign-me|--unassign] [--add L]... [--remove L]... [--close] [--pr N]
  pilot.py event   <issue>... --action NAME [--phase P]  # those tickets' current state as dashboard events, no write
  pilot.py flag    <issue> --comment TEXT      # needs-human + the mandatory why/what's-needed comment
  pilot.py unflag  <issue> --comment TEXT      # resolution comment, then needs-human removed
  pilot.py doctor  [--verbose]                 # preflight: can the commands above work here?
  pilot.py snapshot [--out FILE]               # every open ticket as the dashboard's snapshot document
  pilot.py wiki    index|show|status|lint|add|set  # the project's wiki (wiki/): entries, derived statuses, checks

Every command takes `--repo owner/repo` (default: the git remote of the current directory) and
prints one JSON object on stdout. Exit codes: 0 done / answered, 1 refused by a precondition
(JSON says why), 2 GitHub or usage failure.

claim/set/flag/unflag also return an `event` (and claim an `activity`), and `event` builds them for
tickets the skill changed itself (Discovery, one call for all of them): the ready-made payloads the skills forward to the
project's dashboard (pilot-link-dashboard.md). An event carries the ticket's parent, and the open
PR (`set --pr N`) when the caller just opened one.

Judgment never lives here: which agent to call, what a story/spec/review says, and pair
dialogue stay with the skills. Requires the `gh` CLI and Python 3.
"""
import argparse
import datetime
import json
import os
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
    "proto": {"fresh": None, "inprog": "status:poc-draft", "reclaim": None,
              "gate": False, "containers": set(), "resumable": {"status:poc-draft"}},
}
STATUSES = {
    "draft", "backlog", "in-spec", "dev-ready", "in-dev", "review-ready", "in-review",
    "changes-requested", "approved", "wont-do", "split", "qa", "in-qa", "done",
    "poc-draft", "poc-review", "poc-validated", "poc-rejected",
}
POC_OPEN = ("status:poc-draft", "status:poc-review", "status:poc-validated")  # a prototype can still be rejected
RESCOPABLE = ("status:qa", "status:in-qa", "status:split")  # spec re-scopes these in place
REQUIRED_LABELS = (
    {"type:feature", "type:tech", "type:bug", "type:e2e", "type:poc", "level:epic", "level:story", "level:task",
     "priority:P0", "priority:P1", "priority:P2", "needs-human", "on-hold", "can-resume"}
    | {f"status:{name}" for name in STATUSES}
)
PRIORITY = {"priority:P0": 0, "priority:P1": 1, "priority:P2": 2}
NO_PRIORITY = 9
FLAGS = ("needs-human", "on-hold")
DEPENDS_RE = re.compile(r"Depends on #(\d+)")
BLOCKS_RE = re.compile(r"Blocks #(\d+)")
PROTO_MAX_BYTES = 1_000_000   # one mockup, all parts together
PROTO_PART_BYTES = 200_000     # a database document is capped at 256 KiB
PROTO_FORBIDDEN = (
    (re.compile(r"https?://", re.I), "an external URL (the mockup must be self-contained)"),
    (re.compile(r"""(?:src|href|action|poster)\s*=\s*["']?\s*//""", re.I), "a protocol-relative URL"),
    (re.compile(r"@import", re.I), "@import"),
    (re.compile(r"<\s*(?:iframe|object|embed|link|base)\b", re.I), "an iframe, object, embed, link or base element"),
    (re.compile(r"<\s*meta[^>]+http-equiv\s*=\s*[\"']?refresh", re.I), "a meta refresh"),
)
REMOTE_RE = re.compile(r"(?:github\.com[:/]|/git/)([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")
WIKI_DIR = "wiki"
WIKI_STATUSES = ("proposed", "specified", "implemented", "deprecated")  # the only ones a file holds
WIKI_KEYS = ("status", "tickets", "verifiedAt", "verifiedCommit")
WIKI_HEAD_RE = re.compile(r"^##\s+(.+?)\s*\{#([a-z0-9][a-z0-9-]*)\}\s*$")
WIKI_META_RE = re.compile(r"^<!--\s*wiki:\s*(.*?)\s*-->\s*$")
WIKI_PAIR_RE = re.compile(r"(\w+)=(\S*)")
WIKI_TICKET_RE = re.compile(r"^#(\d+)$")
WIKI_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
WIKI_IN_DEV = ("status:in-dev",)
WIKI_IN_REVIEW = ("status:review-ready", "status:in-review", "status:changes-requested")
WIKI_IN_QA = ("status:qa", "status:in-qa")
WIKI_PRE_DEV = ("status:draft", "status:backlog", "status:in-spec", "status:dev-ready")


class GhError(Exception):
    pass


class GhClient:
    def __init__(self, repo):
        self.repo = repo
        self._me = None

    def _run(self, path, params=None, method="GET", body=None):
        cmd = ["gh", "api", "-X", method, path]
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

    def _pages(self, path, params=None, per_page=100, max_pages=50):
        """All items of a list endpoint. Pages are requested by number: `gh --paginate` follows
        links that use numeric repository ids, which Claude Code sessions' proxy refuses."""
        out = []
        for page in range(1, max_pages + 1):
            data = json.loads(self._run(path, {**(params or {}), "per_page": per_page, "page": page}))
            out.extend(data)
            if len(data) < per_page:
                break
        return out

    def issues_with_label(self, label):
        items = self._pages(f"repos/{self.repo}/issues", {"state": "open", "labels": label})
        return [i for i in items if "pull_request" not in i]

    def open_issues(self):
        items = self._pages(f"repos/{self.repo}/issues", {"state": "open"})
        return [i for i in items if "pull_request" not in i]

    def open_pulls(self):
        return self._pages(f"repos/{self.repo}/pulls", {"state": "open"})

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
        return [c.get("body") or "" for c in self._pages(f"repos/{self.repo}/issues/{number}/comments")]

    def sub_issues(self, number):
        return self._pages(f"repos/{self.repo}/issues/{number}/sub_issues")

    def repo_info(self):
        return json.loads(self._run(f"repos/{self.repo}"))

    def label_names(self):
        return {l["name"] for l in self._pages(f"repos/{self.repo}/labels")}

    def me(self):
        if self._me is None:
            self._me = json.loads(self._run("user"))["login"]
        return self._me

    def patch_issue(self, number, body):
        return json.loads(self._run(f"repos/{self.repo}/issues/{number}", method="PATCH", body=body))

    def post_comment(self, number, text):
        self._run(f"repos/{self.repo}/issues/{number}/comments", method="POST", body={"body": text})


CLOSES_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+#(\d+)", re.I)


def trailing_number(url):
    tail = str(url or "").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else 0


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
        "parent": trailing_number(raw.get("parent_issue_url")),
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


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


SNAPSHOT_MAX_BYTES = 240_000  # a database document holds at most 256 KiB


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
        if (phase == "proto") != ("type:poc" in labels):
            return {"action": "stop", "reason": "not-a-poc" if phase == "proto" else "poc", **base}
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

    # ---- dashboard payloads --------------------------------------------------------------
    def _event(self, issue, action, phase=None, pr=None):
        event = {"kind": "ticket", "n": issue["number"], "title": issue["title"],
                 "labels": sorted(issue["labels"]), "assignees": issue["assignees"],
                 "state": issue["state"], "action": action, "phase": phase,
                 "by": self.gh.me(), "at": now_iso()}
        if issue.get("parent"):
            event["parent"] = issue["parent"]  # lets the dashboard nest a ticket created since its snapshot
        if pr:
            event["pr"] = pr
        return event

    def events(self, numbers, action, phase=None):
        events = []
        for number in numbers:
            raw = self.gh.get_issue(number)
            if raw is None:
                raise Refused({"ok": False, "reason": "not-found", "issue": number})
            events.append(self._event(normalize(raw), action, phase))
        return {"ok": True, "issues": list(numbers), "events": events}

    def snapshot(self):
        """Every open ticket as the dashboard's `snapshots/<owner>__<repo>` document."""
        rows, prs = [], {}
        for pr in self.gh.open_pulls():  # the open PR that closes a ticket: `Closes #<issue>` in its body
            for num in CLOSES_RE.findall(pr.get("body") or ""):
                prs[int(num)] = max(prs.get(int(num), 0), pr["number"])
        for raw in self.gh.open_issues():
            t = normalize(raw)
            row = {"n": t["number"], "t": t["title"], "l": sorted(t["labels"]),
                   "u": raw.get("updated_at", "")}
            if t["assignees"]:
                row["a"] = t["assignees"][0]
            if t["number"] in prs:
                row["r"] = prs[t["number"]]
            parent = str(raw.get("parent_issue_url") or "").rsplit("/", 1)[-1]
            if parent.isdigit():
                row["p"] = int(parent)  # parent issue number: lets the dashboard nest sub-issues
            summary = raw.get("sub_issues_summary") or {}
            if summary.get("total"):
                row["k"] = [summary.get("completed", 0), summary["total"]]  # sub-issues done / total
            rows.append(row)
        rows.sort(key=lambda r: r["u"], reverse=True)
        doc = {"repo": self.gh.repo, "at": now_iso(), "source": "pilot.py", "total": len(rows),
               "truncated": False, "issues": rows}
        while len(json.dumps(doc, ensure_ascii=False).encode()) > SNAPSHOT_MAX_BYTES and rows:
            del rows[max(1, len(rows) * 9 // 10):]
            doc["truncated"] = True
        return doc

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
                "status": status_of(after["labels"]), "labels": sorted(after["labels"]),
                "event": self._event(after, "claim:" + mode, phase),
                "activity": {"kind": "activity", "id": f"{phase}-{number}-{int(datetime.datetime.now().timestamp())}",
                             "phase": phase, "n": number, "title": after["title"], "mode": mode,
                             "by": me, "startedAt": now_iso()}}

    def set(self, number, status=None, assign=None, add=(), remove=(), close=False, pr=None):
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
                "state": after["state"], "event": self._event(after, "set", pr=pr)}

    def proto(self, number, verdict, reason=None):
        """accept / reject a prototype, or check it is accepted before a Discovery starts from it."""
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        issue = normalize(raw)
        labels, status = set(issue["labels"]), status_of(issue["labels"])

        def refuse(why, **extra):
            raise Refused({"ok": False, "reason": why, "issue": number, "status": status, **extra})

        if issue["state"] != "open":
            refuse("closed")
        if issue["is_pr"] or "type:poc" not in labels:
            refuse("not-a-poc")
        flags = sorted(f for f in FLAGS if f in labels)
        if flags:
            refuse("flagged", flags=flags)
        if verdict == "from-proto":
            if status != "status:poc-validated":
                refuse("not-accepted", expected="status:poc-validated")
            return {"ok": True, "verdict": verdict, "issue": number, "status": status, "title": issue["title"]}
        if verdict == "accept":
            if status == "status:poc-validated":
                return {"ok": True, "changed": False, "verdict": verdict, "issue": number, "status": status}
            if status != "status:poc-review":
                refuse("not-reviewable", expected="status:poc-review")
            after = self._write(number, labels - {"status:poc-review"} | {"status:poc-validated"})
            return {"ok": True, "changed": True, "verdict": verdict, "issue": number,
                    "status": status_of(after["labels"]), "event": self._event(after, "accept", "proto")}
        if status not in POC_OPEN:
            refuse("not-rejectable", expected=list(POC_OPEN))
        if not (reason or "").strip():
            raise Refused({"ok": False, "reason": "reason-required"})
        self.gh.post_comment(number, reason)  # the reason is on the record before anything changes
        labels = {l for l in labels if not l.startswith("status:")} - {"can-resume"} | {"status:poc-rejected"}
        after = self._write(number, labels, [], {"state": "closed", "state_reason": "not_planned"})
        return {"ok": True, "changed": True, "verdict": "reject", "issue": number,
                "status": status_of(after["labels"]), "state": after["state"],
                "event": self._event(after, "reject", "proto")}

    def proto_pack(self, number, html_path, out_dir, brief=None, height=None):
        """Check a prototype's mockup and write the cockpit documents for it: proto-<n>.json (the
        metadata, `protos/p<n>`) and protoHtml-<n>-<k>.json (the parts, `protoHtml/<n>-<k>`)."""
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        issue = normalize(raw)
        if "type:poc" not in issue["labels"]:
            raise Refused({"ok": False, "reason": "not-a-poc", "issue": number})
        with open(html_path, encoding="utf-8") as handle:
            html = handle.read()
        size = len(html.encode("utf-8"))
        problems = []
        if not html.strip():
            problems.append("the mockup is empty")
        if size > PROTO_MAX_BYTES:
            problems.append(f"the mockup is {size} bytes, the limit is {PROTO_MAX_BYTES}")
        scan = re.sub(r'xmlns(?::\w+)?\s*=\s*"[^"]*"', "", html)  # an XML namespace is not a resource
        for pattern, label in PROTO_FORBIDDEN:
            if pattern.search(scan):
                problems.append("it contains " + label)
        if problems:
            raise Refused({"ok": False, "reason": "invalid-mockup", "issue": number, "problems": problems})
        parts, current, used = [], [], 0
        for char in html:
            width = len(char.encode("utf-8"))
            if used + width > PROTO_PART_BYTES:
                parts.append("".join(current))
                current, used = [], 0
            current.append(char)
            used += width
        parts.append("".join(current))
        os.makedirs(out_dir, exist_ok=True)
        files = []
        meta = {"kind": "proto", "n": number, "repo": self.gh.repo, "title": issue["title"],
                "brief": (brief or "").strip()[:600], "parts": len(parts), "bytes": size, "at": now_iso()}
        if height:
            meta["height"] = max(200, min(900, int(height)))
        docs = [(f"proto-{number}.json", meta)]
        docs += [(f"protoHtml-{number}-{k}.json", {"n": number, "k": k, "html": text}) for k, text in enumerate(parts)]
        for name, doc in docs:
            path = os.path.join(out_dir, name)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(doc, handle, ensure_ascii=False, separators=(",", ":"))
            files.append(path)
        return {"ok": True, "issue": number, "parts": len(parts), "bytes": size, "files": files}

    def flag(self, number, comment):
        if not comment.strip():
            raise Refused({"ok": False, "reason": "comment-required"})
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        labels = normalize(raw)["labels"]
        self.gh.post_comment(number, comment)  # comment first: a flag never exists without one
        after = self._write(number, labels | {"needs-human"})
        return {"ok": True, "issue": number, "flagged": True, "event": self._event(after, "flag")}

    def unflag(self, number, comment):
        if not comment.strip():
            raise Refused({"ok": False, "reason": "comment-required"})
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        labels = normalize(raw)["labels"]
        self.gh.post_comment(number, comment)  # the resolution is always on the record first
        after = self._write(number, labels - {"needs-human"})
        return {"ok": True, "issue": number, "flagged": False, "event": self._event(after, "unflag")}


class Wiki:
    """The project's wiki: markdown files under `wiki/`, each entry a `## Title {#id}` heading followed
    by one machine-readable line `<!-- wiki: status=... tickets=#1,#2 verifiedAt=... verifiedCommit=... -->`.
    This class is the only writer of that line. Status names a file may hold are WIKI_STATUSES; the
    in-flight ones (in-dev, in-review, in-qa, verified) are derived from ticket labels, never written."""

    def __init__(self, root=WIKI_DIR):
        self.root = root

    def _files(self):
        if not os.path.isdir(self.root):
            raise Refused({"ok": False, "reason": "wiki-absent", "dir": self.root,
                           "hint": "run /pilot-wiki --init"})
        found = []
        for base, _dirs, names in os.walk(self.root):
            found.extend(os.path.join(base, n) for n in names if n.endswith(".md"))
        return sorted(found)

    def _page(self, path):
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    @staticmethod
    def _meta(text):
        pairs = dict(WIKI_PAIR_RE.findall(text))
        problems = [("unknown-key", f"unknown key {k!r}") for k in pairs if k not in WIKI_KEYS]
        tickets, bad = [], []
        for raw in filter(None, pairs.get("tickets", "").split(",")):
            match = WIKI_TICKET_RE.match(raw)
            (tickets if match else bad).append(int(match.group(1)) if match else raw)
        if bad:
            problems.append(("bad-tickets", "tickets must read #N,#M (got %s)" % ", ".join(bad)))
        status = pairs.get("status", "")
        if not status:
            problems.append(("missing-status", "no status"))
        elif status not in WIKI_STATUSES:
            problems.append(("bad-status", f"status {status!r} is not one of {', '.join(WIKI_STATUSES)}"
                             + (" (derived, never written)" if status in ("in-dev", "in-review", "in-qa", "verified") else "")))
        stamp_at, stamp_commit = pairs.get("verifiedAt", ""), pairs.get("verifiedCommit", "")
        if bool(stamp_at) != bool(stamp_commit):
            problems.append(("partial-stamp", "verifiedAt and verifiedCommit go together"))
        return {"status": status, "tickets": tickets, "verifiedAt": stamp_at,
                "verifiedCommit": stamp_commit, "problems": problems}

    @staticmethod
    def _line(status, tickets, verified_at="", verified_commit=""):
        return "<!-- wiki: status=%s tickets=%s verifiedAt=%s verifiedCommit=%s -->" % (
            status, ",".join(f"#{n}" for n in tickets), verified_at, verified_commit)

    def parse(self):
        """(entries, problems): every entry of every page, and the meta lines no heading owns."""
        entries, stray = [], []
        for path in self._files():
            with open(path, encoding="utf-8") as handle:
                lines = handle.read().split("\n")
            page, fenced, owned, metas, open_entry = self._page(path), False, set(), [], None
            for number, line in enumerate(lines):
                if line.lstrip().startswith(("```", "~~~")):
                    fenced = not fenced
                    continue
                if fenced:
                    continue
                if WIKI_META_RE.match(line):
                    metas.append(number)
                if line.startswith("## "):
                    if open_entry:
                        open_entry["end"] = number
                        open_entry = None
                    head = WIKI_HEAD_RE.match(line)
                    if not head:
                        continue
                    entry = {"id": head.group(2), "title": head.group(1), "page": page, "path": path,
                             "line": number + 1, "head": number, "meta_at": None, "end": len(lines)}
                    follower = lines[number + 1] if number + 1 < len(lines) else ""
                    found = WIKI_META_RE.match(follower)
                    if found:
                        entry["meta_at"] = number + 1
                        owned.add(number + 1)
                        entry.update(self._meta(found.group(1)))
                    else:
                        entry.update({"status": "", "tickets": [], "verifiedAt": "", "verifiedCommit": "",
                                      "problems": [("missing-meta", "the line after the heading is not a <!-- wiki: ... --> line")]})
                    entry["lines"] = lines
                    entries.append(entry)
                    open_entry = entry
            stray += [{"page": page, "line": n + 1} for n in metas if n not in owned]
        return entries, stray

    @staticmethod
    def _view(entry):
        return {"id": entry["id"], "title": entry["title"], "page": entry["page"], "line": entry["line"],
                "status": entry["status"], "tickets": entry["tickets"],
                "verifiedAt": entry["verifiedAt"], "verifiedCommit": entry["verifiedCommit"]}

    def _find(self, entry_id):
        entries, _ = self.parse()
        found = [e for e in entries if e["id"] == entry_id]
        if not found:
            raise Refused({"ok": False, "reason": "entry-not-found", "id": entry_id})
        if len(found) > 1:
            raise Refused({"ok": False, "reason": "duplicate-id", "id": entry_id,
                           "pages": sorted(e["page"] for e in found)})
        return found[0]

    def index(self, ticket=None):
        entries, stray = self.parse()
        shown = [e for e in entries if ticket is None or ticket in e["tickets"]]
        return {"ok": True, "dir": self.root, "entries": [self._view(e) for e in shown],
                "problems": sum(len(e["problems"]) for e in entries) + len(stray)}

    def derive(self, entry, gh, cache):
        """The in-flight overlay of one entry, from its tickets: the most advanced of in-dev < in-review <
        in-qa among its open tickets, or `verified` for an implemented entry whose feature story is done."""
        seen, rank, verified = [], 0, False
        for number in entry["tickets"]:
            if number not in cache:
                cache[number] = gh.get_issue(number)
            raw = cache[number]
            if raw is None:
                seen.append({"number": number, "missing": True})
                continue
            ticket = normalize(raw)
            status = status_of(ticket["labels"])
            seen.append({"number": number, "state": ticket["state"], "status": status})
            if ticket["state"] == "open":
                for level, group in ((1, WIKI_IN_DEV), (2, WIKI_IN_REVIEW), (3, WIKI_IN_QA)):
                    if status in group:
                        rank = max(rank, level)
            elif {"type:feature", "level:story", "status:done"} <= ticket["labels"]:
                verified = True
        overlay = ("", "in-dev", "in-review", "in-qa")[rank]
        if not overlay and verified and entry["status"] == "implemented":
            overlay = "verified"
        shown = entry["status"] + (f" · {overlay}" if overlay else "")
        return {"id": entry["id"], "status": entry["status"], "derived": overlay, "display": shown,
                "tickets": seen}

    def status(self, gh, ids=()):
        entries, _ = self.parse()
        wanted = [e for e in entries if not ids or e["id"] in ids]
        missing = sorted(set(ids) - {e["id"] for e in wanted})
        if missing:
            raise Refused({"ok": False, "reason": "entry-not-found", "id": missing[0]})
        cache = {}
        return {"ok": True, "entries": [self.derive(e, gh, cache) for e in wanted]}

    def show(self, entry_id, gh):
        entry = self._find(entry_id)
        text = "\n".join(entry["lines"][entry["head"]:entry["end"]]).rstrip("\n")
        return {"ok": True, **self._view(entry), "text": text, "derived": self.derive(entry, gh, {})}

    def lint(self, gh):
        """The mechanical checks (no judgment): an unreadable entry, a duplicate id, a promise whose
        tickets are all closed, an implemented entry whose ticket went back before dev."""
        entries, stray = self.parse()
        findings = [{"page": s["page"], "line": s["line"], "code": "orphan-meta",
                     "message": "a <!-- wiki: ... --> line with no entry heading above it"} for s in stray]
        seen = {}
        for e in entries:
            seen.setdefault(e["id"], []).append(e)
        cache = {}
        for e in entries:
            where = {"entry": e["id"], "page": e["page"], "line": e["line"]}
            findings += [{**where, "code": c, "message": m} for c, m in e["problems"]]
            if len(seen[e["id"]]) > 1:
                findings.append({**where, "code": "duplicate-id", "message": "this id is used by %d entries" % len(seen[e["id"]])})
            if e["status"] in ("proposed", "specified") and not e["tickets"]:
                findings.append({**where, "code": "no-ticket", "message": f"a {e['status']} entry lists no ticket"})
            if e["status"] not in ("proposed", "specified", "implemented"):
                continue
            states = []
            for number in e["tickets"]:
                if number not in cache:
                    cache[number] = gh.get_issue(number)
                raw = cache[number]
                if raw is None:
                    findings.append({**where, "code": "unknown-ticket", "message": f"#{number} does not exist"})
                    continue
                ticket = normalize(raw)
                states.append((number, ticket))
            if e["status"] in ("proposed", "specified") and states and all(t["state"] == "closed" for _n, t in states):
                findings.append({**where, "code": "orphaned-promise",
                                 "message": "every ticket is closed but the entry is still " + e["status"]})
            if e["status"] == "implemented":
                for number, t in states:
                    if t["state"] == "open" and status_of(t["labels"]) in WIKI_PRE_DEV:
                        findings.append({**where, "code": "implemented-but-reopened",
                                         "message": f"#{number} is back at {status_of(t['labels'])}"})
        return {"ok": not findings, "entries": len(entries), "findings": findings}

    def _write(self, entry, replacement):
        lines = entry["lines"]
        lines[entry["meta_at"]] = replacement
        tmp = entry["path"] + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
        os.replace(tmp, entry["path"])

    def set(self, entry_id, status=None, add=(), remove=(), stamp=None):
        """The only writer of an entry's meta line. `stamp` is the commit lint verified the entry against."""
        entry = self._find(entry_id)
        if entry["meta_at"] is None:
            raise Refused({"ok": False, "reason": "no-meta-line", "id": entry_id})
        if status is not None and status not in WIKI_STATUSES:
            raise Refused({"ok": False, "reason": "bad-status", "expected": list(WIKI_STATUSES),
                           "hint": "in-dev, in-review, in-qa and verified are derived, never written"})
        tickets = [n for n in entry["tickets"] if n not in set(remove)]
        tickets += [n for n in add if n not in tickets]
        at, commit = entry["verifiedAt"], entry["verifiedCommit"]
        if stamp:
            at, commit = now_iso(), stamp
        line = self._line(status or entry["status"], tickets, at, commit)
        self._write(entry, line)
        return {"ok": True, "id": entry_id, "status": status or entry["status"], "tickets": tickets,
                "verifiedAt": at, "verifiedCommit": commit}

    def add(self, page, entry_id, title, status, tickets=(), body=""):
        """Append an entry (heading + meta line + body) to a page, creating the page if needed."""
        if not WIKI_ID_RE.match(entry_id):
            raise Refused({"ok": False, "reason": "bad-id", "id": entry_id,
                           "hint": "lowercase letters, digits and dashes"})
        if status not in WIKI_STATUSES:
            raise Refused({"ok": False, "reason": "bad-status", "expected": list(WIKI_STATUSES)})
        if not page.endswith(".md") or os.path.isabs(page) or ".." in page.split("/"):
            raise Refused({"ok": False, "reason": "bad-page", "page": page})
        os.makedirs(self.root, exist_ok=True)
        entries, _ = self.parse()
        if any(e["id"] == entry_id for e in entries):
            raise Refused({"ok": False, "reason": "duplicate-id", "id": entry_id})
        path = os.path.join(self.root, *page.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        current = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as handle:
                current = handle.read()
        else:
            current = "# " + os.path.splitext(os.path.basename(page))[0].replace("-", " ").title() + "\n"
        block = f"## {title.strip()} {{#{entry_id}}}\n{self._line(status, list(tickets))}\n"
        if body.strip():
            block += "\n" + body.strip() + "\n"
        text = current.rstrip("\n") + "\n\n" + block
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return {"ok": True, "id": entry_id, "page": page.replace(os.sep, "/"), "status": status}


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
    p.add_argument("phase", choices=[x for x in phases if x != "proto"])
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
    p.add_argument("--pr", type=int, help="the open PR that closes this ticket, forwarded in the event")
    p = sub.add_parser("proto")
    p.add_argument("issue", type=int)
    p.add_argument("verdict", choices=["accept", "reject", "from-proto"])
    p.add_argument("--reason", help="why a prototype is rejected (required by reject)")
    p = sub.add_parser("proto-pack")
    p.add_argument("issue", type=int)
    p.add_argument("--html", required=True, help="the mockup, one self-contained HTML file")
    p.add_argument("--out", required=True, help="directory for the documents to write to the cockpit")
    p.add_argument("--brief")
    p.add_argument("--height", type=int)
    p = sub.add_parser("event")
    p.add_argument("issues", type=int, nargs="+")
    p.add_argument("--action", required=True, help="what happened, e.g. created or approved")
    p.add_argument("--phase", help="e.g. discovery")
    p = sub.add_parser("snapshot")
    p.add_argument("--out", help="write the document to this file and print only a summary")
    p = sub.add_parser("doctor")
    p.add_argument("--verbose", action="store_true", help="list every check, not only failures")
    p = sub.add_parser("wiki")
    p.add_argument("--dir", default=WIKI_DIR, help="the wiki directory (default: wiki)")
    ws = p.add_subparsers(dest="wiki_cmd", required=True)
    w = ws.add_parser("index", help="every entry: id, page, status, tickets, stamp (no GitHub call)")
    w.add_argument("--ticket", type=int, help="only the entries that list this ticket")
    w = ws.add_parser("show", parents=[common], help="one entry's text, meta line and derived status")
    w.add_argument("id")
    w = ws.add_parser("status", parents=[common], help="the derived (in-flight) status of entries, from their tickets")
    w.add_argument("ids", nargs="*")
    ws.add_parser("lint", parents=[common], help="mechanical checks, no judgment")
    w = ws.add_parser("add", help="append an entry (heading + meta line + body) to a page")
    w.add_argument("page", help="path under the wiki directory, e.g. features/search.md")
    w.add_argument("id")
    w.add_argument("--title", required=True)
    w.add_argument("--status", required=True, choices=list(WIKI_STATUSES))
    w.add_argument("--ticket", type=int, action="append", default=[])
    w.add_argument("--body", default="")
    w = ws.add_parser("set", help="rewrite an entry's meta line (the only writer of it)")
    w.add_argument("id")
    w.add_argument("--status", choices=list(WIKI_STATUSES))
    w.add_argument("--add-ticket", type=int, action="append", default=[])
    w.add_argument("--remove-ticket", type=int, action="append", default=[])
    w.add_argument("--stamp", metavar="COMMIT", help="verifiedAt = now, verifiedCommit = COMMIT")
    for name in ("flag", "unflag"):
        p = sub.add_parser(name)
        p.add_argument("issue", type=int)
        p.add_argument("--comment", required=True)
    return parser


def run_wiki(args, gh):
    wiki = Wiki(args.dir)
    if args.wiki_cmd == "index":
        return wiki.index(args.ticket)
    if args.wiki_cmd == "show":
        return wiki.show(args.id, gh)
    if args.wiki_cmd == "status":
        return wiki.status(gh, args.ids)
    if args.wiki_cmd == "lint":
        return wiki.lint(gh)
    if args.wiki_cmd == "add":
        return wiki.add(args.page, args.id, args.title, args.status, args.ticket, args.body)
    return wiki.set(args.id, args.status, args.add_ticket, args.remove_ticket, args.stamp)


def needs_github(args):
    return args.cmd != "wiki" or args.wiki_cmd in ("show", "status", "lint")


def run(args, gh):
    if args.cmd == "wiki":
        return run_wiki(args, gh)
    machine = Machine(gh)
    if args.cmd == "pool":
        return {"phase": args.phase, **machine.pool(args.phase, args.limit)}
    if args.cmd == "resolve":
        return machine.resolve(args.phase, args.issue, args.resume)
    if args.cmd == "claim":
        return machine.claim(args.phase, args.issue, args.mode)
    if args.cmd == "set":
        assign = "me" if args.assign_me else "none" if args.unassign else None
        return machine.set(args.issue, args.status, assign, args.add, args.remove, args.close, args.pr)
    if args.cmd == "proto":
        return machine.proto(args.issue, args.verdict, args.reason)
    if args.cmd == "proto-pack":
        return machine.proto_pack(args.issue, args.html, args.out, args.brief, args.height)
    if args.cmd == "event":
        return machine.events(args.issues, args.action, args.phase)
    if args.cmd == "snapshot":
        doc = machine.snapshot()
        if not args.out:
            return doc
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(doc, handle, ensure_ascii=False, separators=(",", ":"))
        return {"ok": True, "file": args.out, "total": doc["total"], "truncated": doc["truncated"]}
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
        repo = (args.repo or resolve_repo()) if needs_github(args) else None
        result = run(args, GhClient(repo) if repo else None)
    except Refused as refusal:
        print(json.dumps(refusal.payload, ensure_ascii=False))
        return 1
    except (GhError, FileNotFoundError, ValueError) as err:
        print(json.dumps({"error": str(err) or "gh CLI not found"}))
        return 2
    print(json.dumps({"repo": repo, **result} if repo else result, ensure_ascii=False))
    return 1 if result.get("ok") is False and args.cmd in ("doctor", "wiki") else 0


if __name__ == "__main__":
    sys.exit(main())
