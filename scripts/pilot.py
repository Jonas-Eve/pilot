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
  pilot.py snapshot [--out FILE]               # every open ticket as the dashboard's snapshot document
  pilot.py wiki    index [--under D] [--depth 1]|search|describe|reindex|show|status|lint|snapshot|add|set|remove|migrate  # the project's wiki (wiki/, an OKF bundle)
  pilot.py arch    index [--active] [--app A] [--under D] [--depth 1]|search|describe|next-number|inventory|reindex|show|lint|snapshot|add|set|remove|supersede  # the architecture bundle (architecture/: overview, guidelines, ADR; no GitHub)

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
import fnmatch
import json
import math
import os
import posixpath
import re
import subprocess
import sys
import unicodedata

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
# What each phase produces (the statuses it sets), on top of what PHASES already says it consumes (fresh, reclaim,
# in progress, resumable). `consumes` adds what a phase reads that PHASES does not list. A phase knows only these two
# sides of itself; the chain is their composition, checked by `composition_problems`.
CONTRACTS = {
    "discovery": {"consumes": ["status:poc-validated"],
                  "produces": ["status:draft", "status:backlog", "status:wont-do"]},
    "spec": {"consumes": ["status:qa", "status:in-qa", "status:split"],
             "produces": ["status:draft", "status:backlog", "status:dev-ready", "status:split", "status:wont-do"]},
    "dev": {"consumes": [], "produces": ["status:review-ready"]},
    "review": {"consumes": [], "produces": ["status:approved", "status:changes-requested"]},
    "qa": {"consumes": [], "produces": ["status:done"]},
    "proto": {"consumes": ["status:poc-review", "status:poc-validated"],
              "produces": ["status:poc-draft", "status:poc-review", "status:poc-validated", "status:poc-rejected"]},
}
# transitions the merge/close workflow makes, not a phase
EXTERNAL = (("status:approved", "status:done"), ("status:split", "status:done"), ("status:split", "status:qa"))
SINKS = ("status:done", "status:wont-do", "status:poc-rejected")  # statuses nothing consumes


DEFAULT_PROFILE = "standard"
# A workflow profile is the part of the chain a project runs (`workflow.profile` in .pilot/state.json). `standard` is
# the whole chain, what every project ran before profiles. A profile drops phases, merge-workflow transitions and the
# statuses only those use, says whether a feature split carries an e2e task (`e2e_task`) and who reviews which type
# (`review`, None = the default sets); what it keeps must still compose (`pilot.py workflow check`). `ready` stays false
# while the skills, the task docs and the merge workflow do not follow a profile: `workflow set` refuses it until they do.
REVIEWERS = ("pilot-pm", "pilot-techlead", "pilot-architect")
DEFAULT_REVIEW = {"feature": ["pilot-pm", "pilot-techlead"], "e2e": ["pilot-pm", "pilot-techlead"],
                  "tech": ["pilot-techlead"], "bug": ["pilot-techlead"]}
PROFILES = {
    "standard": {"drop_phases": (), "drop_external": (), "drop_statuses": (), "e2e_task": True, "review": None,
                 "rank": 1, "default_mode": "pair", "spec_tech": {"architect": "validates"}, "ready": True},
    "lean": {"drop_phases": ("qa",), "drop_external": (("status:split", "status:qa"),),
             "drop_statuses": ("status:qa", "status:in-qa"), "e2e_task": False,
             "review": {kind: ["pilot-techlead"] for kind in DEFAULT_REVIEW},
             "rank": 0, "default_mode": "auto", "spec_tech": {"architect": "on-signal"}, "ready": True},
}


def chain(profile=DEFAULT_PROFILE):
    """The part of the chain a profile runs: its phases, their contracts, the merge-workflow transitions and the
    statuses. A phase keeps no consumption of a status the profile dropped; a contract that still produces one is
    a drift `composition_problems` reports."""
    if profile not in PROFILES:
        raise Refused({"ok": False, "reason": "unknown-profile", "expected": list(PROFILES)})
    drop = PROFILES[profile]
    gone = set(drop["drop_statuses"])
    return {"phases": {k: v for k, v in PHASES.items() if k not in drop["drop_phases"]},
            "contracts": {k: {"consumes": [st for st in v["consumes"] if st not in gone], "produces": list(v["produces"])}
                          for k, v in CONTRACTS.items() if k not in drop["drop_phases"]},
            "external": tuple(t for t in EXTERNAL if t not in drop["drop_external"]),
            "statuses": {f"status:{name}" for name in STATUSES} - gone}


def profile_rules(profile=DEFAULT_PROFILE):
    """What a profile means for the skills, the task docs and the merge workflow, as data they read (`workflow show`)
    instead of restating it: whether there is a QA phase and an e2e task, where a finished feature story goes, and the
    default reviewers of each ticket type."""
    ch, meta = chain(profile), PROFILES[profile]
    review = meta["review"] or DEFAULT_REVIEW
    return {"qa": "qa" in ch["phases"], "e2e_task": meta["e2e_task"],
            "feature_done_goes_to": "status:qa" if ("status:split", "status:qa") in ch["external"] else "status:done",
            "review": {kind: list(review[kind]) for kind in DEFAULT_REVIEW},
            "default_mode": meta["default_mode"], "spec": {"tech": dict(meta["spec_tech"])}}


def rules_problems(profile=DEFAULT_PROFILE):
    """What makes a profile's rules contradict themselves: a QA stop without a QA phase (or the reverse), a review without
    the tech lead (every change is reviewed by it, whatever the profile), or an unknown reviewer."""
    rules, problems = profile_rules(profile), []
    if rules["qa"] != (rules["feature_done_goes_to"] == "status:qa"):
        problems.append({"code": "qa-stop-without-qa-phase" if not rules["qa"] else "qa-phase-without-qa-stop"})
    if rules["default_mode"] not in ("auto", "pair"):
        problems.append({"code": "bad-default-mode", "mode": rules["default_mode"]})
    if rules["spec"]["tech"].get("architect") not in ("validates", "on-signal"):
        problems.append({"code": "bad-spec-rule", "architect": rules["spec"]["tech"].get("architect")})
    for kind, reviewers in rules["review"].items():
        if "pilot-techlead" not in reviewers:
            problems.append({"code": "review-without-techlead", "type": kind})
        problems += [{"code": "unknown-reviewer", "type": kind, "reviewer": r} for r in reviewers if r not in REVIEWERS]
    return problems


def profile_problems(profile=DEFAULT_PROFILE):
    """Everything wrong with a profile: its chain does not compose, or its rules contradict themselves."""
    return composition_problems(profile) + rules_problems(profile)


def phase_contract(phase, profile=DEFAULT_PROFILE):
    """One phase's contract: the statuses it consumes, the one it claims into, the ones it produces."""
    ch = chain(profile)
    if phase not in ch["contracts"]:
        if phase in CONTRACTS:
            raise Refused({"ok": False, "reason": "phase-not-in-profile", "phase": phase, "profile": profile})
        raise Refused({"ok": False, "reason": "unknown-phase", "expected": sorted(ch["contracts"])})
    cfg, extra = ch["phases"].get(phase, {}), ch["contracts"][phase]
    consumes = {cfg.get("fresh"), cfg.get("reclaim"), cfg.get("inprog")} | set(cfg.get("resumable", ())) | set(extra["consumes"])
    consumes.discard(None)
    return {"ok": True, "phase": phase, "consumes": sorted(consumes), "claims": cfg.get("inprog"),
            "produces": sorted(extra["produces"])}


def composition_problems(profile=DEFAULT_PROFILE):
    """The chain a profile runs as the composition of the contracts: every status has a producer and a consumer, a sink apart."""
    ch = chain(profile)
    known = ch["statuses"]
    produced = {cfg["inprog"] for cfg in ch["phases"].values()} | {b for _a, b in ch["external"]}
    consumed = {a for a, _b in ch["external"]}
    for phase in ch["contracts"]:
        contract = phase_contract(phase, profile)
        produced |= set(contract["produces"])
        consumed |= set(contract["consumes"])
    problems = [{"status": st, "code": "no-producer"} for st in sorted(known - produced)]
    problems += [{"status": st, "code": "no-consumer"} for st in sorted(known - consumed - set(SINKS))]
    problems += [{"status": st, "code": "unknown-status"} for st in sorted((produced | consumed) - known)]
    return problems


def transition_allowed(current, new, profile=DEFAULT_PROFILE):
    """Whether some contract of the profile admits `current` -> `new` (a phase that consumes or claims `current` and
    produces `new`, or the merge workflow). Creation (no status yet), no change and clearing the status are always fine."""
    if not current or current == new or new == "status:none":
        return True
    ch = chain(profile)
    if (current, new) in ch["external"]:
        return True
    for phase in ch["contracts"]:
        contract = phase_contract(phase, profile)
        if current in contract["consumes"] + [contract["claims"]] and new in contract["produces"]:
            return True
    return False


POC_OPEN = ("status:poc-draft", "status:poc-review", "status:poc-validated")  # a prototype can still be rejected
RESCOPABLE = ("status:qa", "status:in-qa", "status:split")  # spec re-scopes these in place
REQUIRED_LABELS = (
    {"type:feature", "type:tech", "type:bug", "type:e2e", "type:poc", "level:epic", "level:story", "level:task",
     "priority:P0", "priority:P1", "priority:P2", "needs-human", "on-hold", "can-resume"}
    | {f"status:{name}" for name in STATUSES}
)
# one per profile: required (by `doctor`) only once the project declares a `workflow`, so a project that has not adopted
# profiles does not fail its preflight; the provisioning script creates them all
WORKFLOW_LABELS = {f"workflow:{name}" for name in PROFILES}
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
STATE_PATH = os.path.join(".pilot", "state.json")
WIKI_DIR = "wiki"
ARCH_DIR = "architecture"
# The optional modules a project turns on in .pilot/state.json (`modules`): the skills each owns, the modules
# it needs, the command that turns it on at first use (`use`), the one that drafts its content from what the
# project already has (`bootstrap`, only where there is such content), and the folder (if any) `doctor` expects.
MODULES = {
    "wiki": {"skills": ["pilot-wiki"], "requires": [], "use": "/pilot-wiki", "bootstrap": "/pilot-wiki --bootstrap",
             "dir": WIKI_DIR},
    "architecture": {"skills": ["pilot-architecture"], "requires": [], "use": "/pilot-architecture",
                     "bootstrap": "/pilot-architecture --bootstrap", "dir": ARCH_DIR},
    "dashboard": {"skills": ["pilot-dashboard"], "requires": [], "use": "/pilot-dashboard"},
    "design": {"skills": ["pilot-design"], "requires": ["dashboard"], "use": "/pilot-design"},
    "proto": {"skills": ["pilot-proto"], "requires": ["dashboard"], "use": "/pilot-proto"},
}
WIKI_SNAPSHOT_MAX_BYTES = 240_000  # a database document holds at most 256 KiB
WIKI_STATUSES = ("proposed", "specified", "implemented", "deprecated")  # the only ones a file holds
OKF_VERSION = "0.2"  # the Open Knowledge Format the wiki follows (https://github.com/GoogleCloudPlatform/open-knowledge-format)
WIKI_RESERVED = ("index.md", "log.md")  # OKF: never concept files
WIKI_OKF_STATUS = {"proposed": "draft", "specified": "draft", "implemented": "stable", "deprecated": "deprecated"}
WIKI_VERIFIER = "process:pilot-wiki"
WIKI_DEFAULT_TYPE = "Behavior"
WIKI_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
WIKI_IN_DEV = ("status:in-dev",)
WIKI_IN_REVIEW = ("status:review-ready", "status:in-review", "status:changes-requested")
WIKI_IN_QA = ("status:qa", "status:in-qa")
WIKI_PRE_DEV = ("status:draft", "status:backlog", "status:in-spec", "status:dev-ready")


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


def read_workflow(path=STATE_PATH):
    """The project's workflow profile, from `.pilot/state.json` (`workflow.profile`): {"profile", "source"} where source is
    "state" or "default" (the standard chain: no file, no field, or a name that is not a profile, which `unknown` then names)."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {"profile": DEFAULT_PROFILE, "source": "default"}
    block = data.get("workflow") if isinstance(data, dict) else None
    name = block.get("profile") if isinstance(block, dict) else None
    if name is None:
        return {"profile": DEFAULT_PROFILE, "source": "default"}
    if name not in PROFILES:
        return {"profile": DEFAULT_PROFILE, "source": "default", "unknown": name}
    return {"profile": name, "source": "state"}


def read_profile(path=STATE_PATH):
    return read_workflow(path)["profile"]


def set_workflow(name, path=STATE_PATH):
    """Choose the project's workflow profile in `.pilot/state.json`, leaving every other field alone. Refused for a profile
    the skills do not follow yet, or whose chain does not compose."""
    if name not in PROFILES:
        raise Refused({"ok": False, "reason": "unknown-profile", "expected": list(PROFILES)})
    if not PROFILES[name]["ready"]:
        raise Refused({"ok": False, "reason": "profile-not-ready", "profile": name,
                       "hint": "the skills, task docs and merge workflow do not follow it yet"})
    problems = profile_problems(name)
    if problems:
        raise Refused({"ok": False, "reason": "does-not-compose", "profile": name, "problems": problems})
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        raise Refused({"ok": False, "reason": "no-state", "hint": "run /pilot-init"})
    block = data.get("workflow") if isinstance(data.get("workflow"), dict) else {}
    block["profile"] = name
    data["workflow"] = block
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    result = {"ok": True, "profile": name}
    gone = list(PROFILES[name]["drop_statuses"])
    if gone:  # a ticket already at one of them has no phase to claim it any more
        result["warning"] = {"code": "dropped-statuses", "statuses": gone,
                             "hint": "no ticket should be at these statuses when the profile is switched: nothing claims them afterwards"}
    return result


# ---- risk signals and one ticket's route -----------------------------------------------------------------------
# A signal is a rule a script evaluates (labels, keywords in the title and body, paths), never an opinion. What it adds to
# one ticket's roster: pair only, the architect validating or leading the Spec, extra reviewers, the designer, notes for
# the agents, and a refusal of a lighter profile. Declared per project in `.pilot/state.json` (`workflow.signals`); there is
# no default signal, so a project that declares none is never forced to anything.
SIGNAL_ADDS = {"pair_only": bool, "forbid_lighter": bool, "designer": bool, "architect": str, "reviewers": list, "notes": list}
ARCHITECT_ROLES = ("validates", "leads")
WORKFLOW_LABEL = "workflow:"
# a ticket's workflow label is part of its path: it is fixed before work starts and never changes once the ticket is in Dev
WORKFLOW_FROZEN = ("status:split", "status:in-dev", "status:review-ready", "status:in-review", "status:changes-requested", "status:approved",
                   "status:qa", "status:in-qa", "status:done")
PATH_TOKEN_RE = re.compile(r"[\w.@-]+(?:/[\w.@*-]+)+")
DEPENDENCY_RE = re.compile(r"\b(?:Depends on|Blocks) #\d+", re.IGNORECASE)


def workflow_block(path=STATE_PATH):
    """The `workflow` field of `.pilot/state.json` as it stands ({} when the file or the field is absent)."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    block = data.get("workflow") if isinstance(data, dict) else None
    return block if isinstance(block, dict) else {}


def state_apps(path=STATE_PATH):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    apps = data.get("apps") if isinstance(data, dict) else None
    return [a["name"] for a in apps if isinstance(a, dict) and isinstance(a.get("name"), str)] if isinstance(apps, list) else []


def signals_of(block):
    return list(block["signals"]) if isinstance(block.get("signals"), list) else []


def signal_problems(signals):
    problems, seen = [], set()
    for sig in signals:
        sid = sig.get("id") if isinstance(sig, dict) else None
        if not isinstance(sid, str) or not sid:
            problems.append({"code": "signal-without-id"})
            continue
        if sid in seen:
            problems.append({"code": "duplicate-signal-id", "signal": sid})
        seen.add(sid)
        match = sig.get("match") if isinstance(sig.get("match"), dict) else {}
        if not any(isinstance(match.get(k), list) and match[k] and all(isinstance(x, str) for x in match[k])
                   for k in ("labels", "keywords", "paths")):
            problems.append({"code": "signal-without-match", "signal": sid})
        adds = sig.get("adds") if isinstance(sig.get("adds"), dict) else {}
        for key, value in adds.items():
            if key not in SIGNAL_ADDS:
                problems.append({"code": "unknown-addition", "signal": sid, "addition": key})
            elif not isinstance(value, SIGNAL_ADDS[key]) or (key == "architect" and value not in ARCHITECT_ROLES) \
                    or (key in ("reviewers", "notes") and not all(isinstance(x, str) for x in value)):
                problems.append({"code": "bad-addition", "signal": sid, "addition": key})
        for reviewer in adds.get("reviewers", []) if isinstance(adds.get("reviewers"), list) else []:
            if reviewer not in REVIEWERS:
                problems.append({"code": "unknown-reviewer", "signal": sid, "reviewer": reviewer})
    return problems


def signal_matches(signal, issue, paths=()):
    """Whether a signal fires on a ticket (a normalized issue): any label, any keyword in the title and body, any path
    (a glob against the paths given, e.g. a PR's changed files, and the paths the body names)."""
    match = signal.get("match", {})
    if any(label in issue["labels"] for label in match.get("labels", [])):
        return True
    text = f"{issue['title']}\n{issue['body']}".lower()
    if any(word.lower() in text for word in match.get("keywords", [])):
        return True
    named = set(paths) | set(PATH_TOKEN_RE.findall(f"{issue['title']}\n{issue['body']}"))
    return any(fnmatch.fnmatch(p, glob) for glob in match.get("paths", []) for p in named)


def spec_route(issue, architect_addition, profile, apps, declared=True):
    """Who leads the Spec of a ticket and whether the architect validates: a feature always has the architect lead, a bug
    never has one, and a tech story follows its profile: the tech lead leads, the architect leads instead when the ticket
    declares dependencies, names several apps or a signal says so, and validates when the profile or a signal asks. A
    project that declares no workflow keeps the dialogue of both, as every project had before profiles."""
    both, alone = ["pilot-architect", "pilot-techlead"], ["pilot-techlead"]
    if not declared and "type:bug" not in issue["labels"]:
        return {"architect": "leads", "leads": both, "triggers": []}
    if "type:feature" in issue["labels"]:
        return {"architect": "leads", "leads": both, "triggers": []}
    if "type:bug" in issue["labels"]:
        return {"architect": "absent", "leads": alone, "triggers": []}
    text, triggers = f"{issue['title']}\n{issue['body']}", []
    if DEPENDENCY_RE.search(text):
        triggers.append("dependencies")
    if sum(1 for app in apps if re.search(r"(?<![\w-])" + re.escape(app) + r"(?![\w-])", text, re.IGNORECASE)) >= 2:
        triggers.append("several-apps")
    if architect_addition == "leads":
        triggers.append("signal")
    if triggers:
        return {"architect": "leads", "leads": both, "triggers": triggers}
    asked = architect_addition == "validates" or PROFILES[profile]["spec_tech"]["architect"] == "validates"
    return {"architect": "validates" if asked else "absent", "leads": alone, "triggers": []}


def ticket_route(issue, path=STATE_PATH, paths=()):
    """One ticket's route: its profile (the project's, or its own `workflow:<profile>` label when the project allows it),
    the signals that fire, whether it is pair only, its mode, its reviewers, its Spec rule. A project without a `workflow`
    block has the standard chain and no signal, whatever the labels say."""
    declared = read_workflow(path)
    block = workflow_block(path) if declared["source"] == "state" else {}
    project, labels, warnings = declared["profile"], issue["labels"], []
    labelled = sorted(l[len(WORKFLOW_LABEL):] for l in labels if l.startswith(WORKFLOW_LABEL))
    profile, source = project, "project"
    if labelled and not block:
        warnings.append({"code": "workflow-label-ignored", "hint": "the project declares no workflow profile"})
    elif labelled:
        if len(labelled) > 1:
            return {"ok": False, "reason": "several-workflow-labels", "labels": labelled}
        if labelled[0] not in PROFILES:
            return {"ok": False, "reason": "unknown-workflow-label", "label": labelled[0], "expected": list(PROFILES)}
        allowed = {project} | {n for n in block.get("allow", []) if n in PROFILES} if isinstance(block.get("allow"), list) else {project}
        if labelled[0] not in allowed:
            return {"ok": False, "reason": "profile-not-allowed", "label": labelled[0], "allowed": sorted(allowed)}
        profile, source = labelled[0], "label"
    fired = [s for s in signals_of(block) if isinstance(s, dict) and signal_matches(s, issue, paths)] if block else []
    adds = [s.get("adds", {}) for s in fired]
    if PROFILES[profile]["rank"] < PROFILES[project]["rank"]:
        if any(a.get("forbid_lighter") for a in adds):
            return {"ok": False, "reason": "lighter-forbidden", "profile": profile, "project_profile": project,
                    "signals": [s["id"] for s in fired]}
        warnings.append({"code": "lighter-than-project", "hint": "a lighter profile than the project's needs a written reason on the ticket"})
    rules = profile_rules(profile)
    kind = next((k for k in DEFAULT_REVIEW if f"type:{k}" in labels), None)
    review = list(rules["review"][kind]) if kind else []
    for extra in (r for a in adds for r in a.get("reviewers", [])):
        if kind and extra not in review:
            review.append(extra)
    architect = "leads" if any(a.get("architect") == "leads" for a in adds) else \
        "validates" if any(a.get("architect") == "validates" for a in adds) else None
    pair_only = any(a.get("pair_only") for a in adds)
    return {"ok": True, "profile": profile, "source": source, "project_profile": project, "rules": rules,
            "signals": [s["id"] for s in fired], "pair_only": pair_only,
            "mode": "pair" if pair_only else rules["default_mode"], "review": review,
            "spec": spec_route(issue, architect, profile, state_apps(path), declared["source"] == "state"),
            "designer": any(a.get("designer") for a in adds), "notes": [n for a in adds for n in a.get("notes", [])],
            "warnings": warnings, "inherit_labels": [f"{WORKFLOW_LABEL}{profile}"] if source == "label" else []}


DEFAULT_LANGUAGE = "en"
# a few of the commonest function words per language: enough to tell which of the two a paragraph is written in
LANG_WORDS = {
    "en": frozenset("the of and to in is are for with that this on be as by it from at or an not can when each".split()),
    "fr": frozenset("le la les des du de et en est un une pour avec que qui dans sur par au aux ce cette ne pas ou chaque quand".split()),
}


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


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


SNAPSHOT_MAX_BYTES = 240_000  # a database document holds at most 256 KiB


class Refused(Exception):
    """A precondition failed: the JSON payload explains, exit status 1."""

    def __init__(self, payload):
        super().__init__(payload.get("reason", "refused"))
        self.payload = payload


class Machine:
    def __init__(self, gh, profile=None, state_path=STATE_PATH):
        self.gh = gh
        self.state_path = state_path
        self.profile = profile or read_profile(state_path)
        self._open = {}

    def route_of(self, issue, paths=()):
        return ticket_route(issue, self.state_path, paths)

    def _pair_only(self, issue):
        """The route of a ticket when it is pair only (an `--auto` run must leave it to a human), else None."""
        route = self.route_of(issue)
        return route if route.get("ok") and route["pair_only"] else None

    def _require_phase(self, phase):
        if phase not in chain(self.profile)["phases"]:
            raise Refused({"ok": False, "reason": "phase-not-in-profile", "phase": phase, "profile": self.profile})

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
    def pool(self, phase, limit, only=None, auto=False):
        self._require_phase(phase)
        cfg = PHASES[phase]
        candidates, excluded, raws = [], [], {}

        def reject(issue, reason, **extra):
            excluded.append(public(issue, reason=reason, **extra))

        def consider(issue, pool):
            for flag in FLAGS:
                if flag in issue["labels"]:
                    return reject(issue, flag)
            if auto and self._pair_only(issue):
                return reject(issue, "pair-only", signals=self.route_of(issue)["signals"])
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
            checked = self.resolve_raw(phase, shown[0]["number"], False, auto, raws[shown[0]["number"]])
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
            if "status:split" in labels:
                found += [g["number"] for g in self.gh.sub_issues(child["number"])
                          if g.get("state") == "open"]
        return found

    def resolve(self, phase, number, resume=False, auto=False):
        self._require_phase(phase)
        return self.resolve_raw(phase, number, resume, auto, self.gh.get_issue(number))

    def resolve_raw(self, phase, number, resume, auto, raw):
        result = self._resolve(phase, number, resume, auto, raw)
        if auto and result.get("action") in ("claim-fresh", "reclaim", "resume-orphaned", "resume-cleared"):
            route = self._pair_only(normalize(raw))
            if route:  # a signal makes it pair only: an unattended run leaves it to a human
                return {"action": "stop", "reason": "pair-only", "signals": route["signals"], "issue": number,
                        "status": result.get("status")}
        return result

    def _resolve(self, phase, number, resume, auto, raw):
        cfg = PHASES[phase]
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
                    found = self.pool(phase, 5, only=set(tree), auto=auto)
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
                needed = REQUIRED_LABELS | (WORKFLOW_LABELS if read_workflow(self.state_path)["source"] == "state" else set())
                missing = sorted(needed - self.gh.label_names())
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
            route = self.route_of(t)
            if route.get("ok"):
                guard = {}
                if route["pair_only"]:
                    guard["p"], guard["s"] = 1, route["signals"]
                if route["source"] == "label":
                    guard["w"] = route["profile"]
                if guard:
                    row["g"] = guard  # pair only (and why), or its own workflow profile
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
        modules = state_modules()
        if modules is not None:
            doc["modules"] = modules  # the dashboard's tabs follow the modules a project has on
        doc["language"] = read_language()  # the dashboard opens in it (a reader can switch)
        declared = read_workflow(self.state_path)
        if declared["source"] == "state":  # the chain this project runs: the dashboard shows its phases and its rules
            doc["workflow"] = {"profile": declared["profile"], "phases": sorted(chain(declared["profile"])["contracts"]),
                               "rules": profile_rules(declared["profile"])}
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

    def claim(self, phase, number, mode, auto=False):
        self._require_phase(phase)
        cfg = PHASES[phase]
        raw = self.gh.get_issue(number)
        if raw is None:
            raise Refused({"claimed": False, "reason": "not-found", "issue": number})
        issue = normalize(raw)
        if auto and self._pair_only(issue):
            raise Refused({"claimed": False, "reason": "pair-only", "issue": number,
                           "signals": self.route_of(issue)["signals"]})
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
        before = status_of(labels)
        if status is not None:
            name = status[len("status:"):] if status.startswith("status:") else status
            if name != "none" and name not in STATUSES:
                raise Refused({"ok": False, "reason": "unknown-status", "status": status,
                               "allowed": sorted(STATUSES)})
            labels = {l for l in labels if not l.startswith("status:")}
            if name != "none":
                labels.add(f"status:{name}")
        workflow_before = {l for l in set(normalize(raw)["labels"]) if l.startswith(WORKFLOW_LABEL)}
        labels |= set(add)
        labels -= set(remove)
        if {l for l in labels if l.startswith(WORKFLOW_LABEL)} != workflow_before and before in WORKFLOW_FROZEN:
            raise Refused({"ok": False, "reason": "workflow-label-frozen", "issue": number, "status": before,
                           "hint": "a ticket's workflow is fixed before Dev starts"})
        assignees = [self.gh.me()] if assign == "me" else [] if assign == "none" else None
        extra = {"state": "closed", "state_reason": "completed"} if close else None
        after = self._write(number, labels, assignees, extra)
        result = {"ok": True, "issue": number, "status": status_of(after["labels"]),
                  "labels": sorted(after["labels"]), "assignees": after["assignees"],
                  "state": after["state"], "event": self._event(after, "set", pr=pr)}
        if not transition_allowed(before, result["status"], self.profile):
            result["warning"] = {"code": "unexpected-transition", "from": before, "to": result["status"],
                                 "hint": "no phase contract (`pilot.py contract`) takes a ticket from one to the other"}
        return result

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
    REMOVABLE = "proposed"  # the one status whose entry may be deleted

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
                     "status": "", "tickets": [], "verifiedAt": "", "verifiedCommit": "", "managed": False,
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
        entry["verifiedCommit"] = str(pilot.get("verifiedCommit") or "")
        if bool(entry["verifiedAt"]) != bool(entry["verifiedCommit"]):
            add(("partial-stamp", "`verified.at` and `pilot.verifiedCommit` go together"))
        if not entry["description"]:
            add(("missing-description", "the index shows each entry's one-sentence `description`"))

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
                 and not (active and (e["status"] in self.LIVE or e["type"] in self.ACTIVE_LEFT_OUT))]
        rows = [self._brief(e) if active else self._view(e) for e in shown]
        return {"ok": True, "dir": self.root, "entries": rows,
                "problems": sum(len(e["problems"]) for e in entries)}

    def outline(self, under="", active=False, app=None):
        """One level of the bundle: the sub-folders of `under` (each with its description and how many entries it
        holds below it) and the entries sitting directly in it. A fixed-size first look, however big the bundle."""
        under = (under or "").strip("/")
        counts, direct, known = {}, [], not under
        for e in self.parse():
            if (active and (e["status"] in self.LIVE or e["type"] in self.ACTIVE_LEFT_OUT)) or not self._scoped(e, app):
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
        return {"ok": True, **self._view(entry), "text": entry["text"], "derived": self.derive(entry, gh, {}),
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
            rows.append({"id": e["id"], "title": e["title"], "description": e["description"], "path": e["path"],
                         "status": e["status"], "derived": d["derived"], "display": d["display"],
                         "tickets": e["tickets"], "verifiedAt": e["verifiedAt"], "text": e["text"]})
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

    def set(self, entry_id, status=None, add=(), remove=(), stamp=None, clear_stamp=False, title=None, description=None):
        """The only writer of an entry's frontmatter (unknown keys are kept as they are). `stamp` is the commit
        a lint verified the entry against; `clear_stamp` forgets it when the entry's text changed."""
        entry = self._editable(entry_id)
        if status is not None and status not in self.STATUSES:
            raise Refused({"ok": False, "reason": "bad-status", "expected": list(self.STATUSES),
                           **({"hint": ", ".join(self.DERIVED_NAMES) + " are derived, never written"} if self.DERIVED_NAMES else {})})
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
            fm["verified"] = {"by": WIKI_VERIFIER, "at": now_iso()}
            pilot["verifiedCommit"] = stamp
        fm["pilot"] = pilot
        self._write(entry["abs"], fm, entry["rest"])
        self.reindex()
        after = self._find(entry_id)
        return {"ok": True, "id": entry_id, "status": after["status"], "tickets": after["tickets"],
                "verifiedAt": after["verifiedAt"], "verifiedCommit": after["verifiedCommit"]}

    def _path_ok(self, rel):
        return True

    def add(self, path, title, description, status, tickets=(), body="", typ=None):
        """Create an entry: `<domain>/<id>.md` under the wiki root, then refresh the indexes."""
        rel = path.replace(os.sep, "/")
        stem = posixpath.splitext(posixpath.basename(rel))[0]
        if (not rel.endswith(".md") or rel.startswith("/") or ".." in rel.split("/")
                or posixpath.basename(rel) in WIKI_RESERVED or not WIKI_ID_RE.match(stem)):
            raise Refused({"ok": False, "reason": "bad-path", "path": path,
                           "hint": self.PATH_HINT})
        if not self._path_ok(rel):
            raise Refused({"ok": False, "reason": "bad-path", "path": path, "hint": self.PATH_HINT})
        if status not in self.STATUSES:
            raise Refused({"ok": False, "reason": "bad-status", "expected": list(self.STATUSES)})
        if not title.strip() or not description.strip():
            raise Refused({"ok": False, "reason": "title-and-description-required"})
        os.makedirs(self.root, exist_ok=True)
        entries = self.parse()
        if any(e["id"] == stem for e in entries):
            raise Refused({"ok": False, "reason": "duplicate-id", "id": stem})
        target = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        fm = {"type": typ or self._type_of(rel), "title": title.strip(), "description": description.strip(), "status": self.OKF_STATUS[status],
              "pilot": {"status": status, "tickets": list(tickets)}}
        self._write(target, fm, ("\n" + body.strip() + "\n") if body.strip() else "")
        self.reindex()
        return {"ok": True, "id": stem, "path": rel, "status": status}

    def _max_words(self, entry):
        return {"ADR": 600, "Architecture": 800, "Runbook": 1500}.get(entry["type"], self.MAX_WORDS)

    def _type_of(self, rel):
        return self.DEFAULT_TYPE

    def remove(self, entry_id):
        """Delete a `proposed` entry (a won't-do story's promise); anything else is deprecated, not removed."""
        entry = self._editable(entry_id)
        if entry["status"] != self.REMOVABLE:
            raise Refused({"ok": False, "reason": "not-removable", "id": entry_id, "status": entry["status"],
                           "hint": f"only a {self.REMOVABLE} entry is removed; deprecate the others"})
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
    """The functional wiki: statuses proposed / specified / implemented / deprecated, derived from tickets."""


ARCH_STATUSES = ("proposed", "accepted", "deprecated", "superseded")
ARCH_OKF_STATUS = {"proposed": "draft", "accepted": "stable", "deprecated": "deprecated", "superseded": "deprecated"}


class Architecture(Bundle):
    """The architecture module's bundle: `architecture/overview.md`, `guidelines/<id>.md`, `adr/<NNNN-title>.md` and
    `runbooks/<id>.md` (how to operate: deploy, onboard; read on demand, never carried in a prompt).
    Same OKF files, same frontmatter writer, same indexes as the wiki; its own statuses (an ADR is accepted, then
    deprecated or superseded by a later one, and never edited in between), no ticket-driven checks."""
    TITLE = "Architecture"
    ABSENT = "architecture-absent"
    ABSENT_HINT = "run /pilot-architecture (it turns the architecture module on and creates architecture/)"
    PATH_HINT = ("overview.md, guidelines/<id>.md, adr/<NNNN-title>.md or runbooks/<id>.md; for one app of a monorepo, the same under "
                 "apps/<app>/ with its overview named <app>-overview.md (an id is unique across the whole bundle)")

    @staticmethod
    def _layout_ok(parts, app=None):
        if len(parts) == 1:
            return parts[0] == ("overview.md" if app is None else f"{app}-overview.md")
        return len(parts) == 2 and parts[0] in ("guidelines", "adr", "runbooks")

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
    OKF_STATUS = ARCH_OKF_STATUS
    DEFAULT_TYPE = "Guideline"
    DERIVED_NAMES = ()
    LIVE = ("deprecated", "superseded")
    ACTIVE_LEFT_OUT = ("Runbook",)

    def _type_of(self, rel):
        parts = rel.split("/")
        stem = posixpath.splitext(parts[-1])[0]
        if "adr" in parts[:-1]:
            return "ADR"
        if "runbooks" in parts[:-1]:
            return "Runbook"
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
                         "supersededBy": str(fm.get("supersededBy") or ""), "text": e["text"]})
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
    phases = sorted(PHASES)
    p = sub.add_parser("pool")
    p.add_argument("phase", choices=[x for x in phases if x != "proto"])
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--auto", action="store_true", help="an unattended run: leave out the tickets a signal makes pair only")
    p = sub.add_parser("resolve")
    p.add_argument("phase", choices=phases)
    p.add_argument("issue", type=int)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--auto", action="store_true", help="an unattended run: stop on a ticket a signal makes pair only")
    p = sub.add_parser("claim")
    p.add_argument("phase", choices=phases)
    p.add_argument("issue", type=int)
    p.add_argument("--mode", required=True,
                   choices=["fresh", "reclaim", "resume-orphaned", "resume-cleared", "rescope"])
    p.add_argument("--auto", action="store_true", help="an unattended run: refuse a ticket a signal makes pair only")
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
    p.add_argument("--no-wiki", action="store_true", help="skip the wiki check (/pilot-wiki repairing a missing wiki/)")
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
        w.add_argument("--all", action="store_true", help="include entries that are history (deprecated, superseded)")
        w = ws.add_parser("describe", help="the one sentence an outline shows next to a folder ('' for the bundle)")
        w.add_argument("folder")
        w.add_argument("description")

    p = sub.add_parser("contract", help="a phase's contract (consumes, claims, produces), or all of them and the check that they compose")
    p.add_argument("phase", nargs="?", choices=sorted(CONTRACTS))
    p.add_argument("--profile", choices=list(PROFILES), help="the workflow profile (default: the project's, else standard)")
    p = sub.add_parser("workflow", help="the project's workflow profile: show it, check that every profile composes, or set it")
    p.add_argument("action", choices=["show", "check", "set"])
    p.add_argument("name", nargs="?", choices=list(PROFILES))
    p.add_argument("--ticket", type=int, help="show: one ticket's route (its profile, signals, mode, Spec rule); needs GitHub")
    p.add_argument("--path", action="append", default=[], help="show --ticket: a changed file, for the path signals")
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
    w.add_argument("--status", required=True, choices=list(WIKI_STATUSES))
    w.add_argument("--type", default=WIKI_DEFAULT_TYPE)
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
    w.add_argument("--clear-stamp", action="store_true", help="forget the stamp (the entry's text changed)")
    w = ws.add_parser("remove", help="delete a proposed entry")
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
    w = ws.add_parser("add", help="create an entry file (overview.md, guidelines/<id>.md, adr/<NNNN-title>.md or runbooks/<id>.md)")
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
    w.add_argument("--clear-stamp", action="store_true")
    w = ws.add_parser("remove", help="delete a proposed entry")
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
                    args.title, args.description)


def run_contract(args):
    profile = getattr(args, "profile", None) or read_profile()
    if args.phase:
        return phase_contract(args.phase, profile)
    ch = chain(profile)
    problems = composition_problems(profile)
    return {"ok": not problems, "profile": profile, "phases": {p: phase_contract(p, profile) for p in sorted(ch["contracts"])},
            "external": [list(t) for t in ch["external"]], "sinks": list(SINKS), "problems": problems}


def run_workflow(args, gh=None):
    if args.action == "show" and getattr(args, "ticket", None):
        raw = gh.get_issue(args.ticket)
        if raw is None:
            raise Refused({"ok": False, "reason": "not-found", "issue": args.ticket})
        return {"issue": args.ticket, **ticket_route(normalize(raw), STATE_PATH, args.path)}
    if args.action == "set":
        if not args.name:
            raise Refused({"ok": False, "reason": "profile-name-required", "expected": list(PROFILES)})
        return set_workflow(args.name)
    if args.action == "check":
        profiles = {name: {"ready": meta["ready"], "phases": sorted(chain(name)["contracts"]),
                           "rules": profile_rules(name), "problems": profile_problems(name)}
                    for name, meta in PROFILES.items()}
        signals = signal_problems(signals_of(workflow_block()))
        return {"ok": not signals and not any(p["problems"] for p in profiles.values()), "profiles": profiles,
                "signals": signals}
    current = read_workflow()
    problems = profile_problems(current["profile"]) + signal_problems(signals_of(workflow_block()))
    return {"ok": not problems, **current, "ready": PROFILES[current["profile"]]["ready"],
            "phases": sorted(chain(current["profile"])["contracts"]), "rules": profile_rules(current["profile"]),
            "problems": problems}


def needs_github(args):
    if args.cmd == "workflow":
        return bool(getattr(args, "ticket", None))
    if args.cmd in ("module", "contract"):
        return False
    if args.cmd == "arch":
        return False
    return args.cmd != "wiki" or args.bundle_cmd in ("show", "status", "lint", "snapshot")


def run_module(args):
    if args.action == "list":
        return {"ok": True, "modules": module_registry(read_modules()), "language": read_language()}
    if not args.name:
        raise Refused({"ok": False, "reason": "module-name-required", "expected": list(MODULES)})
    return set_module(args.name, args.action == "enable", with_requires=args.with_requires)


def run(args, gh):
    if args.cmd == "module":
        return run_module(args)
    if args.cmd == "contract":
        return run_contract(args)
    if args.cmd == "workflow":
        return run_workflow(args, gh)
    if args.cmd in ("wiki", "arch"):
        return run_bundle(args, gh)
    machine = Machine(gh)
    if args.cmd == "pool":
        return {"phase": args.phase, **machine.pool(args.phase, args.limit, auto=args.auto)}
    if args.cmd == "resolve":
        return machine.resolve(args.phase, args.issue, args.resume, args.auto)
    if args.cmd == "claim":
        return machine.claim(args.phase, args.issue, args.mode, args.auto)
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
    return 1 if result.get("ok") is False and args.cmd in ("doctor", "wiki", "arch", "contract", "workflow") else 0


if __name__ == "__main__":
    sys.exit(main())
