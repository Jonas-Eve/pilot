"""PILOT's code checks: what a workflow's `check` steps verify, with no judgment (assets/docs/pilot-process.md §3).

`pilot.py check <id> --arg key=value …` runs one of them; `CHECKS` is the registry the workflows' `check` ids resolve to.
A check reads what it needs through a `Ctx` (the documents, the previous version of one, the vocabulary, the run's data, a
ticket) and returns a list of problems, each `{"code": …}`; none means it passes. Formats are `assets/formats.json`.
"""
import datetime
import json
import os
import re
import subprocess

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
XREF_RE = re.compile(r"^[a-z0-9-]+#[A-Z]\d+$")
HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def problem(code, **extra):
    return {"code": code, **extra}


# ---- formats -------------------------------------------------------------------------------------------
_FORMATS = {}


def formats(root="."):
    if "f" not in _FORMATS:
        here = os.path.dirname(os.path.abspath(__file__))
        for path in (os.path.join(here, "formats.json"), os.path.join(here, os.pardir, "assets", "formats.json")):
            if os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    _FORMATS["f"] = json.load(handle)
                break
        else:
            raise FileNotFoundError("formats.json")
    return _FORMATS["f"]


def split_front(text):
    m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", text)


def front_value(front, dotted):
    """A key of a frontmatter block, `pilot.scope` meaning `scope` inside the `pilot:` block (the engine's YAML subset)."""
    parts, block = dotted.split("."), front.splitlines()
    lines = block
    if len(parts) == 2:
        out, inside = [], False
        for line in block:
            if re.match(rf"^{parts[0]}\s*:\s*$", line):
                inside = True
            elif inside and re.match(r"^\s+\S", line):
                out.append(line.strip())
            elif inside:
                break
        lines = out
    for line in lines:
        m = re.match(rf"^\s*{re.escape(parts[-1])}\s*:\s*(.*)$", line)
        if m:
            return m.group(1).strip().strip('"')
    return None


def parse_document(text):
    """{"front": raw frontmatter, "sections": {name: [{"id", "fields", "raw"}]}, "prose": {name: text}}: the lines of every section
    that look like `- ID | key: value | key: value`."""
    front, body = split_front(text)
    sections, prose, name = {}, {}, None
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            name = m.group(1)
            sections.setdefault(name, [])
            prose.setdefault(name, "")
            continue
        if name is None:
            continue
        prose[name] += line + "\n"
        if line.startswith("- "):
            cells = [c.strip() for c in line[2:].split(" | ")]
            fields = {}
            for cell in cells[1:]:
                k, _, v = cell.partition(":")
                if _:
                    fields[k.strip()] = v.strip()
            sections[name].append({"id": cells[0], "fields": fields, "raw": line})
    return {"front": front, "sections": sections, "prose": prose}


def read_doc(path):
    with open(path, encoding="utf-8") as handle:
        return parse_document(handle.read())


def words_ambiguous(text):
    low = f" {text.lower()} "
    return [w for w in formats()["ambiguous"] if re.search(rf"(?<![\w-]){re.escape(w.lower())}(?![\w-])", low)]


def check_type(kind, value, doc, ctx):
    """A problem code, or None, for one field value."""
    if kind.endswith("?"):
        kind = kind[:-1]
    if kind == "text":
        return None if value.strip() else "empty"
    if kind == "date":
        return None if DATE_RE.match(value) else "not-a-date"
    if kind.startswith("enum:"):
        return None if value in kind[5:].split(",") else "not-in-enum"
    if kind.startswith("ref:"):
        ids = {x["id"] for x in doc["sections"].get(kind[4:], [])}
        return None if all(v.strip() in ids for v in value.split(",")) else "unknown-ref"
    if kind == "xref":
        return None if XREF_RE.match(value) else "bad-xref"
    if kind == "xref|to-create":
        return None if XREF_RE.match(value) or value == "to-create" else "bad-xref"
    if kind.startswith("list:"):
        parts = [v.strip() for v in value.split(",") if v.strip()]
        if not parts:
            return "empty"
        inner = kind[5:]
        if inner == "scope":
            vocab = ctx.scopes()
            return None if all(p in vocab for p in parts) else "unknown-scope"
        return next((c for c in (check_type(inner, p, doc, ctx) for p in parts) if c), None)
    return None


def validate_markdown(fmt_id, doc, ctx):
    """The problems of a parsed document against one markdown format."""
    fmt, problems = formats()["formats"][fmt_id], []
    for key, kind in fmt.get("frontmatter", {}).items():
        value = front_value(doc["front"], key)
        if value is None or value in ("", "[]"):
            if not kind.endswith("?"):
                problems.append(problem("missing-frontmatter", key=key))
            continue
        code = check_type(kind, value.strip("[]"), doc, ctx)
        if code:
            problems.append(problem(code, key=key, value=value))
    for name, spec in fmt["sections"].items():
        lines = doc["sections"].get(name)
        if lines is None:
            if spec.get("required"):
                problems.append(problem("missing-section", section=name))
            continue
        if spec.get("required") and not lines:
            problems.append(problem("empty-section", section=name))
        seen = set()
        for line in lines:
            lid = line["id"]
            if not re.fullmatch(spec["id"], lid):
                problems.append(problem("bad-id", section=name, line=line["raw"][:80]))
                continue
            if lid in seen:
                problems.append(problem("duplicate-id", section=name, id=lid))
            seen.add(lid)
            for field, kind in spec["fields"].items():
                value = line["fields"].get(field)
                if value is None:
                    if not kind.endswith("?"):
                        problems.append(problem("missing-field", section=name, id=lid, field=field))
                    continue
                code = check_type(kind, value, doc, ctx)
                if code:
                    problems.append(problem(code, section=name, id=lid, field=field))
                if kind.rstrip("?") == "text":
                    for word in words_ambiguous(value):
                        problems.append(problem("ambiguous-word", section=name, id=lid, word=word))
            extra = set(line["fields"]) - set(spec["fields"])
            if extra:
                problems.append(problem("unknown-field", section=name, id=lid, fields=sorted(extra)))
    return problems


def validate_json(data, schema, path="$"):
    """A mini JSON-schema check: type, required, enum, pattern, min items, items, properties."""
    problems = []
    kinds = {"object": dict, "array": list, "string": str, "number": (int, float), "boolean": bool}
    if "enum" in schema and data not in schema["enum"]:
        return [problem("not-in-enum", path=path)]
    if "type" in schema and not isinstance(data, kinds[schema["type"]]):
        return [problem("wrong-type", path=path, expected=schema["type"])]
    if isinstance(data, str) and "pattern" in schema and not re.fullmatch(schema["pattern"], data):
        problems.append(problem("bad-pattern", path=path, value=data[:60]))
    if isinstance(data, str) and schema.get("type") == "string" and not data.strip():
        problems.append(problem("empty", path=path))
    if isinstance(data, dict):
        problems += [problem("missing-field", path=path, field=k) for k in schema.get("required", []) if k not in data]
        for k, sub in schema.get("properties", {}).items():
            if k in data:
                problems += validate_json(data[k], sub, f"{path}.{k}")
    if isinstance(data, list):
        if len(data) < schema.get("min", 0):
            problems.append(problem("too-few", path=path, min=schema["min"]))
        for i, item in enumerate(data):
            problems += validate_json(item, schema.get("items", {}), f"{path}[{i}]")
    return problems


# ---- context -------------------------------------------------------------------------------------------
class Ctx:
    """What a check may read. `args` are the `--arg key=value` of the command; `run` is the run record's data (when given)."""

    def __init__(self, args=None, root=".", run=None, machine=None):
        self.args, self.root, self.run, self.machine = args or {}, root, run or {}, machine
        self._scopes = None

    def need(self, key):
        if key not in self.args:
            raise KeyError(key)
        return self.args[key]

    def path(self, key):
        return os.path.join(self.root, self.need(key))

    def doc(self, key):
        return read_doc(self.path(key))

    def previous(self, key, ref="origin/main"):
        """The parsed document as `ref` has it, or None when it did not exist there."""
        out = subprocess.run(["git", "show", f"{ref}:{self.need(key)}"], cwd=self.root, capture_output=True, text=True)
        return parse_document(out.stdout) if out.returncode == 0 else None

    def json(self, key):
        with open(self.path(key), encoding="utf-8") as handle:
            return json.load(handle)

    def scopes(self):
        if self._scopes is None:
            terms = set()
            for rel in ("wiki/vocabulary.md", "architecture/scopes.md"):
                path = os.path.join(self.root, rel)
                if os.path.exists(path):
                    terms |= {x["id"] for x in read_doc(path)["sections"].get("Terms", [])}
            self._scopes = terms | set(filter(None, self.args.get("extra_scopes", "").split(",")))
        return self._scopes

    def ticket(self, number):
        return self.machine.gh.get_issue(int(number)) if self.machine else None


# ---- shared rules --------------------------------------------------------------------------------------
def journal_problems(doc, previous):
    """Journal lines are append-only: the previous lines unchanged and in place; a modified entry gains at least one new line."""
    now = [x["raw"] for x in doc["sections"].get("Journal", [])]
    if previous is None:
        return []
    before = [x["raw"] for x in previous["sections"].get("Journal", [])]
    problems = []
    if now[:len(before)] != before:
        problems.append(problem("journal-rewritten"))
    changed = {k: [x["raw"] for x in v] for k, v in doc["sections"].items() if k != "Journal"} != \
              {k: [x["raw"] for x in v] for k, v in previous["sections"].items() if k != "Journal"}
    if changed and len(now) <= len(before):
        problems.append(problem("journal-line-missing"))
    return problems


def overlaps(scope_a, scope_b):
    return bool(set(scope_a) & set(scope_b))


def no_undeclared_overlap(doc, ctx, others_key="accepted", replaces_key="replaces"):
    """An accepted entry whose scope overlaps this one's must be replaced by it (`replaces` in the frontmatter)."""
    scope = [s.strip() for s in (front_value(doc["front"], "pilot.scope") or "").strip("[]").split(",") if s.strip()]
    replaces = {s.strip() for s in (front_value(doc["front"], "replaces") or "").strip("[]").split(",") if s.strip()}
    try:
        accepted = json.loads(ctx.args.get(others_key, "[]"))
    except ValueError:
        accepted = []
    return [problem("overlaps-accepted", id=a["id"]) for a in accepted if overlaps(scope, a.get("scope", [])) and a["id"] not in replaces]


def contrast(fg, bg):
    """WCAG contrast ratio of two #rgb / #rrggbb colors."""
    def lum(c):
        c = c.lstrip("#")
        c = "".join(ch * 2 for ch in c) if len(c) == 3 else c
        out = []
        for i in (0, 2, 4):
            v = int(c[i:i + 2], 16) / 255
            out.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def has_cycle(edges):
    """Whether a {node: [nodes it depends on]} graph has a cycle."""
    state = {}

    def visit(n):
        if state.get(n) == 1:
            return True
        if state.get(n) == 2:
            return False
        state[n] = 1
        if any(visit(m) for m in edges.get(n, []) if m in edges):
            return True
        state[n] = 2
        return False
    return any(visit(n) for n in edges)


# ---- the registry --------------------------------------------------------------------------------------
CHECKS = {}
NEEDS_GH = set()  # checks that read a ticket
PROTO_FORBIDDEN = (
    (re.compile(r"https?://", re.I), "an external URL (the mockup must be self-contained)"),
    (re.compile(r"""(?:src|href|action|poster)\s*=\s*["']?\s*//""", re.I), "a protocol-relative URL"),
    (re.compile(r"@import", re.I), "@import"),
    (re.compile(r"<\s*(?:iframe|object|embed|link|base)\b", re.I), "an iframe, object, embed, link or base element"),
    (re.compile(r"<\s*meta[^>]+http-equiv\s*=\s*[\"']?refresh", re.I), "a meta refresh"),
)
PROTO_BYTES = 200_000


def check(cid, gh=False):
    def register(fn):
        CHECKS[cid] = fn
        if gh:
            NEEDS_GH.add(cid)
        return fn
    return register


def csv(ctx, key, default=""):
    return [x.strip() for x in ctx.args.get(key, default).split(",") if x.strip()]


def jsonarg(ctx, key, default=None):
    """An argument holding a JSON file's path, read."""
    return ctx.json(key) if key in ctx.args else default


def entry_ids(doc, section):
    return [x["id"] for x in doc["sections"].get(section, [])]


def open_tickets_on(ctx, entry_paths, exclude=None):
    """Open tickets other than `exclude` that an entry lists (`pilot.tickets`) and that are being planned, built or reviewed."""
    busy, found = ("status:planning", "status:building", "status:reviewing"), []
    if not ctx.machine:
        return found
    for rel in entry_paths:
        doc = read_doc(os.path.join(ctx.root, rel))
        for n in re.findall(r"\d+", front_value(doc["front"], "pilot.tickets") or ""):
            if exclude is not None and int(n) == int(exclude):
                continue
            raw = ctx.ticket(n)
            labels = {l["name"] if isinstance(l, dict) else l for l in (raw or {}).get("labels", [])}
            if raw and raw.get("state") == "open" and labels & set(busy):
                found.append(int(n))
    return sorted(set(found))


def criteria_of(ctx, paths):
    """{"<entry id>#C1": {"by": …}} for the entries at `paths`."""
    out = {}
    for rel in paths:
        doc = read_doc(os.path.join(ctx.root, rel))
        eid = os.path.splitext(os.path.basename(rel))[0]
        for c in doc["sections"].get("Criteria", []):
            out[f"{eid}#{c['id']}"] = c["fields"]
    return out


# ---- documents of the need, frame and plan workflows ---------------------------------------------------
@check("need.check")
def need_check(ctx):
    """--arg entry=<path> [--arg parcours=a,b] [--arg previous_ref=origin/main]"""
    doc = ctx.doc("entry")
    problems = validate_markdown("need-entry", doc, ctx)
    problems += journal_problems(doc, ctx.previous("entry", ctx.args.get("previous_ref", "origin/main")))
    flows = {c["fields"].get("flow") for c in doc["sections"].get("Criteria", [])}
    problems += [problem("parcours-not-covered", parcours=p) for p in csv(ctx, "parcours") if p not in flows]
    return problems


@check("need.check-2", gh=True)
def need_group_check(ctx):
    """--arg proposal=<json: story (number|"new"), epic (number|"new"|null), entries [ids], explanation>"""
    prop, problems = jsonarg(ctx, "proposal"), []
    if not str(prop.get("explanation") or "").strip():
        problems.append(problem("explanation-missing"))
    entries = prop.get("entries") or []
    if not entries or len(entries) != len(set(entries)):
        problems.append(problem("entries-not-unique-or-empty"))
    for key, level in (("story", "level:story"), ("epic", "level:epic")):
        value = prop.get(key)
        if value in (None, "new"):
            continue
        raw = ctx.ticket(value)
        labels = {l["name"] if isinstance(l, dict) else l for l in (raw or {}).get("labels", [])}
        if raw is None or level not in labels:
            problems.append(problem(f"{key}-not-found", ticket=value))
        elif key == "story" and "status:forming" not in labels:
            problems.append(problem("story-not-forming", ticket=value))
    return problems


def frame_check(ctx):
    doc = ctx.doc("entry")
    return validate_markdown("frame", doc, ctx) + no_undeclared_overlap(doc, ctx)


CHECKS["functional-frame.check"] = frame_check
CHECKS["technical-frame.check"] = frame_check


@check("technical-frame.check-2")
def rule_check(ctx):
    """--arg entry=<path> --arg results=<json: rules [{id, of}], examples [{id, of, kind, ok}], violation_detected>"""
    doc, res, problems = ctx.doc("entry"), jsonarg(ctx, "results"), []
    by_rule = {s["id"] for s in doc["sections"].get("Statements", []) if s["fields"].get("by") == "rule"}
    covered = {r.get("of") for r in res.get("rules", [])}
    problems += [problem("statement-without-rule", id=i) for i in sorted(by_rule - covered)]
    known = set(entry_ids(doc, "Statements"))
    problems += [problem("rule-without-statement", id=r.get("id")) for r in res.get("rules", []) if r.get("of") not in known]
    problems += [problem("example-fails", id=e.get("id")) for e in res.get("examples", []) if not e.get("ok")]
    if not res.get("rules"):
        problems.append(problem("empty-rule"))
    if not res.get("violation_detected"):
        problems.append(problem("injected-violation-not-detected"))
    return problems


@check("plan.check")
def plan_check(ctx):
    """--arg plan=<json> --arg entries=<paths> [--arg adrs=<paths>] --arg orientation=<text|none> [--arg sizes=<json> --arg threshold=N]"""
    plan = jsonarg(ctx, "plan")
    problems = validate_json(plan, formats()["formats"]["plan"]["json"])
    if problems:
        return problems
    tickets = plan["tickets"]
    ids = [t["id"] for t in tickets]
    problems += [problem("duplicate-ticket-id", id=i) for i in sorted({i for i in ids if ids.count(i) > 1})]
    crit = criteria_of(ctx, csv(ctx, "entries"))
    crit.update(criteria_of(ctx, csv(ctx, "adrs")))  # a technical need has no entry: its criteria live in its ADR
    placed = {}
    for t in tickets:
        for c in t["criteria"]:
            placed.setdefault(c, []).append(t["id"])
    problems += [problem("criterion-in-no-ticket", id=c) for c in sorted(set(crit) - set(placed))]
    problems += [problem("criterion-in-several-tickets", id=c, tickets=v) for c, v in sorted(placed.items()) if len(v) > 1]
    problems += [problem("unknown-criterion", id=c) for c in sorted(set(placed) - set(crit))]
    decisions = {}
    for rel in csv(ctx, "adrs"):
        adr = read_doc(os.path.join(ctx.root, rel))
        aid = os.path.splitext(os.path.basename(rel))[0]
        problems += validate_markdown("adr-local", adr, ctx)
        for d in adr["sections"].get("Decisions", []):
            decisions[f"{aid}#{d['id']}"] = [x.strip() for x in d["fields"].get("covers", "").split(",")]
    problems += [problem("unknown-decision", ticket=t["id"], id=d) for t in tickets for d in t.get("decisions", []) if d not in decisions]
    covered = {c for covers in decisions.values() for c in covers}
    own = set(criteria_of(ctx, csv(ctx, "adrs")))  # an ADR's own criteria are covered by it
    problems += [problem("criterion-without-decision", id=c) for c in sorted(set(crit) - covered - own)]
    deps = {t["id"]: t.get("depends", []) for t in tickets}
    problems += [problem("unknown-dependency", ticket=t, depends=d) for t, ds in deps.items() for d in ds if d not in deps]
    if has_cycle(deps):
        problems.append(problem("dependency-cycle"))
    tasks = [t for t in tickets if t["level"] == "task"]
    for t in tasks:
        if not any(crit.get(c, {}).get("by") not in (None, "judgment") for c in t["criteria"]):
            problems.append(problem("task-without-verifiable-criterion", ticket=t["id"]))
    for i, a in enumerate(tasks):
        for b in tasks[i + 1:]:
            if overlaps(a["scope"], b["scope"]) and b["id"] not in deps[a["id"]] and a["id"] not in deps[b["id"]]:
                problems.append(problem("overlap-without-dependency", tickets=[a["id"], b["id"]]))
    sizes, threshold = jsonarg(ctx, "sizes", {}), int(ctx.args.get("threshold", 0) or 0)
    if threshold:
        problems += [problem("task-too-large", ticket=t["id"], size=sizes.get(t["id"])) for t in tasks if sizes.get(t["id"], 0) > threshold]
        if tasks and not any(sizes.get(t["id"], 0) > threshold for t in tickets if t["level"] == "story") and sum(sizes.values()) <= threshold:
            problems.append(problem("split-not-needed", size=sum(sizes.values())))
    if str(ctx.args.get("orientation", "")).strip() == "":
        problems.append(problem("orientation-missing"))
    return problems


@check("plan.eligibility", gh=True)
def plan_eligibility(ctx):
    """--arg ticket=N --arg entries=<paths>: the ticket is to-plan, its entries are proposed and valid, none is being planned"""
    raw, problems = ctx.ticket(ctx.need("ticket")), []
    labels = {l["name"] if isinstance(l, dict) else l for l in (raw or {}).get("labels", [])}
    if raw is None or "status:to-plan" not in labels:
        problems.append(problem("not-to-plan"))
    for rel in csv(ctx, "entries"):
        doc = read_doc(os.path.join(ctx.root, rel))
        if front_value(doc["front"], "pilot.status") != "proposed":
            problems.append(problem("entry-not-ready", entry=rel))
        problems += [dict(p, entry=rel) for p in validate_markdown("need-entry", doc, ctx)]
    problems += [problem("already-being-planned", ticket=n) for n in open_tickets_on(ctx, csv(ctx, "entries"), ctx.args.get("ticket"))]
    return problems


@check("build.claim", gh=True)
def build_claim(ctx):
    """--arg ticket=N [--arg entries=<paths> --arg adrs=<paths>]: criteria ready (or in gap for a fix, provisional for an express), ADRs accepted, dependencies merged, no other open ticket on them"""
    raw = ctx.ticket(ctx.need("ticket"))
    labels = {l["name"] if isinstance(l, dict) else l for l in (raw or {}).get("labels", [])}
    problems = []
    if raw is None or "status:ready" not in labels and "express" not in labels:
        problems.append(problem("not-ready"))
    okay = {"specified", "provisional"} if "fix" not in labels else {"specified", "implemented", "provisional"}
    for rel in csv(ctx, "entries"):
        doc = read_doc(os.path.join(ctx.root, rel))
        if front_value(doc["front"], "pilot.status") not in okay:
            problems.append(problem("criteria-not-ready", entry=rel))
    for rel in csv(ctx, "adrs"):
        status = front_value(read_doc(os.path.join(ctx.root, rel))["front"], "pilot.status")
        if status not in ("accepted",) + (("provisional",) if "express" in labels else ()):
            problems.append(problem("adr-not-accepted", adr=rel, status=status))
    if ctx.machine and raw:
        from pilot import normalize  # the engine's own normalisation of an issue
        deps = ctx.machine.blocking_dependencies(normalize(raw))
        problems += [problem("depends-on-open", ticket=d) for d in deps]
    problems += [problem("other-ticket-on-criteria", ticket=n) for n in open_tickets_on(ctx, csv(ctx, "entries"), ctx.args.get("ticket"))]
    return problems


def _results_problems(ctx, rules):
    res = jsonarg(ctx, "results")
    return [problem(code, **({"detail": res.get(key)} if res.get(key) not in (None, True) else {})) for key, code in rules if not res.get(key)]


@check("build.check")
def build_check(ctx):
    """--arg results=<json: tests_ok, rules_ok, hypotheses_declared, diff_paths, scope_globs, criteria (the ids whose `by` is test), test_refs>"""
    res = jsonarg(ctx, "results")
    problems = _results_problems(ctx, (("tests_ok", "tests-failing"), ("rules_ok", "rules-failing"), ("hypotheses_declared", "hypotheses-undeclared")))
    from fnmatch import fnmatch
    globs = res.get("scope_globs", [])
    problems += [problem("outside-scope", path=p) for p in res.get("diff_paths", []) if globs and not any(fnmatch(p, g) for g in globs)]
    refs = res.get("test_refs", {})
    problems += [problem("criterion-without-test", id=c) for c in res.get("criteria", []) if not refs.get(c)]
    return problems


@check("build.check-2")
def e2e_check(ctx):
    """--arg results=<json: e2e_ok, criteria_e2e (the ids whose `by` is e2e), e2e_refs {id: [tests]}>"""
    res = jsonarg(ctx, "results")
    problems = _results_problems(ctx, (("e2e_ok", "e2e-failing"),))
    return problems + [problem("criterion-without-e2e", id=c) for c in res.get("criteria_e2e", []) if not res.get("e2e_refs", {}).get(c)]


@check("build.decision")
def review_decision(ctx):
    """--arg reviews=<json: [{persona, verdict, defects: [{class, blocking, text}]}]>: the blocking defects, by class"""
    return [problem("blocking-defect", persona=r.get("persona"), class_=d.get("class"), text=str(d.get("text", ""))[:120])
            for r in jsonarg(ctx, "reviews", []) for d in r.get("defects", []) if d.get("blocking")]


@check("express.check")
def express_check(ctx):
    """--arg entry=<path> [--arg changed_paths=<json list>] [--arg accepted=<json>]: provisional documents, journal, no frame touched, nothing accepted contradicted"""
    doc, problems = ctx.doc("entry"), []
    problems += validate_markdown("need-entry", doc, ctx)
    if front_value(doc["front"], "pilot.status") != "provisional":
        problems.append(problem("not-provisional"))
    problems += journal_problems(doc, ctx.previous("entry"))
    problems += no_undeclared_overlap(doc, ctx)
    frames = ("architecture/guidelines/", "architecture/overview", "architecture/scopes", "wiki/vocabulary", "design/")
    changed = jsonarg(ctx, "changed_paths", [])
    problems += [problem("frame-modified", path=p) for p in changed if p.startswith(frames)]
    problems += [problem("ticket-open-on-criteria", ticket=n) for n in open_tickets_on(ctx, [ctx.need("entry")])]
    return problems


@check("persona.check")
def persona_check(ctx):
    """--arg entry=<path>"""
    return validate_markdown("persona", ctx.doc("entry"), ctx)


@check("user-flow.check")
def user_flow_check(ctx):
    """--arg entry=<path>"""
    doc = ctx.doc("entry")
    problems = validate_markdown("user-flow", doc, ctx)
    problems += journal_problems(doc, ctx.previous("entry"))
    steps = {s["id"]: s for s in doc["sections"].get("Steps", [])}
    created = {c["fields"].get("from") for c in doc["sections"].get("Candidates", [])}
    problems += [problem("to-create-without-candidate", step=i) for i, s in steps.items() if s["fields"].get("source") == "to-create" and i not in created]
    for p in (front_value(doc["front"], "pilot.personas") or "").strip("[]").split(","):
        if p.strip() and not os.path.exists(os.path.join(ctx.root, "wiki", "persona", f"{p.strip()}.md")):
            problems.append(problem("unknown-persona", persona=p.strip()))
    return problems


@check("report.check")
def report_check(ctx):
    """--arg form=<json> [--arg known_versions=<json list>]"""
    form = jsonarg(ctx, "form")
    problems = validate_json(form, formats()["formats"]["report-form"]["json"])
    known = jsonarg(ctx, "known_versions", None)
    if not problems and known is not None and form["seen"] not in known and not DATE_RE.match(form["seen"]):
        problems.append(problem("unknown-version", seen=form["seen"]))
    shot = form.get("screenshot") if isinstance(form, dict) else None
    if shot and not (os.path.exists(os.path.join(ctx.root, shot)) and os.path.getsize(os.path.join(ctx.root, shot)) > 0):
        problems.append(problem("screenshot-unreadable", path=shot))
    return problems


@check("report.check-2")
def report_qualification_check(ctx):
    """--arg qualification=<json: kind, cites [ids], severity, scope [terms]> --arg known_ids=<json list>"""
    q, problems = jsonarg(ctx, "qualification"), []
    if q.get("kind") not in ("gap", "uncovered", "technical", "conform", "duplicate"):
        problems.append(problem("kind-missing"))
    if q.get("severity") not in ("blocking", "major", "minor"):
        problems.append(problem("severity-missing"))
    known = set(jsonarg(ctx, "known_ids", []))
    problems += [problem("cited-id-unknown", id=c) for c in q.get("cites", []) if c not in known]
    if q.get("kind") in ("gap", "conform", "duplicate") and not q.get("cites"):
        problems.append(problem("nothing-cited"))
    problems += [problem("unknown-scope", scope=s) for s in q.get("scope", []) if s not in ctx.scopes()]
    return problems


@check("accept.eligibility")
def accept_eligibility(ctx):
    """--arg deployed=<json: version, contains [commits], healthy> --arg merges=<json list of commits> [--arg persona=id] --arg executant=human|ai [--arg criteria_by=<json list>]"""
    dep, problems = jsonarg(ctx, "deployed"), []
    contained = set(dep.get("contains", []))
    problems += [problem("merge-not-deployed", commit=c) for c in jsonarg(ctx, "merges", []) if c not in contained]
    if not dep.get("healthy", True):
        problems.append(problem("environment-unhealthy"))
    persona = ctx.args.get("persona")
    if persona and persona != "none" and not os.path.exists(os.path.join(ctx.root, "wiki", "persona", f"{persona}.md")):
        problems.append(problem("unknown-persona", persona=persona))
    if ctx.args.get("executant") == "ai" and {"human", "judgment"} & set(jsonarg(ctx, "criteria_by", [])):
        problems.append(problem("human-required"))
    return problems


@check("accept.check")
def accept_plan_check(ctx):
    """--arg plan=<json> --arg criteria=<json list of the ids or steps the plan must cover>"""
    plan = jsonarg(ctx, "plan")
    problems = validate_json(plan, formats()["formats"]["recipe-plan"]["json"])
    if problems:
        return problems
    wanted = set(jsonarg(ctx, "criteria", []))
    sources = {c["source"] for c in plan["cases"]}
    return [problem("case-without-source", source=s) for s in sorted(sources - wanted)] + \
           [problem("criterion-without-case", id=c) for c in sorted(wanted - sources)]


@check("accept.dossier")
def accept_dossier(ctx):
    """--arg record=<json> --arg plan=<json>"""
    rec, plan = jsonarg(ctx, "record"), jsonarg(ctx, "plan")
    problems = validate_json(rec, formats()["formats"]["recipe-record"]["json"])
    if problems:
        return problems
    done = {r["case"]: r for r in rec["results"]}
    for case in plan["cases"]:
        r = done.get(case["id"])
        if r is None:
            problems.append(problem("case-without-result", case=case["id"]))
        elif not (r.get("proof") or r.get("comment")):
            problems.append(problem("result-without-proof", case=case["id"]))
    return problems


@check("design-system.check")
def design_check(ctx):
    """--arg entry=<path>"""
    doc = ctx.doc("entry")
    problems = validate_markdown("design-entry", doc, ctx)
    tokens = {t["id"]: t["fields"] for t in doc["sections"].get("Tokens", [])}
    for tid, f in tokens.items():
        for theme in ("light", "dark"):
            if f.get(theme) is None:
                problems.append(problem("theme-incomplete", token=tid, theme=theme))
        on = f.get("on")
        if on:
            if on not in tokens:
                problems.append(problem("unknown-token", token=tid, on=on))
                continue
            for theme in ("light", "dark"):
                fg, bg = f.get(theme, ""), tokens[on].get(theme, "")
                if HEX_RE.match(fg) and HEX_RE.match(bg) and contrast(fg, bg) < 4.5:
                    problems.append(problem("contrast-below-aa", token=tid, on=on, theme=theme, ratio=round(contrast(fg, bg), 2)))
    seen = {}
    for tid, f in tokens.items():
        key = (f.get("light"), f.get("dark"))
        if key in seen:
            problems.append(problem("duplicate-value", tokens=[seen[key], tid]))
        seen[key] = tid
    required = formats()["formats"]["design-entry"]["required_states"]
    for c in doc["sections"].get("Components", []):
        have = {s.strip() for s in c["fields"].get("states", "").split(",")}
        missing = [s for s in required.get(c["fields"].get("category"), []) if s not in have]
        if missing:
            problems.append(problem("states-missing", component=c["id"], states=missing))
        problems += [problem("unknown-token", component=c["id"], token=t.strip()) for t in c["fields"].get("tokens", "").split(",")
                     if t.strip() and t.strip() not in tokens]
    return problems


@check("design-system.check-2")
def design_results_check(ctx):
    """--arg results=<json: build_ok, theme_identical, a11y_violations [], rules_ok, examples_ok, rule_nonempty>"""
    res = jsonarg(ctx, "results")
    problems = _results_problems(ctx, (("build_ok", "build-failing"), ("theme_identical", "theme-edited-by-hand"),
                                       ("rules_ok", "rules-failing"), ("examples_ok", "examples-failing"), ("rule_nonempty", "empty-rule")))
    return problems + [problem("a11y-violation", detail=v) for v in res.get("a11y_violations", [])]


@check("proto.check")
def proto_check(ctx):
    """--arg html=<path> --arg parcours=a,b [--arg render=<json: tap_ok, contrast_ok, keyboard_ok, unreachable []>] [--arg tokens=<design entry path>]"""
    with open(ctx.path("html"), encoding="utf-8") as handle:
        html = handle.read()
    problems = []
    if not html.strip():
        problems.append(problem("empty"))
    if len(html.encode("utf-8")) > PROTO_BYTES:
        problems.append(problem("too-large", bytes=len(html.encode("utf-8"))))
    scan = re.sub(r'xmlns(?::\w+)?\s*=\s*"[^"]*"', "", html)
    problems += [problem("not-self-contained", what=label) for pattern, label in PROTO_FORBIDDEN if pattern.search(scan)]
    if not re.search(r"<meta[^>]+name=[\"']viewport", html, re.I):
        problems.append(problem("no-viewport"))
    covered = set(re.findall(r'data-parcours="([^"]+)"', html))
    covered = {p for group in covered for p in group.split()}
    problems += [problem("parcours-without-screen", parcours=p) for p in csv(ctx, "parcours") if p not in covered]
    render = jsonarg(ctx, "render", None)
    if render is None:
        problems.append(problem("not-rendered"))
    else:
        problems += [problem(code) for key, code in (("tap_ok", "tap-targets-below-44px"), ("contrast_ok", "contrast-below-aa"),
                                                      ("keyboard_ok", "not-keyboard-usable")) if not render.get(key)]
        problems += [problem("unreachable", what=u) for u in render.get("unreachable", [])]
    if "tokens" in ctx.args:
        tokens = ctx.doc("tokens")["sections"].get("Tokens", [])
        known = {v.lower() for t in tokens for v in (t["fields"].get("light"), t["fields"].get("dark")) if v}
        used = sorted({c.lower() for c in re.findall(r"#[0-9a-fA-F]{3,6}\b", html)} - known)
        if used:
            problems.append({"code": "outside-design-system", "values": used, "info": True})
    return problems
