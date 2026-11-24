---
status: approved
tags:
  - org/alpha-apps
  - topic/github
---
# ForgingAlpha/.github

ForgingAlpha's public CI, dependency, security, and release automation control
plane.

[Intent](#intent) · [Requirements](#requirements) · [Architecture](#architecture) · [Local Instructions](#local-instructions)

## Intent

### Purpose

`ForgingAlpha/.github` is the public automation control plane for ForgingAlpha.
It gives every repository current, secure, reproducible CI and dependency
automation without copying workflow logic between repositories.

### Durable Outcomes

- Every repository retains a stable required result named `CI`. Enrolled
  application repositories additionally require the distinct central baseline;
  a document-only bootstrap may obtain its initial complete-profile `CI` from
  the central workflow without inventing a product build result. An explicitly
  enrolled application may also receive its complete product `CI` centrally,
  while its product owner retains meaningful product checks and behavior.
- Every control-plane and protected production-control change is approved by
  an authorized human reviewer on its exact current revision; an agent or
  authoring-bot identity cannot substitute for that approval.
- New active repositories participate in the shared baseline from their first
  governed pull request. Deterministic onboarding identifies supported components
  from committed inputs. Product owners define their test obligations. Before
  relying on CI, the organization verifies enrollment, actual execution and
  preservation of the complete applicable product checks on each repository.
- Protected `.github/main` is the active shared automation source.
  Required checks and exact-revision human review precede the merge; no later tag
  promotion, source acceptance or recurring ruleset repin makes it active.
- Agents develop on nonpersistent task branches. The product owner declares the
  release route. Websites integrate reviewed tasks on protected `dev` and release
  through a reviewed `dev` to `main` PR. Only commercial applications designated
  for paid production require a qualified staging release before their first paid
  production release and for subsequent ordinary releases. Development can continue
  on `dev` before that route is ready. Shared tooling retains its adopted route.
  Every protected merge requires complete applicable checks, exact-revision human
  approval and the merge procedure in REQ-024. Branch existence and repository names confer no
  release authority.

- Every shared execution retains its exact resolved source revision and consumer
  revision. Recovery uses the protected human-reviewed source-change path and
  preserves earlier execution evidence.
- Normal dependency proposals receive a deliberate cooldown; eligible security
  proposals receive immediate classification and exact-patch verification.
  An authorized human approves the exact revision before either a personal merge or a qualified native auto-merge.
- Every versioned dependency, runtime, tool, Action, image, and external plugin
  has exactly one discoverable update owner; unmanaged version literals fail
  required CI.
- Renovate owns normal external updates across supported manifests, locks, and
  annotated literals. Internal `ForgingAlpha/.github@main` references follow
  the protected, human-reviewed merge path. Cooled normal updates follow the repository's
  ordinary integration route through human-approved pull requests with exact-head
  CI; an updater's configured target does not create a route exception.
- Dependabot owns security remediation only. Every eligible security proposal,
  whether its source targets `main` or `dev`, retains trusted classification of
  GitHub's official vulnerability-alert-to-pull-request association and the exact
  approved dependency patch before the source merges.
- Runtime and tool upgrades follow the same normal patch, minor, and major
  automation path while preserving exact committed locks and integrity data.
- Where security remediation uses a separate `dev` source, production promotion
  projects only the exact independently
  verified dependency patch from its merged `dev` security change onto the
  current production base. It never carries unrelated unreleased `dev` work.
  Direct security proposals to `main` retain the same source-classification and
  patch-proof obligations, required checks and exact human approval without
  inventing a second source merge or cross-branch projection.
- Static and cross-cutting checks run once; parallel test lanes remain lean.
- Organization runtime profiles and compatible version tuples have one
  control-plane owner. Every consumer commits an exact, integrity-bearing mise
  projection of its assigned approved profile so local and CI execution remain
  reproducible, and required CI rejects unapproved or internally inconsistent
  projections.
- External automation dependencies are immutable and integrity-verifiable.
- Required CI supplies technical evidence; it does not grant merge authority.
- Every introduced or updated third-party package has license evidence approved
  by central policy: an approved SPDX allowlist covering permissive licenses,
  `LGPL-3.0-or-later`, and the SIL Open Font License (`OFL-1.1`), or a
  reviewed exception for one immutable artifact in one repository. Product
  release owners address the notice, source and distribution obligations of
  their actual use.
  Fixed first-party actions have governed ownership and release provenance;
  unknown evidence fails closed.

### Boundaries

This repository owns shared composite actions, repo-owned automation, the
organization Renovate preset, security-only Dependabot policy, update-ownership
validation, release mechanics, templates, and public-safe cross-repository
enforcement.

`.github` owns approved runtime profiles, compatibility tuples,
artifact-integrity requirements, upgrade policy, repository assignments, and
bounded exceptions. Consumer repositories own product behavior, services,
runtime commands, deployment configuration, secrets, data, and the committed
`mise.toml`/`mise.lock` projection used to execute their assigned profile; they
do not independently choose governed runtime versions. Agents never receive
operator SSH keys or personal credentials. The general-purpose
agent/authoring identity cannot approve or merge changes. Scoped updater,
security, and release identities may prepare proposals, publish checks, or
perform separately authorized tag and deployment operations. They cannot
merge pull requests or directly update persistent branches. Privileged
automation never executes untrusted pull-request code.

### Invariants And Tradeoffs

- `main` is the single active first-party automation source. Existing tags and
  run records retain historical provenance; they are not another active channel.
- The control plane publishes one strict current contract. Obsolete rollout
  exceptions, incremental Markdown enforcement, and compatibility entrypoints
  are removed after qualified replacement preserves required consumers and evidence.
  Bounded migration is not a permanent alternate development route.
- Every control-plane change lands through a reviewed pull request with green
  `CI` and authorized-human approval of the exact current revision. A human personally
  merges changes to review or merge authority. Coherent candidate and affected-consumer validation
  belongs before merge. No existing required check or enrolled consumer gate may
  be deferred. Main membership makes the resulting source active; execution
  observations do not add another activation decision.
- Normal and security automation have disjoint authority. Renovate does not
  remediate vulnerability alerts, and Dependabot does not create normal version
  updates.
- Security urgency may bypass cooldown and release batching, never CI, source
  provenance, exact-patch verification, current-base verification, CodeQL or
  exact human approval. Cross-branch projection additionally reconstructs only
  that proved patch on the current production base.
- Inactive deployment tooling is removed instead of receiving new update
  automation.
- Fail closed when identity, classification, branch state, checks, or deployed
  SHA is ambiguous.
- Centralize only genuinely cross-repository behavior.
- Qualify centrally required CI on explicitly selected consumers before broader
  enrollment. A document-only bootstrap profile is explicit and cannot be
  selected merely because expected application inputs are missing.

## Requirements

> These requirements derive from [Intent](#intent). Architecture chooses
> how this repository satisfies them.

### Shared CI

#### REQ-001 - Stable CI Result And Central Baseline

Shared automation SHALL preserve a stable required result named `CI`. An
enrolled application repository SHALL additionally require the central baseline
under a distinct identity. An explicitly enrolled document-only repository MAY
use its complete central bootstrap result as its initial `CI` producer.
A repository-owned workflow MAY call the shared language checks directly. Its
owner SHALL retain the product checks and the required `CI` result.
An explicitly enrolled full application profile MAY assign its product `CI`
producer to the central workflow only with complete applicable product checks,
an unambiguous producer, preserved protection and qualified transition/recovery.

**Fit:** Every supported consumer can make one `CI` result required without
depending on matrix job names. A centrally required common baseline has a
distinct identity from application CI. An explicitly enrolled document-only
bootstrap may obtain its initial `CI` result from the central workflow only
when that result covers its complete declared profile; it cannot replace an
existing product CI result or its producer restrictions. Application migration
preserves those restrictions and complete product coverage; a common-baseline
result cannot substitute for product CI. A transition cannot accept duplicate
indistinguishable results or weaken required checks while changing producers.

#### REQ-002 - Approved Source Truth

Active repositories SHALL validate approved Intent, Requirements and Architecture before ordinary changes merge.
Use the layout enrolled for that repository, revision and scope. The standalone layout uses
`docs/intent.md`, `docs/requirements.md` and `docs/architecture.md`. The README Intent
layout selects `README.md#intent` and retains separate Requirements and Architecture.
The four-section layout selects `README.md#intent`, `README.md#requirements` and
`README.md#architecture`, together with their bound detail. Its `README.md#local-instructions`
section supplies repository working rules. A change confined to those rules must be
identified as an instruction change and must preserve the three governing digests.
Reject a missing or invalid selected section or detail binding.

The standalone policy action reads `readme_intent_scopes` from the root
Requirements on the protected base. A branch entry for `dev` or `main` selects
the repository root and may name top-level components with their own README
Intent, Requirements and Architecture. Product changes require approved
definitions at every selected scope on both the protected base and the proposed
revision. For a multi-scope product the checker SHALL validate each source
identity and its upstream digests, and preserve the protected set of scopes.
The first root conversion must preserve the existing approved Intent and source
identities. Adding a selection and implementing the product require separate PRs.

For the first release from protected `dev` into the inspected Analyzing Alpha
site main commit `9f61df0595236264e5c515381a73d57625d54585`, the approved
root README definitions on protected `dev` supply the baseline. This exception
applies only to `ForgingAlpha/analyzingalpha-site`, repository ID `1151414035`.
A separate PR into `dev` SHALL first add the identical root scope for `main`
in both the source manifest's selection and its Requirements metadata. All other
bytes SHALL be preserved. The release SHALL be a same-repository PR from the
exact protected `dev` head, with main as its ancestor and its checked merge tree
identical to that head. The checker SHALL verify the complete governing inventory,
approved metadata and source bindings. Later main changes use main's adopted
selection. Existing branch admission and human approvals apply throughout.

**Fit:** Missing, provisional, or malformed source truth produces actionable
failure output while a definition-only change can repair it. The exact canonical
`ForgingAlpha/control-plane` source follows its owning source-adoption rules and
does not require a status marker; its owner CI validates canonical identities
and upstream bindings. Status metadata and structural CI cannot establish
approval or Currentness for any repository.

#### REQ-003 - Strict Checks Without Silent Skips

Every check promised by a shared CI profile SHALL run deterministically or fail
with WHAT-WHY-HOW remediation.

**Fit:** A missing formatter, analyzer, audit tool, lock, or required command is
a failure rather than a skipped success. Markdown validation covers every
tracked Markdown file rather than only the current diff.

#### REQ-004 - Static Once, Tests Lean

Fanned-out application CI SHALL run cross-cutting and static analysis once and
SHALL NOT repeat it inside test lanes.

**Fit:** The static profile contains policy, formatting, compilation, lint,
audit, security, and type analysis; test profiles contain only locked setup,
caller preparation, and their assigned tests.

### Rollout And Protection

#### REQ-005 - Protected Main Is Active

Protected `.github/main` SHALL be the active first-party shared
automation source. Required exact-revision checks and authorized human review
SHALL precede the protected merge under REQ-024. A separate tag promotion, post-merge acceptance
or recurring source-pin update SHALL NOT be required to activate that source.

**Fit:** A new applicable execution selects protected `main`; a successful
merge does not wait for `v1`, an operator repin or a second source approval.
Post-merge failures remain observable and do not silently select older code.

#### REQ-006 - Exact Execution Source Evidence

Shared execution SHALL retain the exact resolved automation commit, applicable
workflow or Action identity, consumer revision and outcome. The source selected
for an execution SHALL remain coherent with its helpers and policy inputs.
An already resolved execution SHALL NOT substitute a later `main` revision.

**Fit:** Central workflow jobs use their defining workflow commit throughout
admission, product lanes and finalization. Composite execution retains the native
resolved Action commit. Central application plans and receipts additionally retain
fingerprints of the exact baseline source, enrollment, route guard, route assignments and runtime catalog from the
same checking checkout. A branch name or consumer commit alone cannot stand in for
executed-source identity.

#### REQ-007 - Human-Reviewed Source Recovery

Recovery of active shared automation SHALL use a corrective or revert pull
request through the same required checks, exact-head human approval and protected
merge into `main` under REQ-024. It SHALL preserve the affected run/source evidence.
Automation SHALL NOT force-update `main`, select a historical tag as an active
fallback or grant itself rollback or merge authority.

**Fit:** A reviewed recovery merge becomes active through REQ-005. Earlier
commits and tag/run records remain historical evidence without a second channel
or an automatic restoration of withdrawn policy approvals.

#### REQ-008 - Least-Privilege Trusted Automation

Write-capable jobs SHALL receive only their necessary permissions and SHALL NOT
execute pull-request code.

**Fit:** Validation jobs are read-only; release and promotion jobs validate
trusted metadata and exact SHAs without checking out a pull-request head.

#### REQ-009 - Immutable External Automation

Every non-local external Action SHALL use a full commit SHA with an adjacent
reviewed release comment. Downloaded tools SHALL use an exact version and
verified integrity or provenance.

**Fit:** CI rejects floating external tags, branches, and unqualified images.
Only fixed first-party `ForgingAlpha/.github/...@main` references are the
documented active-source exception. This does not relax third-party pins.

### Runtime And Dependencies

#### REQ-010 - Centrally Governed Exact Runtime

Application runtime version choices SHALL come from a versioned runtime profile
owned by `.github`. Each consumer repository SHALL commit an exact
`mise.toml`/`mise.lock` projection of its assigned profile for local and CI use,
and SHALL NOT duplicate runtime versions in workflow inputs. Any temporary
deviation SHALL be centrally recorded with its reason, owner, and expiration.

**Fit:** CI fails before compilation when the lock is missing, stale,
incomplete, inconsistent with the assigned central profile, or covered only by
an absent or expired exception.

#### REQ-011 - Complete Update Coverage

Every active repository SHALL assign exactly one machine-verifiable update
owner to every versioned dependency, runtime, tool, external Action, active
container image, and installed external plugin it contains.

**Fit:** Deterministic validation reports any manifest, nested Action directory,
runtime declaration, lock, or version literal without supported management or a
narrow documented exception. The central runtime-profile declaration is the
sole update-owned runtime source; consumer mise declarations and locks are
derived projections rather than independent owners.

#### REQ-012 - Normal Update Cooldown

Every maintained repository SHALL receive automatic proposals for eligible
Renovate-owned dependency patches as part of standard repository setup.
This covers repositories provisioned for ongoing maintenance and existing
repositories the operator identifies as maintained. Existing repositories move
to the same policy within their authorized rollout under REQ-018. Dependency
coverage under REQ-011 continues throughout the transition. No repository-level
patch opt-in or CI profile enrollment SHALL be required.

Renovate SHALL evaluate normal updates daily and use these minimum release ages.

| Routine update | Minimum release age | Proposal |
| --- | --- | --- |
| Patch | 3 days | Weekly batch |
| Minor | 7 days | Weekly batch |
| Refresh of an existing digest | No semantic release cooldown | Weekly batch |
| Major | 30 days | Separate PR per upgrade, eligible any day |

For eligible updates marked “Weekly batch” above, Renovate SHALL create or
refresh a single open batch per repository and ordinary target. Automatic creation and refresh
SHALL run only on Tuesday in `America/New_York`. A human may request a refresh
outside the window. An empty batch SHALL produce no PR. When a dependency needs
independent testing or rollback, the receiving repository’s change owner SHALL
split it into a separate Renovate proposal under the same timing rules.
Security proposal timing is governed by [REQ-013](#req-013---immediate-security-updates).

**Fit:** Standard setup admits an eligible patch without owner action. An
underage release waits. A second eligible routine update joins the open batch
in the next permitted run. The ordinary target SHALL match the repository's governed route under
REQ-027, including its prior route during migration. Runtime and tool proposals
retain their required locks and integrity checks. Each proposal follows REQ-024
after exact-head `CI` and human approval. Renovate's `automerge` and
`platformAutomerge` remain disabled, including in preset overrides. Shared
automation becomes active on protected `main` after its complete gates pass.

#### REQ-013 - Immediate Security Updates

Dependabot SHALL be able to open a separate proposal as soon as a supported
security fix is available, on any day, without a normal release age or weekly
batch window. Security-only Dependabot proposals MAY target the repository's
protected default `main` directly, including when a separate `dev` exists. Every eligible security
source proposal, targeting protected `main` or `dev`, SHALL satisfy the common
classification, exact-patch, current-base, CI, CodeQL and exact human approval obligations
below. Direct-to-main delivery SHALL NOT require a second source merge or a
cross-branch production projection. Ordinary admission SHALL NOT represent any
proposal as classified or projected security evidence.

The security source target SHALL be verified against the actual protected GitHub
default branch independently of the ordinary target in REQ-012. When the two
differ, each lane SHALL qualify its own binding and required checks before
relying on that route. A change of default SHALL revalidate the affected source, hosted
settings and both updater routes. The trusted caller and proof SHALL bind the
actual source branch, repository, pull request, base and head; branch existence or an untrusted
proposal field SHALL NOT select a weaker proof. Existing enrolled security consumers
SHALL retain their proof obligations until their successor flow is reconciled and
qualified. Missing classification capability or evidence leaves security eligibility
unproved; changing ordinary PR admission SHALL NOT bypass that failure.

The direct route grants no security-App credential, new credential exposure,
bypass or merge authority. It SHALL use only the already authorized security
boundary and required least-privilege capabilities; unavailable prerequisites stop
the affected security flow. A separate-dev source additionally requires the
cross-branch projection obligations below before production delivery.

Only a Dependabot pull request with a re-provable official GitHub
vulnerability-alert association and a trusted automation-App classification
check bound to its exact source base, exact current head, complete associated
OPEN or FIXED GHSA set, and approved manifest-and-lock change SHALL be treated
as eligible security remediation. Eligible security updates
SHALL bypass normal cooldown. A source merge under REQ-024 SHALL target the bound
protected source branch and require exact classification, required `CI`, CodeQL and
applicable human approval on the current head. Trusted
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
attribution. A native source merge additionally requires the authorized arming actor and
exact review evidence under REQ-024. An unidentified actor or unqualified automated source
merge is ineligible. The App SHALL be dedicated to security automation; its
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

A direct-main security merge SHALL preserve the same immutable classified source
chain and supported merge shape, with `main` as its source and production branch.
Read-only source observation SHALL re-prove that exact merged pull request, its
pre-merge classification, actual merge actor, exact human approval, ordered parents, source-head tree
and official advisory association. It SHALL NOT manufacture a projection
attestation or retroactively create missing classification. Its exact merged
revision remains subject to the applicable deployment evidence in REQ-014.

Concurrent ordinary changes to the production manifest or lock SHALL NOT relax
the separate-dev projection's exact-preimage requirement. A mismatch stops that
projection until the source and current production base can be reconciled through
their human-reviewed change paths and the required proof is re-established.

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
Consumer callers SHALL provide non-cancelling concurrency groups scoped by
repository and target branch. A group MAY additionally be scoped by lock path
only when that preserves exclusion among every writer that can touch that lock.
A projection affecting multiple locks SHALL share the repository-and-target
group with every potentially overlapping writer. A key derived only from the
selected lock set SHALL NOT substitute for that common group: unequal sets can
overlap. Enrollment SHALL fail until caller-side serialization and transitions
from existing, queued, or running writers are installed and qualified.
Lock ownership proof SHALL reject an
incomplete, capped, mismatched, or duplicate pull-request file enumeration.

#### REQ-014 - Verified Security Delivery And Exact-SHA Deployment

A projected security production pull request SHALL receive fresh strict `main`-target CI
and CodeQL on its exact current head and base. Read-only verification SHALL
independently reconstruct the expected patch, re-prove source and alert
provenance, verify the exact trusted check runs, and reject armed native
auto-merge. An authorized human SHALL approve and execute the exact-revision
merge under the owning repository's protected procedure. Quality and scanning
requirements SHALL have no automation bypass. Creating the draft projection
SHALL NOT require approval or checks that can exist only after its creation.

Where the product has a deployment obligation, its deployed revision SHALL be
the exact resulting `main` merge revision and tree. A separate-dev security flow
SHALL preserve the source Dependabot head, its `dev` merge, production preimage,
projected head, resulting `main` merge and deployment as one traceable immutable
chain; those revisions are not required to share one commit SHA. A direct-main
flow SHALL preserve its classified base and head, observed source merge and applicable
deployment without adding fictitious intermediate revisions. Shared-source
activation under REQ-005 is not evidence of a product deployment.

**Fit:** The recorded source head/base or current production head/base moving or
mismatching before merge fails closed; later unrelated `dev` movement does
not. For a projection, post-merge observation binds the actual push revision and merged pull
request to its trusted projection attestation, verifies current `main`, ordered
parents and expected tree, and performs no mutation. The independently triggered
deployment binds itself to and reports that exact `main` push revision and may
begin concurrently; post-merge observation is not its admission gate. Direct-main
security observation uses the source proof in REQ-013. Ordinary non-security
merges make neither security claim and need no security attestation.
A deployment failure remains visible for
governed retry or roll-forward; automation does not silently roll back to a
vulnerable revision.

### Operations

#### REQ-015 - Protected Branches And Refs

Each persistent branch on a repository's adopted release route SHALL require
pull requests and applicable complete `CI`. Those branches, deployment refs,
and control-plane release tags SHALL reject untrusted direct
writes, deletion, and uncontrolled force pushes.

**Fit:** Independent no-bypass rules enforce required CI, CodeQL, current-base
state, merge shape, deletion, and non-fast-forward protection. The protected merge procedure in REQ-024
retains these rules. Agents and updater Apps have no bypass authorizing persistent-branch
updates, including after human approval. Merge queues remain disabled. Separately scoped tag
rollout and deployment permissions do not confer branch or merge authority.
Missing migration branches confer no creation authority; qualify these protections
before admitting their new integration or release paths under REQ-027.

#### REQ-016 - Operator Boundary

Agents MAY prepare changes, tests, commits, and operator scripts. Destructive
pushes, ruleset administration, credential/App setup and settings transitions
remain operator-owned. Recovery requires the reviewed PR merge in REQ-007. The resulting source becomes
active at merge.

**Fit:** Automation and agent workflows contain no operator SSH key, personal
access token, or agent-readable personal credential.

#### REQ-017 - Scheduled Backstops

Dependency advisory audits SHALL run daily against integration and deployed
refs; a secondary-runner sentinel MAY run weekly as a non-required diagnostic.

**Fit:** Scheduled failures are actionable and deduplicated even when no pull
request is open.

#### REQ-018 - Disjoint Update Authorities

Renovate SHALL own normal external version updates and SHALL NOT create
vulnerability-remediation pull requests. Internal
`ForgingAlpha/.github@main` references SHALL remain excluded from Renovate and
owned by the protected, human-reviewed merge path. Dependabot SHALL own security
remediation and SHALL NOT create normal version-update pull requests.

**Fit:** A transition verifies the intended repository, ordinary target, package
coverage and updater access before transferring ownership. The control-plane
operator SHALL record the authorized repository identities in the rollout's
change record. A shared preset change SHALL account for all current inheritors
and preserve the existing policy outside that recorded scope. Required CI validates
the central Renovate preset, security-only
Dependabot configuration, repository coverage, and absence of overlapping
update ownership. Each enrolled repository declares `renovate` as its sole
normal-update owner; a change of ownership leaves no overlap or unmanaged interval.

#### REQ-019 - Safe Generated-Lock Refresh

An automated change to a source version declaration SHALL refresh every derived
lock or integrity record through constrained automation before merge.

**Fit:** A credential-free resolver runs an exact trusted tool in safe mode; a
separate writer verifies bot identity, exact head, and an allowlisted file diff
before committing only the expected generated artifacts. The new exact head
must pass locked-mode `CI`.

#### REQ-020 - Coherent Premerge Consumer Validation

Before a shared automation change merges, required validation SHALL exercise
one coherent candidate revision and the affected consumer-profile behavior.
An enrolled version-coherent consumer gate SHALL remain a required premerge
obligation; changing the active-source mechanism SHALL NOT silently remove it.
The impact assessment SHALL distinguish preserved coverage, changed obligations
and operational observations still needed for affected consumers.

**Fit:** Candidate checks cannot mix proposed top-level code with helpers from
another mutable reference. Missing required premerge coverage blocks the merge.
Post-merge observations record their actual subjects, times and failures; they
do not retroactively qualify a proposal, waive required checks or activate source.

#### REQ-021 - External Plugin Update Ownership

Installed marketplace plugins SHALL be updated by their official installer or
marketplace. Customized vendored external skills SHALL record a machine-readable
upstream identity and revision and SHALL surface upstream changes through a
reviewable synchronization pull request.

**Fit:** Installed artifacts are inventoried rather than edited in place, and a
vendored copy without an upstream owner fails update-coverage validation.

#### REQ-022 - One Current Automation Contract

Shared automation SHALL expose one strict current contract and SHALL NOT retain
obsolete rollout exceptions, incremental Markdown enforcement, or
compatibility entrypoints.

**Fit:** Current workflows call and test the canonical implementation directly;
old policy paths cannot remain green through a wrapper, opt-out input, or
legacy-tag exception.

#### REQ-023 - Commercial Dependency License Gate

Every pull request that introduces or updates a dependency SHALL run dependency
vulnerability and license review. License policy SHALL use one centrally owned
approved SPDX allowlist; callers SHALL NOT disable the review, substitute a
denylist, or exempt individual packages. The standard allowlist SHALL preserve
its existing permissive license identifiers and include `OFL-1.1` and
`LGPL-3.0-or-later`. The LGPL identifier permits selection of version 3; its
inclusion SHALL NOT imply blanket approval of later license texts or other LGPL, standalone GPL, AGPL,
custom or unknown licenses. Those require a separate reviewed central policy
decision unless an applicable existing artifact exception already covers them.
For a compound SPDX expression, every obligation in the selected licensing
alternative SHALL be centrally eligible: every member of `AND` must be approved;
`OR` requires at least one fully approved alternative. A `WITH` exception SHALL
require explicit central approval of the complete expression. An unknown or
malformed expression SHALL fail closed. Missing, unknown, or custom license
evidence SHALL fail closed for third-party dependencies except for a reviewed
central repository-and-artifact exception as specified below. When GitHub omits
license metadata for a third-party GitHub Action pinned to an exact commit SHA,
the central gate MAY resolve the repository license at that exact revision
through GitHub's official license API and SHALL accept only an SPDX identifier
already present in the same central allowlist. A centrally fixed
`ForgingAlpha/.github/actions/*@main` first-party action MAY instead satisfy the
gate through strict ownership and protected-main provenance: the evidence record
SHALL match the fixed repository and main reference exactly, that reference
SHALL resolve directly to a commit, and that exact commit SHALL
contain the named action. Callers SHALL NOT select or broaden this first-party
evidence class. First-party protected-main evidence requests SHALL reject HTTP
redirects. When GitHub reports a null license for an exact pinned root npm
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
matching family before accepting nonempty license metadata. Only the single
approved canonical record, matching manifest and npm v3 lock, exact artifact, and
unambiguous runtime declaration SHALL pass. Other versions, manifests, duplicate
records, conflicting identities, additional installs, missing evidence, symlinks,
and malformed or oversized files SHALL fail closed. This exception SHALL NOT relax
vulnerability review, the SPDX default, or other evidence classes. Later artifact
updates SHALL require a new reviewed central policy change.

Standard license eligibility SHALL NOT establish compliance for a particular use.
The accountable product release owner SHALL assess the actual use and contents
being delivered. When distributing OFL-covered fonts, the owner SHALL preserve
the copyright notice and license, retain the OFL for the font, and respect any
Reserved Font Names when distributing a modified version. The
[SIL Open Font License 1.1](https://openfontlicense.org/open-font-license-official-text/) gives the full terms.
For LGPL-covered library modifications, linked/combined works
or redistribution, the owner SHALL identify and satisfy applicable copyright and
license notices, license-copy, corresponding-source, replacement/relinking,
reverse-engineering and installation-information conditions before delivery.
Required evidence SHALL be retained with the existing product release record,
bound to the delivered contents and applicable license terms. Unresolved
applicable obligations SHALL stop the affected delivery. A dependency's optional
or development classification alone SHALL NOT establish that it is absent from
the delivered product. Internal build use and generated output SHALL be assessed
from the actual output: using a tool alone SHALL NOT be treated as licensing all
its output under LGPL, and covered content copied into output SHALL NOT be
assumed exempt. Ordinary maintenance that changes neither the applicable terms
nor their use/distribution basis SHALL reuse applicable existing compliance
evidence; it SHALL NOT require a new central package/version exception.

The shared-CI owner SHALL enforce standard SPDX eligibility through the official
dependency-review action and the existing mandatory evidence guard. Product
release owners retain actual-use compliance responsibility; a green license check
SHALL NOT be represented as legal clearance. Vulnerability severity and scope
thresholds, existing evidence classes, the Mapbox artifact exception and human
approval/merge requirements SHALL remain unchanged. Source adoption alone SHALL
NOT establish released enforcement; the consumed gate revision SHALL implement
the adopted policy before operational reliance.

**Fit:** Approved third-party SPDX evidence passes; non-approved evidence
fails; the exact-revision third-party resolver fails closed on malformed
identity, unavailable evidence, or a disallowed SPDX identifier; the fixed
first-party resolver fails closed on any schema, repository, reference, commit,
tree, action-path, or first-party transport redirect mismatch;
npm alias normalization fails closed on any manifest,
PURL, spec, lock format, target, registry, artifact, integrity, license, redirect,
availability, response-size, or lookup-count mismatch;
the artifact exception accepts only its reviewed repository and immutable artifact,
including adversarial version, encoded-name, manifest, and integrity mismatches;
unknown evidence classes fail with WHAT-WHY-HOW
remediation; and non-pull-request events report that the diff-only check is not
applicable.
The enforcing release must demonstrate that `OFL-1.1` and an approved LGPL
expression pass eligibility. Expressions with an unapproved mandatory license,
standalone GPL/AGPL, and unknown/custom evidence must fail without an applicable
central exception. Product release verification checks the owner's assessment against the
actual use, delivered contents and applicable terms, including covered generated
content, library redistribution and changed distribution. Missing required evidence
or unresolved applicable obligations refuse delivery; CI eligibility alone cannot
satisfy these release obligations.

#### REQ-024 - Human Trust-Surface Approval

Every change in a control-plane repository and every change to a repository's
workflow or detected production-control surface SHALL require approval from an
authorized human reviewer on the exact current pull-request revision. An
agent or authoring-bot identity SHALL NOT satisfy or bypass that approval.
For an ordinary, ready PR on a qualified protected route, the protected workflow MAY
request GitHub native auto-merge before approval. GitHub MAY complete it only
after the designated human has effectively approved the exact current head on
that PR and all current required gates pass. Any new head requires a fresh
approval, including a push that preserves the diff. Exact evidence binds the
repository, PR, head, current base and validated integration. Preserve the
original review, human identity, arming actor, actual merge actor, method,
time and resulting commit. An accepted request records the intent to merge. Delivery requires the actual merge event and resulting content.

An authorized human may personally merge through the applicable protected procedure. A human SHALL
personally merge all branch promotions, including separate production security projections
to `main`, any PR relying on an expressly authorized exceptional CI override, and changes
to merge or review authority, including its controls, workflows, callers and enrollment.
Each override retains its original evidence and the owning procedure’s limits on
which quality gates a human may waive. Required review and security protections remain in force. A Dependabot security source on `dev` or directly on `main` MAY use the native path
only on a route qualified for all REQ-013 source proof and REQ-014 observation.
Its exact classification and current required checks SHALL pass before completion. Updater, security,
agent and review identities receive no approval, bypass or direct protected-ref
write authority. Qualification of native auto-merge requires its own hosted evidence.

**Fit:** Team-review verification SHALL be available to repositories that retain
their own product `CI` producer. For an enrolled team-review profile,
protected-branch rules require the approved human-review team for the
complete change and dismiss or invalidate approval when the reviewed head
changes. A centrally enrolled team-review profile validates fresh effective
branch rules against its trusted team identity, approval count, coverage and
stale-approval policy; a missing, unavailable or weaker rule fails closed. A
consumer pull request cannot select that identity or lower those requirements.
Unmigrated callers retain the current canonical `.github/CODEOWNERS` validation
and applicable code-owner rules until an explicit, qualified migration preserves
their required protection. A CODEOWNERS file is not required solely to duplicate
verified team protection in an enrolled profile. Tests exercise permitted
proposal and verification behavior, a qualified native request, and refusal of automation that
approves, directly merges, invokes a merge queue, bypasses a rule or directly updates a persistent branch.
Hosted permissions, team eligibility, effective actors, exact-review enforcement and merge attribution
require operational qualification. This contract creates no enrollment or settings change.

#### REQ-025 - Centrally Required Baseline Pilot

Organization-required workflows SHALL execute the approved shared baseline on
the intended consumer revision, using a coherent reviewed checking-source
revision and read-only permissions. The pilot SHALL preserve existing CI,
scanning, human review, branch protection and pre-execution integrity obligations.
An explicitly enrolled application profile MAY additionally produce complete
product `CI` under REQ-001. Its profile SHALL run the full declared Rust, Astro
or mixed component coverage on the complete consumer revision; missing inputs
or a documentation-only diff SHALL NOT select a lighter profile.

Qualification SHALL cover the enrolled CI profile and the shared behavior that the
proposed change can affect. The shared-CI owner SHALL retain a source-bound, reviewed
impact assessment in the existing task or proposal record, using complete consumer
candidate inputs and base state, checking-source before/after revisions and
dependencies. Material affected-scope and unrelatedness judgments SHALL receive
independent verification, including no-change and scope-exclusion dispositions. A
consumer SHALL NOT narrow its own profile or required coverage. Uncertain impact SHALL
require conservative additional validation or block the affected source or
consumer-change proposal before reliance.

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

Changing the application CI producer SHALL preserve every dependent security,
release and event-trigger contract, including required push-event checks. A
consumer whose existing local-CI security binding or push-event obligations
cannot be preserved and qualified SHALL retain its existing producer. Source
capability SHALL NOT enroll a consumer or update an organization ruleset's
repository or branch selection. An existing enrolled rule SHALL follow protected
`.github/main` after the one-time human-executed settings transition; subsequent protected
merges SHALL NOT require a recurring source-pin update or source-activation gate.
Initial enrollment, selector or producer changes SHALL still bind target,
preserved controls and observed enforcement/recovery evidence. Producer retirement
SHALL follow equivalent-coverage qualification, with a recoverable consumer change
where restoring a removed caller requires source delivery rather than a settings revert.

**Fit:** A narrowly selected pilot proves actual valid, invalid and repaired
changes, GitHub App-created and already-open pull requests, and an observed
controlled source update followed by human-reviewed main recovery with recorded
resulting source and required pass/fail enforcement. A recovered source
that is failed, cancelled, skipped or unexecuted is not recovery. Adding a rule,
passing local tests or publishing source alone does
not establish execution or enforcement. CodeQL remains separately configured.

#### REQ-026 - Explicit Document Bootstrap

An organization-required document-only bootstrap profile SHALL be explicitly enrolled by the approved
central source, validate its governing documents and tracked Markdown, and admit
only its declared non-executable inputs. Application profiles SHALL fail when
their expected manifests or commands are missing rather than select bootstrap.

For a private repository's first definitions, the protection operator MAY enroll
one open same-repository PR against its README-only initial `dev` commit. The
enrollment SHALL bind the exact head, governing scopes and required human team.
CI SHALL verify each scope's provisional README Intent, separate Requirements
and Architecture, their source identities and upstream digests, and the entire
document-only tree. A change of head or movement beyond the seed ends eligibility.

A private repository MAY instead introduce its own required `CI` workflow with
its first definitions on the same README-only `dev` seed. The workflow SHALL
match the shared caller template and declare the root and all governing
components. CI SHALL verify the exact PR head, every declared governing chain,
the document-only tree and tracked Markdown. Subsequent documentation PRs
SHALL preserve the caller and scopes adopted on protected `dev`. A dedicated
workflow-only PR MAY upgrade the caller to the current template at those scopes. Native
protection SHALL require current human team review, including review of the
initial caller on the exact head. Reliance requires an observed hosted run.
Adding application code requires applicable product checks. Under REQ-029, a
verified repository-owned caller also supplies the first-definitions path
when the repository has no central assignment.

**Fit:** Unknown enrollment for a central bootstrap, changed repository identity, application code,
executable lint configuration, custom formatters/rules, untracked required
inputs, malformed configuration and unavailable required evidence fail with
actionable remediation. Bootstrap reuses existing checking implementations only
where their behavior satisfies this boundary. It does not execute consumer
helpers or weaken normal product validation. Transition to an application
profile requires explicit enrollment and its meaningful product checks.

#### REQ-027 - Uniform Proposal Admission

Shared CI SHALL enforce the release route approved by the repository's owner
under control-plane ASR-AUTH-005. Bind the exact repository, source and target,
head and base commits, checking source and applicable release evidence. An
agent proposes a change on a nonpersistent task branch. Every persistent merge
requires complete applicable checks, current-base verification, independent
human approval of the exact revision and the applicable merge procedure in REQ-024.

| Adopted route | Ordinary proposals |
| --- | --- |
| Website or other approved direct release | Task to `dev`, then same-repository protected `dev` to protected `main`. |
| Development pending production qualification | Task to `dev`. Production promotion requires a separately adopted and qualified release route. |
| Commercial application designated for paid production | Task to `dev`, fixed reviewed release candidate to protected `staging`, then same-repository protected `staging` to protected `main`. |
| Main-only shared tooling | Nonpersistent task to protected `main`. |

Before the first paid production release, qualify the commercial application's
actual staging environment and release route. The accountable release owner
retains the release claim, reviews whole-batch consolidation on frozen dev,
records the exact integrated dev snapshot and verifies that the promotion task
carries that snapshot. Review bounded repairs against the active release and
reconcile them to current dev. Movement of a checked head or base reopens
affected checks and approval. A staging branch alone establishes no deployment,
customer-workflow verification, operational activation or authorization.

Keep the existing release record and exact source bindings. A change of route
requires owner reconciliation, review and qualification of the new consumer
and its protections. The candidate's content, repository suffix, default branch,
PR title and existence of a staging branch cannot select the route. Missing or
conflicting evidence stops the dependent promotion. Existing qualified security
classification and exact-patch projection under REQ-013/014 retain their own
evidence, checks and human authority.

**Fit:** Exercise website release and tooling tasks, permit development before
paid launch, and refuse ordinary direct-to-main delivery for a staged application.
Verify the exact protected source tip and target for promotions. Refuse persistent
sources as development tasks, forks masquerading as promotion branches, stale
releases and unproved repairs. Qualify a new paid route on its actual consumer
before allowing production release.

#### REQ-028 - Consumer Qualification

The shared-CI owner SHALL own exact-candidate affected-consumer qualification
and its recorded result. Each consumer SHALL retain its product requirements,
commands and tests. Existing CI, CodeQL, human review and protected merge requirements
remain mandatory for everyone.

Qualification SHALL bind the shared candidate, consumer input, selected checking
source, applicable required workflows and complete outcomes. Successful native
qualification requires those workflows' latest complete results, required steps
and post-job hooks for the exact inputs. Missing, pending, failed, ambiguous or
known-stale evidence SHALL NOT satisfy a required result. Changed inputs SHALL
receive affected requalification; unchanged evidence MAY be reused only after its
scope, dependencies and currentness are verified under REQ-020 and REQ-025.

Standards correctness and consumer compatibility SHALL remain distinct claims.
A checker SHALL accept inputs that conform to its selected contract and reject
violating inputs. A correct rejection can require consumer remediation; it SHALL
NOT count as successful consumer compatibility. A checker that wrongly accepts
or rejects input SHALL require correction. Crashes or omitted required work
SHALL remain non-success until their cause is resolved.

A rejection test MAY pass by demonstrating the required refusal. That assertion
SHALL NOT replace or override the failed consumer workflow. A corrected consumer
revision requires corresponding exact-input evidence. No intent label or
expected-failure classification SHALL waive required native success. The shared-CI
and consumer owners SHALL diagnose the cause against the exact contract,
configuration and inputs and retain the reproduction and conclusion in the owning
change record. An unresolved cause SHALL remain unresolved.

Private source, commands, logs and artifact payloads SHALL stay in consumer
custody. Public reports SHALL disclose only the exact public subject, bounded
outcome and permitted detail location. Synthetic or local evidence SHALL NOT be
reported as native consumer execution. Source adoption alone grants no
credentials, settings or execution authority.

**Fit:** Conforming input passes and violating input fails through the actual
checker and its applicable required result producer. A negative assertion may
pass while the consumer result remains failed. Corrected inputs require their
corresponding evidence. Impact assessment cannot waive a changed required behavior
or an existing mandatory check; it cannot claim execution that did not occur.

#### REQ-029 - Default Participation In The Common Baseline

After qualification of the common baseline and each affected profile under
REQ-025, the protection operator SHALL select new active repositories for the
common baseline on protected `dev` and `main` through an organization-owned
rule. Only the protection operator SHALL control the selection criterion and
its exclusions. It SHALL cover creation outside a template. Existing repositories
enter after their validation configuration and handover are qualified. Shared
tooling keeps its required workflow. A later staging branch receives its
protections during the paid application's release-route qualification under REQ-027.

For the same trusted policy, repository identity, protected base and candidate
tree, onboarding SHALL identify the same supported component types and roots
or report the unresolved input. An application's accepted checks come from
its repository-owned CI under REQ-001 or its explicitly approved central
assignment, including its runtime and the product owner's test obligations.
Without a central assignment, the common baseline SHALL validate governing
documents and tracked Markdown with trusted checks. Branch protection SHALL
require the expected repository-owned `CI` as a separate result on the same candidate.
A first-definitions PR MUST meet the repository-owned admission path in REQ-026
or obtain explicit bootstrap enrollment. Other unconfigured candidates receive
the missing assignment or caller diagnostic. The common baseline retains its
distinct result and cannot grant a product or documentation assignment.

The first application PR SHALL run the complete accepted checks on the full
candidate tree before merge. A change of producer follows the handover in REQ-025. Missing assignments, unsupported layouts and
missing owner decisions SHALL block that transition and identify the necessary
remediation. REQ-026 governs positive admission of a documentation bootstrap.
Changes to declared test obligations require review of the affected coverage.
Removing an identifying input cannot reduce an established obligation.

**Fit:** A fresh repository created outside a template receives the common
baseline on its first governed PR without manual selection of that repository.
The protection operator qualifies an enforcing rule on a bounded target with
observed valid-pass and invalid-block runs before expanding it. Verify positive
documentation admission, its transition to complete application CI and actionable
refusal of unsupported input. On every newly selected target, verify the actual
identity, head/base, check producers and effective protections before reliance.

### Requirements scope

Each repository exposes a required `CI` result and runs its applicable product checks.
Enrolled application repositories also require the central baseline. Before a change
to shared automation can merge, the candidate and affected consumers must pass their
checks and an authorized human must approve the exact revision. The numbered requirements
define acceptance for CI, dependency updates, security delivery and recovery.

## Architecture

### Control Plane

Shared CI implements the owner-approved route in REQ-027. Protected `main`
is the active shared automation source. Website consumers use direct releases
from protected `dev`. Staging belongs to paid production applications. Shared
tooling uses its adopted protected task-to-main route.

The shared policy action uses the runner-provisioned Python 3/PyYAML parser for
bounded YAML frontmatter, rejecting malformed syntax and duplicate keys. It
checks baseline presence and repository-specific status metadata. Only the exact
`ForgingAlpha/control-plane` origin follows canonical source rules without a
required status marker; its own CI validates canonical IDs and upstream digests.
These structural checks cannot establish approval or Currentness.

The policy step in a product workflow reads the governing scope selection from
the protected branch's root Requirements. For a multi-scope product it reads
the selected README Intents and the corresponding Requirements and Architecture
from both Git revisions, validates their identities and upstream bindings, and
rejects product changes while any selected definition is provisional. Other
steps in the workflow exercise the build and product behavior.

For the repository-owned documentation route, the shared action reads Git
objects at the exact PR head and protected base. A README-only seed admits the
shared caller template with explicit governing scopes. Once adopted, the base
supplies the expected caller and scopes. It must still implement the read-only
caller contract, including an immutable checkout revision. A fresh checkout
pin or comment in the shared template therefore preserves existing documentation
PRs. A caller-only PR can update the adopted workflow to the current template.
The action reuses the organization
baseline's document inventory, Markdown lint and branch-rule readers. GitHub
enforces approval. The reviewer checks the actual workflow on the proposed
head because a replacement job could report the same check name.

The released shared policy action validates `.github/CODEOWNERS` before lower-level
language checks. Unmigrated control-plane repositories assign their complete tree to an
authorized human. Consumer repositories assign `.github/` and each detected
production-control file or directory at any tracked depth to an authorized human
in the final active CODEOWNERS block. A detected enclosing control directory
covers its descendants; untracked files do not expand the candidate inventory. Unsupported literal target patterns leave ownership verification
incomplete. The validator preserves GitHub's last-match semantics. Repository
rules retain their applicable code-owner review until qualified migration and
invalidate stale approvals. Agents and the
general-purpose authoring identity may create and update pull requests, but
their approval cannot satisfy this boundary. REQ-024 governs ordinary completion and
reserves specified merges for a human. Updater,
security and release Apps retain only scoped proposal, check, tag rollout and
deployment effects; they cannot merge or update persistent branches directly.

Shared technical checks remain composite actions for unmigrated consumers, whose
repository workflow owns the stable required result named `CI`. An explicitly
enrolled full application profile may instead assign that product result to the
central workflow. In either case, an enrolled application additionally requires
the distinct common baseline result; common-policy success cannot substitute for
product checks. An explicitly enrolled document-only bootstrap can obtain its
initial complete-profile `CI` centrally. These responsibilities implement REQ-001,
REQ-003, REQ-004 and REQ-025. For a central-product profile, lane composition and
aggregation move to the shared-CI owner; the product owner retains product behavior,
command meaning and test completeness. Exact approval remains with the designated human.
Consumers of the existing composites use
`ForgingAlpha/.github/actions/<action>@main`. Self-CI exercises proposed implementations locally. Its lifecycle policy step uses the released shared action so the pull request cannot supply the checker that admits its own governing sources. Candidate policy code runs in the local test suites.

The protected workflow `.github/workflows/request-auto-merge.yml` binds its
defining source and compares current effective branch rules with the settings owner’s
qualification on the protected base. The owner verifies privileged bypass and update
admission across all applicable layers. The requester uses repository metadata to
detect changes without a ruleset administration grant. It requests native
auto-merge with the PR node ID, expected head OID and permitted merge method.
Its execution boundary excludes PR code, PR-supplied credentials, merge queues,
direct merges and protected-ref writes. A lost response requires readback of the
same PR, subject and request. GitHub independently enforces current protections.

The independent workflow `.github/workflows/verify-native-merge-approval.yml` publishes
`Exact human approval`. Before permitting an arm, qualify this required check for
the same PR and current head. Verify the trusted producer and demonstrate that
completion requires an effective review by the designated human on a new head,
including an update that preserves the diff.
The expected head OID binds the request. A rule configuration check, delayed disarm
or approval on an older head cannot authorize eventual completion. Preserve the
independent review, CI, scanning and strict current-base rules, including stronger
target-specific gates. If the actor boundary or the necessary evidence cannot be
qualified, use the applicable personal human procedure. Verify that this route can satisfy
its required checks as well. Source publication and hosted configuration have separate authorization.
After an ordinary native merge, retain its verified outcome with the read-only
`actions/native-auto-merge/observe.py` command. It reads the merged PR, validates
the merge parents and tree, and reconciles the review, requester and recorded merger.
[Operator interface and qualification](docs/operator-checklist.md#native-auto-merge-enrollment)

#### Uniform proposal targets

Control-plane ASR-AUTH-005 owns release authority. The product owner selects
the release route. [Shared CI assignments](actions/ci-merge-flow/routes.json)
bind each consumer by immutable GitHub repository ID to its reviewed route.
The merge check uses assignments from the acquired action archive. The central
workflow also reconciles the product declaration on its exact protected base
and candidate against its trusted enrollment. A conflicting assignment stops CI.
Publication of source assignments does not enroll a consumer in organization CI
or change a hosted branch or environment.

Ordinary task branches can target dev on a development, direct or staged route.
The main-only shared repositories accept a task PR against main. A direct site
release binds the current same-repository dev commit and the current protected
main base. A staged application refuses a dev-to-main shortcut even if staging
is missing. Its release owner freezes the integrated dev revision, checks the
whole batch and binds the nonpersistent promotion task, active release and
staging base. After staging integration, verify the staged candidate in its
isolated environment, retain customer-workflow evidence, and reconcile changes
back to dev before the next batch. The operator qualifies affected release,
security, push-event and protection consumers before activation.

For a staged release the owner records the dev merge hold before taking the
batch snapshot. Every merge route honors the hold through verified staging integration
or reconciled terminal cancellation. If the baseline moves, revalidate it.
Bind the complete integrated batch, including permitted corrections, and the intended
main integration. A reviewed no-change consolidation needs no empty PR. Before a
new release, reconcile the prior main result, staging repairs and current dev.
A cancelled release requires reconciliation of its actual refs and outstanding
proposals before the hold ends. The control-plane's ASR-AUTH-005 owns these
release-record obligations and the release owner's authority.

Neither a task branch name nor a matching dev SHA proves an active release
claim. The current check verifies snapshot and branch identities. No consumer
is assigned a live staged release. Until a qualified release-owner evidence
reader exists, CI refuses ordinary promotions into or out of staging and
staging repairs. Existing first-definition registrations remain
scoped to their governed development targets. REQ-013/014 own the separate
security proof and ordinary proposals cannot claim it by choosing a branch name.

#### Organization-required baseline pilot

The central entrypoint is `.github/workflows/org-baseline.yml` in this
repository, selected by a ForgingAlpha organization ruleset tracking protected
`refs/heads/main`, with explicit consumer repository/branch selectors during the pilot. The
one-time human settings transition replaces the old immutable workflow pin;
later protected merges need no recurring ruleset update or activation.
Required source checks and exact-head human review precede those merges.
Existing protections remain in force. The workflow checks out the consumer
revision separately from its own trusted checking source and records both
identities; actual workflow-context values and GitHub App events require live
qualification. It uses read-only pull-request execution, not a privileged
pull-request-target path, and does not contain CodeQL initialization/analysis.
Its shared Actions and scripts resolve from that separate trusted checkout at
the same workflow-source SHA, using local paths within that checkout. It does
not combine its defining workflow revision with helpers fetched from a newer
`main` or an older tag. It records the exact resolved defining-workflow SHA;
movement of `main` after resolution does not replace that execution's source.

Under REQ-029 the protection operator qualifies the selector on a bounded
target using the REQ-016 settings path and captures the prior rule, saved rule
and effective protections. Existing required checks stay active throughout.
Evaluation-mode insights can inform selection; verified enforcement requires
actual pass and block results. The organization rule selects the common
baseline. Onboarding reads the consumer's exact Git inputs and existing
central enrollment and runtime catalog to prepare reviewable assignments.
Repository content cannot write trusted enrollment or choose a release route.
Product owners retain their tests and release assignments, and the separate
organization security configuration retains its own owner.

The central source owns explicit pilot profiles and their human-review team
identity. A consumer cannot grant itself bootstrap or weaken its required
reviewers. The team-review profile reads fresh effective branch rules and
requires the enrolled team, complete-change coverage, required approval count
and stale-approval invalidation. Missing or partial evidence is a failure.
Team membership and eligibility remain an operator-qualified prerequisite, not
an inference from a team ID. Bypass-actor and complete protection qualification
also remain with the operator; effective-rule reads alone cannot prove them.
The shared-CI owner will expose the same metadata-only verification to
repositories that produce their own product `CI`. The trusted source selects
the team and rule criteria. These repositories keep CODEOWNERS validation
until the standalone check and their hosted protections have been qualified.

Here CI enrollment means the centrally reviewed validation configuration for a
consumer, not an unattended-authority Repository Enrollment or an Operational
Profile. It grants no execution or merge authority and does not create a runtime
profile assignment. Definition-only baseline repair and an enrolled document-only
profile remain distinct; neither can substitute for the other's conditions.

For an initial private definition PR, the protection operator can select the
existing workflow on the target repository's `dev` branch and register the exact
candidate using an organization-managed repository property. The public source
owns the validation rule. The target property binds the PR number, head, human
review team and owning scopes. The workflow checks that the protected base is
the candidate's sole root commit and contains one regular README. It rechecks
the registration and the protected branch at finalization. The operator removes
the temporary workflow assignment and property after the definition merges.
The existing branch-wide CI and human-review rules continue to apply.

Bootstrap accepts only declared document/configuration inputs and refuses
application content and executable lint configuration before invoking shared
validators. Structural metadata does not prove human approval or Currentness.
Product profiles retain their own builds, tests, manifests and exact runtime
inputs.
The shared-CI owner accounts for common-check invocation and profile configuration.
For an unmigrated caller, the product owner accounts for build/test composition;
for a central-product profile the shared-CI owner composes the declared lanes while
the product owner accounts for their command meaning and complete product coverage. Language-only
composition is eligible only while independently verified central enforcement
covers its common checks. Migrate by qualifying the central gate before removing
consumer common calls; restore those calls before removing that gate. Until this
joint invariant is verified, full composite defaults remain unchanged. A consumer
opt-out input or configuration cannot establish the invariant.

#### Full application profiles and producer transitions

The same centrally owned enrollment binds a complete application profile, its
component roots and its selected product `CI` producer. Supported Rust, Astro and
mixed profiles consume the existing language-check implementations; they do not
create a second registry or a general test-selection engine. Discovery inspects
tracked manifests in the exact complete consumer commit and verifies the declared
components. An undeclared component, missing expected manifest, lock, runtime or
required command fails rather than selecting a lighter profile or bootstrap.
Changing only documentation does not narrow an application profile's coverage.
Runtime tuples remain owned by the existing runtime catalog under REQ-010.

For a central-product profile, the trusted central workflow owns the stable
product `CI` result and records its checking source, consumer head/base and complete
applicable profile. Its common baseline retains a distinct result identity. Shared
checks run once; every required product lane must finish successfully before the
product result passes. Failed, cancelled, missing or unexpectedly skipped required
lanes cannot become an accepted aggregate success. Product owners retain the meaning
and completeness of their tests and commands; central execution does not redefine
those obligations.
Consumer build/test code receives no production credentials or privileged executor.
CodeQL analysis and configuration remain separate from this required workflow.

The shared-CI owner coordinates each producer transition with the consumer owner
and the protection operator. Bind the old and new workflow identities, exact
consumer head/base, checking source, complete profile, result producer and preserved
protections before activation. Source capability alone does not enroll a consumer,
retire its caller or select a runtime. Unmigrated callers keep their full default
checks and their selected product result. Missing or ambiguous producer ownership
blocks acceptance; the system must not accept whichever result happens to pass. Qualification may
coexist under a distinct provisional central result while the current caller
continues to own required `CI`, on an explicitly enrolled qualification target.
That target binds the complete candidate and preserved controls; its result is
not an accepted production `CI`. After equivalent coverage is established, the
operator and consumer owner perform a source-bound serialized handover with saved
state readback. For an existing caller, select the central producer before merging
the retirement head; that head removes the caller's `CI` and obtains `CI` solely
from the central producer. The bounded handover explicitly admits pre-retirement
heads that still carry the caller and therefore can emit dual `CI` results:
the separately required common-baseline gate must refuse every such head, regardless
of either `CI` result. Preserve strict current-base protection throughout. After
retirement merges, those heads must update to the post-retirement base and pass
the unique producer's complete checks before acceptance. Bind REQ-025's already-open
pull-request qualification to this stale-head refusal and updated-head success.
The transition record binds affected heads and start/terminal conditions; the window
ends after the retirement merge and current-base new-producer qualification, or
after recovery of the captured prior configuration. Remaining stale heads stay
refused. Outside that controlled state, duplicate indistinguishable producers block
activation. Required `CI` stays in force; a missing result remains an unsatisfied
merge gate and is never waived. If the handover cannot enforce these refusals or
preserve controls, retain the caller. There is no automatic retirement in this revision.
Before caller retirement, recovery preserves the previous qualified producer and
full protection configuration. After retirement, restoring that caller requires
a separately reviewed consumer recovery change merged under REQ-024; a ruleset revert
alone is insufficient. Retain the exact recovery source, checks and transition
evidence before retirement. Reconcile an unknown outcome before another effect.
This source responsibility does not authorize
hosted rule changes, runtime assignments, release activation or a PR merge.

Transition discovery inventories consumers of the CI result, not just its job
name. This revision does not activate central-product profiles for consumers
whose security classifier/verifier is bound to repository-local CI, or whose
required CI relies on push events: they retain their existing producer and full
composite. Organization-required pull-request workflows do not establish their
`workflow_run` wake, exact CI-path binding or push-event coverage. A later migration
must rebind and qualify those dependencies with the security/release owners before
retirement; this source change does not alter that automation or its protections.

Central workflows and fixed first-party composite callers select protected
`.github/main`. Source becomes active through the protected merge; this does not
enroll a new target, alter selectors or establish actual target enforcement.
All central helpers and cores resolve from the same defining-workflow checkout.
Composite execution retains its resolved acquisition SHA, identifying the
Action and bundled helpers it executes. Premerge qualification uses a coherent candidate, including
its sibling helpers, rather than mixing local candidate code with live main.
Runner-dependent archive behavior is qualified for supported caller execution;
a mutable branch label alone is not exact-source evidence.

Central source includes closed Rust, Astro and mixed profile interfaces with fixed
common, static, test and finalization stages. The trusted enrollment and runtime
catalogs declare the exact accepted profiles; neither source fixtures nor a
main merge alone establish hosted enrollment or producer handover. Rust and mixed additionally lack an approved
real Rust runtime assignment. Existing consumer producers and all target-specific
qualification obligations remain in place.

The initial pilot includes the document-bootstrap consumer and an independently verified
current Rust consumer. An unborn local repository or hosted documents-only branch cannot
stand in for the Rust consumer. Each target establishes evidence only for the profile
and shared behavior it actually exercises; neither supplies missing second-target
evidence or completes the whole pilot by itself.

Qualification and enrollment follow that affected scope. The shared-CI owner retains a
reviewed impact assessment in the existing task or proposal record, identifying complete
consumer candidate inputs and base state, dependencies and exact checking-source
before/after revisions. Material judgments about affected scope or unrelatedness,
including no-change and scope exclusions, require independent verification. Shared
inputs include workflow loading, profile selection, permissions, runner assumptions,
result aggregation and pre-execution integrity. Changes affecting these responsibilities
receive coverage across the affected profiles. Unknown impact requires conservative
additional validation or leaves the affected proposal blocked. A missing consumer
manifest or changed file extension cannot select a less demanding profile.

A profile with every required pilot case verified and qualified shared dependencies may
progress independently of unrelated profiles. Cases include valid/invalid/repair,
App-created and already-open triggers, consumer skip/configuration/application-input
refusal and observed source restoration with valid-pass and invalid-block behavior.
A new central product or documentation assignment still requires explicit enrollment.
Every additional repository or branch, including one selected by the common default,
requires live qualification of that target's identity, head/base, token access, check producers and
required protections. Reusable content evidence does not replace current-target CI or
review. The full declared profile runs against the complete proposed tree; this rule
introduces no changed-file test selector.

Every additional enrollment or migration identifies and qualifies its affected profiles
and shared behavior. Common-call retirement requires complete coverage for that affected
scope; whole-pilot completion requires all initial targets and cases. Product-specific
checks remain mandatory, and consumer common calls remain until the central gate's
coverage of those obligations is independently verified. Rust qualification remains
required wherever Rust behavior or shared enforcement affecting it is in scope; it is
not a blanket dependency of an otherwise independently qualified non-Rust profile.

Ruleset administration retains the existing operator-owned path under REQ-016
and the control-plane authority procedure. This amendment does not permit an
agent to save protection changes through a human browser session or to borrow
human credentials; browser consent alone does not establish that authority.
Any protected executor requires separate qualification before a settings write.

Initial enrollment and the one-time main-reference transition require the
human-owned settings path and observable target runs. For that source-reference
transition, compare the complete
captured prior rule, change only the approved source reference, and read back
the complete saved configuration and effective protection on both target
branches. Preserve check identities, strictness, selectors, bypasses and
creation exemptions. A stale or ambiguous state stops the operation; an unknown
save requires readback before retry. This is not permission for an agent to
administer rules or expand its credential scope.

After that transition, a protected merge into main activates source
without another settings operation. Recovery is a human-reviewed corrective or
revert PR into main, with its resulting immutable commit and observed outcomes
recorded. Verify required valid-pass and invalid-block behavior; a failed,
cancelled, skipped or unexecuted run is not enforcement evidence. Retain earlier
pilot/source-restoration evidence without replaying completed cases merely
because the old procedure named a pin cycle. A consumer's actual selector,
producer or coverage change still retains its affected qualification duties.

Implementation and enrollment remain pending until independently qualified.
No workflow, profile, team membership, ruleset or operational capability is
created merely by adopting this architecture. Normal dependency cooldowns,
expedited security eligibility and exact human source approval remain. Product deployment
schedules and settings transitions retain their own authority; shared source
does not wait for a scheduled activation hour after its protected merge.

### Main-Based Shared Source

Protected `.github/main` is active. Required CI and review cover
the exact candidate before the protected merge, including coherent affected
consumer-profile checks. Existing enrolled consumer gates belong to that
premerge validation; they are not silently removed or moved behind a separate
activation decision. Post-merge observations record their actual subjects, times
and failures; they do not retroactively qualify a proposal, promote a tag or
decide whether main is official.

For a centrally required workflow, the ruleset tracks main and GitHub supplies
the immutable defining-workflow identity. Every checking-source checkout uses
that identity. Admission, static work, tests and finalization compare their
source-bound plans/results and fail on disagreement. A later main merge does
not rewrite an already resolved run or authorize falling back to another ref.

First-party composite and probe references use the fixed main family. Their
native acquisition evidence identifies each resolved Action revision and its
bundled helpers. Central application plans and receipts retain SHA256 fingerprints
for the shared route guard, its repository assignments, `actions/ci-org-baseline/scripts/baseline.py`,
`actions/ci-org-baseline/enrollment.json` and `runtime-profiles/catalog.json`,
all read from the same exact checking-source checkout. Candidate validation
must not mix a proposed parent with siblings independently selected from live
main. The source inventory accounts for active callers, templates, provenance
resolvers and ownership rules before retiring channel-dependent machinery.
Unmigrated references remain explicit migration gaps, not a second current
contract or evidence that those consumers already follow main.

Retire the recurring v1 promotion and tag-rollback workflows and their active
helpers after inventory and affected-source verification. Preserve existing
tags, immutable commits and historical rollout/rollback records; this source
change does not delete refs, cancel runs or alter grants. Reconcile any pending
old writer before the human transition rather than retrying it blindly.
Recovery uses the protected human-reviewed revert or forward-fix path on main.

### Shared CI Profiles

A product workflow selects the standard language checks by calling `ci-rust`
or `ci-astro` for the relevant package root. For a nested Cargo workspace,
the Rust caller supplies `working-directory`. Calling the action requires no
repository language label or transfer of the required `CI` result. The product
workflow composes those checks with its own smoke tests, services and storage
checks. Its owner retains deployment configuration and release decisions.

The existing `actions/ci-rust/action.yml` and `actions/ci-astro/action.yml` are the
language-check sources for extraction into coherent central checking cores.
Their present existence is not evidence that central dispatch, complete runtime
admission or producer migration is already implemented or qualified. The shared-CI
owner preserves the full composite entrypoints for unmigrated callers while
implementing the following full application profile contracts under REQ-003,
REQ-004 and REQ-010:

- Rust binds each declared Cargo workspace/root, its tracked manifests and lock,
  and approved locked runtime/tools. Static work includes formatting, Clippy with
  warnings denied, dead-code compilation and dependency audit. Product test lanes
  run all declared targets/features and owner-required tests with locked inputs.
- Astro binds each declared package root, tracked `package.json` and package lock,
  and approved `mise.toml`/`mise.lock` runtime projection. Locked installation,
  formatting, lint, Astro type checking and build checks form the static surface;
  product test lanes run the owner-required test commands. Missing commands or
  tools fail rather than silently omit promised coverage.
- Mixed profiles compose all declared Rust and Astro components. Common checks
  and each static surface run once; product test lanes do not repeat static work.
  No Rust component or runtime is inferred for an Astro-only consumer.

Public-facing Astro websites use a shared website-quality check after the
production build. The same Playwright runner serves the freshly built site
locally and in CI. Chromium covers desktop and phone layouts, site-owned
journeys, and axe checks on public HTML and relevant interactive states.
Release PRs to `main` also run the essential journeys in Firefox and WebKit.
Each site owns its routes, local preview or Worker, expected behavior, and
manual accessibility checks. The [website browser runner](actions/ci-site-browser/README.md)
uses locked test dependencies from the site. The shared Astro build continues
to run once. An enrolled component checks the existing output in that job
before an owner-selected script can replace it. A repository with its own CI
producer calls the same runner after its build. Adoption requires verifying
equivalent coverage before retiring earlier browser checks.

`ci-elixir` exposes `full`, `static`, and `test` profiles. `full` runs all
cross-cutting/static work and the caller test command. `static` runs the same
cross-cutting/static work without tests. `test` performs only locked runtime and
dependency setup, caller preparation, and the assigned test command.

The static surface includes merge flow, approved source truth, Markdown,
workflow safety when relevant, update coverage, dependency review, formatting,
warnings-as-errors compilation, repo-owned architecture checks, Credo strict,
unused dependency validation, dependency audits, Phoenix security analysis, and
Dialyzer. Missing required tools fail clearly.

Markdown validation always enumerates all tracked `.md` and `.markdown` files;
there is no changed-file mode. Dependency review is mandatory on consumer pull
requests and has no caller disable switch. The SHA-pinned official action blocks
low-or-higher vulnerabilities and licenses outside a centrally owned approved
SPDX allowlist, subject to the central artifact admission below. The shared-CI
owner includes the exact `OFL-1.1` and `LGPL-3.0-or-later` identifiers alongside
the existing permissive licenses. The gate evaluates the reported license
expression. Product owners verify the terms against the font files they ship.
Released enforcement must evaluate compound SPDX expressions
under REQ-023: all mandatory terms in an approved alternative must be eligible.
The owner verifies that behavior through the actual pinned official action and
mandatory evidence guard before release; this architecture specifies required
behavior and does not attest to current execution. No broad LGPL package-family
exclusion or consumer-selected license override is permitted.
A following fail-closed check inspects the official dependency-change output.
Recognized licenses need no additional
network lookup. Null or empty third-party licenses still fail except for GitHub
Actions whose package URL names an exact 40-character commit SHA and whose
canonical GitHub source identity matches that package URL. For only that
constrained case, the checker constructs GitHub's repository-license API
endpoint itself, queries the license at the exact immutable SHA with the
caller's read-only GitHub token, and accepts only an SPDX identifier from the
same central allowlist. External lookups have a fixed timeout, are deduplicated,
and are capped at 20 unique revisions per pull request.

The other constrained normalization is an exact pinned npm alias whose official
dependency-change record names the alias but omits its target license. The checker
accepts only root `package.json` aliases of the form `npm:<target>@<exact-version>`
whose canonical alias PURL and root package-lock spec agree. The lock must use npm
format 3 and contain the alias install path with the exact target name, version,
canonical registry tarball, sha512 integrity, and an SPDX identifier from the central
allowlist. The checker first reuses an exact concrete dependency-review record for the
underlying package. Otherwise it makes one anonymous, bounded request to an internally
constructed `registry.npmjs.org` exact-release endpoint, rejects redirects, and requires
the registry name, version, tarball, integrity, and license to match the lock exactly.
No token, caller URL, alternate registry, package exception, or executable package
content enters this evidence path; unavailable or inconsistent evidence fails closed.

The first-party Action evidence class is fixed in central code to
`ForgingAlpha/.github/actions/<action>@main`. An absent or null source repository
URL is allowed; a supplied value must equal
`https://github.com/ForgingAlpha/.github`. These are central identities, not a
caller-configurable exception or a reusable-workflow evidence class.

The existing action assigns `DEPENDENCY_REPOSITORY` from `github.repository`;
`license_policy.py` validates this provider-derived repository identity. No
caller input or environment fallback selects the consumer. Explicit unapproved
or malformed license expressions never enter a missing-license provenance
exception. Existing approved-license and artifact-exception behavior remains.

All admitted first-party Actions in one validation share one internally fixed
protected `refs/heads/main` request and one tree request at the returned immutable
commit. The ref must resolve directly to a commit; a later main cannot replace
the selected snapshot. The complete, untruncated tree must contain exactly one
nonempty regular blob at each Action's fixed path. Require type `blob`, mode
`100644` or `100755`, positive integer size and a valid immutable blob SHA.
Missing, conflicting, malformed or unavailable identity/ref/tree/blob evidence
fails closed. The actual HTTP transport for these fixed first-party requests
rejects redirects; dependency data never supplies an endpoint. Third-party
exact-SHA license resolution, other missing-license evidence classes and
vulnerability enforcement remain separate and unchanged.

The recorded repository, main snapshot, commit and blob establish source
provenance only. They do not prove which Action executed, runtime safety,
license compliance, a grant, human approval or runtime activation. The lookup
composes with the protected, human-reviewed merge path; it does not independently re-prove
that path.

`license_policy.py` also owns the closed artifact exception for
`ForgingAlpha/turnkeyleads-app`, `assets/customer/package-lock.json`, and
`mapbox-gl@3.31.0`. Its record binds the canonical npm tarball, exact sha512
integrity, and reviewed `package/LICENSE.txt` digest. Proposal preparation verifies
that digest inside the integrity-checked, bounded archive without executing package
content. CI compares the checked-out manifest, npm v3 lock, and dependency-review
record with this central immutable evidence; it does not download the archive again.
The source-bound preparation receipt is retained in
`docs/audits/2026-09-26-mapbox-3.31.0-artifact.json`; an offline test binds it to
the policy record and checks canonical identities and digest formats. The record's
license-member path, license digest and archive digest document that reviewed
preparation evidence. They are not claims that routine CI rereads the archive.
Matching license-file bytes do not establish acceptance of external vendor terms or
account entitlement; those remain a separate human admission decision under REQ-024.

Both scripts receive repository identity directly from GitHub context. Only the
fixed repository receives the official action's Mapbox license exclusion. That
upstream exclusion ignores versions and compares decoded names case-insensitively,
so the following `always()` guard checks its entire matching family **before** the
normal nonempty-license shortcut. It requires the one canonical record, a matching
runtime manifest/root-lock declaration (`3.31.0` or `^3.31.0`), and the exact locked
artifact. Additional versions, manifests, installations, contradictory names,
noncanonical PURLs, missing evidence, and unsafe manifest files fail closed.
Vulnerability checks remain independent and unchanged. Other repositories receive
no exclusion; no caller input selects an exception. Any later artifact needs a new
reviewed central policy change.

The central license-policy implementation owns standard SPDX identifiers and
license eligibility. The product release owner owns the actual delivered
contents, the selected licensing alternative when a choice matters, and
applicable compliance evidence in the existing release record. LGPL is a
conditional license, not a permissive-license classification. The owner
reconciles library modifications, combined/linked works, redistribution and
covered content in generated output against the applicable terms, retaining
required notices, license copies, source/relinking or replacement arrangements
and installation information as applicable. Internal use of a build tool does
not alone license its output under LGPL; actual content and distribution decide
which obligations apply. A changed use/distribution basis requires renewed
product assessment; routine dependency updates do not require a centrally fixed
package/version or whole-manifest/build-file digest.

The LGPL version-3 terms are available from the
[SPDX license text](https://spdx.org/licenses/LGPL-3.0-or-later.html), including the
incorporated GPL terms. `LGPL-3.0-or-later` permits selecting version 3 for this
policy; it is not blanket adoption of future terms or other SPDX identifiers.
The gate supplies dependency eligibility evidence, not a legal-compliance
certificate. Unresolved applicable obligations stop product delivery under
REQ-023. The shared-CI owner preserves existing vulnerability thresholds,
first-party and missing-license evidence paths, and the separate Mapbox exception.
Standalone GPL/AGPL, other LGPL identifiers and custom/unknown evidence require
a separate central decision unless already covered by an applicable exception.

The shared-CI owner verifies actual SPDX expression handling and vulnerability,
unknown-license and Mapbox regressions before releasing changed enforcement.
The consumed gate revision must implement the adopted policy before reliance;
source adoption and a list-entry unit test alone do not prove provider behavior
or fresh consumer CI success. REQ-020 retains coherent candidate and affected
consumer validation before merge.

Private organization repositories must have GitHub's dependency-review feature
and required Code Security entitlement enabled before adopting this gate.

Each policy surface has one canonical implementation and test entrypoint.
Workflows and tests invoke it directly.

Fanned-out workflows expose one `CI` fan-in that fails when any required job is
failed, cancelled, or skipped.

### Runtime And Cache Model

Runtime authority is enrolled per consumer. The versioned profile catalog owns
approved compatible tuples, assignments, integrity requirements and exact
expiring exceptions. Each consumer commits `mise.toml` and `mise.lock`; a
required released gate validates their exact assigned projection before locked
installation. Unenrolled repositories retain their existing exact-lock authority.
Workflow YAML does not duplicate runtime versions.

The supplied runtime-profile gate is read-only: direct Renovate mise updates,
Node-engine updates and generic lock maintenance are disabled. Automatic
projection updates require a qualified constrained resolver, writer, consumer
canary and rollout gate. A published catalog alone does not establish enforced
organization-wide runtime authority.

Runtime, dependency/build, and Dialyzer caches are keyed by operating system,
architecture, exact resolved runtimes, dependency locks, and relevant build
inputs. Cache design is validated on both cold and warm Blacksmith runs and may
not restore artifacts across incompatible OTP/Elixir combinations.

### Dependency And Security Flow

Normal updates and security remediation are separate, non-overlapping lanes.

To provision a maintained repository, put the [weekly preset](renovate-weekly.json)
in its root `renovate.json` and declare Renovate as the ordinary owner in
`.github/update-policy.json`. Each repository supplies its ordinary
target and package locations. For an existing repository, the control-plane
operator verifies the approved repository identity, App access, manager
discovery, required CI and target protections before switching its preset.
Reconcile open routine proposals at transfer so coverage continues.

Required `CI` invokes `ci-update-ownership` with the ownership declaration,
the repository's Renovate and Dependabot configurations, and GitHub's actual
default branch. A consumer extends exactly one approved preset. The weekly
preset inherits the [existing policy](renovate-config.json), which existing
consumers can continue to select. Consumers assigned a central runtime also
declare `runtime_profile` and validate their assignment and locked projection
through the runtime-profile gate.

The organization Renovate preset lives in `.github`. The consumer's effective
configuration selects it by its published name. Native
managers own ordinary package manifests and locks, external
Actions, and active non-runtime image references. The preset excludes
`ForgingAlpha/.github` Actions so their internal `@main` references remain owned
by protected, human-reviewed merges instead of being pinned to one release commit or
proposed for a new major. The central runtime-profile
catalog owns governed runtime version declarations; constrained projection
automation owns the derived consumer mise declaration and lock. Narrow
annotated custom managers own irreducible version literals. Exact ranges and
digests remain pinned. Renovate vulnerability remediation is disabled.

The [weekly preset](renovate-weekly.json) implements [REQ-012](#req-012---normal-update-cooldown).
Renovate groups eligible updates across managers on the stable
`weekly-dependencies` branch. A weekly consumer can split one dependency for
independent testing or rollback through a reviewed `packageRules` entry. Its
`description` records the reason, `matchManagers` and `matchPackageNames` each
name one literal, `matchUpdateTypes` lists `minor`, `patch` and `digest`, and
`groupName` is null. The split inherits the same schedule and release ages.
Initial pins, replacements and rollbacks keep their separate handling.
REQ-027 governs the ordinary integration route and its migration. Shared
automation takes effect on protected `main` after coherent candidate and
affected-consumer validation. The receiving repository's
change owner accounts for the updater's disposable exploration, whole-unit review
and refactoring before integration; its release owner accounts for batch identity,
composition and reconciliation. Those owners consume the shared control-plane's
exploration procedure, including its disposable-code duty; this downstream source
defines no exception. A bot PR or green CI alone does not discharge these duties.
Automation identity supplies no exemption.

The existing `ci-update-ownership` validator requires the ordinary base to
equal the hosted default. To support different targets, the validator must
check the Renovate base against the independently established ordinary route
and the security source against GitHub's actual protected default. For example,
with ordinary `dev` and default `main`, a routine PR to `main` or a security
source PR to `dev` fails the corresponding check. Keep the qualified prior
route until the replacement passes both positive and wrong-target cases.

For Renovate-owned ecosystems, repository-local Dependabot configuration uses
`open-pull-requests-limit: 0` to suppress routine version proposals. Verify
effective Dependabot alerts and security updates, supported manifests on the
actual default branch, and the trusted workflow and required checks on that
source. A manifest present only on a development branch does not establish
default-branch security coverage.

Security-only Dependabot updates use the repository's protected default branch,
`main` or `dev`. A default change triggers revalidation of both routes and their
source, checks and hosted settings. Every eligible security source uses the
common exact classification and patch proof below. A direct-main proposal does not manufacture a dev merge or projection;
a separate-dev source additionally uses the cross-branch projection path. Both
retain current-base CI, scanning and exact-head human approval under REQ-024. Existing enrolled proof consumers remain required until their
qualified replacements preserve the applicable evidence and event paths.

The trusted caller binds the source branch from that owned configuration and
passes it consistently to preflight, classification and source observation.
Only protected main or dev is eligible; a candidate branch name, label or workflow
input cannot select an unqualified source or weaker proof. At the recorded
implementation baseline `21a0b865`, Python source-proof operations accept a
source-branch parameter, but the
classification wrapper defaults to dev and there is no direct-source observation
wrapper. Those are implementation and qualification obligations, not evidence that
main-only security delivery already works. Existing authorized security credentials
and environment restrictions remain in force. This route adds no grant or credential
exposure; unavailable rights or trusted execution stop that security flow rather
than moving its secret into ordinary CI.

Security classification never depends on a Dependabot-triggered
workflow having access to an Actions secret. The unprivileged pull-request CI run is only a wake
for a default-branch `workflow_run` job. Before entering an environment or
minting an App token, that job validates the exact CI workflow path, run,
repository, same-repository Dependabot pull request, current base and head, and
then polls the latest exact-head trusted CI and CodeQL checks at a bounded
interval for at most five minutes. It waits only for missing or in-progress
checks and fails immediately for movement, ambiguity, terminal failure, or a
wrong reporting App. CI success remains mandatory. Aggregate CodeQL success is
the normal path; its trusted neutral result remains conditional until exact
source classification proves an exact lockfile-only patch and the check output
and sole pull-request pointer match the released two-configuration Default
setup no-configurations-found condition for the source branch and exact pull
request, base, and head. Every other CodeQL non-success fails closed. An absent
workflow-run pull-request pointer uses a unique live commit association;
malformed or multiple pointers fail closed.
The caller serializes the repository and exact source head without cancellation;
the classifier also re-reads its check after writing and rejects duplicates.

After read-only proof, a separate job enters the branch-restricted
`security-automation` environment, mints the dedicated security
source/projector App,
and re-fetches every source fact. It uses live GitHub pull-request, commit,
file, check, workflow-run, and vulnerability-alert APIs rather than the
event-bound Dependabot metadata Action. Grouped PRs bind every associated OPEN
or FIXED GHSA. All commits must remain verified Dependabot commits, only the
approved manifest and lock may change, and stale native auto-merge or retired
routing state is rejected. `security-patch-classification` writes one trusted
exact-head classification. An identical retry preserves its original completion
time; it cannot create missing pre-merge evidence after a merge. Its App key
exists only in this security boundary and is never available to the general
agent launcher. The normal two-parent source merge follows REQ-024 after
classification, required checks and applicable approval. The unprivileged
preflight does not read vulnerability alerts and is not full classification.

For a separate-dev source, production remediation uses an exact-patch projection
instead of a dev branch promotion. A trusted projector re-proves the merged Dependabot source PR,
classification App, recorded source merger and merge time, exact source base and head, and complete
OPEN or FIXED GHSA set. It accepts only the enrolled repository profile's
dependency manifest and lock paths. The authoritative source base is the first
parent of the recorded security merge and must equal the base bound by source
classification. The root npm profile accepts only a normal two-parent merge
whose ordered parents are the classified source base and source head and whose
tree equals the classified source head. Later unrelated movement of `dev`
does not invalidate that immutable source chain.

For the root npm profile, current `main` must still contain the exact
source pre-fix blob and mode for both `package.json` and `package-lock.json`,
even when only the lock changed. Starting from the exact current `main` commit,
the projector uses GitHub's Git Data API to replace only source-changed entries
with the source post-fix blobs and modes. It performs no checkout, three-way
merge, cherry-pick, conflict resolution, or lock regeneration.

The no-main-bypass projection writer creates one same-repository branch and pull
request and records provenance bound to the repository, source PR, source base
and head, `dev` merge, production base, complete GHSA set, projected head, and
resulting tree. The released control-plane policy pins the dedicated security
source/projector App's public ID as the identity trust anchor for both source
classification and projection writing; consumers install that App but cannot
select or override which App the policy trusts. The projection App's current
slug must match the projection pull-request bot actor. The source merge must postdate classification. Native completion additionally
requires independent proof of the qualified arming actor and exact human approval.
The source observer records the actual merge actor and method under REQ-024. Labels,
titles, bodies, and branch names are routing hints only.
Any divergent preimage, unsupported file type, extra path, ambiguous API result,
concurrent lock change, or moved base stops or rebuilds the projection from the
new production base after the same exact checks.

Projection creation is a deterministic create-or-adopt state machine. Its branch
key contains the source pull request, source head, and production base, while its
tree and commit are content-addressed from the exact source and production
objects. Before creating a pull request, the writer ensures that the branch ref
exists only at the expected projected head and that exactly one App `4618077`
attestation with the exact canonical payload exists on that head. A retry adopts
an existing ref, check, or open draft pull request only after fresh base, fixed-App
actor, branch, head, single-commit tree, file set, disabled maintainer modification,
and sole-lock proof. It never updates or deletes a conflicting ref. Accepted writes whose
responses are lost therefore converge on one proposal; mismatches and concurrent
duplicates remain visible and fail closed.
The writer snapshots ref and check state before mutation and permits only the
three monotonic states: neither object, exact ref only, or exact ref plus one
exact check. It also searches all pull-request history for the deterministic
same-repository head; a closed, merged, wrong-base, or duplicate record is a
fail-closed tombstone rather than permission to create a replacement.

Projection writes use non-cancelling caller concurrency scoped by repository
and target branch. A qualified single-lock writer may additionally scope its
group by lock path. Every writer that can overlap a multi-lock projection uses
the common repository-and-target group; keys based only on the selected lock
set do not exclude unequal overlapping sets. Caller transitions account for
existing, queued, and running writers before the new scope is used. There may
be at most one open production projection touching any affected lock; a second
candidate or any other concurrent lock proposal fails closed rather than batching or
choosing an order. GitHub caps pull-request file enumeration at 3,000 entries,
so the proof compares the detailed pull request's changed-file count with the
complete paginated result and rejects the cap, a mismatch, or duplicates. The
composite action cannot supply workflow concurrency itself: enrollment must
install and qualify the caller groups and their overlap coverage.

Normal pull-request CI and CodeQL then execute for the exact projected head in
the current `main` context with no privileged credential. GitHub also exposes a
live synthetic test merge for that exact head and base. A protected default-branch workflow
first mints the dedicated security source/projector App token narrowed to metadata,
pull-request, check, content, Actions, and vulnerability-alert read access. It
uses that read-only token to independently reconstruct the expected tree,
re-prove the full source and advisory chain; verify the exact CI workflow path,
run, repository, pull-request pointer, projected head, conclusion, and CodeQL
provenance; and independently require the live test merge to have the attested
production base and projected head as its parents and the expected projected tree.
`security-patch-verification` performs this read-only proof and rejects native
auto-merge armed on the proposal. It has no merge credential or merge operation.
An applicable authorized human approves and performs the merge after the
required checks; initial draft creation does not require those later gates.

After GitHub updates `main`, a read-only push observer passes the actual merge
SHA and merged projection PR to `verify-post-merge`. The verifier derives the
expected base, head and tree from the pinned-App projection attestation and
checks the merge and current ref. The ordinary push-triggered deployment binds
itself to and reports that exact revision; it may begin concurrently and is not
represented as gated by this observation.

For a direct-main security merge, the corresponding read-only observer binds the
actual main push, merged source pull request and current main ref, then re-proves
the source classification and attributed source merge through the common source-proof
implementation. It verifies the classified base and head, classification time,
ordered merge parents, source-head tree, approved manifest-and-lock patch and
official advisory association. It does not use the projection-only attestation or
create missing classification after the fact. Where the product requires deployment,
the ordinary deployment records that exact main merge revision and tree; it may
begin concurrently with observation. A shared-source main merge establishes active
source, not a product deployment or an additional post-merge activation gate.

Quality, CodeQL, current-base, deletion, non-fast-forward, and merge-shape rules
remain in no-bypass rulesets. Security and updater identities have no branch
merge or direct-push authority. Consumer enrollment must prove the exact
source classification, checks, caller serialization, credential boundary, exact human
approval and actual source merge. Separate-dev production additionally proves projection. Each product retains
its applicable deployment evidence. Source publication does not establish that
enrollment or change existing hosted settings and queued work.

Privileged jobs process trusted GitHub metadata only. They never check out,
execute, or consume artifacts from pull-request code.

Installed marketplace plugins remain outside repository dependency bots and
are owned by their official installer. Customized vendored external skills
record an upstream repository and revision so deterministic synchronization can
surface reviewable changes. First-party repository skills remain normal source
code rather than pretending to be external dependencies.

### External Dependencies And Scheduled Backstops

All external Actions use full commit SHAs with reviewed-version comments.
Downloaded tools use exact versions plus checksums, lock integrity, or reviewed
provenance. CI rejects floating refs.

A deployment integration remains active for update-ownership purposes while a
live release workflow or configuration references it. A maintained
update-surface inventory names every active integration and owner. Integrations
proven inactive are deleted rather than enrolled in Renovate. The
updater-coverage gate rejects new unmanaged version literals and stale
exceptions.

Advisory audits run daily against the applicable integration and deployed refs.
For a main-only repository, do not invent missing dev/staging
refs or duplicate an audit of the same revision. Qualify the actual successor
integration/release audit subjects when that repository migrates.
Turnkey retains one weekly Ubuntu sentinel for independent runner and timing
diversity; it is diagnostic and never a merge requirement.

### Operator Boundary

Agents prepare scoped repository changes, verification, and `/tmp` scripts.
The operator owns destructive pushes, organization rules, credential/App setup,
exact-revision approval, the personal merges reserved by REQ-024, consumer
enrollment and settings transitions. Source recovery uses the protected human PR path. Updater, security
and release automation retains only its separately
defined non-merge effects. No SSH or personal credentials are available to agents.

### Application development containers

The control-plane [container procedure](https://github.com/ForgingAlpha/control-plane/blob/main/system/runbooks/operate-local-containers.md)
owns the Compose convention and container responsibilities. Applications retain
their product commands, tests and deployment configuration; the shared-CI owner
retains shared mandatory checks.

### Consumer qualification

REQ-020 and REQ-028 own coherent candidate validation and affected-consumer
evidence. The existing change process records the impact assessment and uses the
actual affected shared checks and enrolled consumer workflows.
Existing mandatory results retain their actual producers; a change record cannot
substitute for them. Each consumer retains its product commands, tests, private diagnostics
and applicable required results. Diagnosis binds the exact rule, consumer
configuration and inputs. Fix the consumer when it violates the selected
contract; fix the checker when it misapplies that contract. Preserve unresolved
causes and failed results in the owning change record. A local negative test
does not turn a failed consumer workflow into successful compatibility.

Qualification records the shared candidate, consumer revision, selected checking
source, required workflows and complete outcomes, including required steps and
post-job hooks. Reconcile affected qualification when inputs change. Distinguish
actual consumer execution from synthetic inputs and captured provider responses;
private source, commands, logs and artifacts stay in consumer custody.

### Architecture scope

The organization workflow and shared Actions own cross-repository checks and runtime
profiles. The enrollment record selects the check producer for each enrolled consumer.
Consumers own their product behavior, tests and deployment configuration. Protected
`.github/main` supplies the shared implementation, and each execution records the exact
revision it used.

## Local Instructions

For a change to this repository, propose a nonpersistent task branch to protected main. Check the proposed shared source and
affected callers together before requesting human review. Use the operator checklist
to verify the affected consumers, permissions and hosted settings when applicable.
[Repository route and retirement conditions](#uniform-proposal-targets) · [Operator checklist](docs/operator-checklist.md)

## Consumer Contract

Every repository exposes one required result named `CI`. Unmigrated callers retain
the full composite and their existing producer. An explicitly qualified central
application profile can instead select the organization workflow as that producer,
with a separately required `Organization Baseline` result.

```yaml
name: CI
on:
  push:
    branches: [dev]
  pull_request:
    branches: [dev, main]
permissions:
  contents: read
  checks: read
  pull-requests: read
jobs:
  CI:
    name: CI
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - uses: ForgingAlpha/.github/actions/ci-elixir@main
```

The caller above illustrates a direct-release consumer. Its ordinary task PRs
target dev and its dev-to-main release PR is checked before the protected merge.
Use the release targets selected under [REQ-027](#req-027---uniform-proposal-admission)
for other repositories. The shared merge check runs before consumer language
checks. Its read-only GitHub access verifies the live promotion subject and,
when applicable, the independently attested exact security patch.

## Central Documentation Pilot

The organization-required entrypoint is
[org-baseline.yml](.github/workflows/org-baseline.yml). Its trusted
[enrollment](actions/ci-org-baseline/enrollment.json) selects only
`ForgingAlpha/layaslearninglab-site`, repository ID `1420939261`, on `dev` and `main`.
Its current profile is `astro` with the `central-product` producer. The documentation
bootstrap described in this section is the earlier qualification profile, not that
consumer's current enrollment. Bootstrap rejects unknown identities and application
content; missing manifests never select bootstrap.
The defining `.github` repository is outside this consumer pilot. Its baseline
workflow excludes source-repository jobs, whose names remain distinct from `CI`
even when skipped. Actual target result naming requires hosted qualification. The existing required `CI`
workflow continues to validate this repository.

This candidate changes the bootstrap check topology: `CI` moves from the `baseline`
job to the final `result` job, and `baseline` reports `Organization Baseline`.
The retained live Q6 source B is still adopted source
`97a8a94c884f43c039278d117d0d9313d1465ec9`, with the old topology. Its results do not
qualify this candidate. Protected main is active at the protected merge. Any consumer
transition must reconcile both check identities and recovery, then qualify its exact
target before reliance. No live selector or Q6 binding changes with this source proposal.

The job checks out the defining workflow commit separately from the exact consumer
PR head. It admits tracked, non-executable Markdown, `.gitignore`, three enumerated
JSON data paths, and the two verified root instruction projections to `PROJECT.md`.
It checks governing metadata, fresh exact-base team-review configuration and every
canonical Markdown input. The data-only runner uses the existing locked tool,
central rules and no consumer plugins, formatters, configuration discovery or inline
rule suppression. A document's metadata is not proof of approval or Currentness.

This is source implementation, not active enrollment or completed qualification.
The job refuses missing defining-workflow identity instead of guessing another
source. Actual token access, check producers, selectors, review coverage of root and
nested paths, team eligibility, bypasses, triggering and source restoration require
the [operator pilot procedure](docs/operator-checklist.md#organization-required-documentation-pilot).
CodeQL remains separate. Application execution is available only through an explicitly
qualified full application profile described below. Qualification follows the enrolled
profile and affected shared behavior, with independently verified Material impact
judgments retained in the existing task or proposal record. A qualified profile can
progress independently of unrelated profiles; each additional repository or branch still
needs actual target-context checks. Central documentation and product assignments
require explicit enrollment under REQ-025 and REQ-026. Shared-enforcement changes
and broader migrations require coverage across all affected profiles before reliance or
common-call retirement. The initial documentation and actual hosted Rust cases retain
their own complete pilot-case obligations, including App-created/already-open triggers,
valid/invalid/repair, consumer skip/configuration/application-input refusal and source
restoration with valid-pass and invalid-block behavior. Source enrollment supports
`dev` and `main`; each live selector and target still requires operational qualification
before reliance. Existing language composites and
ordinary `ci-markdown` behavior are unchanged.

## Repository-owned CI for first governing documents

A private repository with a README-only initial `dev` commit can introduce its
first governing documents and a permanent `.github/workflows/ci.yml` together.
Copy the [caller template](actions/ci-governing-docs/caller.yml). Set `scopes`
to `'.'` for root definitions or, for example, `'.,catalog'` for root and
component definitions. Include every directory that owns a governing chain.

The shared action checks the entire proposed tree, the governing sources and
their upstream digests, and every tracked Markdown document. The human team
reviews the exact first caller before merge. Subsequent documentation PRs use
the caller and scopes already adopted on protected `dev`. To update an adopted
checkout pin, open a separate PR changing only the workflow to the current
template with the same scopes. Verify the hosted
`CI` run on the consumer PR. When introducing executable code, extend the
repository workflow with the applicable product checks.

For a product with component definitions, adopt the scope list before introducing
code. The legacy layout records it in root `docs/requirements.md`. A converted
repository records its protected four-section selection in the root source manifest.
For example, `readme_intent_scopes: {dev: [".", "catalog"]}` selects the
root and `catalog/` definitions for product changes into `dev`. Each scope
needs its approved README Intent, Requirements and Architecture with current
upstream references. The usual product CI, including the policy step inside
`ci-rust`, validates the selected scopes and runs its product checks.

An enrolled four-section scope can retire its bound `docs/requirements.md` or
`docs/architecture.md` into the corresponding README section. Place the complete
document body immediately after the section heading. Preserve the source metadata
in the manifest, rebase links to the README location, demote body headings by one
level and refresh exact upstream digests. The protected-base policy compares the
old Git blob with the proposed section before accepting removal of its binding.
Other detail paths and identities retain their bindings. Apply the shared reader
to protected main before proposing a migration that uses this check.

## Complete Application Profile Source

The [organization baseline contract](actions/ci-org-baseline/README.md) defines the
strict schema-2 source capability for Astro, Rust and mixed complete component trees.
The shipped enrollment and runtime catalog define the current profile and runtime
assignments. Source fixtures exercise schema 2; they do not enroll a consumer.
Rust/mixed remain fixture-only until actual approved runtime and consumer evidence exists.

Admission and common checking process consumer data without executing its scripts.
They check complete manifests, declared release route, source and runtime
integrity, policy, controlled Markdown, workflow safety, dependency and update ownership.
Product static checks and tests run in separate jobs on fresh bound checkouts; a final
trusted job rederives the plan, requires every applicable job to succeed and refuses
missing or mismatched component outputs. Changing only Markdown still runs the full
application profile. No matrix result or consumer output can reduce required coverage.

Qualification preserves the exact legacy workflow path/job/blob and emits only
`Organization Profile Qualification`. Current head/base observations belong to each
run, allowing valid, invalid, repaired and already-open revisions without a source
repin. Central-product mode instead refuses any remaining indistinguishable local CI.
Actual required-check producer, permissions and transition/recovery behavior must be
qualified before changing hosted selectors or retiring the caller.
Reusable-workflow jobs and dynamic job names are unsupported in application admission.
Central-product also refuses a literal `CI` producer in any workflow, including a
manual-only workflow; organizational probe wrappers are not an exception.

Only the trusted baseline job adds `checks: read` to the existing contents and
pull-request reads. The unchanged canonical security-projection verifier requires
that metadata read to validate exact check-run proof. Product jobs and the finalizer
do not receive this additional scope; there is no write permission or hosted grant
operation. The staged-route shortcut still refuses before the security carveout.

Runtime projection and version-output checks do not establish binary or backend
provenance. The runtime owner must supply that evidence before actual activation.
The pinned mise action exports `MISE_TRUSTED_CONFIG_PATHS` as the job workspace root;
its `working_directory` controls execution in `baseline-source`. Consumer installation
runs separately through the owned sanitized command. A real locked Astro sequence
through install and fresh static admission remains an activation prerequisite; the
command-stub tests do not prove that installation leaves a clean consumer checkout.
Actionlint retains consumer `.github/actionlint.yaml` configuration, including ignore
patterns that can suppress its findings. The separate full Python safety checker and
its existing reasoned allowlist remain required; this change adds no actionlint policy.

Legacy language wrappers retain their default common coverage, setup and commands;
their checking cores come from the same acquired repository archive. The optional
`ci-dependency-review` workspace input defaults to the existing workflow workspace;
central execution supplies its separate consumer checkout explicitly.
Shared tool literals retain their existing owner YAML locations and values. The current
Renovate configuration does not prove automated coverage for every numeric tool literal.
Consumer execution on a shared runner is not a hostile-code sandbox; separate trusted
jobs protect plan authority, not helper files after a consumer lifecycle script runs.

## Shared Actions

| Action | Contract |
| --- | --- |
| `ci-alphaapps-policy` | Source-truth baseline structure and fail-closed human CODEOWNERS boundaries |
| `ci-markdown` | Locked validation of tracked Markdown under repository policy on Linux |
| `ci-github-actions` | Actionlint, immutable refs, permissions, and trigger safety |
| `ci-dependabot-coverage` | Declared package coverage for Dependabot-managed consumers |
| `ci-update-ownership` | Sole normal-updater ownership and security-only Dependabot configuration |
| `ci-runtime-profile` | Exact consumer mise projection against the central assigned runtime tuple |
| `ci-dependency-review` | Mandatory PR vulnerability review and central approved-license policy |
| `ci-merge-flow` | Repository-bound task and release admission for development, direct, staged and main-only routes |
| `ci-elixir` | Locked runtime, strict static analysis, and repo-owned tests |
| `ci-rust` | Format, Clippy, dead code, tests, and audit |
| `ci-astro` | Format, lint, Astro type checking, and build |
| `ci-site-browser` | Site-owned journeys and accessibility checks against the completed website build |
| `ci-typescript` | Format, lint, type checking, and tests |
| `ci-shell` | ShellCheck at style severity and Bash syntax |
| `security-patch-classification` | Dependabot-safe preflight and trusted exact-source classification |
| `security-patch-projection` | Exact manifest/lock patch reconstruction on current `main` |
| `security-patch-verification` | Read-only production re-proof before a human merge |

External Actions are Renovate-owned and use immutable full SHAs with adjacent
release comments. Internal `ForgingAlpha/.github` shared Actions are excluded
from Renovate and use literal `@main`, owned by protected human-reviewed source
merges. Fixed canonical owner/repository/path spelling is required; other external
Actions retain full SHA pins.

Shared Python validators require Python 3 with PyYAML provisioned on the runner.
The policy action fails when that parser is unavailable; it does not install a
floating dependency or substitute a partial YAML parser. Baseline metadata is
a structural CI check, not proof of approval or Currentness. The exact
`ForgingAlpha/control-plane` origin uses its canonical source procedure without
a required status marker; its owner CI validates canonical identities and exact
upstream bindings. Other repository baseline status requirements remain in force.

## Rust lockfile validation

Set `locked: "true"` on `ci-rust` to require the selected Cargo workspace's
committed, unchanged `Cargo.lock`. The existing `working-directory` input
defaults to `.` and may name a nested workspace or a member directory containing
`Cargo.toml`. The action checks locked resolution before caching, passes
`--locked` to Clippy, compilation and tests, and audits the workspace lockfile.
Cargo keeps its normal package selection, including `default-members`.

Locked mode supports Cargo's conventional workspace-root lockfile. It uses
the `python3` on the job's `PATH` to read configuration from the selected
directory, its ancestors and Cargo home, including referenced config files.
Python 3.11–3.14 supports TOML 1.0. For TOML 1.1 features such as multiline
inline tables, select Python 3.15+ before invoking the action. An explicit
`resolver.lockfile-path` or `CARGO_RESOLVER_LOCKFILE_PATH` setting in those
files or the environment stops the opt-in, even if another setting shadows it.
Repositories that select another lockfile can keep their own locking and audit
checks.
Omitting `locked` or setting it to `"false"` preserves the existing commands.
Repository workflows own additional product checks and checks on other lockfiles.

## Markdown Inputs

Run `ci-markdown` from the checkout root on Linux. It discovers every tracked
`.md` and `.markdown` path, then applies the existing repository configuration,
including its exclusions. Missing, unreadable, non-file, or non-UTF-8 indexed
paths fail explicitly; sparse checkouts must contain every indexed Markdown file.
This input-integrity check runs before lint exclusions, so ignored paths must also
exist and be readable. Repository lint filtering applies after input admission.
Paths containing CR/LF, backslashes, glob escapes rewritten by the locked CLI
(including braces, pipes, `!(` and `@(`), or `+(` in a directory name are unsupported
and fail with a rename diagnostic. Ordinary spaces and supported literal glob
characters are passed without shell interpretation.

The Action owns the tool manifest and integrity-bearing dependency lock. It installs
into a fresh temporary directory, using npm user/environment configuration rather
than the consumer project's `.npmrc`; configure registry access at that scope.
The consumer's packages and lockfiles are not used or modified. Successful empty
inventories require no package installation. Git discovery has a 64 MiB capture
limit and fails explicitly on overflow.

## Elixir Profiles

`ci-elixir` supports:

- `full`: all cross-cutting/static checks plus the caller's tests;
- `static`: all cross-cutting/static checks once, without tests;
- `test`: locked setup plus one caller-owned test lane only.

Small applications use `full`. Fanned-out applications run one `static` job,
parallel `test` jobs, and one required `CI` fan-in.

Runtime versions come from committed `mise.toml` and `mise.lock`; workflow YAML
does not duplicate Elixir, OTP, Node, or npm versions.

## Elixir PostgreSQL Probe

The reusable `.github/workflows/ci-probe-elixir-postgres.yml` workflow delegates
diagnostic execution to the caller's `bin/ci-probe` adapter. Callers can set the
optional string input `postgres_initdb_args` to configure PostgreSQL
initialization. Its default is an empty string, which adds no initialization
arguments. The workflow forwards the value to the service's
`POSTGRES_INITDB_ARGS` environment variable; database sizing remains owned by
the caller.

## Dependency Proposals

For update timing and eligibility, see the [routine update policy](#req-012---normal-update-cooldown) and [security update policy](#req-013---immediate-security-updates).
For updater ownership, branch targets and the route from a security PR to production, see the [dependency and security flow](#dependency-and-security-flow).
To set up or verify a repository, follow the [operator checklist](docs/operator-checklist.md#dependency-proposal-enrollment).

## Active Shared Source And Recovery

Protected `.github/main` is the active shared source. Complete
exact-head source CI, coherent candidate and affected-consumer validation, and
authorized human review precede the protected merge. There is no recurring tag
promotion, source repin or post-merge acceptance gate. Push CI still reports
post-merge failures visibly.

The central workflow selects its defining workflow SHA once per job and uses
that exact checking checkout and its catalogs throughout. Its admission, product
and final plans must agree, including bootstrap. Later main movement does not
replace an already resolved source. Consumer head/base movement still refuses.

Legacy composite callers use the same canonical repository spelling and literal
`@main`. Reusable probes bind native defining-workflow identity and check out that
exact shared source into `probe-source`; its canonical guard runs before the
separate `consumer` checkout. A later main cannot supply a different probe helper. Retain each job's native Action acquisition SHA and outcome;
`github.action_ref`, a live main lookup or the consumer SHA is not execution
identity. Normal same-ref acquisition reuse is supported by inspected runner
source, but deployed runner/cache configuration, including optional symlink cache
behavior, remains to be qualified. A pinned/local candidate parent with nested
live `@main` calls cannot prove a coherent candidate. Central self-CI uses local
owner steps and direct shell checks; affected candidate wrappers require coherent
consumer validation before merge.

First-party dependency evidence resolves only the fixed protected-main ref, then
its immutable commit, tree and admitted Action blob. Reusable workflows have no
first-party missing-license exemption. Evidence records that source snapshot,
not an executed Action receipt. Unknown
dependency-record shapes fail closed; actual hosted main records need native
CI qualification. License, vulnerability and third-party immutable-reference
rules remain mandatory.

Recover with a checked corrective or revert pull request, exact-head human review
and a protected merge into main under REQ-024. Record the new exact source and affected outcomes;
retain prior execution evidence and historical tags. A whole-policy revert may
restore earlier catalog approvals, including withdrawn entries: disclose those
effects and use a forward fix when withdrawal must persist. No automated fallback,
force-write or tag rollback selects an active source.

Existing consumer callers need their own thin migration and target qualification.
This source does not establish all-repository migration, hosted enforcement or
product deployment. The initial required-workflow selector transition is one
separately authorized human operation, with complete expected-old comparison and
readback; future main merges require no recurring selector update.

## Security Boundary

- Root workflow permissions are read-only; write permissions are job-scoped.
- Unmigrated repositories retain authorized human CODEOWNERS validation for
  `.github/` and production controls, including whole-tree control-plane ownership.
  An explicitly qualified central team-review profile can provide its adopted
  protection without a duplicate CODEOWNERS file.
- Privileged workflows never check out or execute pull-request code.
- Agents receive no operator SSH key or personal credential.
- Direct deployment and release writes belong only to the scoped release
  identity and operator.
- Ambiguous identity, classification, checks, branch state, or SHA fails closed.
- The security identity is dedicated and isolated from general agent credentials;
  proposal retries adopt only exact verified state. It has no merge authority.

The durable policy is defined in [Intent](#intent), [Requirements](#requirements) and [Architecture](#architecture).

## Application development containers

The control-plane [container procedure](https://github.com/ForgingAlpha/control-plane/blob/main/system/runbooks/operate-local-containers.md)
owns the Compose convention and container responsibilities. Applications own their
product commands, tests and deployment configuration. Shared mandatory checks
remain shared-CI owned.
