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

### REQ-001 - Stable CI Result And Central Baseline

Shared automation SHALL preserve a stable required result named `CI`. An
enrolled application repository SHALL additionally require the central baseline
under a distinct identity. An explicitly enrolled document-only repository MAY
use its complete central bootstrap result as its initial `CI` producer.

**Fit:** Every supported consumer can make one `CI` result required without
depending on matrix job names. A centrally required common baseline has a
distinct identity from application CI. An explicitly enrolled document-only
bootstrap may obtain its initial `CI` result from the central workflow only
when that result covers its complete declared profile; it cannot replace an
existing product CI result or its producer restrictions.

### REQ-002 - Approved Source Truth

Active repositories SHALL validate approved `docs/intent.md`,
`docs/requirements.md`, and `docs/architecture.md` before ordinary changes
merge.

**Fit:** Missing, provisional, or malformed source truth produces actionable
failure output while a definition-only change can repair it. The exact canonical
`ForgingAlpha/control-plane` source follows its owning source-adoption rules and
does not require a status marker; its owner CI validates canonical identities
and upstream bindings. Status metadata and structural CI cannot establish
approval or Currentness for any repository.

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
immutable tags never move, and every eligible target has the required CI evidence.

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

**Fit:** Eligible patch, minor, and major proposals target a code repository's
protected `dev`; an authorized human merges them after exact-head `CI` and
applicable approval. Renovate and platform auto-merge are disabled, including
policy overrides. Runtime and tool changes use the same path after their exact generated
locks and integrity data pass CI. Main-only control-plane updates merge through
protected `main` only after their complete control-plane gates pass.

### REQ-013 - Immediate Security Updates

Only a Dependabot pull request with a re-provable official GitHub
vulnerability-alert association and a trusted automation-App classification
check bound to its exact source base, exact current head, complete associated
OPEN or FIXED GHSA set, and approved manifest-and-lock change SHALL be treated
as eligible for security-patch projection. Eligible security updates
SHALL bypass normal cooldown. An authorized human SHALL perform the source
merge into protected `dev` only after that exact head passes its classification,
required `CI`, CodeQL, and applicable approval. Trusted
exact-head CI SHALL succeed. Trusted aggregate CodeQL SHALL succeed except that
its terminal neutral result MAY be accepted only after exact source
classification proves an exact lockfile-only patch and the trusted
check's machine-readable output and sole pull-request pointer exactly report
the released two-configuration Default setup no-configurations-found condition
for the source branch and exact pull request, base, and head. Every other
terminal non-success, missing, stale, ambiguous, or wrong-App result SHALL fail
closed.
A successful unprivileged `pull_request` CI run MAY wake the default-branch
classifier through `workflow_run`; no Dependabot-triggered workflow receives an
Actions secret or privileged token. Before any App token is minted, the
classifier SHALL bind the exact CI workflow path, run, repository, pull request,
base, and head, then wait only a bounded interval for the latest trusted
exact-head results. Source classification SHALL use non-cancelling
repository-and-head concurrency and SHALL recheck that its trusted exact-head
classification is unique after writing. An identical retry SHALL preserve the
original classification and completion time. Missing or changed classification
SHALL NOT be created retrospectively for a completed merge.

After the exact Dependabot revision merges into `dev`, a no-main-bypass projection
writer MAY open a production pull request only by reconstructing that exact
approved dependency patch on the current `main` base. For every touched path,
the current `main` blob and mode SHALL equal the source pull request's pre-fix
blob and mode. The writer SHALL apply only the source post-fix blobs and modes;
it SHALL NOT merge or cherry-pick the `dev` branch, resolve conflicts, regenerate
a lock, or include unrelated files.

Projection creation SHALL be retry-safe without updating or deleting an existing
branch. Its deterministic branch identity SHALL bind the source pull request,
source head, and production base. A rerun or ambiguous create response MAY adopt
only an exact ref at the deterministic projected head, one exact successful
attestation written by the pinned security App before the pull request, and one
open same-repository App-authored draft pull request. The adopted pull request
SHALL have maintainer modification disabled, the exact base, branch, head, single
commit, tree, file set, and sole-lock ownership. Every adoption SHALL re-read the
current production base and unique trusted check. A missing, conflicting,
duplicate, moved, wrong-App, or otherwise ambiguous object fails closed without a
ref update, deletion, duplicate check, or second pull-request create request.
The writer SHALL check same-branch history, lock collisions and the deterministic
ref before creating immutable Git tree/commit objects. Those objects do not publish
a branch or proposal. Before its first ref, check or pull-request write, the writer SHALL snapshot the deterministic ref
and trusted checks. It accepts only no ref with no check, the exact ref with no
check, or the exact ref with one exact check; a check without its ref, a moved
ref, a duplicate, or a conflicting check fails with no ref, check or pull-request write. The
writer SHALL enumerate all pull-request history for the exact same-repository
head. Any closed, merged, wrong-base, or duplicate prior record is a tombstone
and SHALL prevent a replacement pull-request create request.

The immutable released control-plane policy SHALL pin the dedicated security
source/projector App's public GitHub App ID for both source classification and
projection writing. A consumer variable, workflow input, label, branch name, or
pull-request field SHALL NOT select or override that trust identity. Each
projection check's current App slug SHALL match the projection pull-request
bot actor. The source merger and merge time SHALL be recorded as provider
attribution; a known bot or automation merger SHALL be ineligible. Account type
alone SHALL NOT establish human authorization. The App SHALL be dedicated to security automation; its
private key SHALL NOT be available to a general agent launcher or any
non-security workflow, and it SHALL have no persistent-branch merge bypass.
Classification and projection operations SHALL NOT request or schedule a merge.
Reconstruction from a completed source merge SHALL re-prove the exact pull
request, classified base and head, unique classification completed before the
merge, observed merger, ordered parents, and source-head tree.

The immutable source preimage SHALL be the first parent of the recorded `dev`
security merge and SHALL equal the source base bound by classification. Each
enrollment SHALL declare and verify its supported source merge shape; the
root npm profile accepts only a normal two-parent merge whose ordered
parents are the classified source base and source head and whose resulting tree
equals the classified source-head tree. Later movement of `dev` SHALL NOT
invalidate that captured source chain. The root npm profile SHALL
compare the pre-fix blobs and modes for both `package.json` and
`package-lock.json` against current `main`, even when a transitive-only fix
changes only the lock.

**Fit:** Stale native auto-merge state and retired security routing labels are
ineligible and fail closed.
A changed source head, untrusted merge identity, incomplete or changed GHSA set,
maintainer modification, disallowed path or file type, mismatched preimage,
rename, binary, symlink, submodule, conflict, ambiguous API result, changed
production base, concurrent lock change, or reconstruction mismatch fails
closed. The resulting pull request is based on current `main`, changes only the
approved manifest and lock paths, and has exactly the source post-fix blobs and
modes. Projection is serialized by repository and lockfile; more than one open
production projection touching the same lock is ambiguous and fails closed. A
rerun after an accepted ref, check, or pull-request write with a lost response
adopts only the exact recorded state and performs no second mutable write.
The consumer caller SHALL provide a non-cancelling concurrency group keyed by
repository, target branch, and lock path. Enrollment SHALL fail until that
caller-side serialization is installed. Lock ownership proof SHALL reject an
incomplete, capped, mismatched, or duplicate pull-request file enumeration.

### REQ-014 - Verified Projection And Exact-SHA Deployment

A security production pull request SHALL receive fresh strict `main`-target CI
and CodeQL on its exact current head and base. Read-only verification SHALL
independently reconstruct the expected patch, re-prove source and alert
provenance, verify the exact trusted check runs, and reject armed native
auto-merge. An authorized human SHALL approve and execute the exact-revision
merge under the owning repository's protected procedure. Quality and scanning
requirements SHALL have no automation bypass. Creating the draft projection
SHALL NOT require approval or checks that can exist only after its creation.

The deployed revision SHALL be the exact resulting `main` merge revision and
tree. The source Dependabot head, its `dev` merge, the production preimage, the
projected head, the resulting `main` merge, and the deployment SHALL remain one
traceable immutable chain; they are not required to share one commit SHA.

**Fit:** The recorded source head/base or current production head/base moving or
mismatching before merge fails closed; later unrelated `dev` movement does
not. Post-merge observation binds the actual push revision and merged pull
request to its trusted projection attestation, verifies current `main`, ordered
parents and expected tree, and performs no mutation. The independently triggered
deployment binds itself to and reports that exact `main` push revision and may
begin concurrently; post-merge observation is not its admission gate.
A deployment failure remains visible for
governed retry or roll-forward; automation does not silently roll back to a
vulnerable revision.

## Operations

### REQ-015 - Protected Branches And Refs

Application `dev` SHALL require pull requests and `CI`. Application `main`,
deployment refs, and control-plane release tags SHALL reject untrusted direct
writes, deletion, and uncontrolled force pushes.

**Fit:** Independent no-bypass rules enforce required CI, CodeQL, current-base
state, merge shape, deletion, and non-fast-forward protection. Only an
applicable authorized human executes PR merges. Automation has no bypass
authorizing persistent-branch updates, including after human approval.
Repository auto-merge and merge queues are disabled. Separately scoped tag
rollout and deployment permissions do not confer branch or merge authority.

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
update ownership. Each enrolled repository declares `renovate` as its sole
normal-update owner; a change of ownership leaves no overlap or unmanaged interval.

### REQ-019 - Safe Generated-Lock Refresh

An automated change to a source version declaration SHALL refresh every derived
lock or integrity record through constrained automation before merge.

**Fit:** A credential-free resolver runs an exact trusted tool in safe mode; a
separate writer verifies bot identity, exact head, and an allowlisted file diff
before committing only the expected generated artifacts. The new exact head
must pass locked-mode `CI`.

### REQ-020 - Version-Coherent Control-Plane Release

For repositories enrolled in the version-coherent consumer gate, an update to
shared automation SHALL NOT advance `v1` until representative consumer profiles exercise one
coherent candidate revision and the exact merged control-plane commit remains
green and current. Every rollout SHALL satisfy REQ-005 through REQ-007 and the
operator checklist, whether or not the consumer gate is enrolled.

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
evidence SHALL fail closed for third-party dependencies except for a reviewed
central repository-and-artifact exception as specified below. When GitHub omits
license metadata for a third-party GitHub Action pinned to an exact commit SHA,
the central gate MAY resolve the repository license at that exact revision
through GitHub's official license API and SHALL accept only an SPDX identifier
already present in the same central allowlist. A centrally fixed
`ForgingAlpha/.github/actions/*@v1` first-party action MAY instead satisfy the
gate through strict ownership and release provenance: the evidence record
SHALL match the fixed repository and major channel exactly, the protected `v1`
reference SHALL resolve directly to a commit, and that exact commit SHALL
contain the named action. Callers SHALL NOT select or broaden this first-party
evidence class. When GitHub reports a null license for an exact pinned root npm
alias, the central gate MAY normalize it to the underlying package only when the
manifest and npm v3 lock agree on the exact alias, target name and version, canonical
registry artifact, sha512 integrity, and centrally approved SPDX license. Evidence
SHALL come from either one exact concrete dependency-review record or one anonymous,
bounded, non-redirecting lookup of the internally constructed npm exact-release
endpoint whose identity, artifact, integrity, and license match the lock. No caller
URL, alternate registry, credential, package exception, or executable package content
SHALL enter the resolver. Ranged, tagged, malformed, or non-root aliases SHALL fail
closed.

The control plane MAY admit a custom-licensed artifact through a reviewed policy
change binding one repository, canonical dependency identity, exact version,
manifest and install path, canonical registry URL, sha512 integrity, and reviewed
license-file digest. Preparation SHALL verify the license file within the bounded
registry artifact against that integrity. Each exception proposal SHALL retain a
source-bound verification receipt in central source with its policy review,
recording the canonical source URL, verified SHA512 integrity, archive digest,
license-member path and digest, retrieval time, and applied resource limits. These
are reviewed preparation evidence; routine CI SHALL enforce the approved artifact
through its exact identity and lock integrity without downloading the archive
again. File identity alone SHALL NOT establish vendor terms acceptance
or account entitlement. Human approval SHALL resolve that separate basis before
adoption under REQ-024. Callers SHALL NOT supply or broaden exceptions.

If the official action's package exclusion ignores versions, the independent,
mandatory evidence guard SHALL inspect every added dependency in its normalized
matching family before accepting nonempty license metadata. Each such dependency
SHALL match exactly one approved canonical artifact record, manifest and npm v3
lock, exact artifact, and the admission's required use binding. Custom-licensed
admission SHALL still require its unambiguous runtime declaration.
Other versions, manifests, duplicate
records, conflicting identities, additional installs, missing evidence, symlinks,
and malformed or oversized files SHALL fail closed. This exception SHALL NOT relax
vulnerability review, the SPDX default, or other evidence classes. Later artifact
updates SHALL require a new reviewed central policy change.

Separate from that custom-license class, central policy MAY admit only the fourteen
immutable optional Sharp/libvips artifacts recorded in
[the Alpha Apps static-build policy](alphaapps-site-build-dependencies.md), solely
for `ForgingAlpha/alphaapps-site` under that policy's build and delivery conditions.
Their recorded LGPL-containing SPDX expressions SHALL remain outside the general
allowlist. This admission SHALL bind the exact repository, root manifest and npm
v3 lock paths, package identity, version, install path, registry URL, SHA512
integrity, declared license expression, and integrity-verified packaged notice
member digest. A notice table in `package/README.md` MAY supply that member;
its identity SHALL NOT establish complete terms, corresponding source, compliance,
or an authorized human's use-basis decision.

Before this admission is operational, an authorized human SHALL resolve the
applicable terms and obligations for the recorded build use through the policy's
attributable decision binding, and a reviewed
enforcing implementation SHALL satisfy that policy's complete acceptance.
Every added or updated member of its protected package families SHALL receive
independent exact-record validation before any nonempty-license shortcut.
Unlisted identities or versions, duplicate or additional installations, changed
license expressions, missing or conflicting evidence, and use outside the approved
build envelope SHALL fail closed. Optional or development metadata alone SHALL
NOT prove build-only use. Vulnerability review, other repositories and the
existing custom-license admission SHALL remain unchanged. Later artifact or
build-envelope changes SHALL require a new reviewed central policy proposal.
While this admission is present in the consumer lock, its fixed build/deploy
input verification SHALL run on every pull request, including changes with no
dependency diff. Release admission SHALL separately require the exact candidate's
retained output-composition evidence and verification result under that policy.

**Fit:** Approved third-party SPDX evidence passes; non-approved evidence
fails; the exact-revision third-party resolver fails closed on malformed
identity, unavailable evidence, or a disallowed SPDX identifier; the fixed
first-party resolver fails closed on any schema, repository, channel, commit,
tree, or action-path mismatch; npm alias normalization fails closed on any manifest,
PURL, spec, lock format, target, registry, artifact, integrity, license, redirect,
availability, response-size, or lookup-count mismatch;
the artifact exception accepts only its reviewed repository and immutable artifact,
including adversarial version, encoded-name, manifest, and integrity mismatches;
unknown evidence classes fail with WHAT-WHY-HOW
remediation; and non-pull-request events report that the diff-only check is not
applicable.
The separate Alpha Apps dependency guard rejects cross-repository reuse and
unreviewed artifact or input-envelope mutation, including an envelope-only pull
request. Release admission refuses missing, mismatched or nonconforming output
composition and use outside its conditions. Neither admission can pass solely
because a notice digest or an agent-authored decision status matches.

### REQ-024 - Human Trust-Surface Approval

Every change in a control-plane repository and every change to a repository's
workflow or detected production-control surface SHALL require approval from an
authorized human reviewer on the exact current pull-request revision. An
agent or authoring-bot identity SHALL NOT satisfy or bypass that approval.
Every PR merge, including dependency and security changes, SHALL be executed
by an applicable authorized human. Separately scoped classification, proposal,
tag rollout and deployment effects retain their own authorization; none
authorizes an automated merge or persistent-branch push.

**Fit:** For an enrolled team-review profile, protected-branch rules require the approved human-review team for the
complete change and dismiss or invalidate approval when the reviewed head
changes. A centrally enrolled team-review profile validates fresh effective
branch rules against its trusted team identity, approval count, coverage and
stale-approval policy; a missing, unavailable or weaker rule fails closed. A
consumer pull request cannot select that identity or lower those requirements.
Unmigrated callers retain the current canonical `.github/CODEOWNERS` validation
and applicable code-owner rules until an explicit, qualified migration preserves
their required protection. A CODEOWNERS file is not required solely to duplicate
verified team protection in an enrolled profile. Tests exercise permitted
proposal and verification behavior and reject automation that approves, merges,
queues a merge, or directly updates a persistent branch. Hosted permissions,
team eligibility, bypass actors and human execution require operational qualification; local
tests cannot prove them. This contract creates no enrollment or settings change.

### REQ-025 - Centrally Required Baseline Pilot

Organization-required workflows SHALL execute the approved shared baseline on
the intended consumer revision, using a coherent reviewed checking-source
revision and read-only permissions. The pilot SHALL preserve existing CI,
scanning, human review, branch protection and pre-execution integrity obligations.

Qualification SHALL cover the enrolled CI profile and the shared behavior that the
proposed change can affect. The shared-CI owner SHALL retain a source-bound, reviewed
impact assessment in the existing task or proposal record, using complete consumer
candidate inputs and base state, checking-source before/after revisions and
dependencies. Material affected-scope and unrelatedness judgments SHALL receive
independent verification, including no-change and scope-exclusion dispositions. A
consumer SHALL NOT narrow its own profile or required coverage. Uncertain impact SHALL
require conservative additional validation or block the affected rollout.

A qualified profile MAY progress independently of unrelated profiles only when all of
its required pilot cases and the shared behavior it relies on are verified. These cases
include valid, invalid and repaired changes, App-created and already-open pull-request
triggers, consumer skip/configuration/application-input refusal, and source restoration
with observed valid-pass and invalid-block behavior. A new repository or branch SHALL
additionally qualify its actual target context, identity, current-base checks, result
producers and required protections; earlier content validation is not a current-target
CI result. Changes to shared enforcement, profile selection, permissions or other common
inputs SHALL receive qualification across every affected profile.

The document-bootstrap and actual hosted Rust targets establish their own scoped
evidence; neither can substitute for the other or establish whole-pilot completion.
Their presence in the initial pilot does not make an unrelated profile's missing
evidence a blanket prerequisite for additional enrollment. Every proposed enrollment or
migration SHALL identify and qualify its affected profiles and shared behavior. Removal
of consumer common calls requires complete coverage for that affected scope, preserving
product-specific checks; whole-pilot completion requires all initial pilot targets and
their required cases.

**Fit:** A narrowly selected pilot proves actual valid, invalid and repaired
changes, GitHub App-created and already-open pull requests, and an observed
controlled source update followed by successful restoration to the previously
qualified pilot source and its required pass/fail enforcement. A restored source
that is failed, cancelled, skipped or unexecuted is not recovery. Adding a rule,
passing local tests or publishing source alone does
not establish execution or enforcement. CodeQL remains separately configured.

### REQ-026 - Explicit Document Bootstrap

A document-only bootstrap profile SHALL be explicitly enrolled by the approved
central source, validate its governing documents and tracked Markdown, and admit
only its declared non-executable inputs. Application profiles SHALL fail when
their expected manifests or commands are missing rather than select bootstrap.

**Fit:** Unknown enrollment, changed repository identity, application code,
executable lint configuration, custom formatters/rules, untracked required
inputs, malformed configuration and unavailable required evidence fail with
actionable remediation. Bootstrap reuses existing checking implementations only
where their behavior satisfies this boundary. It does not execute consumer
helpers or weaken normal product validation. Transition to an application
profile requires explicit enrollment and its meaningful product checks.
