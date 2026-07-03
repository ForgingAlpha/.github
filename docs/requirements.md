---
status: approved
tags:
  - org/alpha-apps
  - topic/github
---
# ForgingAlpha/.github - Requirements

> Reading note. These requirements derive from [intent.md](intent.md).
> Architecture chooses how this repo satisfies them.

---

## Actors

- **Consumer Repository** - a ForgingAlpha repository that uses shared GitHub
  automation from this repository.
- **Control-Plane Maintainer** - a human or bot-assisted maintainer changing
  this repository through review and release.
- **Shared Automation** - composite actions, workflows, templates, examples,
  Dependabot helpers, release mechanics, and policy checks owned by this repo.
- **Diagnostic Workflow** - a manually or selectively run workflow that collects
  evidence without granting merge permission.
- **Dependency Update Coverage** - repo-local Dependabot configuration that
  covers the dependency ecosystems and GitHub Actions manifests present in a
  Consumer Repository.
- **Product Evidence** - required repo-local verification evidence files under
  `docs/evidence/` that connect important promises to current proof for active
  ForgingAlpha repositories.

## Requirements

### Shared Automation Contract

#### REQ-001 - Consistent Required Status

Shared Automation SHALL preserve a single required GitHub status named `CI` for
standard Consumer Repository workflows.

**Fit:** A standard consumer workflow can call shared automation from a job
named `CI` without creating a different required-check name.

#### REQ-002 - Centralized Cross-Repo Rules

Shared Automation SHALL contain only rules that are intended to apply across
ForgingAlpha repositories.

**Fit:** A proposed shared rule is rejected or moved back to the consuming repo
when it depends on one repo's product behavior, runtime command, local service,
or private environment.

#### REQ-003 - Strict Reproducible Checks

Shared Automation SHALL run strict, reproducible checks for the languages and
surfaces it claims to support.

**Fit:** Supported shared checks have deterministic commands, pinned or declared
tool versions where practical, and fail on violations instead of silently
downgrading.

#### REQ-004 - Composite Action Job-Name Preservation

WHEN Shared Automation must preserve the caller's required job name, the
Control-Plane Maintainer SHALL provide it as a composite action.

**Fit:** A consumer job named `CI` can use the shared action as a step while the
reported GitHub status remains `CI`.

#### REQ-005 - Merge Flow Enforcement

Shared Automation SHALL enforce the Alpha Apps merge flow for repositories with
a `dev` branch: pull requests into `main` or `staging` must come from `dev`.

**Fit:** Language CI actions run the merge-flow guard before language checks,
and main-only control-plane repositories are exempt.

### Release And Consumer Contract

#### REQ-006 - Required CI Released Tag Consumption

Required CI examples SHALL reference released shared-action tags such as `@v1`,
not ordinary branch refs such as `@main`.

**Fit:** Repository examples for required merge-authority CI use released tags
for shared actions.

#### REQ-007 - Required CI Deliberate Shared Rollout

Moving a required-CI release tag SHALL be a deliberate release action after
review.

**Fit:** Merging to `main` updates this repo but does not by itself move the
required-CI `v1` rollout boundary.

### Public Safety

#### REQ-008 - Public-Safe Repository Content

Shared Automation and public documentation SHALL NOT include runtime secrets,
deployment credentials, private customer data, private worktree paths, private
incident evidence, or repo-specific private failure details.

**Fit:** A public-safety scan over changed files finds no prohibited private
content before release.

#### REQ-009 - Private Policy Source Boundary

Shared Automation SHALL NOT require Consumer Repositories to check out private
Alpha Apps lifecycle, convention, skill, agent, or runbook sources during CI.

**Fit:** A consumer workflow can run the shared policy surface with normal
repository checkout and GitHub-provided credentials only.

### Merge Authority And Diagnostics

#### REQ-010 - CI Is Merge Authority

Required CI SHALL remain the merge authority for normal consuming repositories.

**Fit:** Required-check examples and ruleset documentation treat `CI` as the
merge gate.

#### REQ-011 - Diagnostics Are Evidence Only

WHEN Diagnostic Workflows are provided, their outputs SHALL NOT be required
merge checks or release gates.

**Fit:** Probe templates and documentation describe diagnostics as evidence, and
no required-check example depends on a diagnostic workflow.

#### REQ-012 - Constrained Diagnostic Execution

WHEN Diagnostic Workflows are provided, they SHALL constrain their inputs and
SHALL NOT accept arbitrary shell commands.

**Fit:** Invalid probe modes, paths, labels, refs, and command-like inputs are
rejected before command construction.

#### REQ-012A - Latest Diagnostic Standard

WHEN Diagnostic Workflows are provided for internal Alpha Apps agent debugging,
they SHALL use the latest approved reusable diagnostic workflow on this repo's
`main` branch.

**Fit:** A Consumer Repository's manual `ci-probe.yml` calls a centralized
`ForgingAlpha/.github/.github/workflows/ci-probe-*.yml@main` workflow, and the
workflow remains diagnostic-only and non-required.

#### REQ-012B - Repo-Owned Probe Adapter

WHEN Diagnostic Workflows execute repo behavior, the Consumer Repository SHALL
own the adapter that maps validated selectors to concrete commands.

**Fit:** The shared reusable workflow validates inputs and invokes
`./bin/ci-probe`; it does not accept arbitrary command strings or embed
private repo-specific diagnostics in this public control-plane repo.

### Deterministic Enforcement

#### REQ-013 - Deterministic Checks First

WHEN a policy or quality rule can be checked mechanically, Shared Automation
SHALL enforce it with deterministic tooling rather than LLM judgment alone.

**Fit:** Mechanical policy failures come from executable checks with clear
pass/fail behavior.

#### REQ-014 - Actionable Failure Output

Shared Automation SHALL explain failures with what failed, why it matters, and
how to fix it.

**Fit:** Invalid inputs and policy failures identify the violated rule and the
next corrective action.

#### REQ-015 - Self Validation Before Release

This repository's own CI SHALL validate workflow syntax, composite action
metadata, forbidden branch refs, and high-risk workflow triggers before
consumer-facing release tags move.

**Fit:** A pull request that introduces an invalid shared action, forbidden
`@main` action reference, or disallowed trigger fails this repo's `CI` job.

#### REQ-016 - Dependabot Coverage Standard

Shared Automation SHALL define a standard Dependabot configuration pattern for
Consumer Repositories.

**Fit:** A Consumer Repository can copy or sync a standard Dependabot template
that covers the package ecosystems and GitHub Actions manifests present in that
repo.

#### REQ-017 - Dependabot Coverage Validation

Shared Automation SHALL provide deterministic validation for missing obvious
Dependabot coverage.

**Fit:** A repository with workflows, composite actions, Cargo manifests, npm
manifests, Mix projects, or Python dependency manifests receives an actionable
failure or report when `.github/dependabot.yml` does not cover the detected
surface.

#### REQ-018 - Baseline Source-Truth Enforcement

Shared Automation SHALL provide deterministic enforcement for approved
`docs/intent.md`, `docs/requirements.md`, and `docs/architecture.md` in
active ForgingAlpha repositories that run the Alpha Apps policy check.

**Fit:** A Consumer Repository that is missing an approved baseline receives an
actionable failure for ordinary code, test, dependency, or runtime changes while
definition/backfill-only changes remain possible.

#### REQ-019 - Durable Rationale Reference Enforcement

Shared Automation SHALL reject durable code, test, and assertion rationale that
uses plans, phases, PRs, handoffs, audits, or other execution artifacts as the
primary authority.

**Fit:** A durable source comment, docstring, or assertion message that cites an
execution artifact as its reason fails with guidance to cite requirements,
architecture, ADRs, stable conventions, or local invariants instead.

#### REQ-020 - Required Product Evidence Validation

Shared Automation SHALL require and validate Product Evidence for active
ForgingAlpha repositories that run the Alpha Apps policy check.

**Fit:** A Consumer Repository without `docs/evidence/product-evidence.json`
receives an actionable failure for ordinary code, test, dependency, runtime,
maintenance, release, or broad planning changes while source-truth and
evidence-backfill-only changes remain possible. Malformed manifests,
unsupported statuses, orphaned generated views, and stale generated views
receive actionable failures.
