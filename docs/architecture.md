---
status: approved
tags:
  - org/alpha-apps
  - topic/github
---
# ForgingAlpha/.github - Architecture

## Control Plane

`.github` and `alphaapps-docs` are main-only control planes. Every change lands
through a pull request with required `CI` and authorized-human code-owner
approval of the exact current revision. Application repositories use
feature/worktree branches into protected `dev`; `main` is the deployed branch.

The shared policy action validates `.github/CODEOWNERS` before lower-level
language checks. Control-plane repositories assign their complete tree to an
authorized human. Consumer repositories assign `.github/` and each detected
production-control file or directory to an authorized human in the final
active CODEOWNERS block, preserving GitHub's last-match semantics. Repository
rules require code-owner review and invalidate stale approvals. Agents and the
general-purpose authoring identity may create and update pull requests, but
their approval cannot satisfy this boundary and they cannot merge
trust-surface or control-plane changes. Separately scoped updater, security,
and release Apps retain only their governed exact-revision update, merge,
promotion, rollout, and rollback authority; they cannot substitute for human
approval of a trust-surface or control-plane change.

Shared merge-authority checks are composite actions so the caller preserves a
single required job named `CI`. Consumers call internal actions at
`ForgingAlpha/.github/actions/<action>@v1`. Self-CI uses local paths so a pull
request validates its proposed implementation.

Routine approval activation uses a repository-owned `workflow_run` job. The
local job statically owns the default-branch-only `release-automation`
environment and invokes the centrally versioned `approved-automerge@v1`
composite. The composite resolves one exact open revision before minting the
short-lived release App token. It validates GitHub's workflow-run pull-request
pointer against the live open same-repository pull request and exact signal
head; when GitHub supplies no pointer, it requires a unique live commit
association instead. Neither pointer is authorization. The composite then
revalidates the current human approval and head before calling GitHub's
synchronous REST pull-request merge endpoint as that App, with the approved
head SHA and governed merge method in the request.
An update-only ruleset authorizes the release App to update the persistent
branch through pull requests only, while independent protection rulesets give
it no bypass from review, code-owner, latest-push, thread, CI, CodeQL, or
current-base requirements. The merge uses neither deferred auto-merge nor an
administrative bypass and fails closed if any protection changes before GitHub
atomically updates the ref.
Privileged activation never checks out or executes pull-request code, and
environment credentials never traverse a called reusable-workflow boundary.

## Current-Channel Rollout

`v1` is a mutable current channel. A trusted release gate observes successful
`CI` on a push to `.github/main`, verifies that the completed head is still the
remote `main` SHA, and then performs the serialized rollout below. Initial
rollouts use this same exact-green-current-main gate; there is no exception for
the implementation that previously occupied `v1`.

Phase 6 adds a version-coherent candidate gate before rollout. Once active, it
is mandatory for every `v1` movement: every live consumer profile must resolve
the proposed top-level and sibling shared Actions from the same revision, never
mixing the candidate with the already-live `v1` implementation.

After those gates pass, the release enters a non-cancelling `v1-rollout`
concurrency group. It advances `v1` with a raw-ref expected-old lease, then
creates `v1-rollout-<UTC timestamp>-<short SHA>` and records the transition.
Mutable movement and immutable record creation are one atomic Git push, so a
failure changes neither ref; an existing completed record makes a retry a
no-op.

The rollout job alone receives `contents: write`. Validation remains read-only.
Tag rules permit only the release identity and operator. The obsolete semver
writer is removed before the replacement first moves `v1`.

Rollback is a protected manual workflow. It accepts only an existing immutable
`v1-rollout-*` tag, verifies historical successful `CI` and ancestry from
current `main`, serializes with normal rollout, moves mutable `v1` with a
raw-ref expected-old lease, and creates an immutable `v1-rollback-*` record in
the same atomic push.
The pre-policy implementation is not an eligible rollback target. Rollout stays
disabled until the protected environment and release controls are configured;
rollback is exercised only between immutable `v1-rollout-*` records created by
this contract.

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
commercial-use SPDX allowlist. A following fail-closed check inspects the
official dependency-change output. Recognized licenses need no additional
network lookup. Null or empty third-party licenses still fail except for GitHub
Actions whose package URL names an exact 40-character commit SHA and whose
canonical GitHub source identity matches that package URL. For only that
constrained case, the checker constructs GitHub's repository-license API
endpoint itself, queries the license at the exact immutable SHA with the
caller's read-only GitHub token, and accepts only an SPDX identifier from the
same central allowlist. External lookups have a fixed timeout, are deduplicated,
and are capped at 20 unique revisions per pull request.

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
Package-specific license exceptions require a reviewed control-plane policy
change rather than a consumer input.
Private organization repositories must have GitHub's dependency-review feature
and required Code Security entitlement enabled before adopting this gate.

Each policy surface has one canonical implementation and test entrypoint.
Workflows and tests invoke it directly; obsolete compatibility wrappers are not
published alongside the current contract.

Fanned-out workflows expose one `CI` fan-in that fails when any required job is
failed, cancelled, or skipped.

## Runtime And Cache Model

Current enforcement is transitional: each consumer repository's exact
`mise.toml` and integrity-bearing `mise.lock` are the executable source used by
local development and CI, and runtime changes require a governed exact-head
repository pull request. The control plane now contains the initial
machine-readable catalog, assignment validator, and exact-projection gate for a
single Node site canary. That assignment becomes authoritative only when the
released gate is required by the assigned consumer. Other repositories remain
under their existing exact-lock authority until explicitly enrolled.

The Renovate plan's runtime phase establishes the target model through bounded,
fail-closed enrollment. `.github` owns a versioned, machine-verifiable profile catalog with
approved compatible tuples, repository assignments, integrity requirements,
rollout state, and exact time-bounded exceptions. Each consumer will continue
to commit `mise.toml` and `mise.lock` as the reproducible local projection of
its assignment. Shared CI will validate that projection before installing only
locked bytes; workflow YAML will not duplicate language runtime versions.

Normal runtime changes will originate in the central profile and produce exact
consumer projections through constrained automation. The initial canary is
read-only: direct Renovate mise updates and generic lock maintenance are
disabled, and the gate only proves an already-committed projection. A profile
may not claim automated-update status until its resolver, constrained writer,
consumer canary, and rollout gate are all proven. Publishing a catalog as an
unenforced organization-wide update authority remains prohibited.

Runtime, dependency/build, and Dialyzer caches are keyed by operating system,
architecture, exact resolved runtimes, dependency locks, and relevant build
inputs. Cache design is validated on both cold and warm Blacksmith runs and may
not restore artifacts across incompatible OTP/Elixir combinations.

## Dependency And Security Flow

Normal updates and security remediation are separate, non-overlapping lanes.

The source Dependabot classification capability described below is partially
implemented; its stronger source-base and complete-GHSA attestation plus the
production projection and activation path remain target state. The Renovate
ownership, lock-refresh, consumer-profile, and
updater-coverage portions are target state implemented in Phases 2 through 7 of
`docs/plans/renovate-normal-dependency-automation.md`. Until each repository's
audited cutover, its declared normal-update owner remains Dependabot; the
repository never has two owners or a bot-less interval.

The organization Renovate preset now lives in `.github`;
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
after three, seven, and thirty days respectively, then auto-merge through a
pull request into protected code-repository `dev` only after exact-head `CI`.
They do not auto-promote to `main`. Main-only control-plane updates target
protected `main`; `.github` release remains independently gated by coherent
consumer validation before `v1` moves.

For enrolled repositories, repository-local Dependabot entries remain only to customize
security updates; normal version-update capacity is zero. During migration, the
updater-coverage gate validates a machine-readable sole-owner mode per
repository. It also validates the applicable central preset and local coverage,
Dependabot configuration, annotated literals, and exactly one owner per
detected surface.

Security classification uses the SHA-pinned official Dependabot metadata Action
with alert lookup plus GitHub's alert-to-pull-request association. Grouped PRs
bind every associated GHSA. A trusted default-branch workflow validates actor,
base, allowed dependency paths, maintainer-change state, and exact head. Every
synchronization first clears stale auto-merge and routing state. The automation
App records an exact-head classification and GitHub merges the security revision
into protected `dev` only after required CI.

Production remediation is a separate exact-patch projection, not a `dev` branch
promotion. A trusted projector re-proves the merged Dependabot source PR,
classification App and merge identity, exact source base and head, and complete
OPEN or FIXED GHSA set. It accepts only the enrolled repository profile's
dependency manifest and lock paths. The authoritative source base is the first
parent of the recorded security merge and must equal the base bound by source
classification. The initial site profile accepts only a one-parent squash merge
whose tree equals the classified source head. Later unrelated movement of `dev`
does not invalidate that immutable source chain.

For the initial root npm profile, current `main` must still contain the exact
source pre-fix blob and mode for both `package.json` and `package-lock.json`,
even when only the lock changed. Starting from the exact current `main` commit,
the projector uses GitHub's Git Data API to replace only source-changed entries
with the source post-fix blobs and modes. It performs no checkout, three-way
merge, cherry-pick, conflict resolution, or lock regeneration.

The no-bypass projection writer creates one same-repository branch and pull
request and records provenance bound to the repository, source PR, source base
and head, `dev` merge, production base, complete GHSA set, projected head, and
resulting tree. Labels, titles, bodies, and branch names are routing hints only.
Any divergent preimage, unsupported file type, extra path, ambiguous API result,
concurrent lock change, or moved base stops or rebuilds the projection from the
new production base after the same exact checks.

Projection is serialized by repository and lockfile. There may be at most one
open production projection touching the root npm lock; a second candidate or
any other concurrent lock proposal fails closed rather than batching or
choosing an order.

Normal pull-request CI and CodeQL then execute for the exact projected head in
the current `main` context with no privileged credential. GitHub also exposes a
live synthetic test merge for that exact head and base. A protected default-branch workflow
first mints the no-bypass automation App token narrowed to metadata,
pull-request, check, content, Actions, and vulnerability-alert read access. It
uses that read-only token to independently reconstruct the expected tree,
re-prove the full source and advisory chain; verify the exact CI workflow path,
run, repository, pull-request pointer, projected head, conclusion, and CodeQL
provenance; and independently require the live test merge to have the attested
production base and projected head as its parents and the expected projected tree.
Only then may it enter the branch-restricted security environment,
mint the dedicated merge-only security activation token, and request GitHub's
synchronous pull-request merge with the exact projected head SHA.

Immediately after GitHub updates `main`, the activator verifies the returned
merge SHA, current ref, parentage, and tree. The ordinary push-triggered
deployment binds itself to and reports that exact merge revision; it may begin
concurrently with the activator's postcondition and is not represented as being
gated by it.

Quality, CodeQL, current-base, deletion, non-fast-forward, and merge-shape rules
remain in no-bypass rulesets. Human review is a separate rule with
pull-request-only bypass for the security activator, and UPDATE authority is a
separate pull-request-only rule. The projector has no bypass. No identity can
directly push a persistent branch through this flow.

Current migration status: Dependabot security classification and protected
`dev` integration exist. Exact production projection and unattended activation
are not yet active. `alphaapps-site` is the first observation-mode canary;
unattended authority follows only after its exact projection, checks, rulesets,
credential boundary, merge, and production deployment are proven. The legacy
whole-branch reusable promotion workflow remains only for existing callers
pending separate migration and is not security authority for new enrollments.

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
exact-revision trust-surface approval, trust-surface and control-plane merges,
rollout activation, and rollback execution. Governed updater, security, and
release automation retains only its separately defined persistent-branch and
release authority. No SSH or personal credentials are available to agents.
