# Renovate Normal Dependency Automation Plan

## Overview

Adopt Renovate as ForgingAlpha's single owner for normal dependency, runtime,
tool, Action, and active image updates while retaining Dependabot exclusively
for GitHub-native security remediation. Preserve exact pins, reproducible locks,
three/seven/thirty-day cooldowns, exact-head CI, and exact-SHA security
promotion.

This is a change of normal-update ownership, not removal of Dependabot. It does
not change the application release model: normal changes integrate into
protected `dev`, while only re-proven security updates automatically continue
to deployed `main`.

## Definition Sources

- Intent: `docs/intent.md`
- Requirements: `docs/requirements.md`, especially REQ-009 through REQ-021
- Architecture: `docs/architecture.md`
- Operator bootstrap: `docs/operator-checklist.md`
- Glossary: `n/a - no new product vocabulary`
- Product or UI design: `n/a - repository automation control plane`

## Desired End State

- Every versioned input maps to exactly one update owner.
- Renovate creates every normal version-update pull request.
- Dependabot creates security-remediation pull requests only.
- Normal patch, minor, and major updates wait at least three, seven, and thirty
  days respectively.
- Eligible normal updates auto-merge into code-repository `dev` after complete
  exact-head CI.
- Main-only control-plane updates auto-merge only through their complete
  protected-main gates.
- Runtime changes regenerate exact locks safely before CI can pass.
- `.github` moves `v1` only after one coherent candidate passes every live
  consumer profile.
- Official plugin installers own installed marketplace artifacts; customized
  vendored external skills carry an upstream identity and revision.

## Scope

In scope:

- central Renovate configuration and validation;
- npm, Mix, nested pip requirements, GitHub Actions, mise, and active container
  dependencies;
- annotated custom managers for irreducible version literals;
- security-only Dependabot configuration;
- safe generated-lock refresh;
- updater coverage and overlap detection;
- code-repository, docs-control-plane, and shared-action-control-plane rollout;
- installed-plugin and vendored-upstream ownership inventory.

Out of scope:

- cloud-provider migration or deployment redesign;
- maintaining obsolete deployment integrations;
- changing the exact-SHA application release model;
- replacing GitHub's vulnerability-alert association;
- self-hosting Renovate unless the free hosted service proves insufficient;
- weakening CI so an update can merge.

## Phase 0 - Finish The Existing Release Foundation

1. Land the in-flight `.github` automation refactor with `V1_ROLLOUT_ENABLED`
   false.
2. Complete the protected rollback environment, tag rules, bootstrap record,
   and one operator-approved rollback exercise.
3. Perform the first exact-green-main `v1` rollout.
4. Merge each compatible consumer automation branch after its surfaced strict
   application findings are corrected.

Acceptance:

- rollback and rollout are proven before updater ownership changes;
- every participating application has protected `dev` as its default branch;
- required `CI` is active and the automation App has no CI bypass.

## Phase 1 - Normalize Version Sources

1. Inventory active and inactive integrations in a maintained update-surface
   record. Remove only integrations proven unreferenced by the current release
   path; if none qualify, record that explicitly.
2. Remove floating `latest` references.
3. Inventory every runtime tuple and duplicated runtime default, designate
   `.github` as the target profile authority, and keep each repository's exact
   `mise.toml`/`mise.lock` as the enforced source until the coherent runtime
   cutover in Phase 5.
4. Move command-line tools into exact manifests or a single integrity-bearing
   catalog when practical.
5. Single-source versions that are currently duplicated between implementation
   and tests.
6. Add explicit Renovate annotations only for irreducible literals.
7. Record upstream identity and revision for customized vendored external
   skills; inventory installed marketplace plugins by installer.

Acceptance:

- every remaining version literal has one authoritative declaration;
- every participating repository's current runtime tuple and intended profile
  assignment are inventoried, and any temporary deviation records a reason,
  owner, and expiration;
- no test asserts a separately copied version string;
- the inventory names every active integration and owner, explicitly records
  when no other inactive integration exists, and gives inactive integrations no
  update exception.

## Phase 2 - Replace The Coverage Contract

Replace `ci-dependabot-coverage` with updater-neutral coverage that:

1. reads a machine-verifiable `normal-update-owner` mode of `dependabot` or
   `renovate` for each repository during migration;
2. detects every supported manifest, lock, nested Action, runtime declaration,
   active image, and annotated literal;
3. in `dependabot` mode, validates complete normal-update Dependabot coverage
   and the absence of active Renovate ownership;
4. in `renovate` mode, validates the shared preset with the official validator,
   verifies local configuration extends it, verifies Dependabot is
   security-only, and rejects Renovate vulnerability remediation;
5. rejects overlapping, missing, or mode-inconsistent ownership;
6. permits a mode change only when the proposed head completely satisfies the
   destination mode;
7. rejects floating external refs and unannotated version literals;
8. permits internal `@v1` only through the reviewed allowlist.

Acceptance:

- seeded missing, overlapping, and unmanaged examples fail with WHAT-WHY-HOW
  output;
- every current repository passes in its declared mode before any bot cutover;
- final-state organization validation rejects `dependabot` normal-update mode.

## Phase 3 - Establish The Organization Renovate Preset

Create a versioned preset in `.github` with:

- exact ranges and digest pinning;
- `minimumReleaseAge` of three, seven, and thirty days for patch, minor, and
  major updates;
- strict internal stability checks;
- pull-request auto-merge only after required status checks;
- automatic rebasing of stale update branches;
- the lock-writer's unique Git author in `gitIgnoredAuthors` so Renovate can
  continue managing safely generated lock commits;
- dependency dashboard and bounded grouping;
- majors kept separate from patches and minors;
- Renovate vulnerability remediation disabled;
- native managers for actual supported ecosystems;
- narrowly documented custom managers.

Each repository adds a thin configuration extending the preset. Code
repositories target `dev`; `.github` and `alphaapps-docs` target `main`. The
initial site canary may add a catalog assignment and required exact-projection
validator in read-only mode while direct Renovate mise updates and generic lock
maintenance remain disabled. Repository mise locks remain the executable source,
and the canary gate proves that source is the exact assigned tuple. Automated
runtime updates still require the resolver, writer, canary, and rollout gate in
Phase 5; the read-only catalog must not be described as that complete authority.

Acceptance:

- configuration validation passes centrally and in every repository;
- after the transition-capable coverage gate and preset pass, the operator
  installs the hosted App on the canary in silent lookup mode;
- hosted dry-run logs report the intended managers, base branch, cooldown, and
  ownership without creating branches or pull requests.

## Phase 4 - Prepare Dependabot Security-Only Mode

For every detected security-supported ecosystem:

1. define the repository Dependabot configuration needed to customize security
   pull requests after cutover;
2. set normal version-update pull-request capacity to zero in the destination
   mode;
3. retain GitHub Dependabot alerts and security updates;
4. retain official alert lookup and alert-to-pull-request verification;
5. retain exact-head merge, post-merge re-proof, and exact-SHA promotion;
6. prohibit normal Dependabot version-update ownership in required CI.

Acceptance:

- coverage fixtures prove Dependabot can create security PRs but not normal
  version PRs in `renovate` mode;
- Renovate cannot classify a pull request for automatic security promotion;
- the existing security path fails closed on missing alert association.

## Phase 5 - Automate Safe Lock Refresh

For centrally governed runtime changes:

1. extend the proven read-only `.github` profile catalog and assignments with
   the resolver, constrained writer, and fan-out machinery, then accept
   version-tuple changes only through that central profile;
2. create synchronized pull requests for every assigned consumer;
3. trigger consumer lock refresh only for an allowlisted update pull request
   projecting that exact approved profile tuple;
4. run the exact trusted mise version without write credentials and in safe
   mode;
5. emit the proposed lock as an artifact;
6. have a separate writer verify actor, assigned profile, exact head,
   source-version change, and allowlisted output paths;
7. reject unrelated lock changes;
8. commit only expected source and lock artifacts;
9. configure Renovate to ignore only the unique writer Git author;
10. rerun the resolver idempotently after every update rebase and run full
   locked-mode CI on the new exact head.

Acceptance:

- one central runtime-profile update completes end-to-end into a protected
  canary `dev` and exposes the rollout state of every assigned repository;
- the same runtime update survives one forced Renovate rebase, regenerates the
  expected lock, and remains managed;
- malicious configuration, changed head, unexpected path, or incomplete lock
  fails closed.

## Phase 6 - Complete Control-Plane Gates

For `alphaapps-docs`:

- cover the root npm lock and every active nested Python skill environment;
- pin CI-only Python and Markdown dependencies;
- smoke-test every environment changed by an update.

For `.github`:

- make candidate shared Actions version-coherent;
- exercise every live Elixir, Astro, TypeScript, shell, and other consumer
  profile against the same candidate revision;
- require candidate success before `v1` movement;
- retain serialized immutable rollout records and protected rollback.

Acceptance:

- a deliberately incoherent candidate fails before `v1` moves;
- a failed control-plane update cannot affect consumers;
- rollback restores an immutable previously green rollout.

## Phase 7 - Progressive Automation Rollout

1. On one site canary, atomically flip `normal-update-owner` from `dependabot`
   to `renovate`, activate the already-installed hosted App, and merge the
   security-only Dependabot configuration in the same protected change.
2. Enable patch auto-merge on the canary only.
3. Prove one patch, one minor, one major, and one locked runtime update.
4. Expand with the same audited per-repository mode flip; never disable one
   normal updater before the other is configured and validated.
5. Enable control-plane patch automation after complete local gates.
6. Enable control-plane minor and major automation only after Phase 6 passes.
7. Retain a narrow reviewed carve-out for major changes to privileged
   token-minting or security-classification Actions unless an equivalent
   compatibility and security proof is added.

Acceptance:

- normal updates follow the same cooldown and merge path in every repository;
- security updates continue independently when normal-update automation is
  unavailable;
- no normal update automatically promotes from code-repository `dev` to
  `main`.

## Phase 8 - Operate And Reverify

- Run daily update and advisory health checks.
- Keep the weekly alternate-runner sentinel diagnostic and non-required.
- Alert when either updater is paused, configuration validation fails, a lock
  refresh stalls, or an installed plugin lacks a current-version inventory.
- Review and expire exceptions; unused integrations are removed instead of
  permanently allowlisted.
- Re-run seeded coverage and version-coherence failures after material updater
  or shared-release changes.

## Go/No-Go Gates

- No-go on Renovate PR creation until Phases 0 through 3 pass.
- No-go on each repository's Dependabot cutover until updater-neutral coverage
  proves that repository's complete destination mode on the exact proposed
  head.
- No-go on mise management until lock refresh is proven on a canary.
- No-go on code-repository auto-merge until protected `dev` requires exact-head
  `CI` without bot bypass.
- No-go on control-plane minor or major auto-merge until complete local gates
  pass.
- No-go on `v1` movement until version-coherent consumer profiles and protected
  rollback pass.

## Operator-Owned Actions

Agents may prepare repository changes, tests, configuration, and `/tmp`
operator scripts. The operator owns:

- installing and authorizing the Renovate GitHub App;
- changing default branches and organization rulesets;
- enabling organization Dependabot alerts and security updates;
- configuring App credentials and protected environments;
- destructive pushes, bot cutover, rollout enablement, and rollback execution.
