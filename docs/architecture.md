---
status: approved
tags:
  - org/alpha-apps
  - topic/github
---
# ForgingAlpha/.github - Architecture

## Architecture Posture

`ForgingAlpha/.github` is a public GitHub Actions control plane. It owns
reusable automation surfaces; consuming repositories own the jobs, services,
runtime setup, and product behavior that call those surfaces.

Status preservation is the core constraint: shared checks that report through a
consumer repo's required `CI` status run as composite actions inside the
consumer job.

## Automation Surfaces

### Composite Actions

Composite actions live under `actions/<name>/action.yml`. They are the default
surface for shared CI, lint, policy, and dependency checks.

Use a composite action when a check must execute inside the caller's job,
preserve the caller's job name, or inherit caller-owned services or
environment.

Composite actions do not own workflow triggers, job services, runner selection,
checkout, or branch protection. The consuming workflow owns those concerns.

### Workflows

Workflows under `.github/workflows/` are either repo-owned automation for this
repository or explicit reusable workflows where a separate workflow/job boundary
is intentional.

Use repo-owned workflows for self CI, release-tag movement, and Dependabot
automation. Use reusable workflows only when the shared automation contract
requires a separate workflow/job boundary.

Self CI uses local action paths such as `./actions/<name>` so pull requests
validate proposed action code before any release tag moves.

Self CI validates workflow syntax, composite action metadata, forbidden branch
refs, and high-risk workflow triggers before release tags move.

### Templates And Examples

README examples define the public consumer contract; workflow templates do the
same when present. Show the smallest valid caller workflow and keep
repo-specific runtime commands in the consuming repo.

## Consumer Integration Model

Consumers call released shared actions from a job named `CI`:

```yaml
- uses: ForgingAlpha/.github/actions/<shared-action>@v1
```

The consuming workflow owns checkout, permissions, timeouts, services,
environment variables, and repo-specific command inputs.

Shared actions may expose explicit inputs for caller-owned behavior. Private
product knowledge, private runtime state, local service contracts, and
repo-specific command definitions stay in the consuming repository.

Language CI actions run the merge-flow guard before language checks. Repos with
a `dev` branch must merge feature work through `dev` before `main` or
`staging`; main-only control-plane repos are exempt from that guard.

## Policy Enforcement Model

`actions/ci-alphaapps-policy` is the shared policy composite action. It is
self-contained so public and private Consumer Repositories can run it without
checking out private control-plane sources.

The action owns deterministic checks for approved baseline source truth,
durable rationale references, and required Product Evidence for active
ForgingAlpha repositories. It mirrors the public enforcement contract; private
lifecycle process detail stays outside this repo.

Baseline source-truth enforcement checks for approved `docs/intent.md`,
`docs/requirements.md`, and `docs/architecture.md`. When the baseline is
missing, malformed, or provisional, ordinary implementation changes fail and
definition/backfill-only changes remain the permitted path.

Durable rationale validation scans durable code comments, docstrings, and
assertion messages. It rejects plans, phases, PRs, handoffs, audits, and other
execution artifacts as the reason a behavior exists while ignoring execution
artifact folders themselves.

Product Evidence validation is required for ordinary code, test, dependency,
runtime, maintenance, release, and broad planning changes in active
ForgingAlpha repositories. When the manifest is missing, only source-truth or
evidence-backfill-only changes that create or repair the required evidence
artifacts remain permitted. The action validates manifest schema, status
taxonomy, orphaned generated views, and generated view freshness.

Bounded Product Evidence waivers are operator-scoped source-truth exceptions,
not a normal shared-action input. A shared action caller cannot casually turn
Product Evidence off for ordinary work.

## Dependency Update Model

Dependabot configuration is repo-local. Each Consumer Repository keeps its own
`.github/dependabot.yml` on the default branch.

This repo owns the public Dependabot standard: templates, examples, validation,
and the shared Dependabot auto-merge helper.

Dependabot coverage must match the repository surface. Repos with workflows
cover GitHub Actions at `/`; repos with nested composite actions cover the
action manifest directories as well. Package ecosystems are listed only when
their manifests exist in that repo.

Dependabot updates GitHub Actions references and package manifests. It does not
own hardcoded tool versions embedded inside shell commands or scripts; shared CI
validation must audit those pins separately when they are part of the public
contract.

## Release And Rollout Model

`main` is the authoring branch. Merging to `main` does not roll shared-action
changes out to required CI consumers.

Semver tags record reviewed releases. Mutable major tags such as `v1` are the
required-CI consumer rollout boundary.

Consumer examples and published shared-action dependencies use released refs
such as `@v1` for required CI. Branch refs such as `@main` are not the required
CI consumer contract. Self CI may use local `./actions/...` paths to validate
branch-local changes.

Manual diagnostic probes are the exception. Probe wrappers in Consumer
Repositories call centralized reusable workflows on `ForgingAlpha/.github@main`
so internal agent diagnostics always use the latest approved probe platform.
This latest-on-main model is allowed because probes are non-required,
manual-only, read-only, and not merge authority.

## Public And Private Boundary

This public repo may mirror deterministic policy that can run without private
context.

Private Alpha Apps lifecycle policy, conventions, skills, agents, runbooks,
operator notes, incident detail, customer data, and local worktree paths stay
outside this repo.

Consumer CI must not check out private `alphaapps-docs` sources. If a policy
cannot run publicly without leaking private context, keep it in private review
tooling.

## Diagnostic Workflow Model

Diagnostic workflows, when provided, collect CI-only evidence; they do not
replace required `CI` and do not grant merge permission.

Diagnostic entrypoints must use constrained inputs, never arbitrary shell
commands. This repo owns reusable diagnostic workflow scaffolding and the
shared input guard. The consuming repository owns the executable
`bin/ci-probe` command adapter that maps constrained inputs to runtime probes.

When a diagnostic workflow needs to test branch code, the workflow definition
must remain trusted while the target checkout ref is treated as input.

Diagnostic runs should upload artifacts or summaries even on failure.

Reusable diagnostic workflows live under `.github/workflows/ci-probe-*.yml`.
Consumer wrappers call those workflows at `@main` and pass only reviewed static
configuration plus manual selector inputs. The reusable workflow validates
selectors before checkout, checks out the target ref only after validation, and
then invokes the repo-owned adapter.

## Durable State

- Git commits record reviewed control-plane changes.
- Release tags record consumer-facing action versions.
- Action metadata defines shared action inputs and execution steps.
- Workflow files define repo-owned automation and reusable workflow entrypoints.
- README examples define the public consumer contract; workflow templates do the
  same when present.

## Security Posture

- Default workflow permissions are read-only unless a specific job needs more.
- Avoid `pull_request_target`; any use requires an explicit allowlist reason.
- Diagnostic workflows must not accept arbitrary shell commands.
- Keep secrets, private paths, customer data, and private operational evidence
  out of public files.
- Prefer deterministic validation for enforceable policy.
