#!/usr/bin/env python3
"""Mechanical coherence checks for this repo (maintainers of PILOT only; never copied into a project).

Automates the checks CLAUDE.md §3 asks for by hand (cross-references, persona/task-doc lists, label vocabulary,
marked blocks, size of the LLM-read files). No judgment: a finding is either an error (exit 1) or a warning.

Run: python3 scripts/lint_pilot.py [--root DIR] [--json]
"""
import argparse
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SIZE_WARN = {"skill": 26000, "agent": 5000, "doc": 30000}  # bytes: past it, a file loaded on every run deserves a look
LABEL_RE = re.compile(r"`((?:status|type|level|priority|workflow):[a-z0-9-]+)`")
DOC_RE = re.compile(r"pilot-(?:task|link)-[a-z0-9-]+\.md")
COMMAND_RE = re.compile(r"python3 \.pilot/pilot\.py\s+([a-z][a-z-]*)")
MARKER_RE = re.compile(r"<!-- PILOT:([A-Z_]+):(START|END) -->")


def load_pilot(root):
    spec = importlib.util.spec_from_file_location("pilot_engine", root / "scripts" / "pilot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    out = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        if _ and not line.startswith(" "):
            out[k.strip()] = v.strip().strip('"')
    return out


class Linter:
    def __init__(self, root):
        self.root = root
        self.findings = []  # (level, rule, file, message)

    def add(self, level, rule, path, msg):
        self.findings.append((level, rule, str(path.relative_to(self.root)) if isinstance(path, pathlib.Path) else path, msg))

    def files(self):
        r = self.root
        skills = sorted((r / ".claude/skills").glob("*/SKILL.md"))
        agents = sorted((r / ".claude/agents").glob("pilot-*.md"))
        docs = sorted((r / "assets/docs").glob("pilot-*.md"))
        return skills, agents, docs

    def check_frontmatter(self, skills, agents):
        for p in skills:
            fm = frontmatter(p.read_text())
            if fm is None or not fm.get("description"):
                self.add("error", "frontmatter", p, "missing frontmatter or description")
            elif fm.get("name") != p.parent.name:
                self.add("error", "frontmatter", p, f"name '{fm.get('name')}' != directory '{p.parent.name}'")
            elif not p.parent.name.startswith("pilot-"):
                self.add("error", "prefix", p, "a project-local skill needs the pilot- prefix")
        for p in agents:
            fm = frontmatter(p.read_text())
            if fm is None or not fm.get("description"):
                self.add("error", "frontmatter", p, "missing frontmatter or description")
            elif fm.get("name") != p.stem:
                self.add("error", "frontmatter", p, f"name '{fm.get('name')}' != file '{p.stem}'")

    def check_doc_refs(self, skills, agents, docs):
        existing = {p.name for p in docs}
        consumers = skills + agents + docs
        cited = {}
        for p in consumers:
            for name in set(DOC_RE.findall(p.read_text())):
                if name == p.name:
                    continue
                cited.setdefault(name, set()).add(p.name)
                if name not in existing:
                    self.add("error", "doc-ref", p, f"cites {name}, which does not exist in assets/docs/")
        for p in docs:
            if p.name.startswith(("pilot-task-", "pilot-link-")) and p.name not in cited:
                self.add("error", "orphan-doc", p, "no skill, agent or doc cites it")

    def check_agents(self, agents, docs):
        existing = {p.name for p in docs}
        for p in agents:
            body = p.read_text()
            at = body.rfind("Your duties")
            if at < 0:
                self.add("error", "agent-duties", p, "no 'Your duties' paragraph listing its task docs")
                continue
            block = body[at:]  # the closing paragraph: duties line(s) and the skim-the-others reminder
            if "\n\n" in block.rstrip() and block.count("\n\n") > 1:
                self.add("warning", "agent-duties", p, "the duties paragraph should end the file")
            listed = set(re.findall(r"pilot-task-[a-z0-9-]+\.md", block))
            if not listed:
                self.add("error", "agent-duties", p, "duties paragraph cites no pilot-task-*.md")
            for name in listed - existing:
                self.add("error", "agent-duties", p, f"duty {name} does not exist")
            for name in set(re.findall(r"pilot-task-[a-z0-9-]+\.md", body[:at])):
                self.add("warning", "agent-duties", p, f"{name} is cited outside the duties paragraph (a persona carries identity only)")

    def check_labels(self, files):
        mod = load_pilot(self.root)
        known = set(mod.REQUIRED_LABELS) | set(mod.WORKFLOW_LABELS) | set(getattr(mod, "POC_OPEN", ()))
        for p in files:
            for lab in sorted(set(LABEL_RE.findall(p.read_text()))):
                if lab not in known:
                    self.add("error", "label", p, f"`{lab}` is not in the label taxonomy of scripts/pilot.py")

    def check_commands(self, files):
        """Every `python3 .pilot/pilot.py <command>` a skill, doc or refusal message tells to run is a command pilot.py has."""
        mod = load_pilot(self.root)
        parser = mod.build_parser()
        known = set(next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction)).choices)
        for p in files + [self.root / "scripts" / "pilot.py"]:
            for cmd in sorted(set(COMMAND_RE.findall(p.read_text()))):
                if cmd not in known:
                    self.add("error", "command", p, f"`pilot.py {cmd}` is not a command of scripts/pilot.py")

    def check_templates(self):
        tdir = self.root / "assets/templates"
        for name in ("CLAUDE.md.tmpl", "README.md.tmpl"):
            p = tdir / name
            if not p.exists():
                self.add("error", "template", p if isinstance(p, pathlib.Path) else name, "missing")
                continue
            text = p.read_text()
            marks = MARKER_RE.findall(text)
            starts = [n for n, k in marks if k == "START"]
            ends = [n for n, k in marks if k == "END"]
            if sorted(starts) != sorted(ends):
                self.add("error", "marker", p, f"unbalanced PILOT markers: START {sorted(starts)} / END {sorted(ends)}")
            for n in starts:
                kind = "claude" if name.startswith("CLAUDE") else "readme"
                if not (tdir / f"pilot-{n.lower()}-{kind}.md.tmpl").exists():
                    self.add("error", "marker", p, f"marker {n} has no canonical snippet pilot-{n.lower()}-{kind}.md.tmpl")
            outside = MARKER_RE.sub("\x00", re.sub(r"<!-- PILOT:[A-Z_]+:START -->.*?<!-- PILOT:[A-Z_]+:END -->", "\x00", text, flags=re.S))
            for i, ln in enumerate(outside.splitlines(), 1):
                if re.search(r"/pilot-[a-z]+|\.pilot/", ln):
                    self.add("error", "marker", p, f"bare PILOT reference outside a PILOT:<name> block: {ln.strip()[:70]}")

    def check_sizes(self, skills, agents, docs):
        for kind, group in (("skill", skills), ("agent", agents), ("doc", docs)):
            for p in group:
                n = len(p.read_bytes())
                if n > SIZE_WARN[kind]:
                    self.add("warning", "size", p, f"{n} bytes > {SIZE_WARN[kind]} — read on every run; keep it essential-only")

    def check_claude_md(self, skills):
        text = (self.root / "CLAUDE.md").read_text() if (self.root / "CLAUDE.md").exists() else ""
        for p in skills:
            if f"`{p.parent.name}`" not in text:
                self.add("warning", "claude-md", "CLAUDE.md", f"skill {p.parent.name} is not mentioned in §2")

    def run(self):
        skills, agents, docs = self.files()
        llm_read = skills + agents + [p for p in docs if "companion" not in p.name]
        self.check_frontmatter(skills, agents)
        self.check_doc_refs(skills, agents, docs)
        self.check_agents(agents, docs)
        self.check_labels(llm_read)
        self.check_commands(llm_read)
        self.check_templates()
        self.check_sizes(skills, agents, docs)
        self.check_claude_md(skills)
        return self.findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    findings = Linter(pathlib.Path(args.root).resolve()).run()
    errors = [f for f in findings if f[0] == "error"]
    if args.json:
        print(json.dumps([dict(zip(("level", "rule", "file", "message"), f)) for f in findings], indent=1))
    else:
        for lvl, rule, path, msg in findings:
            print(f"{lvl.upper():7} [{rule}] {path}: {msg}")
        print(f"{len(errors)} error(s), {len(findings) - len(errors)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
