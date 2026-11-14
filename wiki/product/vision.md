---
type: Vision
title: Vision
description: PILOT gives a project a lightweight, agent-driven ticket process that works the same on every Claude Code surface.
status: stable
pilot:
  status: implemented
  tickets: []
---

PILOT gives a project a lightweight, agent-driven ticket process, from a raw idea to a merged and verified change, that works the same way on every Claude Code surface (CLI, web, mobile). Its users are the maintainers of the projects that copy it, the humans who drive a phase, and the agents that run one. It is not an application: its product is the process and the tools that carry it.

## What it covers

- The ticket process: five phases (Discovery, Spec, Dev, Review, human QA), each run by a skill in an isolated agent context, with the labels, the claim protocol and the state machine that move a ticket between them.
- The personas the phases delegate to, each with one identity and one task doc per duty.
- Project commands outside the phases: design system and prototypes, the wiki, the architecture bundle, the cockpit dashboard, help.
- Deterministic mechanics as a CLI, so judgment stays with the agents and the rules stay testable.
- Distribution as a plain repo that projects clone and copy from, with optional modules, workflow profiles and per-ticket adaptation.

## What it does not do

- It is not a Claude Code plugin: installation stays local to one machine.
- It has no server or database of its own: tickets live on GitHub, the cockpit's data in its own Claude Artifact.
- It does not replace a project's own CI, deployment or documentation conventions.
- It never merges a pull request on its own: only a human merges, unless they pass `--merge` explicitly.
