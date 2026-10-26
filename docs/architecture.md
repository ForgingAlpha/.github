---
status: approved
tags:
  - org/alpha-apps
  - topic/github
---
# ForgingAlpha/.github - Architecture

## Control Plane

`.github` and `control-plane` are main-only control planes. Every change lands
through a pull request with required `CI` and authorized-human
approval of the exact current revision. Application repositories use
feature/worktree branches into protected `dev`; `main` is the deployed branch.

The shared policy action uses the runner-provisioned Python 3/PyYAML parser for
bounded YAML frontmatter, rejecting malformed syntax and duplicate keys. It
checks baseline presence and repository-specific status metadata. Only the exact
`ForgingAlpha/control-plane` origin follows canonical source rules without a
required status marker; its own CI validates canonical IDs and upstream digests.
These structural checks cannot establish approval or Currentness.

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
their approval cannot satisfy this boundary. An applicable authorized human
executes every PR merge, including dependency and security updates. Updater,
security and release Apps retain only scoped proposal, check, tag rollout and
deployment effects; they cannot merge or update persistent branches directly.

Shared technical checks are composite actions so the caller preserves a
stable required job named `CI`. Enrolled applications additionally require the
distinct central baseline workflow; an enrolled document-only bootstrap can
obtain its initial complete-profile `CI` centrally. Consumers call internal actions at
`ForgingAlpha/.github/actions/<action>@v1`. Self-CI uses local paths so a pull
request validates its proposed implementation.

Protected branches require the applicable human review, current-revision CI,
scanning and current-base checks. Repository settings disable auto-merge and
merge queues; automation receives no persistent-branch update bypass.
Approval does not schedule a merge. A human executes it under the owning
repository's protected procedure. Hosted settings, caller enrollment and
credentials are verified separately from this source contract.

### Organization-required baseline pilot

The target central entrypoint is `.github/workflows/org-baseline.yml` in this
repository, selected by a ForgingAlpha organization ruleset. The initial pilot
binds an exact human-merged `main` source SHA with successful push CI on that
merged revision, reverified as current `main` before initial activation, plus
explicit consumer repository/branch selectors. The same source requirements
apply to a new pilot revision. Existing rules remain in force. The workflow checks out the consumer
revision separately from its own trusted checking source and records both
identities; actual workflow-context values and GitHub App events require live
qualification. It uses read-only pull-request execution, not a privileged
pull-request-target path, and does not contain CodeQL initialization/analysis.
Its shared Actions and scripts resolve from that separate trusted checkout at
the same workflow-source SHA, using local paths within that checkout. It does
not combine a pinned pilot workflow with sibling Actions from moving `v1`.
Existing `@v1` callers and the protected channel remain unchanged.

The central source owns explicit pilot profiles and their human-review team
identity. A consumer cannot grant itself bootstrap or weaken its required
reviewers. The team-review profile reads fresh effective branch rules and
requires the enrolled team, complete-change coverage, required approval count
and stale-approval invalidation. Missing or partial evidence is a failure.
Team membership and eligibility remain an operator-qualified prerequisite, not
an inference from a team ID. Bypass-actor and complete protection qualification
also remain with the operator; effective-rule reads alone cannot prove them.
This profile can replace CODEOWNERS validation
only after its approved implementation and actual hosted protection are
qualified; other callers keep their existing checks.

Here CI enrollment means the centrally reviewed validation configuration for a
consumer, not an unattended-authority Repository Enrollment or an Operational
Profile. It grants no execution or merge authority and does not create a runtime
profile assignment. Definition-only baseline repair and an enrolled document-only
profile remain distinct; neither can substitute for the other's conditions.

Bootstrap accepts only declared document/configuration inputs and refuses
application content and executable lint configuration before invoking shared
validators. Structural metadata does not prove human approval or Currentness.
Product profiles retain their own builds, tests, manifests and exact runtime
inputs. Foundation integrity stays before any copied helper or adapter;
independent central execution alone cannot establish that ordering.
The shared-CI owner accounts for common-check invocation and profile configuration;
the product owner accounts for its build/test composition. Language-only
composition is eligible only while independently verified central enforcement
covers its common checks. Migrate by qualifying the central gate before removing
consumer common calls; restore those calls before removing that gate. Until this
joint invariant is verified, full composite defaults remain unchanged. A consumer
opt-out input or configuration cannot establish the invariant.

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
additional validation or leaves the affected rollout blocked. A missing consumer
manifest or changed file extension cannot select a less demanding profile.

A profile with every required pilot case verified and qualified shared dependencies may
progress independently of unrelated profiles. Cases include valid/invalid/repair,
App-created and already-open triggers, consumer skip/configuration/application-input
refusal and observed source restoration with valid-pass and invalid-block behavior.
Adding a repository or branch still requires explicit central enrollment and live
qualification of that target's identity, head/base, token access, check producers and
required protections. Reusable content evidence does not replace current-target CI or
review. The full declared profile runs against the complete proposed tree; this rule
introduces no changed-file test selector.

Every additional enrollment or migration identifies and qualifies its affected profiles
and shared behavior. Common-call retirement requires complete coverage for that affected
scope; whole-pilot completion requires all initial targets and cases. Product-specific
checks remain mandatory, and consumer common calls remain until the central gate's
coverage of those obligations is independently verified. Rust qualification remains
required wherever Rust behavior or shared enforcement affecting it is in scope; it is
not a blanket dependency of an otherwise independently qualified document profile.

Ruleset administration retains the existing operator-owned path under REQ-016
and the control-plane authority procedure. This amendment does not permit an
agent to save protection changes through a human browser session or to borrow
human credentials; browser consent alone does not establish that authority.
Any protected executor requires separate qualification before a settings write.

Activation requires the qualified merged source, that operator path and
observable target runs. Serialize activation and rollback against the captured
expected prior source and rule configuration; refuse stale or ambiguous state.
Retain immutable transition evidence binding prior/new source SHAs, rules,
successful source push CI and operator attribution. Pilot recovery accepts only
the previously qualified human-merged source with that original green-CI and
transition evidence, preserving the existing channel's source and recovery
guarantees without moving `v1`. After an initial qualified revision A, a
controlled human-merged and green revision B is selected and observed, then the pilot selector is restored
to A. Verify that A runs successfully on valid input and again blocks the known
invalid case; recording the selector or a failed, cancelled or skipped run does
not establish recovery. Record target/source SHAs, saved rules and runs;
an uncertain settings write requires readback before retry. Recover the captured
pre-pilot rule configuration if the new rule itself cannot execute, preserving
preexisting obligations. This pilot does not move `v1` or activate global scope.

Implementation and enrollment remain pending until independently qualified.
No workflow, profile, team membership, ruleset or operational capability is
created merely by adopting this architecture. Scheduled shared-CI activation
is a separate rollout change: retain normal dependency cooldowns and expedited
security eligibility, human source merges, exact-source qualification and
existing serialized release/rollback controls. No release hour is inferred.

## Current-Channel Rollout

`v1` is a mutable current channel. A trusted release gate observes successful
`CI` on a push to `.github/main`, verifies that the completed head is still the
remote `main` SHA, and then performs the serialized rollout below.

The version-coherent consumer gate, once enrolled, is mandatory before every
`v1` movement: every live consumer profile must resolve
the proposed top-level and sibling shared Actions from the same revision, never
mixing the candidate with the already-live `v1` implementation.

After those gates pass, the release enters a non-cancelling `v1-rollout`
concurrency group. It advances `v1` with a raw-ref expected-old lease, then
creates `v1-rollout-<UTC timestamp>-<short SHA>` and records the transition.
Mutable movement and immutable record creation are one atomic Git push, so a
failure changes neither ref; an existing completed record makes a retry a
no-op.

The rollout job alone receives `contents: write`. Validation remains read-only.
Tag rules permit only the release identity and operator.

Rollback is a protected manual workflow. It accepts only an existing immutable
`v1-rollout-*` tag, verifies historical successful `CI` and ancestry from
current `main`, serializes with normal rollout, moves mutable `v1` with a
raw-ref expected-old lease, and creates an immutable `v1-rollback-*` record in
the same atomic push.
Rollout stays disabled until the protected environment and release controls are
configured; rollback is exercised only between immutable `v1-rollout-*` records
created by this contract.

The rollout is intentionally fail-closed: if current `main` is red or stale,
`v1` stays at its last green SHA. Recovery is a newer reviewed green commit,
not an out-of-order release.

## Shared CI Profiles

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
low-or-higher vulnerabilities and licenses outside a centrally owned permissive
commercial-use SPDX allowlist, subject to the central artifact exception below.
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

The separate first-party evidence class is fixed in central code to
`ForgingAlpha/.github/actions/<action>@v1`; callers cannot select an owner,
repository, channel, or exception. The checker requires the dependency record
to match that family exactly, resolves the protected lightweight `v1` tag
directly to a commit, fetches that exact commit's tree once, rejects truncated
or malformed evidence, and requires exactly one blob at the named action path.
The fixed repository, channel, commit, and path prove first-party ownership and
released-source provenance. The API lookup does not independently re-prove the
governed release ceremony; it composes with the protected `v1` rollout. All
endpoints are constructed internally rather than taken from dependency data,
both first-party requests are cached per validation, and every identity, API,
schema, tree, or policy error fails closed.

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

Private organization repositories must have GitHub's dependency-review feature
and required Code Security entitlement enabled before adopting this gate.

Each policy surface has one canonical implementation and test entrypoint.
Workflows and tests invoke it directly.

Fanned-out workflows expose one `CI` fan-in that fails when any required job is
failed, cancelled, or skipped.

## Runtime And Cache Model

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

## Dependency And Security Flow

Normal updates and security remediation are separate, non-overlapping lanes.

Each consumer binds its sole normal-update owner and enrolls required gates,
callers, credentials and hosted protections before relying on them. The
ownership change must leave no overlapping updater or unmanaged interval.
Source definitions alone do not prove enrollment or live execution.

Required `CI` invokes `ci-update-ownership` with `.github/update-policy.json`,
the consumer Renovate and Dependabot configurations, and the actual default
branch. The policy declares its schema version, normal-update owner and base
branch. Consumers enrolled in centrally assigned runtimes also declare
`runtime_profile`; their separate runtime-profile gate requires the exact active
assignment and locked projection. Update ownership alone does not establish
runtime enrollment.

The organization Renovate preset lives in `.github`;
repository-local Renovate configuration extends it and selects the repository
class. Native managers own ordinary package manifests and locks, external
Actions, and active non-runtime image references. The preset excludes
`ForgingAlpha/.github` Actions so their internal `@v1` references remain owned
by the protected control-plane rollout instead of being pinned to one release
commit or proposed for a new major. The central runtime-profile
catalog owns governed runtime version declarations; constrained projection
automation owns the derived consumer mise declaration and lock. Narrow
annotated custom managers own irreducible version literals. Exact ranges and
digests remain pinned. Renovate vulnerability remediation is disabled.

Normal updates are evaluated daily. Patches, minors, and majors become eligible
after three, seven, and thirty days respectively. Renovate proposes a pull
request into protected code-repository `dev`; a human merges it after exact-head
`CI` and applicable approval. Root bot and platform auto-merge are explicitly
disabled. The central validator admits only the defined policy shapes, and
consumer configurations cannot override them. Main-only control-plane updates target
protected `main`; `.github` release remains independently gated by coherent
consumer validation before `v1` moves.

For enrolled repositories, repository-local Dependabot entries remain only to customize
security updates; normal version-update capacity is zero. The updater-coverage
gate requires a machine-readable Renovate sole-owner declaration per enrolled
repository. It also validates the applicable central preset and local coverage,
Dependabot configuration, annotated literals, and exactly one owner per
detected surface.

Security classification never depends on a Dependabot-triggered workflow having
access to an Actions secret. The unprivileged pull-request CI run is only a wake
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
agent launcher. A human performs the normal two-parent source merge after
classification, required checks and applicable approval. The unprivileged
preflight does not read vulnerability alerts and is not full classification.

Production remediation is a separate exact-patch projection, not a `dev` branch
promotion. A trusted projector re-proves the merged Dependabot source PR,
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
slug must match the projection pull-request bot actor. The source merge must
postdate classification and must not be attributed to a known bot or automation
account. That attribution does not prove human authorization; the protected
human merge procedure owns that decision. Labels,
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

Projection is serialized by repository and lockfile. There may be at most one
open production projection touching the root npm lock; a second candidate or
any other concurrent lock proposal fails closed rather than batching or
choosing an order. GitHub caps pull-request file enumeration at 3,000 entries,
so the proof compares the detailed pull request's changed-file count with the
complete paginated result and rejects the cap, a mismatch, or duplicates. The
composite action cannot supply workflow concurrency itself: enrollment must add
a non-cancelling caller group keyed by repository, target branch, and lock path.

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

Quality, CodeQL, current-base, deletion, non-fast-forward, and merge-shape rules
remain in no-bypass rulesets. Security and updater identities have no branch
merge or direct-push authority. Consumer enrollment must prove the exact
classification, projection, checks, caller serialization, credential boundary,
human merge and deployment chain. Source publication does not establish that
enrollment or change existing hosted settings and queued work.

Privileged jobs process trusted GitHub metadata only. They never check out,
execute, or consume artifacts from pull-request code.

Installed marketplace plugins remain outside repository dependency bots and
are owned by their official installer. Customized vendored external skills
record an upstream repository and revision so deterministic synchronization can
surface reviewable changes. First-party repository skills remain normal source
code rather than pretending to be external dependencies.

## External Dependencies And Scheduled Backstops

All external Actions use full commit SHAs with reviewed-version comments.
Downloaded tools use exact versions plus checksums, lock integrity, or reviewed
provenance. CI rejects floating refs.

A deployment integration remains active for update-ownership purposes while a
live release workflow or configuration references it. A maintained
update-surface inventory names every active integration and owner. Integrations
proven inactive are deleted rather than enrolled in Renovate. The
updater-coverage gate rejects new unmanaged version literals and stale
exceptions.

Advisory audits run daily against application `dev` and deployed `main`.
Turnkey retains one weekly Ubuntu sentinel for independent runner and timing
diversity; it is diagnostic and never a merge requirement.

## Operator Boundary

Agents prepare scoped repository changes, verification, and `/tmp` scripts.
The operator owns destructive pushes, organization rules, credential/App setup,
exact-revision approval, every PR merge, rollout activation, and rollback
execution. Updater, security and release automation retains only its separately
defined non-merge effects. No SSH or personal credentials are available to agents.

## Selected Container Foundation Source

Each consumer workflow runs the standalone `ci-foundation@v1` gate as a required
step, followed by its adapter in a success-dependent step. The action never
invokes the adapter. Enrollment qualification and human review of the protected
workflow establish that order before any copied helper runs. The released
action owns an approved fingerprint catalog and verifies the actual
checkout without importing or executing its copied code. Applications select one
payload at `tools/container-foundation/` (standard) or `.foundation/` (legacy
transition), with `foundation.lock` at the checkout root. The foundation owns
their `foundation-source-v1` export format and local import/update/migration
behavior. The verifier resolves the sole existing fixed payload leaf, rejects
dual or partial selections and linked targets or ancestors, and preserves
unrelated `tools/` content.

Each catalog record contains the fixed canonical foundation repository and
numeric ID, full human-merged source commit, payload tree, export format and
SHA256 of the exact exported lock bytes. The designated `github-operator`
acquires canonical source through its qualified scoped nonhuman access and
verifies identity, human delivery and required checks; no personal or operator
SSH credential is used. Independent derivation
reads committed Git blobs and executable modes and reproduces the exact lock
serialization; an exporter assertion or application-provided lock is insufficient.
The source and derivation evidence remain in private retained custody. Public
records contain identity, commit/tree, format, opaque fingerprints and optional
nonsecret supported-location metadata. The `payload_paths` field permits a nonempty,
unique subset of the two fixed locations for a qualified helper revision.
Records without this field permit only `.foundation`; schema version 1 accepts
no other record fields. Placement is outside upstream identity and lock
inventory. Consumer-provided metadata cannot grant source-layout eligibility.

A record becomes usable after the existing human-reviewed `.github` merge and
protected `v1` release. One record serves all consumers of that core revision.
The exact core source must first be human-merged and its canonical delivery
verified before the shared admission merge and release; application source
updates and layout migrations follow that release. A task-branch candidate
record does not authorize runtime use.
The catalog starts empty until an eligible core revision is available. Multiple
compatible approved versions can coexist. Record preparation emits a candidate;
it cannot grant source eligibility or modify the released catalog automatically.

The verifier authenticates the lock's exact bytes against its own catalog,
validates the supported strict schema and cross-checks repository, numeric ID,
commit, tree and format against the matched record, then compares actual paths,
regular-file bytes, sizes and Git executable modes. Unexpected entries, empty
directories, links, special files, path escapes, partial imports, malformed or
ambiguous metadata and unsupported formats fail with WHAT-WHY-HOW remediation
before candidate execution. A changed
payload and matching rewritten lock cannot redefine the trusted expected hash.
The caller cannot supply a catalog, source repository, URL, reference or policy
override. Ordinary checking uses Python's standard library and needs neither
private upstream credentials nor a source lookup.

Under REQ-011, this exact first-party pair has one narrow reviewed-import
management profile: the application integration owner prepares complete imports
through the foundation importer and its human-reviewed PR. The shared catalog
owner separately controls which source revisions may be selected. Renovate and
Dependabot do not independently rewrite the pair. The update-ownership action
delegates to the same canonical verifier whenever either member exists; the
standalone gate also refuses a wholly absent pair for enrolled consumers. Fixed
source identity, format, admitted revision and complete-pair checks bound this
profile mechanically; it is not a caller-selected general exception. Other
dependencies and images retain their existing update owners.

Each decision records the actual verifier and catalog content fingerprints and
action reference. Hosted evidence also retains the runner's resolved action
commit from its native action acquisition log; `v1` and the consumer workflow
SHA are not substitutes for that identity. Candidate self-CI establishes source
qualification, not protected release or operational consumer admission. Public
self-CI uses synthetic source/lock fixtures only; real private locks, inventories
and derivation receipts remain in qualified private custody.

Removing a record withdraws admission under the newly released policy. An
application cannot supply an older catalog as a fallback. Existing protected
whole-policy rollback can restore older approvals, including a record withdrawn
by a later policy; the authorized human reviews that exact rollback target.
Preserving a withdrawal requires a compatible target or a reviewed forward fix.
An application rollback still requires a complete approved pair and compatible
integration; it does not reverse schemas or data.

Source authenticity, approved selection, working-file integrity, application
compatibility and host/storage admission are separate observations. Applications
own integration and hosts own storage. This gate is not a hostile-process
sandbox and does not qualify NAS behavior or deploy services. Foundation
consumption guidance references this owner instead of copying its admission
policy. Signing, new CI credentials and automatic record admission are not part
of this mechanism.
