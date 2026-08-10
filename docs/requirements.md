---
status: approved
tags:
  - org/alpha-apps
  - topic/github
---
# ForgingAlpha/.github - Requirements

> These requirements derive from [intent.md](intent.md). Architecture chooses
> how this repository satisfies them.

## Shared CI

### REQ-001 - Single Merge Authority

Shared automation SHALL preserve one required status named `CI`.

**Fit:** Every supported consumer can make one `CI` result required without
depending on matrix job names.

### REQ-002 - Approved Source Truth

Active repositories SHALL validate approved `docs/intent.md`,
`docs/requirements.md`, and `docs/architecture.md` before ordinary changes
merge.

**Fit:** Missing, provisional, or malformed source truth produces actionable
failure output while a definition-only change can repair it.

### REQ-003 - Strict Checks Without Silent Skips

Every check promised by a shared CI profile SHALL run deterministically or fail
with WHAT-WHY-HOW remediation.

**Fit:** A missing formatter, analyzer, audit tool, lock, or required command is
a failure rather than a skipped success.

### REQ-004 - Static Once, Tests Lean

Fanned-out application CI SHALL run cross-cutting and static analysis once and
SHALL NOT repeat it inside test lanes.

**Fit:** The static profile contains policy, formatting, compilation, lint,
audit, security, and type analysis; test profiles contain only locked setup,
caller preparation, and their assigned tests.

## Rollout And Protection

### REQ-005 - Reviewed Green Current-Channel Rollout

A reviewed merge to `.github/main` SHALL advance mutable `v1` only after the
approved `CI` workflow succeeds from a `push` on that exact merged commit and it
remains the current `main` SHA.

**Fit:** A red, stale, or superseded commit cannot move `v1`.

### REQ-006 - Serialized And Recorded Rollout

Every `v1` movement SHALL be serialized, use an expected-old raw-ref lease, and
SHALL create an immutable rollout or rollback tag plus a summary containing the
previous SHA, new SHA, CI run or rollback source, and actor. Mutable movement
and immutable record creation SHALL use one atomic push so a failure changes
neither ref.

**Fit:** Concurrent runs cannot reorder `v1`; every deployed control-plane
version has an immutable recovery point.

### REQ-007 - Constrained Rollback

Rollback SHALL require operator approval and SHALL accept only an existing
protected immutable rollout tag whose commit historically passed `CI`, except
for the exact operator-recorded pre-cutover bootstrap commit.

**Fit:** Arbitrary refs, non-`main` ancestry, and shell input are rejected;
immutable tags never move and the one bootstrap exception is SHA-bound.

### REQ-008 - Least-Privilege Trusted Automation

Write-capable jobs SHALL receive only their necessary permissions and SHALL NOT
execute pull-request code.

**Fit:** Validation jobs are read-only; release and promotion jobs validate
trusted metadata and exact SHAs without checking out a pull-request head.

### REQ-009 - Immutable External Automation

Every non-local external Action SHALL use a full commit SHA with an adjacent
reviewed release comment. Downloaded tools SHALL use an exact version and
verified integrity or provenance.

**Fit:** CI rejects floating external tags, branches, and unqualified images.
Internal `ForgingAlpha/.github/...@v1` remains the documented current-channel
exception.

## Runtime And Dependencies

### REQ-010 - Repository-Owned Exact Runtime

Application runtime versions SHALL come from the repository's committed exact
lock and SHALL NOT be duplicated in workflow inputs.

**Fit:** CI fails before compilation when the lock is missing, stale,
incomplete, or inconsistent with the active runtime.

### REQ-011 - Complete Update Coverage

Every active repository SHALL assign exactly one machine-verifiable update
owner to every versioned dependency, runtime, tool, external Action, active
container image, and installed external plugin it contains.

**Fit:** Deterministic validation reports any manifest, nested Action directory,
runtime declaration, lock, or version literal without supported management or a
narrow documented exception.

### REQ-012 - Normal Update Cooldown

Renovate-owned normal updates SHALL be evaluated daily with minimum cooldowns
of three days for patches, seven days for minors, and thirty days for majors.

**Fit:** Eligible patch, minor, and major PRs merge automatically into a code
repository's protected `dev` after exact-head `CI`; they do not auto-promote to
`main`. Runtime and tool changes use the same path after their exact generated
locks and integrity data pass CI. Main-only control-plane updates merge through
protected `main` only after their complete control-plane gates pass.

### REQ-013 - Immediate Security Updates

Only a Dependabot pull request with a re-provable official GitHub
vulnerability-alert association and a trusted automation-App classification
check bound to its exact current head SHALL be treated as an automatically
promotable security update. Eligible security updates SHALL bypass normal
cooldown and SHALL automatically merge and promote after that exact current
head passes complete required `CI`.

**Fit:** Every synchronization clears stale auto-merge state and routing labels.
A changed head, untrusted merge identity, missing or ambiguous alert association
at merge or promotion time, failed trusted workflow run, disallowed file,
changed target, or non-fast-forward state fails closed.

### REQ-014 - Exact-SHA Deployment

Security promotion SHALL deploy the exact tested, still-current source SHA.
Turnkey SHALL prove that SHA in staging before lease-protected promotion to
`main` and production.

**Fit:** CI, staging, `main`, and the production deployment record identify the
same commit; notification lists the promoted `dev` commit range.

## Operations

### REQ-015 - Protected Branches And Refs

Application `dev` SHALL require pull requests and `CI`. Application `main`,
deployment refs, and control-plane release tags SHALL reject untrusted direct
writes, deletion, and uncontrolled force pushes.

**Fit:** Only the scoped release identity and operator can perform authorized
promotion or release movements.

### REQ-016 - Operator Boundary

Agents MAY prepare changes, tests, commits, and operator scripts. Destructive
pushes, ruleset administration, rollout enablement, and rollback execution
remain operator-owned.

**Fit:** Automation and agent workflows contain no operator SSH key, personal
access token, or agent-readable personal credential.

### REQ-017 - Scheduled Backstops

Dependency advisory audits SHALL run daily against integration and deployed
refs; a secondary-runner sentinel MAY run weekly as a non-required diagnostic.

**Fit:** Scheduled failures are actionable and deduplicated even when no pull
request is open.

### REQ-018 - Disjoint Update Authorities

Renovate SHALL own normal version updates and SHALL NOT create vulnerability
remediation pull requests. Dependabot SHALL own security remediation and SHALL
NOT create normal version-update pull requests.

**Fit:** Required CI validates the central Renovate preset, security-only
Dependabot configuration, repository coverage, and absence of overlapping
update ownership. During migration, each repository declares its sole normal
update owner as `dependabot` or `renovate`; the audited mode flip is atomic, and
final-state validation permits only `renovate`.

### REQ-019 - Safe Generated-Lock Refresh

An automated change to a source version declaration SHALL refresh every derived
lock or integrity record through constrained automation before merge.

**Fit:** A credential-free resolver runs an exact trusted tool in safe mode; a
separate writer verifies bot identity, exact head, and an allowlisted file diff
before committing only the expected generated artifacts. The new exact head
must pass locked-mode `CI`.

### REQ-020 - Version-Coherent Control-Plane Release

After the Renovate plan's Phase 6 gate is active, an update to shared automation
SHALL NOT advance `v1` until representative consumer profiles exercise one
coherent candidate revision and the exact merged control-plane commit remains
green and current. Before that gate is activated, bootstrap rollouts SHALL
satisfy REQ-005 through REQ-007 and the operator checklist; this transition
exception expires when Phase 6 acceptance passes.

**Fit:** Candidate tests cannot mix proposed top-level Actions with sibling
Actions from the already-live `v1`; failure or ambiguity leaves `v1` unchanged.

### REQ-021 - External Plugin Update Ownership

Installed marketplace plugins SHALL be updated by their official installer or
marketplace. Customized vendored external skills SHALL record a machine-readable
upstream identity and revision and SHALL surface upstream changes through a
reviewable synchronization pull request.

**Fit:** Installed artifacts are inventoried rather than edited in place, and a
vendored copy without an upstream owner fails update-coverage validation.
