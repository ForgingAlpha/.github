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
a failure rather than a skipped success. Markdown validation covers every
tracked Markdown file rather than only the current diff.

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
protected immutable rollout tag whose commit historically passed `CI`.

**Fit:** Arbitrary refs, non-`main` ancestry, and shell input are rejected;
immutable tags never move, and no pre-policy commit can bypass historical CI.

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

### REQ-010 - Centrally Governed Exact Runtime

Application runtime version choices SHALL come from a versioned runtime profile
owned by `.github`. Each consumer repository SHALL commit an exact
`mise.toml`/`mise.lock` projection of its assigned profile for local and CI use,
and SHALL NOT duplicate runtime versions in workflow inputs. Any temporary
deviation SHALL be centrally recorded with its reason, owner, and expiration.

**Fit:** CI fails before compilation when the lock is missing, stale,
incomplete, inconsistent with the assigned central profile, or covered only by
an absent or expired exception.

### REQ-011 - Complete Update Coverage

Every active repository SHALL assign exactly one machine-verifiable update
owner to every versioned dependency, runtime, tool, external Action, active
container image, and installed external plugin it contains.

**Fit:** Deterministic validation reports any manifest, nested Action directory,
runtime declaration, lock, or version literal without supported management or a
narrow documented exception. The central runtime-profile declaration is the
sole update-owned runtime source; consumer mise declarations and locks are
derived projections rather than independent owners.

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
check bound to its exact source base, exact current head, complete associated
OPEN or FIXED GHSA set, and approved manifest-and-lock change SHALL be treated
as an automatically promotable security update. Eligible security updates
SHALL bypass normal cooldown and SHALL automatically merge into protected
`dev` only after that exact head passes complete required `CI`.

After the exact Dependabot revision merges into `dev`, a no-bypass projection
writer MAY open a production pull request only by reconstructing that exact
approved dependency patch on the current `main` base. For every touched path,
the current `main` blob and mode SHALL equal the source pull request's pre-fix
blob and mode. The writer SHALL apply only the source post-fix blobs and modes;
it SHALL NOT merge or cherry-pick the `dev` branch, resolve conflicts, regenerate
a lock, or include unrelated files.

The immutable released control-plane policy SHALL pin the no-bypass security
automation App's public GitHub App ID for both source classification and
projection writing. A consumer variable, workflow input, label, branch name, or
pull-request field SHALL NOT select or override that trust identity. Each
trusted check's current App slug SHALL match the corresponding merge or
pull-request bot actor.

The immutable source preimage SHALL be the first parent of the recorded `dev`
security merge and SHALL equal the source base bound by classification. Each
enrollment SHALL declare and verify its supported source merge shape; the
initial site profile accepts only a one-parent squash merge whose resulting
tree equals the classified source head. Later movement of `dev` SHALL NOT
invalidate that captured source chain. The initial root npm profile SHALL
compare the pre-fix blobs and modes for both `package.json` and
`package-lock.json` against current `main`, even when a transitive-only fix
changes only the lock.

**Fit:** Every synchronization clears stale auto-merge state and routing labels.
A changed source head, untrusted merge identity, incomplete or changed GHSA set,
maintainer modification, disallowed path or file type, mismatched preimage,
rename, binary, symlink, submodule, conflict, ambiguous API result, changed
production base, concurrent lock change, or reconstruction mismatch fails
closed. The resulting pull request is based on current `main`, changes only the
approved manifest and lock paths, and has exactly the source post-fix blobs and
modes. Projection is serialized by repository and lockfile; more than one open
production projection touching the same lock is ambiguous and fails closed.

### REQ-014 - Exact-SHA Deployment

An unattended security production pull request SHALL receive fresh strict
`main`-target CI and CodeQL on its exact current head and base. Protected
security activation SHALL independently reconstruct the expected patch,
re-prove source and alert provenance, verify the exact trusted check runs, and
request a pull-request merge with the exact head SHA. Quality and scanning
requirements SHALL have no automation bypass.

The deployed revision SHALL be the exact resulting `main` merge revision and
tree. The source Dependabot head, its `dev` merge, the production preimage, the
projected head, the resulting `main` merge, and the deployment SHALL remain one
traceable immutable chain; they are not required to share one commit SHA.

**Fit:** The recorded source head/base or current production head/base moving or
mismatching before activation fails closed; later unrelated `dev` movement does
not. GitHub atomically rejects a stale exact-SHA merge. Immediately after the
merge, the activator verifies the returned merge SHA, current `main` SHA,
parentage, and expected tree. The independently triggered deployment binds
itself to and reports that exact `main` push revision and may begin concurrently
with the activator's postcondition. A deployment failure remains visible for
governed retry or roll-forward; automation does not silently roll back to a
vulnerable revision.

## Operations

### REQ-015 - Protected Branches And Refs

Application `dev` SHALL require pull requests and `CI`. Application `main`,
deployment refs, and control-plane release tags SHALL reject untrusted direct
writes, deletion, and uncontrolled force pushes.

**Fit:** Independent no-bypass rules enforce required CI, CodeQL, current-base
state, merge shape, deletion, and non-fast-forward protection. Human review is
enforced separately; the dedicated security activator is the only automation
actor with pull-request-only bypass in that ruleset. GitHub scopes this bypass
to the actor and ruleset, so the protected workflow and environment—not the
ruleset—confine its use to a re-proved REQ-013/REQ-014 projection. Update
authority is also pull-request-only. The projection writer has no bypass, and
neither identity can directly push a persistent branch.

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

Renovate SHALL own normal external version updates and SHALL NOT create
vulnerability-remediation pull requests. Internal
`ForgingAlpha/.github@v1` references SHALL remain excluded from Renovate and
owned by the protected control-plane rollout. Dependabot SHALL own security
remediation and SHALL NOT create normal version-update pull requests.

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
green and current. Before that gate is activated, initial rollouts SHALL satisfy
REQ-005 through REQ-007 and the operator checklist.

**Fit:** Candidate tests cannot mix proposed top-level Actions with sibling
Actions from the already-live `v1`; failure or ambiguity leaves `v1` unchanged.

### REQ-021 - External Plugin Update Ownership

Installed marketplace plugins SHALL be updated by their official installer or
marketplace. Customized vendored external skills SHALL record a machine-readable
upstream identity and revision and SHALL surface upstream changes through a
reviewable synchronization pull request.

**Fit:** Installed artifacts are inventoried rather than edited in place, and a
vendored copy without an upstream owner fails update-coverage validation.

### REQ-022 - One Current Automation Contract

Shared automation SHALL expose one strict current contract and SHALL NOT retain
obsolete rollout exceptions, incremental Markdown enforcement, or
compatibility entrypoints.

**Fit:** Current workflows call and test the canonical implementation directly;
old policy paths cannot remain green through a wrapper, opt-out input, or
legacy-tag exception.

### REQ-023 - Commercial Dependency License Gate

Every pull request that introduces or updates a dependency SHALL run dependency
vulnerability and license review. License policy SHALL use one centrally owned
commercial-use allowlist; callers SHALL NOT disable the review, substitute a
denylist, or exempt individual packages. Missing, unknown, or custom license
evidence SHALL fail closed for third-party dependencies. When GitHub omits
license metadata for a third-party GitHub Action pinned to an exact commit SHA,
the central gate MAY resolve the repository license at that exact revision
through GitHub's official license API and SHALL accept only an SPDX identifier
already present in the same central allowlist. A centrally fixed
`ForgingAlpha/.github/actions/*@v1` first-party action MAY instead satisfy the
gate through strict ownership and release provenance: the evidence record
SHALL match the fixed repository and major channel exactly, the protected `v1`
reference SHALL resolve directly to a commit, and that exact commit SHALL
contain the named action. Callers SHALL NOT select or broaden this first-party
evidence class.

**Fit:** Approved third-party SPDX evidence passes; non-approved evidence
fails; the exact-revision third-party resolver fails closed on malformed
identity, unavailable evidence, or a disallowed SPDX identifier; the fixed
first-party resolver fails closed on any schema, repository, channel, commit,
tree, or action-path mismatch; unknown evidence classes fail with WHAT-WHY-HOW
remediation; and non-pull-request events report that the diff-only check is not
applicable.

### REQ-024 - Human Trust-Surface Approval

Every change in a control-plane repository and every change to a repository's
workflow or detected production-control surface SHALL require approval from an
authorized human code owner on the exact current pull-request revision. An
agent or authoring-bot identity SHALL NOT satisfy or bypass that approval and
SHALL NOT merge the protected persistent branch. This does not prohibit the
separately scoped security and release identities from performing the exact,
pre-authorized operations required by REQ-005 through REQ-008 and REQ-013
through REQ-015.

**Fit:** Required CI validates a canonical `.github/CODEOWNERS` file whose final
active block assigns the complete control-plane tree, or the applicable trust
and production-control paths, to an authorized human. Protected-branch rules
require code-owner review and dismiss or invalidate approval when the reviewed
head changes. The protected non-agent operator performs trust-surface and
control-plane merges.
