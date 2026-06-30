---
status: approved
tags:
  - org/alpha-apps
  - repo/forgingalpha-github
---
# ForgingAlpha/.github - Intent

## Purpose

`ForgingAlpha/.github` exists to provide the public shared GitHub automation
layer for ForgingAlpha repositories.

It centralizes CI, workflow templates, Dependabot automation, release mechanics,
and cross-repo workflow policy so consuming repositories stay consistent without
copying or forking workflow logic.

## Served Audience Or System

- ForgingAlpha repositories that consume shared GitHub automation.
- AI coding agents and human maintainers who need predictable cross-repo CI
  behavior.

## Durable Outcomes

- Consuming repositories have a consistent required `CI` status.
- Shared automation remains centralized, strict, and reproducible.
- Organization-wide automation changes are reviewed and released deliberately.
- Public `.github` content remains safe to expose.
- Active ForgingAlpha repositories can rely on shared policy checks to require
  baseline source truth and Product Evidence before ordinary work proceeds.
- Required CI remains the merge authority; diagnostic workflows provide evidence
  only.

## Boundaries

### Intended Ownership

- Shared composite actions under `actions/`.
- Repo-owned GitHub workflows under `.github/workflows/`.
- Workflow templates and public examples for consuming repos.
- Release-tag mechanics for shared action versions.
- Public-safe cross-repo CI and workflow policy.

### Not Intended To Own

- Product behavior inside consuming application repositories.
- Runtime secrets, deployment credentials, or private customer data.
- Private worktree paths, private incident evidence, or repo-specific failure
  details.
- The private Alpha Apps lifecycle, convention, skill, agent, or runbook source.
- Repo-specific runtime commands that must remain owned by the consuming repo.
- Diagnostic probe workflows as required merge checks.

## Invariants And Tradeoffs

- Consuming repositories keep a single required status named `CI`.
- Shared action consumers use released tags such as `@v1`; moving `v1` is the
  shared-action rollout boundary.
- Use composite actions when preserving the caller job name is part of the
  consumer contract.
- Prefer deterministic CI checks over LLM judgment when behavior can be checked
  mechanically.
- Centralize only rules that are genuinely cross-repo.
- Keep private Alpha Apps policy and evidence out of this public repository.
