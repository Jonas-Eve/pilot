---
type: Vision
title: Vision
description: PILOT gives a project a lightweight, agent-driven ticket process that works the same on every Claude Code surface.
status: stable
pilot:
  status: implemented
  tickets: []
---

PILOT gives a project a lightweight, agent-driven ticket process, from a raw idea to a merged and verified change, that works the same way on every Claude Code surface (CLI, web, mobile). Its users are the maintainers of the projects that copy it, the humans who drive a workflow, and the agents that run one. It is not an application: its product is the process and the tools that carry it.

## What it covers

- The workflows: need, plan, build, accept, report and express, each run by a skill step by step in isolated agent contexts, with the statuses, the claim and the resumable run that move a ticket between them. The human decides through formatted documents; agents execute; code checks.
- The personas the workflows delegate to, each with one identity and one task doc per duty.
- Frames and project commands: the wiki, the architecture bundle, the design system, prototypes, personas and user flows, the cockpit dashboard, help.
- Deterministic mechanics as a CLI, so judgment stays with the agents and the rules stay testable.
- Distribution as a plain repo that projects clone and copy from, with optional modules.

## What it does not do

- It is not a Claude Code plugin: installation stays local to one machine.
- It has no server or database of its own: tickets live on GitHub, the cockpit's data in its own Claude Artifact.
- It does not replace a project's own CI, deployment or documentation conventions.
- It never merges without its checks: the build script merges a PR only once CI passes, after the local review; a human merges any other.
