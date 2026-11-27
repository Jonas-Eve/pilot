#!/usr/bin/env python3
"""PILOT's deterministic ticket mechanics (assets/docs/pilot-process.md §3-§4), as a CLI.

  pilot.py pool    <spec|dev|review|qa> [--limit N]
  pilot.py resolve <phase> <issue> [--resume]
  pilot.py claim   <phase> <issue> --mode fresh|reclaim|resume-orphaned|resume-cleared|rescope
  pilot.py set     <issue> [--status S] [--assign-me|--unassign] [--add L]... [--remove L]... [--close] [--pr N]
  pilot.py event   <issue>... --action NAME [--phase P]  # those tickets' current state as dashboard events, no write
  pilot.py flag    <issue> --comment TEXT      # needs-human + the mandatory why/what's-needed comment
  pilot.py unflag  <issue> --comment TEXT      # resolution comment, then needs-human removed
  pilot.py doctor  [--verbose] [--no-wiki]      # preflight: can the commands above work here? (+ wiki/, when that module is on)
  pilot.py contract [PHASE] [--profile P]      # a phase's contract (statuses it consumes / claims / produces); bare: all, and whether they compose
  pilot.py module  list|enable|disable [NAME] [--with-requires]  # the optional modules of .pilot/state.json
  pilot.py workflow show|check|set [PROFILE]   # the project's workflow profile: the chain it runs, and the check that every profile composes
  pilot.py snapshot [--out FILE]               # every open ticket as the dashboard's snapshot document, with each ticket's stage history (`h`) and `needs-human` start (`nh`), one label-events call per ticket; with `--out` the summary also gives `history_failed`
  pilot.py wiki    index [--under D] [--depth 1]|search|describe|reindex|show|status|lint|snapshot|add|set|remove|migrate  # the project's wiki (wiki/, an OKF bundle)
  pilot.py flow    doc --in FILE [--out FILE]   # the dashboard's `flowRuns` document of a run of a user flow (no GitHub)
  pilot.py arch    index [--active] [--app A] [--under D] [--depth 1]|search|describe|next-number|inventory|reindex|show|lint|snapshot|add|set|remove|supersede  # the architecture bundle (architecture/: overview, guidelines, ADR; no GitHub)

Every command takes `--repo owner/repo` (default: the git remote of the current directory) and
prints one JSON object on stdout. Exit codes: 0 done / answered, 1 refused by a precondition
(JSON says why), 2 GitHub or usage failure.

claim/set/flag/unflag also return an `event`, and `event` builds it for
tickets the skill changed itself (Discovery, one call for all of them): the ready-made payloads the skills forward to the
project's dashboard (pilot-link-dashboard.md). An event carries the ticket's parent, and the open
PR (`set --pr N`) when the caller just opened one.

Judgment never lives here: which agent to call, what a story/spec/review says, and pair
dialogue stay with the skills. Requires the `gh` CLI and Python 3.
"""
import argparse
import concurrent.futures
import copy
import datetime
import hashlib
import json
import math
import os
import posixpath
import re
import subprocess
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot_checks  # noqa: E402  (the code checks and the formats, shipped next to this file)

# The model (assets/docs/pilot-process.md §2): levels, statuses per level, flags, and what no workflow does by itself.
LEVELS = ("epic", "story", "task")
STATUSES = ("forming", "to-plan", "planning", "planned", "ready", "building", "reviewing", "merged", "done", "wont-do")
LEVEL_STATUSES = {"epic": ("forming", "to-plan", "planning", "planned", "done", "wont-do"), "story": STATUSES,
                  "task": ("ready", "building", "reviewing", "merged", "done")}
# Transitions no workflow makes: a human closing a forming ticket or dropping one, or the script deriving a parent from its children.
EXTERNAL = (("status:forming", "status:to-plan"), ("status:forming", "status:wont-do"), ("status:to-plan", "status:wont-do"),
            ("status:planned", "status:building"), ("status:planned", "status:done"), ("status:building", "status:merged"))
SINKS = ("status:done", "status:wont-do")  # statuses nothing consumes
PERSONAS = ("pm", "architect", "techlead", "dev", "e2e", "qa", "designer")  # .claude/agents/pilot-<name>.md
STEP_KINDS = ("human-start", "human-gate", "human-optional", "agent", "validator", "judge", "check", "wait", "end")
OPEN_IF = ("delta-not-empty", "delta-not-empty-or-overcost", "blocked")  # when an optional human step opens


# ---- the workflows: assets/workflows/*.json (`.pilot/workflows/` in a project), expanded and checked here ----
def workflow_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(here, "workflows"), os.path.join(here, os.pardir, "assets", "workflows")):
        if os.path.isdir(candidate):
            return os.path.normpath(candidate)
    raise Refused({"ok": False, "reason": "no-workflows", "hint": "run /pilot-update: .pilot/workflows/ is missing"})


def renumber(steps):
    """Display numbers: 1, 2, … and `5bis` for a step that is the alternative of the one before it."""
    n = 0
    for step in steps:
        if step.get("alt_of"):
            step["n"] = f"{n}bis"
        else:
            n += 1
            step["n"] = str(n)
    return steps


def expand(raw, wid):
    """A workflow's steps with its `include` entries replaced by the steps of the workflow they name (prefixed ids, patched fields)."""
    wf, steps = copy.deepcopy(raw[wid]), []
    for step in wf["steps"]:
        if "include" not in step:
            steps.append(step)
            continue
        source = raw[step["include"]]["steps"]
        wanted = step.get("ids") or [s["id"] for s in source]
        prefix, patch = step.get("prefix", ""), step.get("patch", {})
        for s in (copy.deepcopy(s) for s in source if s["id"] in wanted):
            changes = patch.get(s["id"], {})
            if "on_fail" in changes:
                s["on_fail"] = {**s.get("on_fail", {}), **changes.pop("on_fail")}
            s.update(changes)
            old = s["id"]
            s["id"] = prefix + old
            for key in ("loop_to", "alt_of"):
                if s.get(key) in wanted:
                    s[key] = prefix + s[key]
            if s.get("on_fail", {}).get("to") in wanted:
                s["on_fail"]["to"] = prefix + s["on_fail"]["to"]
            for rej in s.get("on_reject", []):
                if rej["to"] in wanted:
                    rej["to"] = prefix + rej["to"]
            steps.append(s)
    wf["steps"] = renumber(steps)
    return wf


def load_workflows(directory=None):
    """Every workflow of the project, expanded: {id: workflow}."""
    directory = directory or workflow_dir()
    raw = {}
    for name in sorted(os.listdir(directory)):
        if name.endswith(".json"):
            with open(os.path.join(directory, name), encoding="utf-8") as handle:
                data = json.load(handle)
            raw[data["id"]] = data
    return {wid: expand(raw, wid) for wid in raw}


def workflow_problems(wfs):
    """What is wrong with the workflows as data: structure, references, unknown personas, unimplemented checks, statuses that do not compose."""
    problems = []
    for wid, wf in wfs.items():
        ids = [s["id"] for s in wf["steps"]]

        def bad(code, step=None, **extra):
            problems.append({"workflow": wid, **({"step": step["id"]} if step else {}), "code": code, **extra})

        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            bad("duplicate-step-id", id=dup)
        for step in wf["steps"]:
            if step.get("kind") not in STEP_KINDS:
                bad("unknown-kind", step, kind=step.get("kind"))
            for key in ("loop_to", "alt_of"):
                if step.get(key) and step[key] not in ids:
                    bad("unknown-target", step, field=key, target=step[key])
            targets = ([step["on_fail"]["to"]] if step.get("on_fail") else []) + [r["to"] for r in step.get("on_reject", [])]
            bad_targets = [t for t in targets if t not in ids]
            if bad_targets:
                bad("unknown-target", step, target=bad_targets[0])
            for agent in step.get("agents", []):
                if agent["persona"] not in PERSONAS:
                    bad("unknown-persona", step, persona=agent["persona"])
            if step.get("open_if") and step["open_if"] not in OPEN_IF:
                bad("unknown-open-if", step, open_if=step["open_if"])
            if step["kind"] == "check" and not step.get("check"):
                bad("check-without-id", step)
            if step["kind"] == "judge" and not step.get("questions"):
                bad("judge-without-questions", step)
            if step.get("check") and not step.get("action") and step["check"] not in CHECKS:
                bad("unimplemented-check", step, check=step["check"])
        if not any(s["kind"] == "end" for s in wf["steps"]):
            bad("no-end-step")
    return problems + composition_problems(wfs)


def wf_cfg(wfs, wid):
    """The claim/pool/resolve configuration of one workflow, from its contract (the `PHASES` of earlier versions)."""
    if wid not in wfs:
        raise Refused({"ok": False, "reason": "unknown-workflow", "expected": sorted(wfs)})
    c = wfs[wid].get("contract") or {}
    status = lambda name: f"status:{name}" if name else None
    return {"fresh": status((c.get("consumes") or [None])[0]), "inprog": status(c.get("claims")), "reclaim": None,
            "gate": bool(c.get("gate")), "containers": set(c.get("containers", ())),
            "resumable": {status(n) for n in c.get("resumable", ())}}


def workflow_contract(wfs, wid):
    """One workflow's contract: the statuses it consumes, the one it claims into, the ones it produces."""
    if wid not in wfs:
        raise Refused({"ok": False, "reason": "unknown-workflow", "expected": sorted(wfs)})
    c = wfs[wid].get("contract") or {}
    pre = lambda names: sorted(f"status:{n}" for n in names or ())
    return {"ok": True, "workflow": wid, "consumes": pre(set(c.get("consumes", ())) | set(c.get("resumable", ()))),
            "claims": f"status:{c['claims']}" if c.get("claims") else None, "produces": pre(c.get("produces"))}


def composition_problems(wfs):
    """The chain as the composition of the contracts: every status has a producer and a consumer, a sink apart."""
    known = {f"status:{s}" for s in STATUSES}
    produced = {b for _a, b in EXTERNAL}
    consumed = {a for a, _b in EXTERNAL}
    for wid in wfs:
        c = workflow_contract(wfs, wid)
        produced |= set(c["produces"]) | ({c["claims"]} if c["claims"] else set())
        consumed |= set(c["consumes"]) | ({c["claims"]} if c["claims"] else set())
    problems = [{"status": st, "code": "no-producer"} for st in sorted(known - produced)]
    problems += [{"status": st, "code": "no-consumer"} for st in sorted(known - consumed - set(SINKS))]
    problems += [{"status": st, "code": "unknown-status"} for st in sorted((produced | consumed) - known)]
    return problems


def transition_allowed(wfs, current, new):
    """Whether some contract admits `current` -> `new` (a workflow that consumes or claims `current` and produces or claims
    `new`, or a closing or derivation). Creation (no status yet), no change and clearing the status are always fine."""
    if not current or current == new or new == "status:none" or (current, new) in EXTERNAL:
        return True
    for wid in wfs:
        c = workflow_contract(wfs, wid)
        if current in c["consumes"] + [c["claims"]] and new in c["produces"] + [c["claims"]]:
            return True
    return False


def required_labels(wfs=None):
    return set(LABELS) | {f"run:{w}" for w in (wfs if wfs is not None else load_workflows())}


CHECKS = pilot_checks.CHECKS  # check id -> function(Ctx) -> problems: one per `check` step of the workflows


# What a v5 label becomes (`labels migrate`); a label with no entry has no equivalent and is reported.
STATUS_MIGRATION = {"draft": "forming", "backlog": "to-plan", "in-spec": "planning", "dev-ready": "ready", "in-dev": "building",
                    "review-ready": "reviewing", "in-review": "reviewing", "changes-requested": "reviewing", "approved": "reviewing",
                    "split": "planned", "qa": "merged", "in-qa": "merged", "done": "done", "wont-do": "wont-do"}
TYPE_MIGRATION = {"type:bug": ("type:tech", "fix"), "type:e2e": ("type:tech", None)}


# name -> (color, description): the one list of PILOT labels (`pilot.py labels sync` creates them)
LABELS = {
    "type:feature": ("1D76DB", "PILOT: a ticket that changes what the product does; validated by the PM, run by human F"),
    "type:tech": ("0E8A16", "PILOT: a technical need; run by human T"),
    "level:epic": ("5319E7", "PILOT: groups stories a human wants designed together; never built itself"),
    "level:story": ("BFD4F2", "PILOT: one or more wiki entries that go together; built as is, or split into tasks"),
    "level:task": ("C2C2C2", "PILOT: a technical split of a story, only when the code checks say it does not fit"),
    "priority:P0": ("B60205", "PILOT: highest priority"),
    "priority:P1": ("D93F0B", "PILOT: medium priority"),
    "priority:P2": ("FBCA04", "PILOT: lowest priority"),
    "status:forming": ("C5DEF5", "PILOT: still takes entries until a human closes it"),
    "status:to-plan": ("BFD4F2", "PILOT: ready for the plan workflow"),
    "status:planning": ("C5DEF5", "PILOT: the plan workflow has claimed it"),
    "status:planned": ("D4C5F9", "PILOT: split into tasks; follows them"),
    "status:ready": ("BFD4F2", "PILOT: designed, ready for the build workflow"),
    "status:building": ("C5DEF5", "PILOT: the build workflow has claimed it"),
    "status:reviewing": ("FBCA04", "PILOT: implemented, being reviewed and checked before the merge"),
    "status:merged": ("0E8A16", "PILOT: merged on main, waits for the Recette"),
    "status:done": ("0E8A16", "PILOT: the Recette passed"),
    "status:wont-do": ("E4E669", "PILOT: decided not to build it"),
    "needs-human": ("B60205", "PILOT: a blocking question for a human; status: stays where it was"),
    "on-hold": ("C2C2C2", "PILOT: deliberately paused; in no pool"),
    "can-resume": ("0E8A16", "PILOT: a human's signal that an interrupted run is safe to continue"),
    "express": ("D93F0B", "PILOT: made by the express workflow; provisional documents await their catch-up"),
    "fix": ("F9D0C4", "PILOT: a correction ticket made by a Recette"),
    "gap": ("F9D0C4", "PILOT: depends on a ticket whose Recette is in gap"),
}

PRIORITY = {"priority:P0": 0, "priority:P1": 1, "priority:P2": 2}
NO_PRIORITY = 9
FLAGS = ("needs-human", "on-hold")
DEPENDS_RE = re.compile(r"Depends on #(\d+)")
BLOCKS_RE = re.compile(r"Blocks #(\d+)")
PROTO_MAX_BYTES = 1_000_000   # one mockup, all parts together
PROTO_PART_BYTES = 200_000     # a database document is capped at 256 KiB
PROTO_FORBIDDEN = pilot_checks.PROTO_FORBIDDEN
REMOTE_RE = re.compile(r"(?:github\.com[:/]|/git/)([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")
STATE_PATH = os.path.join(".pilot", "state.json")
WIKI_DIR = "wiki"
ARCH_DIR = "architecture"
# The optional modules a project turns on in .pilot/state.json (`modules`): the skills each owns, the modules
# it needs, the command that turns it on at first use (`use`), the one that drafts its content from what the
# project already has (`bootstrap`, only where there is such content), and the folder (if any) `doctor` expects.
MODULES = {
    "wiki": {"skills": ["pilot-wiki", "pilot-flow"], "requires": [], "use": "/pilot-wiki", "bootstrap": "/pilot-wiki --bootstrap",
             "dir": WIKI_DIR},
    "architecture": {"skills": ["pilot-architecture"], "requires": [], "use": "/pilot-architecture",
                     "bootstrap": "/pilot-architecture --bootstrap", "dir": ARCH_DIR},
    "dashboard": {"skills": ["pilot-dashboard"], "requires": [], "use": "/pilot-dashboard"},
    "design": {"skills": ["pilot-design"], "requires": ["dashboard"], "use": "/pilot-design"},
    "proto": {"skills": ["pilot-proto"], "requires": ["dashboard"], "use": "/pilot-proto"},
}
WIKI_SNAPSHOT_MAX_BYTES = 240_000  # a database document holds at most 256 KiB
WIKI_STATUSES = ("proposed", "specified", "implemented", "provisional")  # the only ones a file holds
OKF_VERSION = "0.2"  # the Open Knowledge Format the wiki follows (https://github.com/GoogleCloudPlatform/open-knowledge-format)
WIKI_RESERVED = ("index.md", "log.md")  # OKF: never concept files
WIKI_OKF_STATUS = {"proposed": "draft", "specified": "draft", "implemented": "stable", "provisional": "draft"}
WIKI_VERIFIER = "process:pilot-wiki"
WIKI_VERIFIERS = ("process:pilot-wiki", "process:pilot-dev", "process:pilot-qa")  # who verified: a lint, a Dev PR, a QA run
WIKI_DEFAULT_TYPE = "Behavior"
WIKI_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
WIKI_IN_DEV = ("status:building",)
WIKI_IN_REVIEW = ("status:reviewing",)
WIKI_IN_QA = ("status:merged",)  # merged, waiting for the Recette
WIKI_PRE_DEV = ("status:forming", "status:to-plan", "status:planning", "status:planned", "status:ready")


class GhError(Exception):
    pass


def read_modules(path=STATE_PATH):
    """The project's optional modules, from `.pilot/state.json`: {"wiki": True, ...}; {} when the file
    or the field is absent (a project from before modules has none enabled)."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    modules = data.get("modules") if isinstance(data, dict) else None
    return {k: bool(v) for k, v in modules.items()} if isinstance(modules, dict) else {}


def state_apps(path=STATE_PATH):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    apps = data.get("apps") if isinstance(data, dict) else None
    return [a["name"] for a in apps if isinstance(a, dict) and isinstance(a.get("name"), str)] if isinstance(apps, list) else []


DEFAULT_LANGUAGE = "en"
# a few of the commonest function words per language: enough to tell which of the two a paragraph is written in
LANG_WORDS = {
    "en": frozenset("the of and to in is are for with that this on be as by it from at or an not can when each".split()),
    "fr": frozenset("le la les des du de et en est un une pour avec que qui dans sur par au aux ce cette ne pas ou chaque quand".split()),
}


CONFIG_KEYS = ("projectName", "language", "dashboardUrl", "commands", "scopes", "threshold")  # what `config` may write
COMMAND_KEYS = ("test", "rules", "e2e", "build", "a11y", "render", "version")  # the project's own commands the checks read results from


def config_value(key, path=STATE_PATH):
    """A dotted key of `.pilot/state.json` (`commands.test`), or None."""
    try:
        with open(path, encoding="utf-8") as handle:
            node = json.load(handle)
    except (OSError, ValueError):
        return None
    for part in key.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node


def config_set(key, value, path=STATE_PATH):
    """Write one dotted key of `.pilot/state.json`, leaving everything else alone. `commands.<name>` takes a shell command."""
    head, _, tail = key.partition(".")
    if head not in CONFIG_KEYS or (head == "commands" and tail not in COMMAND_KEYS):
        raise Refused({"ok": False, "reason": "unknown-key", "allowed": list(CONFIG_KEYS), "commands": list(COMMAND_KEYS)})
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        data = {}
    if tail:
        data.setdefault(head, {})[tail] = value
    else:
        data[head] = value
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return {"ok": True, "key": key, "value": value}


def read_language(path=STATE_PATH):
    """The language of the project's wiki and architecture text, from `.pilot/state.json` (`language`, an ISO code such as
    "fr"); English when the file or the field is absent."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return DEFAULT_LANGUAGE
    value = data.get("language") if isinstance(data, dict) else None
    return value.strip().lower() if isinstance(value, str) and value.strip() else DEFAULT_LANGUAGE


def detect_language(text):
    """`en` or `fr` when the text clearly is one of them, else None (too short, mixed, or another language)."""
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    scores = {lang: sum(1 for w in words if w in vocab) for lang, vocab in LANG_WORDS.items()}
    best, other = sorted(scores, key=scores.get, reverse=True)
    if scores[best] >= 4 and scores[best] > 2 * scores[other]:
        return best
    return None


def module_registry(modules):
    """Every known module with whether it is on, what it needs, its skills, its first-use command and its bootstrap."""
    return {name: {"enabled": bool(modules.get(name)), "requires": meta["requires"], "skills": meta["skills"],
                   "use": meta["use"], "bootstrap": meta.get("bootstrap")} for name, meta in MODULES.items()}


def state_modules(path=STATE_PATH):
    """The `modules` field of `.pilot/state.json` as it stands, or None when the file or the field is absent
    (a project from before modules: the dashboard then shows every tab)."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    modules = data.get("modules") if isinstance(data, dict) else None
    return {k: bool(v) for k, v in modules.items()} if isinstance(modules, dict) else None


def set_module(name, enabled, path=STATE_PATH, with_requires=False):
    """Turn a module on or off in `.pilot/state.json`, leaving every other field alone. Turning one on needs
    the modules it requires to be on (`with_requires` turns them on too); turning one off is refused while an
    enabled module requires it."""
    if name not in MODULES:
        raise Refused({"ok": False, "reason": "unknown-module", "expected": list(MODULES)})
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        raise Refused({"ok": False, "reason": "no-state", "hint": "run /pilot-init"})
    modules = data.get("modules") if isinstance(data.get("modules"), dict) else {}
    if enabled:
        pending, missing = [name], []
        while pending:
            for needed in MODULES[pending.pop()]["requires"]:
                if not modules.get(needed) and needed not in missing:
                    missing.append(needed)
                    pending.append(needed)
        if missing and not with_requires:
            raise Refused({"ok": False, "reason": "requires", "missing": missing,
                           "hint": "--with-requires turns them on too"})
        for needed in missing:
            modules[needed] = True
    else:
        by = [n for n, meta in MODULES.items() if modules.get(n) and name in meta["requires"]]
        if by:
            raise Refused({"ok": False, "reason": "required-by", "by": by})
    modules[name] = bool(enabled)
    data["modules"] = modules
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return {"ok": True, "modules": {k: bool(v) for k, v in modules.items()}}


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

    def issue_events(self, number):
        """The ticket's label events (`labeled`/`unlabeled`), oldest first."""
        items = self._pages(f"repos/{self.repo}/issues/{number}/events", max_pages=5)
        return [e for e in items if e.get("event") in ("labeled", "unlabeled")]

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

    def comment_items(self, number):
        return [{"id": c["id"], "body": c.get("body") or ""} for c in self._pages(f"repos/{self.repo}/issues/{number}/comments")]

    def patch_comment(self, comment_id, text):
        self._run(f"repos/{self.repo}/issues/comments/{comment_id}", method="PATCH", body={"body": text})

    def create_issue(self, title, body, labels, assignees):
        return json.loads(self._run(f"repos/{self.repo}/issues", method="POST",
                                    body={"title": title, "body": body, "labels": labels, "assignees": assignees}))

    def create_pull(self, title, body, head, base):
        return json.loads(self._run(f"repos/{self.repo}/pulls", method="POST", body={"title": title, "body": body, "head": head, "base": base}))

    def get_pull(self, number):
        return json.loads(self._run(f"repos/{self.repo}/pulls/{number}"))

    def check_runs(self, sha):
        """The check runs of a commit (the CI): [{name, status, conclusion}]."""
        items = json.loads(self._run(f"repos/{self.repo}/commits/{sha}/check-runs?per_page=100")).get("check_runs", [])
        return [{"name": c["name"], "status": c["status"], "conclusion": c.get("conclusion")} for c in items]

    def merge_pull(self, number, method):
        return json.loads(self._run(f"repos/{self.repo}/pulls/{number}/merge", method="PUT", body={"merge_method": method}))

    def add_sub_issue(self, parent, child_id):
        self._run(f"repos/{self.repo}/issues/{parent}/sub_issues", method="POST", body={"sub_issue_id": child_id})

    def upsert_label(self, name, color, description, exists):
        body = {"color": color, "description": description[:100]}
        if exists:
            self._run(f"repos/{self.repo}/labels/{name}", method="PATCH", body=body)
        else:
            self._run(f"repos/{self.repo}/labels", method="POST", body={"name": name, **body})


def stage_history(events, labels):
    """What the dashboard's work view needs of a ticket's label events: `h`, the statuses it went through
    with the time it entered each (`[[status, at], ...]`, a repeated status dropped), and `nh`, since when
    `needs-human` stands (only while the ticket carries it)."""
    history, flagged = [], ""
    for e in sorted(events, key=lambda e: str(e.get("created_at", ""))):
        name = str((e.get("label") or {}).get("name", ""))
        at = str(e.get("created_at", ""))
        if e.get("event") == "labeled" and name.startswith("status:"):
            status = name[len("status:"):]
            if not history or history[-1][0] != status:
                history.append([status, at])
        elif name == "needs-human":
            flagged = at if e.get("event") == "labeled" else ""
    out = {}
    current = next((l[len("status:"):] for l in labels if l.startswith("status:")), "")
    if not history or history[-1][0] != current:  # a history that does not end on the current status is incomplete (events cap): nothing of it is trusted
        return out
    out["h"] = history
    if flagged and "needs-human" in labels:
        out["nh"] = flagged
    return out


CLOSES_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+#(\d+)", re.I)


def trailing_number(url):
    tail = str(url or "").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def normalize(raw):
    return {
        "number": raw["number"],
        "title": raw.get("title", ""),
        "state": str(raw.get("state", "open")).lower(),
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


def entry_hash(entry):
    """What a flow run remembers of an entry: a short hash of its title and prose, so a later change is seen."""
    return hashlib.sha256((entry["title"] + "\n" + entry["text"]).encode("utf-8")).hexdigest()[:12]


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


SNAPSHOT_MAX_BYTES = 240_000  # a database document holds at most 256 KiB


class Refused(Exception):
    """A precondition failed: the JSON payload explains, exit status 1."""

    def __init__(self, payload):
        super().__init__(payload.get("reason", "refused"))
        self.payload = payload


class Machine:
    def __init__(self, gh, workflows=None, state_path=STATE_PATH):
        self.gh = gh
        self.state_path = state_path
        self.wfs = workflows if workflows is not None else load_workflows()
        self._open = {}
        self._parent_bodies = {}

    def _cfg(self, workflow):
        cfg = wf_cfg(self.wfs, workflow)
        if not cfg["inprog"]:
            raise Refused({"ok": False, "reason": "workflow-claims-no-ticket", "workflow": workflow})
        return cfg

    # ---- shared checks -------------------------------------------------------------------
    def open_state(self, number):
        if number not in self._open:
            self._open[number] = self.gh.is_open(number)
        return self._open[number]

    def split_story_body(self, number):
        """(the raw parent, None when it cannot be read; its body when it is a `level:story`, else '' — an Epic's line is not inherited)."""
        if number not in self._parent_bodies:
            try:
                found = self.gh.get_issue(number)
            except (GhError, ValueError):
                found = None
            names = [l["name"] if isinstance(l, dict) else l for l in (found or {}).get("labels", [])]
            self._parent_bodies[number] = (found, (found.get("body") or "") if found and "level:story" in names else "")
        return self._parent_bodies[number]

    def blocking_dependencies(self, issue):
        """Open (or unreadable) 'Depends on #N' references in the issue body, and in its parent story's: a split story keeps
        the line its own spec recorded and its tasks inherit it. A parent that cannot be read counts as open."""
        body, unreadable = issue["body"], []
        if issue.get("parent"):
            found, parent_text = self.split_story_body(issue["parent"])
            if found is None:
                unreadable.append(issue["parent"])
            body += "\n" + parent_text
        return sorted({int(m) for m in DEPENDS_RE.findall(body) if self.open_state(int(m)) is not False} | set(unreadable))

    def blocks_open_ticket(self, issue):
        """True when a 'Blocks #M' comment on this issue points at a still-open M."""
        for body in self.gh.comments(issue["number"]):
            for m in BLOCKS_RE.findall(body):
                if self.open_state(int(m)) is True:
                    return True
        return False

    # ---- pool ----------------------------------------------------------------------------
    def pool(self, phase, limit, only=None):
        cfg = self._cfg(phase)
        candidates, excluded, raws = [], [], {}

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
            found = [i for i in self.gh.issues_with_label(label) if only is None or i["number"] in only]
            raws.update({i["number"]: i for i in found})
            return found

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
        if shown and only is None:  # the pick is resolved here, from what was listed: the caller acts on `action` at once
            checked = self.resolve_raw(phase, shown[0]["number"], False, raws[shown[0]["number"]])
            shown[0] = {**shown[0], "action": checked["action"], **({"reason": checked["reason"]} if "reason" in checked else {})}
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
            if "status:planned" in labels:
                found += [g["number"] for g in self.gh.sub_issues(child["number"])
                          if g.get("state") == "open"]
        return found

    def resolve(self, phase, number, resume=False):
        self._cfg(phase)
        return self.resolve_raw(phase, number, resume, self.gh.get_issue(number))

    def resolve_raw(self, phase, number, resume, raw):
        return self._resolve(phase, number, resume, raw)

    def _resolve(self, phase, number, resume, raw):
        cfg = self._cfg(phase)
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
                    "planned" if "level:story" in labels and status == "status:planned" else None)
            if kind in cfg["containers"]:
                tree = self.open_tree(number)
                if tree:
                    found = self.pool(phase, 5, only=set(tree))
                    return {"action": "descend", "via": number, "pick": found["pick"],
                            "candidate_count": found["candidate_count"]}
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
            return {"action": "stop", "reason": "in-progress-unassigned",
                    "hint": "no assignee and no can-resume: a human adds can-resume to hand it to a sweep, or sets the status back", **base}
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
    def doctor(self, wiki_dir=WIKI_DIR, modules=None):
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
            check("github-api", False, str(err) or "gh CLI not found, or `gh api user` fails (`gh auth status` can be wrong behind a token-swapping proxy: check `gh api user`)")
        if login:
            try:
                info = self.gh.repo_info()
                check("repo-readable", True, info.get("full_name", ""))
                perms = info.get("permissions") or {}
                check("repo-write-permission", perms.get("push") or perms.get("admin"),
                      "the account can push (a session may still restrict writes)"
                      if perms.get("push") or perms.get("admin")
                      else "read-only access: claim/set/flag would be refused")
                missing = sorted(required_labels(self.wfs) - self.gh.label_names())
                check("pilot-labels", not missing,
                      "all present" if not missing else
                      f"{len(missing)} missing (run /pilot-update): " + ", ".join(missing[:6])
                      + ("…" if len(missing) > 6 else ""))
            except (GhError, ValueError) as err:
                check("repo-readable", False, str(err))
        if modules is None:
            modules = read_modules()
        for name, meta in MODULES.items():
            folder = wiki_dir if name == "wiki" else meta.get("dir")
            if modules.get(name) and folder:
                check(name, os.path.isdir(folder),
                      f"{folder}/ found" if os.path.isdir(folder) else
                      f"the {name} module is enabled but {folder}/ is missing: run {meta['use']}")
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
        self._add_history(rows)
        rows.sort(key=lambda r: r["u"], reverse=True)
        doc = {"repo": self.gh.repo, "at": now_iso(), "source": "pilot.py", "total": len(rows),
               "truncated": False, "issues": rows}
        modules = state_modules()
        if modules is not None:
            doc["modules"] = modules  # the dashboard's tabs follow the modules a project has on
        doc["language"] = read_language()  # the dashboard opens in it (a reader can switch)
        doc["workflows"] = sorted(self.wfs)  # the dashboard shows the workflows this project runs
        while len(json.dumps(doc, ensure_ascii=False).encode()) > SNAPSHOT_MAX_BYTES and rows:
            del rows[max(1, len(rows) * 9 // 10):]
            doc["truncated"] = True
        return doc

    def _add_history(self, rows):
        """Best effort: the work view's `h`/`nh` for every ticket in a status that is worked on (an Epic or
        a split story only holds sub-issues). A ticket whose events cannot be read has no history; `history_failed`
        counts them so that a throttled run is reported, not published as complete."""
        failed = []
        def history(row):
            status = next((l[len("status:"):] for l in row["l"] if l.startswith("status:")), "")
            if not status or status == "planned":
                return
            try:
                row.update(stage_history(self.gh.issue_events(row["n"]), row["l"]))
            except (GhError, ValueError):
                failed.append(row["n"])
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(history, rows))
        self.history_failed = len(failed)

    # ---- writes --------------------------------------------------------------------------
    def _write(self, number, labels, assignees=None, extra=None):
        body = {"labels": sorted(labels)}
        if assignees is not None:
            body["assignees"] = assignees
        body.update(extra or {})
        return normalize(self.gh.patch_issue(number, body))

    def claim(self, phase, number, mode):
        cfg = self._cfg(phase)
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
        elif mode == "resume-orphaned":
            if status not in cfg["resumable"] or not issue["assignees"]:
                refuse("not-claimable", expected=sorted(cfg["resumable"]))
        elif mode == "resume-cleared":
            if status != cfg["inprog"] or "can-resume" not in labels:
                refuse("not-claimable", expected=cfg["inprog"] + " + can-resume")
            new_assignees = None  # already claimed: only the one-time signal is consumed
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
                "event": self._event(after, "claim:" + mode, phase)}

    def set(self, number, status=None, assign=None, add=(), remove=(), close=False, pr=None):
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        labels = set(normalize(raw)["labels"])
        before = status_of(labels)
        if status is not None:
            name = status[len("status:"):] if status.startswith("status:") else status
            if name != "none" and name not in STATUSES:
                raise Refused({"ok": False, "reason": "unknown-status", "status": status,
                               "allowed": list(STATUSES)})
            labels = {l for l in labels if not l.startswith("status:")}
            if name != "none":
                labels.add(f"status:{name}")
        labels |= set(add)
        labels -= set(remove)
        assignees = [self.gh.me()] if assign == "me" else [] if assign == "none" else None
        extra = {"state": "closed", "state_reason": "completed"} if close else None
        after = self._write(number, labels, assignees, extra)
        result = {"ok": True, "issue": number, "status": status_of(after["labels"]),
                  "labels": sorted(after["labels"]), "assignees": after["assignees"],
                  "state": after["state"], "event": self._event(after, "set", pr=pr)}
        if not transition_allowed(self.wfs, before, result["status"]):
            result["warning"] = {"code": "unexpected-transition", "from": before, "to": result["status"],
                                 "hint": "no workflow contract (`pilot.py contract`) takes a ticket from one to the other"}
        return result

    def proto_pack(self, number, html_path, out_dir, brief=None, height=None):
        """Check a prototype's mockup and write the cockpit documents for it: proto-<n>.json (the
        metadata, `protos/p<n>`) and protoHtml-<n>-<k>.json (the parts, `protoHtml/<n>-<k>`)."""
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        issue = normalize(raw)
        if "run:proto" not in issue["labels"]:
            raise Refused({"ok": False, "reason": "not-a-proto-run", "issue": number})
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

    # ---- runs: one JSON comment on the run's issue, advanced by the workflow's own data -------------------------
    RUN_MARK = "<!-- pilot:run -->"

    def _wf(self, workflow):
        if workflow not in self.wfs:
            raise Refused({"ok": False, "reason": "unknown-workflow", "expected": sorted(self.wfs)})
        return self.wfs[workflow]

    def _run_comment(self, number):
        found = None
        for item in self.gh.comment_items(number):
            if item["body"].startswith(self.RUN_MARK):
                found = item
        if found is None:
            raise Refused({"ok": False, "reason": "no-run", "issue": number})
        body = found["body"][len(self.RUN_MARK):].strip()
        return found["id"], json.loads(body.removeprefix("```json").removesuffix("```").strip())

    def _run_write(self, number, comment_id, record):
        text = self.RUN_MARK + "\n```json\n" + json.dumps(record, ensure_ascii=False, indent=1) + "\n```"
        if comment_id is None:
            self.gh.post_comment(number, text)
        else:
            self.gh.patch_comment(comment_id, text)

    def _run_event(self, number, record, action):
        event = {"kind": "run", "n": number, "workflow": record["workflow"], "step": record["step"], "state": record["state"],
                 "loops": record["loops"], "action": action, "by": self.gh.me(), "at": now_iso()}
        if record.get("result"):
            event["result"] = record["result"]  # a finished run's outcome (a prototype's accepted or rejected), shown by the dashboard
        return event

    @staticmethod
    def step_view(step):
        """What a runner needs to run one step: no prose, only the fields that decide what to do."""
        keep = ("id", "n", "kind", "title", "actor", "agents", "task", "check", "judge", "questions", "open_if", "loop_to",
                "alt_of", "on_fail", "on_reject", "in", "out")
        return {k: step[k] for k in keep if k in step}

    def run_start(self, workflow, issue=None, title=None, data=None):
        wf = self._wf(workflow)
        record = {"v": 1, "workflow": workflow, "state": "running", "step": wf["steps"][0]["id"], "history": [], "loops": {},
                  "assumptions": [], "data": data or {}, "started": now_iso()}
        if issue is None:
            made = self.gh.create_issue(f"run:{workflow} {title or ''}".strip(), "A PILOT run. Its state is the JSON comment below.",
                                        [f"run:{workflow}"], [self.gh.me()])
            issue = made["number"]
        else:
            raw = self.gh.get_issue(issue)
            if raw is None:
                raise Refused({"ok": False, "reason": "not-found", "issue": issue})
            try:
                _cid, old = self._run_comment(issue)
                if old["state"] != "done" and old["workflow"] == workflow:
                    raise Refused({"ok": False, "reason": "run-in-progress", "issue": issue, "step": old["step"],
                                   "hint": "`pilot.py run resume`"})
            except Refused as err:
                if err.payload.get("reason") != "no-run":
                    raise
        self._run_write(issue, None, record)
        return {"ok": True, "run": issue, "step": self.step_view(wf["steps"][0]),
                "event": self._run_event(issue, record, "start")}

    def run_show(self, number):
        _cid, record = self._run_comment(number)
        step = next((s for s in self._wf(record["workflow"])["steps"] if s["id"] == record["step"]), None)
        return {"ok": True, "run": number, **record, "current": self.step_view(step) if step else None}

    def run_note(self, number, assumption=None, data=None):
        """Record an assumption (with its default, shown at the gate) or a value the later steps need (e.g. the executant)."""
        cid, record = self._run_comment(number)
        if assumption:
            record["assumptions"].append(assumption)
        record["data"].update(data or {})
        self._run_write(number, cid, record)
        return {"ok": True, "run": number, "assumptions": len(record["assumptions"]), "data": record["data"]}

    def run_advance(self, number, result, note=None):
        """The next step after the current one, decided by the workflow's data: ok, skip, loop (a human revised: back to the
        step that audits), fail (a check, judge or validator: back to the producer, twice at most, then the gate or a question)
        or reject:<label> (a gate sends the work back where its label says)."""
        cid, record = self._run_comment(number)
        wf = self._wf(record["workflow"])
        steps = wf["steps"]
        index = next(i for i, s in enumerate(steps) if s["id"] == record["step"])
        cur = steps[index]
        if record["state"] == "done":
            raise Refused({"ok": False, "reason": "run-done", "run": number})
        record["history"].append({"step": cur["id"], "result": result, "at": now_iso(), **({"note": note} if note else {})})

        def jump(step_id):
            return next(i for i, s in enumerate(steps) if s["id"] == step_id)

        def following(i):
            j = i + 1
            if j + 1 < len(steps) and steps[j + 1].get("alt_of") == steps[j]["id"]:  # entering alternatives: one runs
                return j + 1 if record["data"].get("executant") == "human" else j
            if j < len(steps) and steps[j].get("alt_of") == steps[i]["id"]:  # leaving the first alternative: skip the other
                return j + 1
            return j

        record["state"] = "running"
        target = None
        if result in ("ok", "skip"):
            target = following(index)
            if cur["kind"] == "end":
                record["state"] = "done"
                target = None
        elif result == "loop":
            if not cur.get("loop_to"):
                raise Refused({"ok": False, "reason": "no-loop", "step": cur["id"]})
            target = jump(cur["loop_to"])
        elif result == "fail":
            rule = cur.get("on_fail")
            if not rule:
                raise Refused({"ok": False, "reason": "no-on-fail", "step": cur["id"]})
            count = record["loops"].get(cur["id"], 0)
            if count < rule.get("max", 2):
                record["loops"][cur["id"]] = count + 1
                target = jump(rule["to"])
            elif rule.get("then") == "gate":
                target = next((i for i in range(index + 1, len(steps)) if steps[i]["kind"] == "human-gate"), None)
                record["data"]["escalated"] = {"from": cur["id"], "failures": count + 1}
                if target is None:
                    record["state"] = "waiting-human"
            else:
                record["state"] = "waiting-human"
                record["data"]["escalated"] = {"from": cur["id"], "failures": count + 1}
        elif result.startswith("reject:"):
            label = result.split(":", 1)[1]
            rule = next((r for r in cur.get("on_reject", []) if r["label"] == label), None)
            if not rule:
                raise Refused({"ok": False, "reason": "unknown-reject", "step": cur["id"],
                               "expected": [r["label"] for r in cur.get("on_reject", [])]})
            target = jump(rule["to"])
        else:
            raise Refused({"ok": False, "reason": "unknown-result", "expected": ["ok", "skip", "loop", "fail", "reject:<label>"]})
        if target is not None and target >= len(steps):
            record["state"], target = "done", None
        if target is not None:
            record["step"] = steps[target]["id"]
        self._run_write(number, cid, record)
        out = {"ok": True, "run": number, "from": cur["id"], "state": record["state"], "loops": record["loops"],
               "event": self._run_event(number, record, "advance:" + result)}
        if record["state"] == "running" and target is not None:
            out["step"] = self.step_view(steps[target])
        if record["state"] == "waiting-human":
            out["escalated"] = record["data"].get("escalated")
        return out

    def run_resume(self, number):
        """Where a run stopped: its step, loop counters and assumptions. Refused while a human question is open."""
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        issue = normalize(raw)
        if "needs-human" in issue["labels"]:
            raise Refused({"ok": False, "reason": "needs-human", "issue": number, "hint": "a human removes the flag first"})
        cid, record = self._run_comment(number)
        if record["state"] == "done":
            raise Refused({"ok": False, "reason": "run-done", "run": number})
        record["state"] = "running"
        self._run_write(number, cid, record)
        shown = self.run_show(number)
        return {**shown, "event": self._run_event(number, record, "resume")}

    def run_end(self, number, result=None, data=None):
        """Close a run: the record stays as the last comment (a Recette's record is read from it, a prototype's verdict too);
        a run issue is closed, a ticket is left to its own status."""
        cid, record = self._run_comment(number)
        record.update({"state": "done", "ended": now_iso(), "result": result, "step": record["step"]})
        if data:
            record["record"] = data
        self._run_write(number, cid, record)
        raw = normalize(self.gh.get_issue(number))
        if not any(l.startswith("level:") for l in raw["labels"]):
            self._write(number, raw["labels"], [], {"state": "closed", "state_reason": "completed"})
        return {"ok": True, "run": number, "result": result, "event": self._run_event(number, record, "end")}

    # ---- tickets: the two human closings, and the statuses derived from the children --------------------------
    def ticket_create(self, level, kind, title, body, status, parent=None, priority=None, labels=()):
        """Create an epic, story or task as a GitHub issue (a story points to its entries in its body; nothing is copied), under `parent`
        as a native sub-issue. The status must exist for the level."""
        if level not in LEVELS or kind not in ("feature", "tech"):
            raise Refused({"ok": False, "reason": "bad-level-or-type", "levels": list(LEVELS), "types": ["feature", "tech"]})
        if status not in LEVEL_STATUSES[level]:
            raise Refused({"ok": False, "reason": "status-not-for-level", "level": level, "allowed": list(LEVEL_STATUSES[level])})
        names = [f"level:{level}", f"type:{kind}", f"status:{status}", *labels] + ([f"priority:{priority}"] if priority else [])
        made = self.gh.create_issue(title, body, names, [])
        if parent:
            self.gh.add_sub_issue(parent, made["id"])
        issue = normalize(made)
        return {"ok": True, "issue": issue["number"], "labels": sorted(issue["labels"]), "event": self._event(issue, "created")}

    def ticket_merged(self, number):
        """A ticket whose PR merged: `merged` (a ticket still `building` or `reviewing`), then its parent derived. Idempotent, so the merge
        workflow of GitHub and the build run may both call it."""
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        issue = normalize(raw)
        status = status_of(issue["labels"])
        if status not in ("status:building", "status:reviewing", "status:merged"):
            raise Refused({"ok": False, "reason": "wrong-status", "issue": number, "status": status})
        out = self.set(number, "merged", None, (), ()) if status != "status:merged" else {"ok": True, "issue": number, "status": status}
        if issue.get("parent"):
            out["parent"] = self.derive(issue["parent"])
        return out

    def ticket_close_forming(self, number, drop=False):
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        issue = normalize(raw)
        status = status_of(issue["labels"])
        allowed = ("status:forming", "status:to-plan") if drop else ("status:forming",)
        if status not in allowed:
            raise Refused({"ok": False, "reason": "wrong-status", "issue": number, "status": status, "expected": list(allowed)})
        new = "wont-do" if drop else "to-plan"
        return self.set(number, new, None, (), (), close=drop)

    def derive(self, number):
        """The status of a split story (from its tasks) or of an epic (from its stories), written when it changed."""
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": number})
        issue = normalize(raw)
        status = status_of(issue["labels"])
        children = [normalize(c) for c in self.gh.sub_issues(number)]
        if "level:story" in issue["labels"] and status in ("status:planned", "status:building", "status:merged") and children:
            states = [status_of(c["labels"]) for c in children]
            if all(s in ("status:merged", "status:done") for s in states):
                new = "merged"
            elif any(s in ("status:building", "status:reviewing", "status:merged", "status:done") for s in states):
                new = "building"
            else:
                new = "planned"
        elif "level:epic" in issue["labels"] and status == "status:planned" and children:
            done = all(c["state"] == "closed" for c in children)
            new = "done" if done else "planned"
        else:
            return {"ok": True, "issue": number, "status": status, "changed": False}
        if f"status:{new}" == status:
            return {"ok": True, "issue": number, "status": status, "changed": False}
        result = self.set(number, new, None, (), (), close=(new == "done" and "level:epic" in issue["labels"]))
        return {**result, "changed": True}

    # ---- pull requests: the carrier of a change, and the CI's verdict ------------------------------------------
    def pr_open(self, branch, title, body, base="main"):
        made = self.gh.create_pull(title, body, branch, base)
        return {"ok": True, "pr": made["number"], "url": made.get("html_url", ""), "head": (made.get("head") or {}).get("sha", "")}

    def pr_ci(self, number):
        """The CI's verdict on a PR now: `pending`, `green` or `red` (no check at all counts as green: a docs-only PR runs none)."""
        pull = self.gh.get_pull(number)
        runs = self.gh.check_runs(pull["head"]["sha"])
        failed = [r["name"] for r in runs if r["status"] == "completed" and r["conclusion"] not in ("success", "neutral", "skipped")]
        waiting = [r["name"] for r in runs if r["status"] != "completed"]
        verdict = "red" if failed else "pending" if waiting else "green"
        return {"ok": True, "pr": number, "ci": verdict, "failed": failed, "waiting": waiting}

    def pr_merge(self, number, method="squash"):
        """Merge a PR whose CI is green (the only way a PR is merged here; a human approval is the workflow's gate before it)."""
        verdict = self.pr_ci(number)
        if verdict["ci"] != "green":
            raise Refused({"ok": False, "reason": "ci-not-green", **verdict})
        done = self.gh.merge_pull(number, method)
        return {"ok": True, "pr": number, "merged": bool(done.get("merged")), "sha": done.get("sha", "")}

    def migrate_labels(self, apply=False):
        """Move the open tickets of a v5 project to the v6 labels: statuses (`STATUS_MIGRATION`), `type:bug`/`type:e2e`, an epic with no
        status to `planned`. A prototype ticket, or any label with no equivalent, is only reported. Dry run unless `apply`."""
        changes, unmapped = [], []
        for raw in self.gh.open_issues():
            labels = set(normalize(raw)["labels"])
            add, remove, stuck = set(), set(), []
            for label in sorted(labels):
                if label.startswith("status:"):
                    name = label[len("status:"):]
                    if name in STATUSES:
                        continue
                    if name in STATUS_MIGRATION:
                        remove.add(label)
                        add.add(f"status:{STATUS_MIGRATION[name]}")
                    else:
                        stuck.append(label)
                elif label in TYPE_MIGRATION:
                    new, flag = TYPE_MIGRATION[label]
                    remove.add(label)
                    add |= {new} | ({flag} if flag else set())
                elif label == "type:poc":
                    stuck.append(label)
            if "level:epic" in labels and not any(l.startswith("status:") for l in labels):
                add.add("status:planned")
            if stuck:
                unmapped.append({"issue": raw["number"], "labels": stuck})
            if add or remove:
                changes.append({"issue": raw["number"], "remove": sorted(remove), "add": sorted(add - labels)})
        if apply:
            for change in changes:
                current = set(normalize(self.gh.get_issue(change["issue"]))["labels"])
                self._write(change["issue"], current - set(change["remove"]) | set(change["add"]))
        return {"ok": True, "applied": apply, "changes": changes, "unmapped": unmapped}

    def sync_labels(self):
        """Create or update every PILOT label (idempotent), and stamp `lastLabelsSyncAt` in .pilot/state.json when it exists."""
        names = required_labels(self.wfs)
        have = self.gh.label_names()
        for name in sorted(names):
            color, description = LABELS.get(name, ("EDEDED", f"PILOT: a run of the {name.split(':', 1)[-1]} workflow"))
            self.gh.upsert_label(name, color, description, name in have)
        if os.path.exists(self.state_path):
            with open(self.state_path, encoding="utf-8") as handle:
                state = json.load(handle)
            if "lastLabelsSyncAt" in state:
                state["lastLabelsSyncAt"] = now_iso()
                with open(self.state_path, "w", encoding="utf-8") as handle:
                    json.dump(state, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
        return {"ok": True, "labels": len(names)}


def split_frontmatter(text):
    """(block, rest): the YAML between the opening and the closing `---` line, and what follows the closing
    line; (None, text) when the file has no frontmatter."""
    lines = text.split("\n")
    if lines[0].rstrip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None, text


def _y_split(inner):
    parts, cur, quote = [], "", None
    for ch in inner:
        if quote:
            cur += ch
            if ch == quote and not cur.endswith("\\" + quote):
                quote = None
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch == ",":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def _y_close(v, closer):
    """`v` cut after its closing bracket, when what follows is blank or a `# comment`."""
    end = v.rfind(closer)
    rest = v[end + 1:].strip() if end > 0 else "x"
    if end <= 0 or (rest and not rest.startswith("#")):
        raise ValueError("unterminated YAML value: " + v)
    return v[:end + 1]


def _y_scalar(raw):
    v = raw.strip()
    if v in ("", "null", "~") or v.startswith("#"):
        return None
    if v[0] == '"':
        try:
            value, end = json.JSONDecoder().raw_decode(v)
        except ValueError:
            raise ValueError("bad quoted string: " + v)
        if v[end:].strip() and not v[end:].strip().startswith("#"):
            raise ValueError("bad quoted string: " + v)
        return value
    if v[0] == "'":
        m = re.match(r"^'((?:[^']|'')*)'\s*(?:#.*)?$", v)
        if not m:
            raise ValueError("bad quoted string: " + v)
        return m.group(1).replace("''", "'")
    if v[0] == "[":
        inner = _y_close(v, "]")[1:-1]
        return [_y_scalar(x) for x in _y_split(inner)] if inner.strip() else []
    if v[0] == "{":
        inner = _y_close(v, "}")[1:-1]
        out = {}
        for part in _y_split(inner) if inner.strip() else []:
            m = re.match(r"^\s*([A-Za-z_][\w.\-]*)\s*:(?:\s+(.*))?$", part)
            if not m:
                raise ValueError("unsupported YAML value: " + v)
            out[m.group(1)] = _y_scalar(m.group(2) or "")
        return out
    if v[0] in "&*!|>":
        raise ValueError("unsupported YAML value: " + v)
    v = re.split(r"\s+#", v, maxsplit=1)[0].strip()
    if v in ("true", "false"):
        return v == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


YAML_KEY_RE = re.compile(r"^([A-Za-z_][\w.\-]*):(?:[ \t]+(.*))?$")


def parse_frontmatter(block):
    """The YAML subset PILOT writes and reads: `key: scalar`, `key: [a, b]`, and one level of nested
    `key:` + indented `sub: scalar` lines. Anything else (a list of mappings, a flow mapping, deeper nesting)
    raises ValueError: such a file is left alone, never rewritten."""
    data, lines, i = {}, block.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":
            raise ValueError("unexpected indentation: " + line.strip())
        match = YAML_KEY_RE.match(line.rstrip())
        if not match:
            raise ValueError("not a `key: value` line: " + line.strip())
        key, rest = match.group(1), match.group(2)
        if key in data:
            raise ValueError("duplicate key " + key)
        if rest is not None and rest.strip():
            data[key] = _y_scalar(rest)
            continue
        nested = []
        while i < len(lines) and (not lines[i].strip() or lines[i][0] in " \t"):
            if lines[i].strip():
                nested.append(lines[i])
            i += 1
        if not nested:
            data[key] = None
        elif nested[0].lstrip().startswith("- "):
            if any(": " in n or n.rstrip().endswith(":") for n in nested):
                raise ValueError(f"{key}: a list of mappings is not supported")
            data[key] = [_y_scalar(n.lstrip()[2:]) for n in nested]
        else:
            sub = {}
            indent = len(nested[0]) - len(nested[0].lstrip())
            for n in nested:
                if len(n) - len(n.lstrip()) != indent:
                    raise ValueError(f"{key}: nesting deeper than one level is not supported")
                m = YAML_KEY_RE.match(n.strip())
                if not m:
                    raise ValueError(f"{key}: not a `key: value` line: " + n.strip())
                sub[m.group(1)] = _y_scalar(m.group(2) or "")
            data[key] = sub
    return data


def _y_text(s):
    if (s == "" or s != s.strip() or "\n" in s or ": " in s or " #" in s or s[0] in "-?:,[]{}#&*!|>'\"%@`"
            or s in ("true", "false", "null", "~") or re.fullmatch(r"-?\d+", s)):
        return json.dumps(s, ensure_ascii=False)
    return s


def _y_value(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_y_value(x) for x in v) + "]"
    return _y_text(str(v))


def dump_frontmatter(data):
    out = []
    for key, value in data.items():
        if isinstance(value, dict):
            if value:
                out.append(f"{key}:")
                out += [f"  {k}: {_y_value(v)}" for k, v in value.items()]
        else:
            out.append(f"{key}: {_y_value(value)}")
    return "\n".join(out) + "\n"


class Bundle:
    """The engine of an OKF bundle that PILOT writes (the wiki, the architecture): one entry per file, a YAML frontmatter
    (`type`, `title`, `description`, `status`, `verified`, and PILOT's own `pilot:` block with the finer
    status, the tickets and the verified commit), a prose body, and an `index.md` per folder this class keeps
    up to date. This class is the only writer of the frontmatter. The statuses a file holds are
    STATUSES; a subclass may derive more (the wiki's in-flight ones, from ticket labels), never written."""

    DIR = WIKI_DIR
    TITLE = "Wiki"
    ABSENT = "wiki-absent"
    ABSENT_HINT = "run /pilot-wiki (it turns the wiki module on and creates wiki/)"
    PATH_HINT = "<domain>/<id>.md, the id in lowercase letters, digits and dashes"
    STATUSES = WIKI_STATUSES
    OKF_STATUS = WIKI_OKF_STATUS
    DEFAULT_TYPE = WIKI_DEFAULT_TYPE
    DERIVED_NAMES = ("in-dev", "in-review", "in-qa", "verified")  # in-flight names a file never holds
    STATUSLESS = ("Vision", "Persona")  # types that carry no status: they promise no behavior
    NEVER_STAMPED = ("Vision", "Persona", "UserFlow")  # nothing in the code verifies them
    STAMP_STATUS = "implemented"  # a stamp is written only on an entry in this status

    def __init__(self, root=None, language=None):
        self.root = root or self.DIR
        self._language = language

    # ---- reading --------------------------------------------------------------------------
    def _concept_files(self):
        if not os.path.isdir(self.root):
            raise Refused({"ok": False, "reason": self.ABSENT, "dir": self.root,
                           "hint": self.ABSENT_HINT})
        found = []
        for base, _dirs, names in os.walk(self.root):
            found.extend(os.path.join(base, n) for n in names if n.endswith(".md") and n not in WIKI_RESERVED)
        return sorted(found)

    def _rel(self, path):
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    def parse(self):
        """Every concept file of the bundle as an entry (readable or not)."""
        entries = []
        for path in self._concept_files():
            rel = self._rel(path)
            stem = posixpath.splitext(posixpath.basename(rel))[0]
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            block, rest = split_frontmatter(text)
            entry = {"id": stem, "path": rel, "abs": path, "title": stem, "description": "", "type": "",
                     "status": "", "tickets": [], "verifiedAt": "", "verifiedBy": "", "verifiedCommit": "", "managed": False,
                     "fm": None, "rest": rest, "text": rest.strip(), "problems": []}
            entries.append(entry)
            if block is None:
                entry["problems"].append(("no-frontmatter", "an OKF concept starts with a `---` YAML block"))
                continue
            try:
                fm = parse_frontmatter(block)
            except ValueError as err:
                # valid OKF the script cannot read is fine for a concept it does not manage; only an entry that
                # carries a `pilot:` block must be readable (it is the script that rewrites it)
                if re.search(r"(?m)^pilot:", block):
                    entry["problems"].append(("bad-frontmatter", str(err)))
                continue
            entry["fm"] = fm
            self._read_fields(entry, fm)
        return entries

    def _read_fields(self, entry, fm):
        add = entry["problems"].append
        if not fm.get("type"):
            add(("missing-type", "`type` is the one required frontmatter key"))
        entry["type"] = str(fm.get("type") or "")
        entry["title"] = str(fm.get("title") or entry["id"])
        entry["description"] = str(fm.get("description") or "")
        pilot = fm.get("pilot")
        if pilot is None:
            return  # a concept PILOT does not manage: indexed, never checked
        if not isinstance(pilot, dict):
            add(("bad-pilot", "`pilot:` must be a block of `key: value` lines"))
            return
        entry["managed"] = True
        if not WIKI_ID_RE.match(entry["id"]):
            add(("bad-id", "the file name (the id) is lowercase letters, digits and dashes"))
        status = pilot.get("status")
        if not status:
            if entry["type"] not in self.STATUSLESS:
                add(("missing-status", "no `pilot.status`"))
        elif status not in self.STATUSES:
            add(("bad-status", f"status {status!r} is not one of {', '.join(self.STATUSES)}"
                 + (" (derived, never written)" if status in self.DERIVED_NAMES else "")))
        else:
            entry["status"] = status
            if (fm.get("status") or "stable") != self.OKF_STATUS[status]:  # OKF: no `status` means stable
                add(("status-mismatch", f"`status` is {fm.get('status') or 'absent (stable)'!r}, {self.OKF_STATUS[status]!r} expected for {status}"))
        tickets = pilot.get("tickets") or []
        if not isinstance(tickets, list) or not all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in tickets):
            add(("bad-tickets", "`pilot.tickets` is a list of ticket numbers, e.g. [12, 15]"))
        else:
            entry["tickets"] = list(tickets)
        verified = fm.get("verified")
        entry["verifiedAt"] = str(verified.get("at") or "") if isinstance(verified, dict) else ""
        entry["verifiedBy"] = str(verified.get("by") or "") if isinstance(verified, dict) else ""
        entry["verifiedCommit"] = str(pilot.get("verifiedCommit") or "")
        if bool(entry["verifiedAt"]) != bool(entry["verifiedCommit"]):
            add(("partial-stamp", "`verified.at` and `pilot.verifiedCommit` go together"))
        if not entry["description"]:
            add(("missing-description", "the index shows each entry's one-sentence `description`"))

    def _removal_refusal(self, entry):
        """(reason, hint) when an entry is never deleted, or None."""
        return None

    def _extra_citers(self, entry, entries):
        """Ids of entries that cite this one other than by a link."""
        return []

    @staticmethod
    def _view(entry):
        return {"id": entry["id"], "title": entry["title"], "description": entry["description"],
                "path": entry["path"], "status": entry["status"], "tickets": entry["tickets"],
                "verifiedAt": entry["verifiedAt"], "verifiedCommit": entry["verifiedCommit"]}

    def _find(self, entry_id):
        found = [e for e in self.parse() if e["id"] == entry_id]
        if not found:
            raise Refused({"ok": False, "reason": "entry-not-found", "id": entry_id})
        if len(found) > 1:
            raise Refused({"ok": False, "reason": "duplicate-id", "id": entry_id,
                           "paths": sorted(e["path"] for e in found)})
        return found[0]

    LIVE = ()  # statuses that are history, left out of a `--active` index and of a search
    ACTIVE_LEFT_OUT = ()  # types read on demand, never carried in a prompt: left out of a `--active` index too
    ACTIVE_LEFT_OUT_STATUS = ()  # statuses not yet in force: left out of a `--active` index, found by search and show

    def _left_out(self, entry):
        """Whether a `--active` index (what a phase prompt carries) leaves an entry out."""
        return (entry["status"] in self.LIVE or entry["status"] in self.ACTIVE_LEFT_OUT_STATUS
                or entry["type"] in self.ACTIVE_LEFT_OUT)
    MAX_DESCRIPTION = 160  # characters: the line an index shows
    MAX_WORDS = 400  # words of prose in one entry: one concept per file, short enough to open without cost
    ROW = ("id", "path", "description", "status")

    def _max_words(self, entry):
        return self.MAX_WORDS

    @staticmethod
    def _under(entry, under):
        under = (under or "").strip("/")
        return not under or entry["path"].startswith(under + "/")

    def _brief(self, entry):
        return {k: entry[k] for k in self.ROW}

    def _scoped(self, entry, app):
        """Whether an entry is in view for `app` (a bundle with no per-app content shows everything)."""
        return True

    def index(self, ticket=None, active=False, under=None, app=None):
        """Every entry; `active` keeps only what is in force and shrinks each row to id, path, description and
        status (a line an agent can carry in its prompt, then open the entries that bear on its task); `under`
        keeps the entries below one folder."""
        entries = self.parse()
        shown = [e for e in entries if (ticket is None or ticket in e["tickets"]) and self._under(e, under)
                 and self._scoped(e, app)
                 and not (active and self._left_out(e))]
        rows = [self._brief(e) if active else self._view(e) for e in shown]
        return {"ok": True, "dir": self.root, "entries": rows,
                "problems": sum(len(e["problems"]) for e in entries)}

    def outline(self, under="", active=False, app=None):
        """One level of the bundle: the sub-folders of `under` (each with its description and how many entries it
        holds below it) and the entries sitting directly in it. A fixed-size first look, however big the bundle."""
        under = (under or "").strip("/")
        counts, direct, known = {}, [], not under
        for e in self.parse():
            if (active and self._left_out(e)) or not self._scoped(e, app):
                continue
            folder = posixpath.dirname(e["path"])
            if under and not (folder == under or folder.startswith(under + "/")):
                continue
            known = True
            rest = folder[len(under):].lstrip("/")
            if rest:
                name = rest.split("/")[0]
                counts[name] = counts.get(name, 0) + 1
            else:
                direct.append(self._brief(e))
        if not known:
            raise Refused({"ok": False, "reason": "unknown-folder", "folder": under})
        folders = [{"path": posixpath.join(under, n), "description": self._folder_description(posixpath.join(under, n)),
                    "entries": counts[n]} for n in sorted(counts)]
        return {"ok": True, "dir": self.root, "under": under, "description": self._folder_description(under),
                "folders": folders, "entries": direct}

    # ---- search ---------------------------------------------------------------------------
    _STOP = frozenset("a an and are as at be by de des du el en et for from il in is la le les of on or the to un une "
                      "with".split())

    @classmethod
    def _terms(cls, text):
        folded = unicodedata.normalize("NFKD", str(text).lower())
        words = re.findall(r"[a-z0-9]+", "".join(c for c in folded if not unicodedata.combining(c)))
        return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if len(w) > 1 and w not in cls._STOP]

    def search(self, query, under="", limit=8, include_history=False, app=None):
        """The entries that best match some words, ranked (title, description, tags and id weigh more than the
        text; rarer words weigh more), each with a one-line extract. Lexical and deterministic."""
        terms = sorted(set(self._terms(query)))
        if not terms:
            raise Refused({"ok": False, "reason": "empty-query"})
        limit = max(1, min(int(limit), 25))
        pool = [e for e in self.parse() if self._under(e, under) and self._scoped(e, app)
                and (include_history or e["status"] not in self.LIVE)]
        docs = []
        for e in pool:
            tags = (e["fm"] or {}).get("tags") or []
            tags = tags if isinstance(tags, list) else [tags]
            fields = ((3, e["title"]), (2, e["description"]), (2, " ".join(map(str, tags))), (2, e["id"].replace("-", " ")),
                      (1, e["text"]))
            tf = {}
            for weight, text in fields:
                for t in self._terms(text):
                    tf[t] = tf.get(t, 0) + weight
            docs.append((e, tf))
        size = len(docs) or 1
        df = {t: sum(1 for _e, tf in docs if t in tf) for t in terms}
        scored = []
        for e, tf in docs:
            score = sum((1 + math.log(tf[t])) * math.log(1 + size / df[t]) for t in terms if t in tf)
            if score > 0:
                scored.append((-score, e["path"], e))
        scored.sort(key=lambda x: (x[0], x[1]))
        rows = [{**self._brief(e), "score": round(-neg, 2), "snippet": self._snippet(e, terms)}
                for neg, _p, e in scored[:limit]]
        return {"ok": True, "query": query, "total": len(scored), "results": rows}

    def _snippet(self, entry, terms):
        best, hits = "", 0
        for line in re.split(r"(?<=[.!?])\s+|\n+", entry["text"]):
            n = len(set(self._terms(line)) & set(terms))
            if n > hits:
                best, hits = line.strip(), n
        return best[:157] + "..." if len(best) > 160 else best

    # ---- links ----------------------------------------------------------------------------
    _LINK_RE = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")

    def _stems(self, entry):
        return [posixpath.splitext(posixpath.basename(t))[0] for t in self._LINK_RE.findall(entry["rest"])
                if not t.startswith(("http://", "https://"))]

    def _related(self, entry, entries):
        """What an entry cites and what cites it, inside the bundle; links that leave it are listed as paths."""
        by_id = {e["id"]: e for e in entries}
        links, external = [], []
        for target in self._LINK_RE.findall(entry["rest"]):
            if target.startswith(("http://", "https://")):
                continue
            stem = posixpath.splitext(posixpath.basename(target))[0]
            if stem == entry["id"]:
                continue
            if stem in by_id:
                other = by_id[stem]
                row = {"id": stem, "path": other["path"], "title": other["title"]}
                if row not in links:
                    links.append(row)
            elif target not in external:
                external.append(target)
        back = [{"id": e["id"], "path": e["path"], "title": e["title"]} for e in entries
                if e["id"] != entry["id"] and entry["id"] in self._stems(e)]
        return {"links": links, "backlinks": back, "external": external}

    # ---- folder descriptions --------------------------------------------------------------
    def _folder_description(self, folder):
        path = os.path.join(self.root, folder, "index.md")
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as handle:
            block, _rest = split_frontmatter(handle.read())
        try:
            fm = parse_frontmatter(block) if block is not None else {}
        except ValueError:
            return ""
        return str(fm.get("description") or "")

    def describe(self, folder, description):
        """Give a folder (or the bundle, with '') the one sentence an outline shows next to it."""
        folder = (folder or "").strip("/")
        description = " ".join(description.split())
        if not description or '"' in description or "\\" in description or len(description) > self.MAX_DESCRIPTION:
            raise Refused({"ok": False, "reason": "bad-description",
                           "hint": f"one sentence of at most {self.MAX_DESCRIPTION} characters, no quote or backslash"})
        entries = self.parse()
        if folder and not any(self._under(e, folder) for e in entries):
            raise Refused({"ok": False, "reason": "unknown-folder", "folder": folder})
        self._set_folder_description(folder, description)
        return {"ok": True, "folder": folder, "description": description, "changed": self.reindex(entries)}

    def _set_folder_description(self, folder, description):
        path = os.path.join(self.root, folder, "index.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self._index_head(folder, description) + "\n")

    @staticmethod
    def _index_head(folder, description):
        lines = []
        if folder == "":
            lines.append(f'okf_version: "{OKF_VERSION}"')
        if description:
            lines.append("description: " + json.dumps(description, ensure_ascii=False))
        return "---\n" + "\n".join(lines) + "\n---" if lines else ""

    @property
    def language(self):
        if self._language is None:
            self._language = read_language()
        return self._language

    def _language_findings(self, entries):
        """Warnings: an entry clearly written in English or French when the project's language is the other one."""
        if self.language not in LANG_WORDS:
            return []
        out = []
        for e in entries:
            found = detect_language(e["description"] + " " + e["text"])
            if found and found != self.language:
                out.append({"entry": e["id"], "path": e["path"], "level": "warn", "code": "other-language",
                            "message": f"written in {found}, the project's language is {self.language} (`language` in .pilot/state.json)"})
        return out

    def _size_findings(self, entries):
        """Warnings, never errors: a description longer than an index line, a concept too long to be one concept."""
        out = []
        for e in entries:
            where = {"entry": e["id"], "path": e["path"], "level": "warn"}
            if len(e["description"]) > self.MAX_DESCRIPTION:
                out.append({**where, "code": "long-description",
                            "message": f"{len(e['description'])} characters; an index line stays under {self.MAX_DESCRIPTION}"})
            words, limit = len(e["text"].split()), self._max_words(e)
            if words > limit:
                out.append({**where, "code": "long-entry",
                            "message": f"{words} words; one concept per file, split it or tighten it ({limit} at most)"})
        return out

    @staticmethod
    def _report(entries, findings):
        return {"ok": not [f for f in findings if f.get("level") != "warn"], "entries": len(entries), "findings": findings}

    # ---- index.md files -------------------------------------------------------------------
    def _generated_indexes(self, entries):
        """{folder relative to the root ('' for the root): the text its index.md should have}."""
        by_dir, dirs = {}, {""}
        for e in entries:
            d = posixpath.dirname(e["path"])
            by_dir.setdefault(d, []).append(e)
            while d:
                dirs.add(d)
                d = posixpath.dirname(d)
        out = {}
        for d in sorted(dirs):
            lines = ["# " + (posixpath.basename(d) or self.TITLE), ""]
            for sub in sorted(x for x in dirs if x and posixpath.dirname(x) == d):
                n = sum(1 for e in entries if e["path"].startswith(sub + "/"))
                count = f"{n} entr{'y' if n == 1 else 'ies'}"
                about = self._folder_description(sub)
                lines.append(f"* [{posixpath.basename(sub)}]({posixpath.basename(sub)}/) - " + (f"{about} ({count})" if about else count))
            for e in sorted(by_dir.get(d, []), key=lambda x: x["path"]):
                lines.append(f"* [{e['title']}]({posixpath.basename(e['path'])})" + (f" - {e['description']}" if e["description"] else ""))
            head = self._index_head(d, self._folder_description(d))
            out[d] = (head + "\n" if head else "") + "\n".join(lines) + "\n"
        return out

    def reindex(self, entries=None):
        """Write the index.md of every folder (and the root's, which carries `okf_version`); returns the files
        that changed. An index.md in a folder that no longer holds an entry is removed."""
        os.makedirs(self.root, exist_ok=True)  # turning a module on creates its folder: reindex is how
        entries = self.parse() if entries is None else entries
        wanted, changed = self._generated_indexes(entries), []
        for d, text in wanted.items():
            path = os.path.join(self.root, d, "index.md")
            old = None
            if os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    old = handle.read()
            if old != text:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(text)
                changed.append(self._rel(path))
        for base, _dirs, names in os.walk(self.root, topdown=False):
            d = os.path.relpath(base, self.root).replace(os.sep, "/")
            d = "" if d == "." else d
            if "index.md" in names and d not in wanted:
                os.remove(os.path.join(base, "index.md"))
                changed.append(posixpath.join(d, "index.md"))
            if d and not os.listdir(base):
                os.rmdir(base)
        return sorted(changed)

    def derive(self, entry, gh, cache):
        """The in-flight overlay of one entry, from its tickets: the most advanced of in-dev < in-review <
        in-qa among its open tickets, or `verified` for a stamped implemented entry whose feature story is done."""
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
            level = next((l[6:] for l in sorted(ticket["labels"]) if l.startswith("level:")), "")
            seen.append({"number": number, "state": ticket["state"], "status": status, "level": level})
            if ticket["state"] == "open":
                for lvl, group in ((1, WIKI_IN_DEV), (2, WIKI_IN_REVIEW), (3, WIKI_IN_QA)):
                    if status in group:
                        rank = max(rank, lvl)
            elif {"type:feature", "level:story", "status:done"} <= ticket["labels"]:
                verified = True
        overlay = ("", "in-dev", "in-review", "in-qa")[rank]
        if not overlay and verified and entry["status"] == "implemented" and entry["verifiedAt"]:
            overlay = "verified"
        shown = entry["status"] + (f" · {overlay}" if overlay else "")
        return {"id": entry["id"], "status": entry["status"], "derived": overlay, "display": shown,
                "tickets": seen}

    def _managed(self, entries):
        return [e for e in entries if e["managed"]]

    def status(self, gh, ids=()):
        entries = self._managed(self.parse())
        wanted = [e for e in entries if not ids or e["id"] in ids]
        missing = sorted(set(ids) - {e["id"] for e in wanted})
        if missing:
            raise Refused({"ok": False, "reason": "entry-not-found", "id": missing[0]})
        cache = {}
        return {"ok": True, "entries": [self.derive(e, gh, cache) for e in wanted]}

    def show(self, entry_id, gh):
        entry = self._find(entry_id)
        return {"ok": True, **self._view(entry), "type": entry["type"], "text": entry["text"], "derived": self.derive(entry, gh, {}),
                **self._related(entry, self.parse())}

    def lint(self, gh):
        """The mechanical checks (no judgment): an unreadable entry, a duplicate id, a stale index.md, a promise
        whose tickets are all closed, an implemented entry whose ticket went back before dev."""
        entries = self.parse()
        findings, seen, cache = [], {}, {}
        for e in entries:
            seen.setdefault(e["id"], []).append(e)
        for e in entries:
            where = {"entry": e["id"], "path": e["path"]}
            findings += [{**where, "code": c, "message": m} for c, m in e["problems"]]
            if len(seen[e["id"]]) > 1:
                findings.append({**where, "code": "duplicate-id", "message": "this id is used by %d files" % len(seen[e["id"]])})
            if not e["managed"] or e["status"] not in ("proposed", "specified", "implemented"):
                continue
            if e["status"] in ("proposed", "specified") and not e["tickets"]:
                findings.append({**where, "code": "no-ticket", "message": f"a {e['status']} entry lists no ticket"})
            states = []
            for number in e["tickets"]:
                if number not in cache:
                    cache[number] = gh.get_issue(number)
                raw = cache[number]
                if raw is None:
                    findings.append({**where, "code": "unknown-ticket", "message": f"#{number} does not exist"})
                    continue
                states.append((number, normalize(raw)))
            if e["status"] in ("proposed", "specified") and states and all(t["state"] == "closed" for _n, t in states):
                findings.append({**where, "code": "orphaned-promise",
                                 "message": "every ticket is closed but the entry is still " + e["status"]})
            if e["status"] == "implemented":
                for number, t in states:
                    if t["state"] == "open" and status_of(t["labels"]) in WIKI_PRE_DEV:
                        findings.append({**where, "code": "implemented-but-reopened",
                                         "message": f"#{number} is back at {status_of(t['labels'])}"})
        for d, text in self._generated_indexes(entries).items():
            path = os.path.join(self.root, d, "index.md")
            current = None
            if os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    current = handle.read()
            if current != text:
                findings.append({"path": self._rel(path), "code": "stale-index",
                                 "message": "run `python3 .pilot/pilot.py wiki reindex`"})
        return self._report(entries, findings + self._size_findings(entries) + self._language_findings(entries))

    def snapshot(self, gh):
        """Every managed entry as the dashboard's wiki document: frontmatter fields, derived status and the
        entry's text (shortened, then dropped, to keep the document under a database document's size)."""
        cache, rows = {}, []
        for e in self._managed(self.parse()):
            d = self.derive(e, gh, cache)
            rows.append({"id": e["id"], "type": e["type"], "hash": entry_hash(e), "title": e["title"], "description": e["description"], "path": e["path"],
                         "status": e["status"], "derived": d["derived"], "display": d["display"],
                         "tickets": e["tickets"], "verifiedAt": e["verifiedAt"], "verifiedBy": e["verifiedBy"], "text": e["text"]})
        doc = {"kind": "wiki", "repo": gh.repo, "at": now_iso(), "total": len(rows), "truncated": False, "entries": rows}
        return self._fit(doc, rows)

    @staticmethod
    def _fit(doc, rows):
        """Shorten, then drop, the entries' text until the document fits a database document."""
        full = [r["text"] for r in rows]
        for cap in (1500, 400, 0):
            for r, text in zip(rows, full):
                r["text"] = text[:cap]
            doc["truncated"] = any(len(t) > cap for t in full)
            if len(json.dumps(doc, ensure_ascii=False).encode("utf-8")) <= WIKI_SNAPSHOT_MAX_BYTES:
                break
        return doc

    # ---- writing --------------------------------------------------------------------------
    @staticmethod
    def _write(path, fm, rest):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("---\n" + dump_frontmatter(fm) + "---\n" + rest)

    def _editable(self, entry_id):
        entry = self._find(entry_id)
        if entry["fm"] is None:
            raise Refused({"ok": False, "reason": "unreadable-frontmatter", "id": entry_id,
                           "problems": [m for _c, m in entry["problems"]]})
        if not entry["managed"]:
            raise Refused({"ok": False, "reason": "not-a-pilot-entry", "id": entry_id})
        return entry

    def set(self, entry_id, status=None, add=(), remove=(), stamp=None, clear_stamp=False, title=None, description=None, by=None):
        """The only writer of an entry's frontmatter (unknown keys are kept as they are). `stamp` is the commit
        a lint verified the entry against; `clear_stamp` forgets it when the entry's text changed."""
        entry = self._editable(entry_id)
        if status is not None and status not in self.STATUSES:
            raise Refused({"ok": False, "reason": "bad-status", "expected": list(self.STATUSES),
                           **({"hint": ", ".join(self.DERIVED_NAMES) + " are derived, never written"} if self.DERIVED_NAMES else {})})
        if status is not None and entry["type"] in self.STATUSLESS:
            raise Refused({"ok": False, "reason": "status-not-allowed", "id": entry_id, "hint": f"a {entry['type']} carries no status"})
        if by is not None and by not in WIKI_VERIFIERS:
            raise Refused({"ok": False, "reason": "bad-verifier", "expected": list(WIKI_VERIFIERS)})
        if stamp:
            if entry["type"] in self.NEVER_STAMPED:
                raise Refused({"ok": False, "reason": "never-stamped", "id": entry_id, "hint": f"nothing in the code verifies a {entry['type']}"})
            if (status or entry["status"]) != self.STAMP_STATUS:
                raise Refused({"ok": False, "reason": "stamp-needs-status", "id": entry_id, "status": status or entry["status"],
                               "hint": f"an entry is verified when it is {self.STAMP_STATUS}"})
        fm = entry["fm"]
        pilot = dict(fm["pilot"])
        if status:
            pilot["status"] = status
            fm["status"] = self.OKF_STATUS[status]
        tickets = [n for n in entry["tickets"] if n not in set(remove)]
        tickets += [n for n in add if n not in tickets]
        pilot["tickets"] = tickets
        if title:
            fm["title"] = title
        if description:
            fm["description"] = description
        if clear_stamp:
            fm.pop("verified", None)
            pilot.pop("verifiedCommit", None)
        if stamp:
            fm["verified"] = {"by": by or WIKI_VERIFIER, "at": now_iso()}
            pilot["verifiedCommit"] = stamp
        fm["pilot"] = pilot
        self._write(entry["abs"], fm, entry["rest"])
        self.reindex()
        after = self._find(entry_id)
        return {"ok": True, "id": entry_id, "status": after["status"], "tickets": after["tickets"],
                "verifiedAt": after["verifiedAt"], "verifiedCommit": after["verifiedCommit"]}

    def _path_ok(self, rel):
        return True

    def add(self, path, title, description, status=None, tickets=(), body="", typ=None):
        """Create an entry: `<domain>/<id>.md` under the wiki root, then refresh the indexes."""
        rel = path.replace(os.sep, "/")
        stem = posixpath.splitext(posixpath.basename(rel))[0]
        if (not rel.endswith(".md") or rel.startswith("/") or ".." in rel.split("/")
                or posixpath.basename(rel) in WIKI_RESERVED or not WIKI_ID_RE.match(stem)):
            raise Refused({"ok": False, "reason": "bad-path", "path": path,
                           "hint": self.PATH_HINT})
        if not self._path_ok(rel):
            raise Refused({"ok": False, "reason": "bad-path", "path": path, "hint": self.PATH_HINT})
        kind = typ or self._type_of(rel)
        if kind in self.STATUSLESS:
            if status:
                raise Refused({"ok": False, "reason": "status-not-allowed", "hint": f"a {kind} carries no status"})
        elif status not in self.STATUSES:
            raise Refused({"ok": False, "reason": "bad-status", "expected": list(self.STATUSES)})
        if not title.strip() or not description.strip():
            raise Refused({"ok": False, "reason": "title-and-description-required"})
        os.makedirs(self.root, exist_ok=True)
        entries = self.parse()
        if any(e["id"] == stem for e in entries):
            raise Refused({"ok": False, "reason": "duplicate-id", "id": stem})
        target = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        fm = {"type": kind, "title": title.strip(), "description": description.strip()}
        if status:
            fm["status"] = self.OKF_STATUS[status]
        fm["pilot"] = ({"status": status} if status else {}) | {"tickets": list(tickets)}
        self._write(target, fm, ("\n" + body.strip() + "\n") if body.strip() else "")
        self.reindex()
        return {"ok": True, "id": stem, "path": rel, "status": status or ""}

    def _max_words(self, entry):
        return {"ADR": 600, "Architecture": 800, "Runbook": 1500, "UserFlow": 800}.get(entry["type"], self.MAX_WORDS)

    def _type_of(self, rel):
        return self.DEFAULT_TYPE

    def remove(self, entry_id):
        """Delete an entry: a retired entry is gone, not kept as history. Refused while another entry cites it, and
        for the entries a bundle never deletes."""
        entry = self._editable(entry_id)
        refusal = self._removal_refusal(entry)
        if refusal:
            raise Refused({"ok": False, "reason": refusal[0], "id": entry_id, "hint": refusal[1]})
        entries = self.parse()
        cited = sorted({c["id"] for c in self._related(entry, entries)["backlinks"]} | set(self._extra_citers(entry, entries)))
        if cited:
            raise Refused({"ok": False, "reason": "cited", "id": entry_id, "citedBy": cited,
                           "hint": "edit or remove the entries that cite it first"})
        os.remove(entry["abs"])
        self.reindex()
        return {"ok": True, "id": entry_id, "removed": entry["path"]}

    def migrate(self):
        """Convert a wiki written in the earlier format (several `## Title {#id}` entries per page, each followed by
        a `<!-- wiki: ... -->` line) into OKF files, one per entry, and write the indexes."""
        head_re = re.compile(r"^##\s+(.+?)\s*\{#([a-z0-9][a-z0-9-]*)\}\s*$")
        meta_re = re.compile(r"^<!--\s*wiki:\s*(.*?)\s*-->\s*$")
        if not os.path.isdir(self.root):
            raise Refused({"ok": False, "reason": "wiki-absent", "dir": self.root})
        created, removed, skipped = [], [], []
        for base, _dirs, names in sorted(os.walk(self.root)):
            for name in sorted(names):
                if not name.endswith(".md") or name in WIKI_RESERVED:
                    continue
                path = os.path.join(base, name)
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                if split_frontmatter(text)[0] is not None:
                    continue
                lines, found, fenced = text.split("\n"), [], False
                for n, line in enumerate(lines):
                    if line.lstrip().startswith(("```", "~~~")):
                        fenced = not fenced
                    head = None if fenced else head_re.match(line)
                    if head and n + 1 < len(lines) and meta_re.match(lines[n + 1]):
                        found.append((n, head.group(1), head.group(2), dict(re.findall(r"(\w+)=(\S*)", meta_re.match(lines[n + 1]).group(1)))))
                rel_dir = posixpath.dirname(self._rel(path)) or "general"
                if not found and name == "README.md" and base == self.root:
                    os.remove(path)
                    removed.append(self._rel(path))
                    continue
                if not found:
                    skipped.append(self._rel(path))
                    continue
                for k, (n, title, eid, meta) in enumerate(found):
                    end = found[k + 1][0] if k + 1 < len(found) else len(lines)
                    cut = next((m for m in range(n + 2, end) if lines[m].startswith("## ")), end)
                    body = "\n".join(lines[n + 2:cut]).strip()
                    first = re.split(r"(?<=[.!?])\s", body.replace("\n", " "), maxsplit=1)[0].strip() if body else ""
                    status = meta.get("status", "")
                    if status not in self.STATUSES:
                        skipped.append(f"{self._rel(path)}#{eid} (status {status!r})")
                        continue
                    target = os.path.join(self.root, *rel_dir.split("/"), eid + ".md")
                    if os.path.exists(target):
                        skipped.append(f"{self._rel(path)}#{eid} (already exists)")
                        continue
                    tickets = [int(t) for t in re.findall(r"#(\d+)", meta.get("tickets", ""))]
                    pilot = {"status": status, "tickets": tickets}
                    fm = {"type": self.DEFAULT_TYPE, "title": title, "description": (first or title)[:300],
                          "status": self.OKF_STATUS[status]}
                    if meta.get("verifiedAt") and meta.get("verifiedCommit"):
                        fm["verified"] = {"by": WIKI_VERIFIER, "at": meta["verifiedAt"]}
                        pilot["verifiedCommit"] = meta["verifiedCommit"]
                    fm["pilot"] = pilot
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    self._write(target, fm, ("\n" + body + "\n") if body else "")
                    created.append(self._rel(target))
                os.remove(path)
                removed.append(self._rel(path))
        changed = self.reindex()
        return {"ok": True, "created": created, "removed": removed, "skipped": skipped, "indexes": changed}


class Wiki(Bundle):
    """The functional wiki: statuses proposed / specified / implemented, derived from tickets. A Vision or a Persona
    carries no status."""
    FOLDER_TYPES = {"persona": "Persona", "user-flow": "UserFlow"}

    def _removal_refusal(self, entry):
        if entry["type"] == "Vision":
            return ("vision-never-removed", "the vision is edited, never removed")
        return None

    def _extra_citers(self, entry, entries):
        """A flow names its personas on a `Personas:` line, not with links."""
        if entry["type"] != "Persona":
            return []
        out = []
        for e in entries:
            if e["type"] == "UserFlow":
                for line in e["rest"].splitlines():
                    if line.strip().startswith("Personas:") and entry["id"] in [x.strip() for x in line.split(":", 1)[1].split(",")]:
                        out.append(e["id"])
        return out

    def _type_of(self, rel):
        return self.FOLDER_TYPES.get(rel.split("/")[0], self.DEFAULT_TYPE) if "/" in rel else self.DEFAULT_TYPE


ARCH_STATUSES = ("proposed", "accepted", "superseded")
ARCH_OKF_STATUS = {"proposed": "draft", "accepted": "stable", "superseded": "deprecated"}  # OKF has no "superseded": a replaced entry is `deprecated` there


class Architecture(Bundle):
    """The architecture module's bundle: `architecture/overview.md`, `guidelines/<id>.md` (rules to respect),
    `reference/<id>.md` (how the code is built today: stack and versions, data model, structure; `--verify` checks it, the overview and the accepted
    guidelines and ADRs against the code, a human arbitrating each divergence), `adr/<NNNN-title>.md` (why a choice was made) and `runbooks/<id>.md`
    (how to operate: deploy, onboard; read on demand, never carried in a prompt).
    Same OKF files, same frontmatter writer, same indexes as the wiki; its own statuses (an ADR is accepted, then
    deprecated or superseded by a later one, and never edited in between), no ticket-driven checks."""
    TITLE = "Architecture"
    ABSENT = "architecture-absent"
    ABSENT_HINT = "run /pilot-architecture (it turns the architecture module on and creates architecture/)"
    PATH_HINT = ("overview.md, guidelines/<id>.md, reference/<id>.md, adr/<NNNN-title>.md or runbooks/<id>.md; for one app of a monorepo, the same under "
                 "apps/<app>/ with its overview named <app>-overview.md (an id is unique across the whole bundle)")

    @staticmethod
    def _layout_ok(parts, app=None):
        if len(parts) == 1:
            return parts[0] == ("overview.md" if app is None else f"{app}-overview.md")
        return len(parts) == 2 and parts[0] in ("guidelines", "reference", "adr", "runbooks")

    def _path_ok(self, rel):
        parts = rel.split("/")
        if parts[0] == "apps":
            return len(parts) >= 3 and bool(WIKI_ID_RE.match(parts[1])) and self._layout_ok(parts[2:], parts[1])
        return self._layout_ok(parts)

    def _scoped(self, entry, app):
        """The transversal entries plus those of one app (`apps/<app>/…`); none of the other apps'."""
        if not app:
            return True
        parts = entry["path"].split("/")
        return parts[0] != "apps" or (len(parts) > 1 and parts[1] == app)

    INVENTORY_MAX = 200

    def inventory(self, root="."):
        """What the project already has that could become architecture entries, as outlines only — a path, a size, a
        title, a first line — so a first look costs nothing however much there is: the apps, `docs/**` and each app's own
        `README.md`/`CLAUDE.md`/`docs/**`, and whether the `PILOT:ARCHITECTURE`/`PILOT:COMMANDS` blocks of `CLAUDE.md`
        and `README.md` are placeholders, pointers or the project's own content."""
        apps = set()
        apps_dir = os.path.join(root, "apps")
        if os.path.isdir(apps_dir):
            apps |= {n for n in os.listdir(apps_dir) if os.path.isdir(os.path.join(apps_dir, n)) and not n.startswith(".")}
        try:
            with open(os.path.join(root, STATE_PATH), encoding="utf-8") as handle:
                listed = json.load(handle).get("apps")
            apps |= {a["name"] for a in listed if isinstance(a, dict) and a.get("name")} if isinstance(listed, list) else set()
        except (OSError, ValueError, AttributeError):
            pass
        found = []
        candidates = []
        for base, _dirs, names in os.walk(os.path.join(root, "docs")):
            candidates += [os.path.join(base, n) for n in names if n.endswith(".md")]
        for app in sorted(apps):
            for name in ("README.md", "CLAUDE.md"):
                candidates.append(os.path.join(apps_dir, app, name))
            for base, _dirs, names in os.walk(os.path.join(apps_dir, app, "docs")):
                candidates += [os.path.join(base, n) for n in names if n.endswith(".md")]
        for path in sorted(set(candidates)):
            if not os.path.isfile(path):
                continue
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            title = next((l.lstrip("# ").strip() for l in text.split("\n") if l.startswith("#")), "")
            first = next((l.strip() for l in text.split("\n") if l.strip() and not l.startswith(("#", "---", "<!--"))), "")
            parts = rel.split("/")
            found.append({"path": rel, "bytes": len(text.encode("utf-8")), "title": title[:120], "summary": first[:160],
                          "app": parts[1] if parts[0] == "apps" and len(parts) > 2 else ""})
        blocks = {}
        for name in ("CLAUDE.md", "README.md"):
            try:
                with open(os.path.join(root, name), encoding="utf-8") as handle:
                    text = handle.read()
            except OSError:
                continue
            for marker in ("ARCHITECTURE", "COMMANDS"):
                m = re.search(r"<!-- PILOT:%s:START -->\n(.*?)\n<!-- PILOT:%s:END -->" % (marker, marker), text, flags=re.S)
                if not m:
                    state = "absent"
                elif "pilot-init-archi" in m.group(1):
                    state = "placeholder"
                elif "/pilot-architecture" in m.group(1) or "architecture/" in m.group(1):
                    state = "pointer"
                else:
                    state = "filled"
                blocks[f"{name}:{marker}"] = state
        return {"ok": True, "apps": sorted(apps), "docs": found[:self.INVENTORY_MAX], "truncated": len(found) > self.INVENTORY_MAX,
                "blocks": blocks}

    def next_number(self):
        """The next free ADR number, counted across the whole bundle (an app's ADRs share the sequence)."""
        used = [int(m.group(1)) for e in self.parse() for m in [re.match(r"(\d{4})-", e["id"])] if m]
        return {"ok": True, "next": "%04d" % (max(used, default=0) + 1)}
    DIR = ARCH_DIR
    STATUSES = ARCH_STATUSES
    STATUSLESS = ()
    NEVER_STAMPED = ()
    STAMP_STATUS = "accepted"
    OKF_STATUS = ARCH_OKF_STATUS
    DEFAULT_TYPE = "Guideline"
    DERIVED_NAMES = ()
    LIVE = ("superseded",)

    def _removal_refusal(self, entry):
        if entry["id"] == "overview":
            return ("overview-never-removed", "the root overview is edited, never removed")
        if entry["type"] == "ADR" and entry["status"] == "accepted":
            return ("accepted-adr", "an accepted ADR is retired by a new one that supersedes it (`/pilot-architecture --adr`)")
        if entry["status"] == "superseded":
            return ("superseded-is-history", "a superseded ADR stays as the history of the decision that replaced it")
        return None
    ACTIVE_LEFT_OUT = ("Runbook",)
    ACTIVE_LEFT_OUT_STATUS = ("proposed",)

    def _type_of(self, rel):
        parts = rel.split("/")
        stem = posixpath.splitext(parts[-1])[0]
        if "adr" in parts[:-1]:
            return "ADR"
        if "runbooks" in parts[:-1]:
            return "Runbook"
        if "reference" in parts[:-1]:
            return "Reference"
        return "Architecture" if stem == "overview" or stem.endswith("-overview") else self.DEFAULT_TYPE

    def show(self, entry_id, gh=None):
        entry = self._find(entry_id)
        pilot = (entry["fm"] or {}).get("pilot") or {}
        return {"ok": True, **self._view(entry), "type": entry["type"], "text": entry["text"],
                "supersedes": pilot.get("supersedes") or "", "supersededBy": pilot.get("supersededBy") or "",
                **self._related(entry, self.parse())}

    def snapshot(self, repo):
        """Every managed entry as the dashboard's architecture document (no GitHub call): frontmatter fields, the
        supersession links and the entry's text, shortened to fit."""
        rows = []
        for e in self._managed(self.parse()):
            fm = e["fm"]["pilot"] if isinstance(e.get("fm"), dict) and isinstance(e["fm"].get("pilot"), dict) else {}
            rows.append({"id": e["id"], "title": e["title"], "description": e["description"], "path": e["path"],
                         "status": e["status"], "tickets": e["tickets"], "supersedes": str(fm.get("supersedes") or ""),
                         "supersededBy": str(fm.get("supersededBy") or ""), "verifiedAt": e["verifiedAt"], "verifiedBy": e["verifiedBy"], "text": e["text"]})
        doc = {"kind": "architecture", "repo": repo, "at": now_iso(), "total": len(rows), "truncated": False,
               "entries": rows}
        return self._fit(doc, rows)

    def supersede(self, new_id, old_id):
        """A new ADR replaces an accepted one: the old becomes `superseded` (and links forward), the new links back."""
        if new_id == old_id:
            raise Refused({"ok": False, "reason": "same-entry", "id": new_id})
        new, old = self._editable(new_id), self._editable(old_id)
        if old["status"] != "accepted":
            raise Refused({"ok": False, "reason": "not-accepted", "id": old_id, "status": old["status"],
                           "hint": "only an accepted entry is superseded"})
        if new["status"] not in ("proposed", "accepted"):
            raise Refused({"ok": False, "reason": "cannot-supersede-with", "id": new_id, "status": new["status"]})
        old_fm, new_fm = old["fm"], new["fm"]
        old_fm["status"] = self.OKF_STATUS["superseded"]
        old_fm["pilot"] = {**old_fm["pilot"], "status": "superseded", "supersededBy": new_id}
        new_fm["pilot"] = {**new_fm["pilot"], "supersedes": old_id}
        self._write(old["abs"], old_fm, old["rest"])
        self._write(new["abs"], new_fm, new["rest"])
        self.reindex()
        return {"ok": True, "id": new_id, "supersedes": old_id}

    def lint(self, gh=None):
        """The mechanical checks (no judgment, no GitHub): an unreadable entry, a duplicate id, a stale index.md, and
        supersession that does not hold together (a superseded entry with no successor, a link to nothing)."""
        entries = self.parse()
        findings, seen = [], {}
        for e in entries:
            seen.setdefault(e["id"], []).append(e)
        by_id = {e["id"]: e for e in entries if e["managed"]}
        for e in entries:
            where = {"entry": e["id"], "path": e["path"]}
            findings += [{**where, "code": c, "message": m} for c, m in e["problems"]]
            if len(seen[e["id"]]) > 1:
                findings.append({**where, "code": "duplicate-id", "message": "this id is used by %d files" % len(seen[e["id"]])})
            if not e["managed"]:
                continue
            pilot = e["fm"]["pilot"]
            by, sup = pilot.get("supersededBy") or "", pilot.get("supersedes") or ""
            if e["status"] == "superseded" and not by:
                findings.append({**where, "code": "missing-supersededBy", "message": "a superseded entry names the one that replaces it"})
            if by and (by not in by_id or by_id[by]["fm"]["pilot"].get("supersedes") != e["id"]):
                findings.append({**where, "code": "supersession-mismatch", "message": f"{by} does not say it supersedes this entry"})
            if by and e["status"] != "superseded":
                findings.append({**where, "code": "supersession-mismatch", "message": "supersededBy is set but the status is not superseded"})
            if sup and (sup not in by_id or by_id[sup]["status"] != "superseded" or by_id[sup]["fm"]["pilot"].get("supersededBy") != e["id"]):
                findings.append({**where, "code": "supersession-mismatch", "message": f"{sup} is not a superseded entry pointing back here"})
        for d, text in self._generated_indexes(entries).items():
            path = os.path.join(self.root, d, "index.md")
            current = None
            if os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    current = handle.read()
            if current != text:
                findings.append({"path": self._rel(path), "code": "stale-index", "message": "run `python3 .pilot/pilot.py arch reindex`"})
        return self._report(entries, findings + self._size_findings(entries) + self._language_findings(entries))

    def migrate(self):
        raise Refused({"ok": False, "reason": "not-applicable", "hint": "the architecture bundle has no earlier format"})


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
    try:
        phases = sorted(w for w, wf in load_workflows().items() if (wf.get("contract") or {}).get("claims"))
    except Refused:
        phases = []
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
                   choices=["fresh", "resume-orphaned", "resume-cleared"])
    p = sub.add_parser("set")
    p.add_argument("issue", type=int)
    p.add_argument("--status", help="a status name (e.g. building) or 'none'")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--assign-me", action="store_true")
    group.add_argument("--unassign", action="store_true")
    p.add_argument("--add", action="append", default=[])
    p.add_argument("--remove", action="append", default=[])
    p.add_argument("--close", action="store_true")
    p.add_argument("--pr", type=int, help="the open PR that closes this ticket, forwarded in the event")
    p = sub.add_parser("proto-pack")
    p.add_argument("issue", type=int, help="the prototype's run issue")
    p.add_argument("--html", required=True, help="the mockup, one self-contained HTML file")
    p.add_argument("--out", required=True, help="directory for the documents to write to the cockpit")
    p.add_argument("--brief")
    p.add_argument("--height", type=int)
    p = sub.add_parser("event")
    p.add_argument("issues", type=int, nargs="+")
    p.add_argument("--action", required=True, help="what happened, e.g. created or approved")
    p.add_argument("--phase", help="e.g. discovery")
    p = sub.add_parser("snapshot")
    p.add_argument("--out", help="write the document to this file and print only a summary (with `history_failed`: the tickets whose stage history could not be read)")
    p = sub.add_parser("doctor")
    p.add_argument("--verbose", action="store_true", help="list every check, not only failures")
    p.add_argument("--no-wiki", action="store_true", help="skip the wiki check (/pilot-wiki repairing a missing wiki/)")
    p = sub.add_parser("flow")
    p.add_argument("action", choices=["doc"], help="doc: the dashboard's `flowRuns` document of a run of a user flow")
    p.add_argument("--in", dest="input", required=True, metavar="FILE", help='{"flow": ID, "personas": [each persona run], "report": the consolidation, "reportUrl": …}')
    p.add_argument("--out", help="write the document to this file and print only a summary")
    p.add_argument("--dir", default=WIKI_DIR, help="the wiki folder")
    p = sub.add_parser("module")
    p.add_argument("action", choices=["list", "enable", "disable"])
    p.add_argument("name", nargs="?", choices=list(MODULES))
    p.add_argument("--with-requires", action="store_true", help="enable: turn the modules it needs on too")
    def index_flags(w, app=False):
        if app:
            w.add_argument("--app", metavar="APP", help="the transversal entries plus those of this app (apps/<APP>/…)")
        w.add_argument("--active", action="store_true", help="only what is in force, one short row each")
        w.add_argument("--under", metavar="FOLDER", help="only the entries below this folder")
        w.add_argument("--depth", type=int, choices=[1], help="one level: the sub-folders (description, entry count) and the entries directly here")

    def read_cmds(ws, app=False):
        w = ws.add_parser("search", help="the entries that best match some words, ranked, with an extract")
        w.add_argument("query")
        if app:
            w.add_argument("--app", metavar="APP", help="the transversal entries plus those of this app")
        w.add_argument("--under", metavar="FOLDER")
        w.add_argument("--limit", type=int, default=8)
        w.add_argument("--all", action="store_true", help="include entries that are history (superseded)")
        w = ws.add_parser("describe", help="the one sentence an outline shows next to a folder ('' for the bundle)")
        w.add_argument("folder")
        w.add_argument("description")

    p = sub.add_parser("contract", help="a workflow's contract (consumes, claims, produces), or all of them and the check that they compose")
    p.add_argument("workflow", nargs="?")
    p = sub.add_parser("workflow", help="the workflows as data: list them, show one (or one step), check them")
    p.add_argument("action", choices=["list", "show", "check"])
    p.add_argument("id", nargs="?")
    p.add_argument("--step", help="show: one step, in the form a runner needs (id or number)")
    p = sub.add_parser("run", help="a run of a workflow: its state is one JSON comment on its issue")
    rs = p.add_subparsers(dest="run_cmd", required=True)
    w = rs.add_parser("start", parents=[common])
    w.add_argument("workflow")
    w.add_argument("--issue", type=int, help="the ticket it works (default: a new `run` issue)")
    w.add_argument("--title")
    w.add_argument("--data", help="JSON object kept in the run (e.g. the executant)")
    w = rs.add_parser("show", parents=[common])
    w.add_argument("issue", type=int)
    w = rs.add_parser("note", parents=[common], help="record an assumption, or a value later steps need")
    w.add_argument("issue", type=int)
    w.add_argument("--assumption")
    w.add_argument("--data", help="JSON object merged into the run's data")
    w = rs.add_parser("advance", parents=[common], help="the next step, decided by the workflow's data")
    w.add_argument("issue", type=int)
    w.add_argument("--result", required=True, help="ok | skip | loop | fail | reject:<label>")
    w.add_argument("--note")
    w = rs.add_parser("resume", parents=[common])
    w.add_argument("issue", type=int)
    w = rs.add_parser("end", parents=[common])
    w.add_argument("issue", type=int)
    w.add_argument("--result", help="e.g. accepted, rejected, ok, ko")
    w.add_argument("--record", help="a JSON file kept in the run's last comment (a Recette's record)")
    p = sub.add_parser("ticket", help="create a ticket, or the two human closings of one")
    ts = p.add_subparsers(dest="ticket_cmd", required=True)
    w = ts.add_parser("create", parents=[common])
    w.add_argument("--level", required=True, choices=list(LEVELS))
    w.add_argument("--type", required=True, choices=["feature", "tech"], dest="kind")
    w.add_argument("--title", required=True)
    w.add_argument("--body", default="")
    w.add_argument("--status", required=True)
    w.add_argument("--parent", type=int)
    w.add_argument("--priority", choices=["P0", "P1", "P2"])
    w.add_argument("--label", action="append", default=[], help="express, fix, gap")
    for name in ("close-forming", "drop", "merged"):
        w = ts.add_parser(name, parents=[common])
        w.add_argument("issue", type=int)
    p = sub.add_parser("pr", help="open a PR, read its CI verdict, merge it once the CI is green")
    ps = p.add_subparsers(dest="pr_cmd", required=True)
    w = ps.add_parser("open", parents=[common])
    w.add_argument("--branch", required=True)
    w.add_argument("--title", required=True)
    w.add_argument("--body", default="")
    w.add_argument("--base", default="main")
    w = ps.add_parser("ci", parents=[common])
    w.add_argument("number", type=int)
    w = ps.add_parser("merge", parents=[common])
    w.add_argument("number", type=int)
    w.add_argument("--method", choices=["squash", "rebase", "merge"], default="squash")
    p = sub.add_parser("config", help="read or write one key of .pilot/state.json (commands.test, language, …)")
    p.add_argument("action", choices=["get", "set"])
    p.add_argument("key")
    p.add_argument("value", nargs="?")
    p = sub.add_parser("derive", help="a split story's status from its tasks, an epic's from its stories")
    p.add_argument("issue", type=int)
    p = sub.add_parser("labels", help="create or update every PILOT label, or move a v5 project's tickets to the v6 labels")
    p.add_argument("action", choices=["sync", "migrate"])
    p.add_argument("--apply", action="store_true", help="migrate: write the changes (default: a dry run)")
    p = sub.add_parser("check", help="run one code check of a workflow step")
    p.add_argument("id")
    p.add_argument("--arg", action="append", default=[], metavar="KEY=VALUE", help="what the check reads (paths, JSON files, ids)")
    p.add_argument("--run", type=int, help="the run whose data the check may read")
    p = sub.add_parser("judge", help="validate a judge's answers: every question answered twice, with a quote, passes agreeing")
    p.add_argument("id")
    p.add_argument("--input", required=True, help="the JSON file of the two passes")
    p = sub.add_parser("wiki")
    p.add_argument("--dir", default=WIKI_DIR, help="the wiki directory (default: wiki)")
    ws = p.add_subparsers(dest="bundle_cmd", required=True)
    read_cmds(ws)
    w = ws.add_parser("index", help="every entry: id, path, description, status, tickets, stamp (no GitHub call)")
    w.add_argument("--ticket", type=int, help="only the entries that list this ticket")
    index_flags(w)
    ws.add_parser("reindex", help="write the index.md of every folder (OKF progressive disclosure)")
    w = ws.add_parser("show", parents=[common], help="one entry's text and derived status")
    w.add_argument("id")
    w = ws.add_parser("status", parents=[common], help="the derived (in-flight) status of entries, from their tickets")
    w.add_argument("ids", nargs="*")
    ws.add_parser("lint", parents=[common], help="mechanical checks, no judgment")
    w = ws.add_parser("snapshot", parents=[common], help="every entry as the dashboard's wiki document")
    w.add_argument("--out", help="write the document to this file and print only a summary")
    w = ws.add_parser("add", help="create an entry file <domain>/<id>.md (and refresh the indexes)")
    w.add_argument("path", help="path under the wiki directory, e.g. search/search-by-name.md (the file name is the id)")
    w.add_argument("--title", required=True)
    w.add_argument("--description", required=True, help="one sentence, shown in the index")
    w.add_argument("--status", choices=list(WIKI_STATUSES), help="required, except for a Vision or a Persona (they carry none)")
    w.add_argument("--type", default=None, help="default: set by the folder (persona/, user-flow/), else Behavior")
    w.add_argument("--ticket", type=int, action="append", default=[])
    w.add_argument("--body", default="")
    w = ws.add_parser("set", help="rewrite an entry's frontmatter (the only writer of it)")
    w.add_argument("id")
    w.add_argument("--status", choices=list(WIKI_STATUSES))
    w.add_argument("--title")
    w.add_argument("--description")
    w.add_argument("--add-ticket", type=int, action="append", default=[])
    w.add_argument("--remove-ticket", type=int, action="append", default=[])
    w.add_argument("--stamp", metavar="COMMIT", help="verified = now, pilot.verifiedCommit = COMMIT")
    w.add_argument("--by", choices=list(WIKI_VERIFIERS), help="who verified the entry (default: process:pilot-wiki, a lint)")
    w.add_argument("--clear-stamp", action="store_true", help="forget the stamp (the entry's text changed)")
    w = ws.add_parser("remove", help="delete an entry (refused while another entry cites it)")
    w.add_argument("id")
    ws.add_parser("migrate", help="convert a wiki from the earlier multi-entry page format to OKF files")
    p = sub.add_parser("arch")
    p.add_argument("--dir", default=ARCH_DIR, help="the architecture directory (default: architecture)")
    ws = p.add_subparsers(dest="bundle_cmd", required=True)
    read_cmds(ws, app=True)
    w = ws.add_parser("index", help="every entry: id, path, description, status (no GitHub call)")
    w.add_argument("--ticket", type=int, help=argparse.SUPPRESS)
    index_flags(w, app=True)
    ws.add_parser("reindex", help="write the index.md of every folder")
    w = ws.add_parser("snapshot", help="every entry as the dashboard's architecture document (no GitHub call)")
    w.add_argument("--out", help="write the document to this file and print only a summary")
    ws.add_parser("next-number", help="the next free ADR number, counted across the whole bundle")
    ws.add_parser("inventory", help="what the project already has that could become entries: apps, docs, the CLAUDE.md/README.md blocks (outlines only)")
    w = ws.add_parser("show", help="one entry's text; an ADR also its supersession")
    w.add_argument("id")
    ws.add_parser("lint", help="mechanical checks, no judgment")
    w = ws.add_parser("add", help="create an entry file (overview.md, guidelines/<id>.md, reference/<id>.md, adr/<NNNN-title>.md or runbooks/<id>.md)")
    w.add_argument("path")
    w.add_argument("--title", required=True)
    w.add_argument("--description", required=True, help="one sentence, shown in the index")
    w.add_argument("--status", required=True, choices=list(ARCH_STATUSES))
    w.add_argument("--type", default=None)
    w.add_argument("--ticket", type=int, action="append", default=[])
    w.add_argument("--body", default="")
    w = ws.add_parser("set", help="rewrite an entry's frontmatter (the only writer of it)")
    w.add_argument("id")
    w.add_argument("--status", choices=list(ARCH_STATUSES))
    w.add_argument("--title")
    w.add_argument("--description")
    w.add_argument("--add-ticket", type=int, action="append", default=[])
    w.add_argument("--remove-ticket", type=int, action="append", default=[])
    w.add_argument("--stamp", metavar="COMMIT", help="verified = now, pilot.verifiedCommit = COMMIT")
    w.add_argument("--by", choices=list(WIKI_VERIFIERS), help="who verified the entry (default: process:pilot-wiki)")
    w.add_argument("--clear-stamp", action="store_true")
    w = ws.add_parser("remove", help="delete an entry (refused while another entry cites it)")
    w.add_argument("id")
    w = ws.add_parser("supersede", help="an accepted ADR is replaced by a new one")
    w.add_argument("new")
    w.add_argument("old")
    for name in ("flag", "unflag"):
        p = sub.add_parser(name)
        p.add_argument("issue", type=int)
        p.add_argument("--comment", required=True)
    return parser


def run_bundle(args, gh):
    wiki = (Wiki if args.cmd == "wiki" else Architecture)(args.dir)
    if args.bundle_cmd == "index":
        app = getattr(args, "app", None)
        if args.depth:
            return wiki.outline(args.under or "", args.active, app)
        return wiki.index(args.ticket, args.active, args.under, app)
    if args.bundle_cmd == "next-number":
        return wiki.next_number()
    if args.bundle_cmd == "inventory":
        return wiki.inventory()
    if args.bundle_cmd == "search":
        return wiki.search(args.query, args.under or "", args.limit, args.all, getattr(args, "app", None))
    if args.bundle_cmd == "describe":
        return wiki.describe(args.folder, args.description)
    if args.bundle_cmd == "show":
        return wiki.show(args.id, gh)
    if args.bundle_cmd == "status":
        return wiki.status(gh, args.ids)
    if args.bundle_cmd == "lint":
        return wiki.lint(gh)
    if args.bundle_cmd == "snapshot":
        doc = wiki.snapshot(gh) if args.cmd == "wiki" else wiki.snapshot(args.repo or resolve_repo())
        if not args.out:
            return doc
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(doc, handle, ensure_ascii=False, separators=(",", ":"))
        return {"ok": True, "file": args.out, "total": doc["total"], "truncated": doc["truncated"]}
    if args.bundle_cmd == "add":
        return wiki.add(args.path, args.title, args.description, args.status, args.ticket, args.body, args.type)
    if args.bundle_cmd == "reindex":
        return {"ok": True, "changed": wiki.reindex()}
    if args.bundle_cmd == "remove":
        return wiki.remove(args.id)
    if args.bundle_cmd == "migrate":
        return wiki.migrate()
    if args.bundle_cmd == "supersede":
        return wiki.supersede(args.new, args.old)
    return wiki.set(args.id, args.status, args.add_ticket, args.remove_ticket, args.stamp, args.clear_stamp,
                    args.title, args.description, args.by)


def run_contract(args):
    wfs = load_workflows()
    if args.workflow:
        return workflow_contract(wfs, args.workflow)
    problems = composition_problems(wfs)
    return {"ok": not problems, "workflows": {w: workflow_contract(wfs, w) for w in sorted(wfs) if (wfs[w].get("contract") or {})},
            "external": [list(t) for t in EXTERNAL], "sinks": list(SINKS), "problems": problems}


def run_workflow(args):
    wfs = load_workflows()
    if args.action == "list":
        return {"ok": True, "workflows": [{"id": w, "title": wf["title"], "category": wf["category"], "steps": len(wf["steps"])}
                                          for w, wf in sorted(wfs.items())]}
    if args.action == "check":
        problems = workflow_problems(wfs)
        return {"ok": not problems, "workflows": len(wfs), "problems": problems}
    if args.id not in wfs:
        raise Refused({"ok": False, "reason": "unknown-workflow", "expected": sorted(wfs)})
    wf = wfs[args.id]
    if args.step:
        step = next((s for s in wf["steps"] if args.step in (s["id"], s["n"])), None)
        if step is None:
            raise Refused({"ok": False, "reason": "unknown-step", "expected": [s["id"] for s in wf["steps"]]})
        return {"ok": True, "workflow": args.id, "step": Machine.step_view(step)}
    return {"ok": True, "workflow": args.id, "title": wf["title"], "category": wf["category"], "contract": wf.get("contract"),
            "steps": [Machine.step_view(s) for s in wf["steps"]]}


def judge_check(wfs, jid, passes):
    """A judge's answers are valid when both passes answer every question with yes or no and a quote, and agree. The failing
    questions are those answered the way their `fail_on` says."""
    step = next((s for wf in wfs.values() for s in wf["steps"] if s.get("judge") == jid), None)
    if step is None:
        raise Refused({"ok": False, "reason": "unknown-judge", "expected": sorted(s["judge"] for wf in wfs.values() for s in wf["steps"] if s.get("judge"))})
    questions, problems = step["questions"], []
    if not isinstance(passes, list) or len(passes) != 2:
        raise Refused({"ok": False, "reason": "two-passes-required"})
    answers = []
    for n, one in enumerate(passes, 1):
        by_q = {a.get("q"): a for a in one if isinstance(a, dict)}
        row = {}
        for i, q in enumerate(questions):
            a = by_q.get(i)
            if a is None:
                if q.get("when") is None:
                    problems.append({"code": "unanswered", "pass": n, "q": i})
                continue
            if a.get("answer") not in ("yes", "no"):
                problems.append({"code": "answer-not-yes-or-no", "pass": n, "q": i})
            elif not str(a.get("quote") or "").strip():
                problems.append({"code": "no-quote", "pass": n, "q": i})
            else:
                row[i] = a["answer"]
        answers.append(row)
    for i in sorted(set(answers[0]) & set(answers[1])):
        if answers[0][i] != answers[1][i]:
            problems.append({"code": "passes-disagree", "q": i})
    failing = [{"q": i, "text": questions[i]["q"]} for i in sorted(set(answers[0]) & set(answers[1]))
               if answers[0][i] == answers[1][i] == questions[i]["fail_on"]]
    return {"ok": not problems, "judge": jid, "problems": problems, "failing": failing, "passed": not problems and not failing}


def run_check(args, gh):
    """`check <id> --arg key=value … [--run N]`: the problems the check finds (those flagged `info` do not fail it)."""
    fn = CHECKS.get(args.id)
    if fn is None:
        raise Refused({"ok": False, "reason": "unimplemented-check", "check": args.id, "implemented": sorted(CHECKS)})
    given = dict(a.split("=", 1) for a in args.arg)
    machine = Machine(gh) if gh else None
    run = machine.run_show(args.run)["data"] if machine and args.run else {}
    try:
        problems = fn(pilot_checks.Ctx(given, ".", run, machine))
    except KeyError as err:
        raise Refused({"ok": False, "reason": "missing-arg", "arg": str(err).strip("'\"")})
    failing = [p for p in problems if not p.get("info")]
    return {"ok": not failing, "check": args.id, "problems": problems}


def run_runs(args, gh):
    machine = Machine(gh)
    cmd = args.run_cmd
    if cmd == "start":
        return machine.run_start(args.workflow, args.issue, args.title, json.loads(args.data) if args.data else None)
    if cmd == "show":
        return machine.run_show(args.issue)
    if cmd == "note":
        return machine.run_note(args.issue, args.assumption, json.loads(args.data) if args.data else None)
    if cmd == "advance":
        return machine.run_advance(args.issue, args.result, args.note)
    if cmd == "resume":
        return machine.run_resume(args.issue)
    record = None
    if args.record:
        with open(args.record, encoding="utf-8") as handle:
            record = json.load(handle)
    return machine.run_end(args.issue, args.result, record)


def needs_github(args):
    if args.cmd == "check":
        return args.id in pilot_checks.NEEDS_GH
    if args.cmd in ("module", "contract", "flow", "workflow", "judge", "config"):
        return False
    if args.cmd == "arch":
        return False
    return args.cmd != "wiki" or args.bundle_cmd in ("show", "status", "lint", "snapshot")


FLOW_RESULTS = ("passed", "partial", "failed")


def persona_result(run):
    """One persona's run: `failed` if a step failed, `partial` if a step was untestable or the session did not start."""
    steps = run.get("steps") or []
    if any(x.get("result") == "failed" for x in steps):
        return "failed"
    if run.get("session") == "not-started" or not steps or any(x.get("result") != "passed" for x in steps):
        return "partial"
    return "passed"


def flow_run_doc(wiki, repo, data):
    """The `flowRuns` document of a run: what the dashboard shows on the flow (when it was played, by which personas,
    with what result) and what lets it see the flow or a persona changed since. No GitHub call, no judgment."""
    if not isinstance(data, dict):
        raise Refused({"ok": False, "reason": "bad-input", "hint": "the input is one JSON object"})
    by_id = {e["id"]: e for e in wiki.parse()}
    flow = by_id.get(data.get("flow"))
    if flow is None or flow["type"] != "UserFlow":
        raise Refused({"ok": False, "reason": "not-a-user-flow", "id": data.get("flow")})
    if flow["status"] != "implemented":
        raise Refused({"ok": False, "reason": "flow-not-playable", "id": flow["id"], "hint": "only an implemented flow is played"})
    personas = []
    for run in data.get("personas") or []:
        if not isinstance(run, dict):
            raise Refused({"ok": False, "reason": "bad-input", "hint": "each persona run is a JSON object"})
        entry = by_id.get(run.get("persona"))
        if entry is None or entry["type"] != "Persona":
            raise Refused({"ok": False, "reason": "not-a-persona", "id": run.get("persona")})
        steps = run.get("steps") or []
        personas.append({"id": entry["id"], "hash": entry_hash(entry), "result": persona_result(run),
                         "steps": {k: sum(1 for x in steps if x.get("result") == k) for k in ("passed", "failed", "untestable")}})
    if not personas:
        raise Refused({"ok": False, "reason": "no-persona-run"})
    if not any(x["steps"]["passed"] + x["steps"]["failed"] for x in personas):
        raise Refused({"ok": False, "reason": "nothing-run", "hint": "no step was played: the flow's last result is kept"})
    results = [x["result"] for x in personas]
    bugs = []
    for b in (data.get("report") or {}).get("bugs") or []:
        try:
            n = int(str(b.get("ticket") if isinstance(b, dict) else b).lstrip("#"))
        except ValueError:
            continue
        if n > 0:
            bugs.append(n)
    return {"kind": "flowRun", "repo": repo, "flow": flow["id"], "at": now_iso(), "hash": entry_hash(flow),
            "result": next(r for r in ("failed", "partial", "passed") if r in results),
            "personas": personas, "bugs": bugs, "report": str(data.get("reportUrl") or "")}


def run_flow(args):
    with open(args.input, encoding="utf-8") as handle:
        data = json.load(handle)
    doc = flow_run_doc(Wiki(args.dir), args.repo or resolve_repo(), data)
    if not args.out:
        return doc
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, ensure_ascii=False, separators=(",", ":"))
    return {"ok": True, "file": args.out, "flow": doc["flow"], "result": doc["result"]}


def run_module(args):
    if args.action == "list":
        return {"ok": True, "modules": module_registry(read_modules()), "language": read_language()}
    if not args.name:
        raise Refused({"ok": False, "reason": "module-name-required", "expected": list(MODULES)})
    return set_module(args.name, args.action == "enable", with_requires=args.with_requires)


def run(args, gh):
    if args.cmd == "config":
        if args.action == "get":
            return {"ok": True, "key": args.key, "value": config_value(args.key)}
        if args.value is None:
            raise Refused({"ok": False, "reason": "value-required"})
        return config_set(args.key, args.value)
    if args.cmd == "module":
        return run_module(args)
    if args.cmd == "contract":
        return run_contract(args)
    if args.cmd == "flow":
        return run_flow(args)
    if args.cmd == "workflow":
        return run_workflow(args)
    if args.cmd == "judge":
        with open(args.input, encoding="utf-8") as handle:
            return judge_check(load_workflows(), args.id, json.load(handle))
    if args.cmd == "check":
        return run_check(args, gh)
    if args.cmd == "run":
        return run_runs(args, gh)
    if args.cmd in ("wiki", "arch"):
        return run_bundle(args, gh)
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
    if args.cmd == "ticket":
        if args.ticket_cmd == "create":
            return machine.ticket_create(args.level, args.kind, args.title, args.body, args.status, args.parent, args.priority, args.label)
        if args.ticket_cmd == "merged":
            return machine.ticket_merged(args.issue)
        return machine.ticket_close_forming(args.issue, drop=args.ticket_cmd == "drop")
    if args.cmd == "derive":
        return machine.derive(args.issue)
    if args.cmd == "pr":
        if args.pr_cmd == "open":
            return machine.pr_open(args.branch, args.title, args.body, args.base)
        return machine.pr_ci(args.number) if args.pr_cmd == "ci" else machine.pr_merge(args.number, args.method)
    if args.cmd == "labels":
        return machine.migrate_labels(args.apply) if args.action == "migrate" else machine.sync_labels()
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
        return {"ok": True, "file": args.out, "total": doc["total"], "truncated": doc["truncated"],
                "history_failed": machine.history_failed}
    if args.cmd == "doctor":
        report = machine.doctor(WIKI_DIR, {} if args.no_wiki else None)
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
    return 1 if result.get("ok") is False and args.cmd in ("doctor", "wiki", "arch", "contract", "workflow", "check", "judge") else 0


if __name__ == "__main__":
    sys.exit(main())
