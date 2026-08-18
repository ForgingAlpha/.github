# Dependabot Auto-Approve And Auto-Merge Org Rollout Implementation Plan

## Overview

Implement ALP-25 by making Dependabot patch/minor PRs able to auto-approve and
enable auto-merge safely across active ForgingAlpha repositories, while leaving
required branch checks as merge authority and leaving major updates manual.

This is control-plane work in `ForgingAlpha/.github`: first make the policy
durable in `.github` source truth, then update the shared composite action and
consumer contract, release it deliberately, and roll the standardized caller out
to active repos.

## Definition Sources

- Intent: `docs/intent.md` - approved. `.github` owns public shared GitHub
  automation, Dependabot automation, workflow templates, release mechanics, and
  cross-repo workflow policy (`docs/intent.md:11`, `docs/intent.md:14`).
- Requirements: `docs/requirements.md` - approved. Existing requirements cover
  shared automation, released-tag consumption, CI merge authority, deterministic
  enforcement, self-validation before release, and Dependabot coverage
  (`docs/requirements.md:35`, `docs/requirements.md:79`,
  `docs/requirements.md:116`, `docs/requirements.md:160`,
  `docs/requirements.md:176`, `docs/requirements.md:185`).
- Glossary: `n/a - no repo-local glossary exists and this plan does not add
  product-domain vocabulary`.
- Architecture: `docs/architecture.md` - approved. Composite actions are the
  default shared surface; Dependabot configuration remains repo-local; `.github`
  owns Dependabot templates, examples, validation, and the shared auto-merge
  helper; `v1` is the consumer rollout boundary (`docs/architecture.md:21`,
  `docs/architecture.md:106`, `docs/architecture.md:124`).
- ADRs: `n/a - no existing ADR governs this narrow Dependabot automation
  decision`.
- Design: `n/a - no user workflow or UI design artifact applies`.
- Stories: `n/a - ALP-25 is a control-plane improvement, not a product story`.

## Backlog Inputs

- Linear issue: `ALP-25` -
  `https://linear.app/alpha-apps/issue/ALP-25/roll-out-dependabot-auto-approve-and-auto-merge`
- Other backlog/historical input: live GitHub API inventory gathered on
  2026-07-04 for active, non-archived ForgingAlpha repos.

Backlog inputs are non-authoritative. Current-state claims from these inputs
were verified against live source truth, code, tests, conventions, runbooks,
official GitHub documentation, and live GitHub API state before this plan was
written.

## Current State Analysis

- `.github` already has a shared composite action at
  `actions/dependabot-automerge/action.yml`. It fetches Dependabot metadata,
  gates patch/minor/major update types, validates merge method, and runs
  `gh pr merge --auto` (`actions/dependabot-automerge/action.yml:26`,
  `actions/dependabot-automerge/action.yml:32`,
  `actions/dependabot-automerge/action.yml:63`,
  `actions/dependabot-automerge/action.yml:82`).
- The shared action has no `auto_approve` input and no `gh pr review --approve`
  step today (`actions/dependabot-automerge/action.yml:3`).
- `.github` has a thin repo-owned caller workflow that runs only on Dependabot
  PRs and grants write permissions only on the Dependabot job
  (`.github/workflows/dependabot-automerge.yml:3`,
  `.github/workflows/dependabot-automerge.yml:18`,
  `.github/workflows/dependabot-automerge.yml:21`).
- README documents weekly Tuesday Dependabot cadence, grouped ecosystem
  updates, patch/minor auto-merge, major manual review, and a single direct
  composite-action caller example (`README.md:393`, `README.md:407`).
- Self CI validates GitHub Actions safety, Dependabot coverage, shell syntax,
  and unit test suites before release tags move (`.github/workflows/ci.yml:36`,
  `.github/workflows/ci.yml:39`, `.github/workflows/ci.yml:42`,
  `.github/workflows/ci.yml:81`).
- Existing README contract tests parse workflow YAML examples so copied
  examples stay syntactically valid (`tests/test_shared_ci_contract.py:334`).

Live org inventory on 2026-07-04:

| Repo | Default | Auto-merge setting | Required checks on target | Dependabot config | Auto-merge caller |
| --- | --- | --- | --- | --- | --- |
| `.github` | `main` | enabled | verify before opt-in | present | direct composite |
| `alphaapps-docs` | `main` | enabled | verify before opt-in | present | direct composite |
| `alphaapps-composer` | `dev` | enabled | verify before opt-in | present | direct composite |
| `analyzingalpha-vault` | `dev` | enabled | verify before opt-in | present | direct composite |
| `whosyouragent-app` | `dev` | enabled | verify before opt-in | present | direct composite |
| `alphaapps-site` | `dev` | enabled | verify before opt-in | present | missing reusable workflow path |
| `analyzingalpha-engine` | `dev` | enabled | verify before opt-in | present | missing reusable workflow path |
| `analyzingalpha-site` | `dev` | enabled | verify before opt-in | present | missing reusable workflow path |
| `turnkeyleads-site` | `dev` | enabled | verify before opt-in | present | missing reusable workflow path |
| `turnkeyleads-app` | `dev` | enabled | verify before opt-in | missing | missing |
| `alphaapps-outliers` | `dev` | disabled | verify before opt-in | missing | missing |
| `alphaapps-adr-pipeline` | `dev` | disabled | verify before opt-in | missing | missing |

The reusable caller path
`ForgingAlpha/.github/.github/workflows/dependabot-automerge-reusable.yml@v1`
returned `404` at both `.github@main` and `.github@v1`. The rollout therefore
must standardize consumers onto the direct composite-action caller; adding
auto-approval alone would leave four active repos pointing at a nonexistent
surface.

## Desired End State

- `.github` source truth explicitly describes the Dependabot auto-approve and
  auto-merge standard for patch/minor updates, the major-update manual boundary,
  the required-check gate, and the explicit opt-in requirement.
- `actions/dependabot-automerge` supports `auto_approve`, defaulting to
  `"false"` for backward compatibility, and only approves PRs after the
  existing Dependabot/update-type eligibility check passes.
- Consumers opt into auto-approval explicitly in their thin caller workflow.
- The action still uses `pull_request`, not `pull_request_target`; workflow
  permissions stay root read-only and job-scoped write-only.
- Code repos target `dev` and use `merge_method: squash`; control-plane repos
  target `main` and use `merge_method: merge`.
- Required branch checks and GitHub auto-merge remain the merge gate. The
  workflow may approve and enable auto-merge; it must not bypass required
  reviews, required status checks, branch protection, or merge queue policy.
- Every repo that opts into `auto_approve: "true"` has required checks or an
  equivalent ruleset on the Dependabot target branch. Repos without that gate
  stop for operator decision before opt-in.
- Active repos have Dependabot coverage for detected dependency surfaces or an
  explicit unmanaged-surface comment accepted by the coverage validator.
- Active repos use direct composite-action callers. The missing reusable
  workflow caller path is removed from all consumers.

### Key Discoveries

- GitHub's Dependabot automation docs show the supported pattern of using
  `dependabot/fetch-metadata`, `gh pr review --approve`, and
  `gh pr merge --auto`, and explicitly recommend required status checks for
  Dependabot target branches:
  `https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/automate-dependabot-with-actions`
- GitHub auto-merge merges only after required reviews and required status
  checks are satisfied, and repository auto-merge must be enabled:
  `https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request`
- GitHub Actions security guidance says `GITHUB_TOKEN` should have minimum
  required permissions and job-level elevation is preferred:
  `https://docs.github.com/en/actions/reference/security/secure-use`
- OpenSSF flags "workflows allowed to approve pull requests" as a security
  concern. This rollout is therefore a documented exception for Dependabot
  patch/minor PRs only; the usage is narrow, but the GitHub setting grants
  approval capability to any workflow with `pull-requests: write` in scope:
  `https://best.openssf.org/SCM-BestPractices/github/actions/actions_can_approve_pull_requests.html`

## Plan Decision Records

Plan Decision Records are plan-local execution evidence. They are not ADRs,
product source truth, or operator approval of intent, requirements, glossary, or
architecture.

### PDR-001: Standard Consumer Surface

- **Status:** accepted
- **Decision class:** architecture, integration
- **Evidence tier:** full
- **Reversibility:** moderate
- **Blast radius:** broad
- **Force-full overrides checked:** external lock-in, security/authz,
  agent-authority, broad GitHub/CI blast radius
- **Touched surfaces:** git/github/CI/worktree, external-system/API/vendor,
  tests/fixtures, docs/lifecycle
- **Governing sources checked:**
  - `docs/intent.md` applies - shared Dependabot automation is an owned surface.
  - `docs/requirements.md` applies - required CI released refs and deterministic
    self-validation govern consumers.
  - `docs/architecture.md` applies - composite actions are the default shared
    surface and consumers own workflow triggers/permissions.
  - `notes/Alpha Apps Git and GitHub Process.md` applies - code repos route
    through `dev`, control-plane repos route through `main`.
  - `system/runbooks/GitHub Actions CI Diagnostics.md` applies by contrast -
    diagnostic probes may use `@main`; required automation stays on release
    tags.
- **Proof modes:** research, architecture-check, external-smoke
- **Decision:** Standardize on direct composite-action callers using
  `ForgingAlpha/.github/actions/dependabot-automerge@v1`; do not add a reusable
  workflow as the canonical Dependabot auto-merge surface.
- **Objective function:** keep the consumer workflow thin, released,
  repo-owned, permissions-explicit, and aligned with `.github` architecture.
- **Candidate solution classes:**
  - **Baseline/default:** Keep current mixed state: some direct callers, some
    missing setup, and some reusable-workflow callers.
  - **Alternative A:** Add the missing reusable workflow and standardize on
    `jobs.<job>.uses`.
  - **Alternative B:** Standardize all active repos on the existing composite
    action with explicit inputs.
- **Fit analysis:** Alternative B matches the approved architecture:
  composite actions are the default shared surface and consuming workflows own
  triggers, permissions, and merge method. It also fixes the live `404` reusable
  path without creating a second public automation surface.
- **Why not the tempting safe option:** Leaving mixed callers in place is
  smaller but preserves broken consumers and makes future `.github@v1` releases
  harder to reason about.
- **Evidence ledger:**
  - `docs/architecture.md:23` says composite actions are the default surface.
  - `docs/architecture.md:30` says consuming workflows own triggers and
    permissions.
  - Live GitHub API returned `404` for the reusable workflow path at both
    `main` and `v1`.
- **Evidence safety:** Persist only command summaries, repo names, refs, and
  HTTP status classifications. Do not persist tokens, full API payloads, or raw
  private repo response bodies.
- **Proof obligations:** update README/examples and tests so the standard caller
  is direct composite usage; verify all consumers no longer reference the
  nonexistent reusable workflow path.
- **Operator-owned judgment:** none remaining; user already chose org-wide
  standardization.
- **Supersedes:** n/a

### PDR-002: Auto-Approval Authority

- **Status:** accepted
- **Decision class:** security, agent-authority
- **Evidence tier:** full
- **Reversibility:** hard
- **Blast radius:** broad
- **Force-full overrides checked:** security/privacy/authz, credential
  handling, agent authority, external-system behavior
- **Touched surfaces:** security/privacy/authz, git/github/CI/worktree,
  external-system/API/vendor, evidence/audit, tests/fixtures
- **Governing sources checked:**
  - `system/conventions/Security Service Principal and Workload Identity.md`
    applies by principle - `dependabot[bot]` and `github-actions[bot]` are
    non-human actors with bounded purpose.
  - `system/conventions/Security Tool Authorization.md` applies by analogy -
    approving and enabling auto-merge are side-effecting tool actions.
  - `system/conventions/Security Evidence and Audit Safety.md` applies -
    durable evidence must be refs/digests/classification, not raw tokens or API
    payloads.
  - GitHub Actions security docs apply - grant `GITHUB_TOKEN` only minimum
    required job permissions.
  - OpenSSF SCM best practices apply - automated PR approval is risky unless it
    is explicitly constrained and audited.
- **Proof modes:** research, external-smoke, architecture-check,
  operator-judgment
- **Decision:** Add `auto_approve` input defaulting to `"false"`; when consumers
  set it to `"true"`, the action auto-approves only eligible Dependabot
  patch/minor PRs using the caller-provided `GITHUB_TOKEN`. The org/repo
  setting that permits GitHub Actions to approve PRs must be treated honestly:
  it grants approval capability to any workflow with `pull-requests: write` in
  that scope, while this plan constrains only our intended usage.
- **Objective function:** allow no-human patch/minor dependency flow without
  creating a broad PAT/GitHub App credential, bypassing branch rules, or
  surprising existing `@v1` consumers.
- **Candidate solution classes:**
  - **Baseline/default:** Auto-merge only, with any required review still manual.
  - **Alternative A:** Auto-approve with `GITHUB_TOKEN` through an explicit
    opt-in input.
  - **Alternative B:** Auto-approve with a dedicated PAT or GitHub App token.
- **Fit analysis:** Alternative A is least-privilege for the current goal. It
  uses GitHub's documented automation path, stays job-scoped, and preserves
  branch protection as the authority. The compensating controls are root
  read-only workflow permissions, job-scoped `pull-requests: write`, no
  `pull_request_target`, required target-branch checks, Dependabot-only guards,
  and default-off consumer opt-in. Alternative B is reserved only if live rules
  prove `GITHUB_TOKEN` cannot satisfy the configured approval gate.
- **Why not the tempting safe option:** Auto-merge-only is safer but fails
  ALP-25 whenever branch rules require an approval. A default-on approval would
  be simpler for consumers but is a hidden authority change for existing `@v1`
  callers.
- **Evidence ledger:**
  - GitHub docs show `gh pr review --approve` and `gh pr merge --auto` for
    Dependabot automation.
  - GitHub auto-merge docs state required reviews and status checks must still
    be met before merge.
  - GitHub token docs require minimum permissions; `.github` currently keeps
    root workflow permissions read-only and grants write only on the Dependabot
    job (`.github/workflows/dependabot-automerge.yml:6`,
    `.github/workflows/dependabot-automerge.yml:21`).
  - OpenSSF's best-practice posture treats workflow PR approval as risky, which
    justifies explicit opt-in, narrow bot/user gates, and smoke evidence.
- **Residual risk:** Enabling `auto_approve: "true"` in `.github` itself is
  higher impact than ordinary consumers because `.github` repo-owned workflows
  take effect from `main` immediately; the `v1` boundary protects downstream
  consumers, not `.github`'s own `main`. Phase 4/5 must make this an explicit
  operator-accepted line before self-application.
- **Evidence safety:** Never persist `GITHUB_TOKEN`, GitHub API response bodies,
  reviewer bodies containing secrets, or full PR payloads. Persist PR number,
  repo, update-type, outcome, check status summary, and redacted command result.
- **Proof obligations:** add tests for default `auto_approve: false`, eligible
  patch/minor approval, major denial, unsupported update-type denial, and
  invalid merge method; verify every opt-in target branch has required checks or
  an equivalent ruleset; run a live/sandbox external-smoke on a Dependabot
  patch/minor PR before org-wide rollout.
- **Operator-owned judgment:** enabling "Allow GitHub Actions to create and
  approve pull requests" is a security-policy exception; the user has accepted
  it for Dependabot patch/minor automation, but any PAT/GitHub App fallback
  requires a separate operator decision. The implementation must record whether
  the setting is enabled org-wide or per-repo, and `.github` self-application
  requires explicit operator acceptance after Phase 4 smoke.
- **Supersedes:** n/a

### PDR-003: Release Ref And Merge Method Policy

- **Status:** accepted
- **Decision class:** integration, git/github/CI
- **Evidence tier:** full
- **Reversibility:** moderate
- **Blast radius:** broad
- **Force-full overrides checked:** durable workflow contract, security/authz,
  external-system behavior
- **Touched surfaces:** git/github/CI/worktree, docs/lifecycle, tests/fixtures
- **Governing sources checked:**
  - `docs/intent.md` applies - moving `v1` is the shared-action rollout
    boundary.
  - `docs/requirements.md` applies - required CI examples use released tags,
    and tag movement is deliberate after review.
  - `docs/architecture.md` applies - required consumer refs use released refs;
    probes alone use `@main`.
  - `notes/Alpha Apps Git and GitHub Process.md` applies - code repos route to
    `dev`; control-plane repos route to `main`.
  - `system/runbooks/GitHub Actions CI Diagnostics.md` applies - `@main` is for
    manual diagnostic probes, not merge-authority automation.
- **Proof modes:** research, architecture-check, external-smoke
- **Decision:** Keep required Dependabot automation on `@v1`; move `v1`
  deliberately after `.github` CI and review pass. Use `merge_method: squash`
  for code repos targeting `dev` and `merge_method: merge` for control-plane
  repos targeting `main`.
- **Objective function:** preserve the release boundary while matching the
  history shape we use for repo class.
- **Candidate solution classes:**
  - **Baseline/default:** Leave every caller on its current method/ref.
  - **Alternative A:** Move all callers to `@main` to always use latest.
  - **Alternative B:** Keep all callers on `@v1`, update `v1` after release,
    and standardize merge method by repo class.
- **Fit analysis:** Alternative B matches source truth. `@main` is allowed for
  diagnostic probes because they are not merge authority; Dependabot auto-merge
  is merge-affecting automation and should consume a released ref.
- **Why not the tempting safe option:** Keeping current callers avoids immediate
  diffs but preserves reusable-workflow `404`s and inconsistent merge history.
- **Evidence ledger:**
  - `docs/intent.md:58` names `v1` as the shared-action rollout boundary.
  - `docs/requirements.md:81` requires released refs in required examples.
  - `docs/architecture.md:129` says mutable major tags are the rollout
    boundary.
  - `docs/architecture.md:137` limits `@main` to manual diagnostic probes.
- **Evidence safety:** Persist tag names, commit SHAs, and release commands; do
  not persist auth tokens.
- **Proof obligations:** verify `v1` movement only after `.github` PR merge and
  CI success; verify consumers reference `@v1`; verify diagnostic probe `@main`
  exceptions remain unchanged.
- **Operator-owned judgment:** none remaining for this rollout. Future major
  version/default-on changes require operator approval.
- **Supersedes:** n/a

### PDR-004: Org-Wide Consumer Rollout Shape

- **Status:** accepted
- **Decision class:** integration, implementation-shape
- **Evidence tier:** full
- **Reversibility:** moderate
- **Blast radius:** broad
- **Force-full overrides checked:** broad repo blast radius, agent authority,
  external-system behavior
- **Touched surfaces:** git/github/CI/worktree, external-system/API/vendor,
  tests/fixtures, docs/lifecycle
- **Governing sources checked:**
  - `docs/architecture.md` applies - Dependabot config is repo-local and
    `.github` owns templates/examples/validation.
  - `notes/Alpha Apps Git and GitHub Process.md` applies - code repo PRs target
    `dev`; control-plane PRs target `main`.
  - `templates/dependabot/*` applies - existing repo-local templates should be
    reused rather than hand-written from scratch.
  - `actions/ci-dependabot-coverage` applies - coverage validation is the
    deterministic gate for missing obvious dependency surfaces.
- **Proof modes:** research, external-smoke, architecture-check
- **Decision:** Roll out with separate consumer PRs by repo/default-branch class:
  control-plane repos to `main`, code repos to `dev`, all using direct
  composite callers and the standard Dependabot cadence.
- **Objective function:** fix all active org repos without creating an
  unreviewable mega-PR or mixing unrelated product code with control-plane
  config.
- **Candidate solution classes:**
  - **Baseline/default:** Update only repos that already have direct callers.
  - **Alternative A:** One org-wide automation script pushes directly to every
    default branch.
  - **Alternative B:** Create normal PRs per repo or small repo-class batch,
    using fresh worktrees and deterministic checks.
- **Fit analysis:** Alternative B follows Alpha Apps git process and preserves
  reviewability. It also handles missing Dependabot configs and disabled repo
  auto-merge settings explicitly.
- **Why not the tempting safe option:** Updating only existing direct callers is
  smaller but leaves `turnkeyleads-app`, `alphaapps-outliers`,
  `alphaapps-adr-pipeline`, and the four broken reusable callers out of the
  standard.
- **Evidence ledger:** Live GitHub API inventory identified 12 active repos, 3
  missing Dependabot configs, 3 missing auto-merge workflows, 2 disabled
  repository auto-merge settings, and 4 callers referencing a missing reusable
  workflow path.
- **Evidence safety:** Store only repo names, branch names, config presence,
  caller shape, and setting booleans. Do not persist private API response bodies
  or credentials.
- **Proof obligations:** every consumer PR runs that repo's normal CI; coverage
  validation passes or unmanaged surfaces are explicitly documented; live API
  inventory after rollout shows no missing caller, no reusable `404` reference,
  and auto-merge enabled wherever auto-approval is configured.
- **Operator-owned judgment:** if a repo is intentionally unmanaged, the
  operator must approve that exception in the consumer PR.
- **Supersedes:** n/a

## What We're NOT Doing

- Not enabling Dependabot major updates to auto-approve or auto-merge.
- Not bypassing required checks, required reviews, branch protection, rulesets,
  or merge queues.
- Not using `pull_request_target`.
- Not introducing a broad PAT or GitHub App token unless the GITHUB_TOKEN smoke
  test proves it is impossible and the operator approves a separate plan
  amendment.
- Not moving required automation callers to `.github@main`; `@main` remains for
  diagnostic probes only.
- Not copying private Alpha Apps conventions, runbooks, agents, or local paths
  into the public `.github` repository.
- Not making direct pushes to protected `dev`, `staging`, or `main`.

## Prerequisites

- **Fresh `.github` branch from `origin/main`** - required because control-plane
  changes must start from the fetched default branch. Status: done via
  `spec-metadata` on branch `docs/dependabot-automerge-org-rollout` at
  `2a9ad1c3e7633c4a2378579e96d70e148e98ba37`.
- **Approved `.github` source truth exists** - required before broad
  control-plane planning. Status: done at `docs/intent.md:2`,
  `docs/requirements.md:2`, and `docs/architecture.md:2`.
- **Product Evidence manifest exists** - required for active ForgingAlpha repos.
  Status: done at `docs/evidence/product-evidence.json`.

If implementation discovers an unstated prerequisite, stop and amend this
section before continuing.

## Implementation Approach

Use the `.github` repo as the owning control-plane plan. First amend source
truth and Product Evidence so auto-approval is a durable rule, not just a Linear
task. Then implement and test the shared composite action. Then update public
consumer examples and self-validation. After merge, deliberately move `v1` and
roll out consumer PRs to active repositories through the normal feature branch
and PR process.

## Phase Context Packets

The deterministic selector returned no matching convention for the exact
`infrastructure` plus `github-actions` query. The following governing sources
were selected manually from the current index and explicit read-before-acting
tables.

### Phase 1: Source Truth And Product Evidence Amendment

- Selected conventions: `system/conventions/Architecture Planning Artifact
  Lifecycle.md`, `system/conventions/Architecture Decision Evidence
  Protocol.md`, `system/conventions/Security Evidence and Audit Safety.md`,
  `system/conventions/Subagent Review Operations.md`.
- `docs/intent.md`, `docs/requirements.md`, `docs/architecture.md`, and
  `docs/evidence/product-evidence.json` because this phase changes durable
  control-plane source truth/evidence.
- `notes/Alpha Apps Git and GitHub Process.md` because PR and release routing is
  part of the policy.

### Phase 2: Shared Composite Action Implementation

- Selected conventions: `system/conventions/Testing Strategy.md`,
  `system/conventions/Architecture Implementation Phase Gates.md`,
  `system/conventions/Error Handling Principles.md`,
  `system/conventions/Security Tool Authorization.md`,
  `system/conventions/Security Service Principal and Workload Identity.md`,
  `system/conventions/Security Evidence and Audit Safety.md`,
  `system/conventions/Subagent Review Operations.md`.
- `docs/requirements.md#REQ-013`, `REQ-014`, `REQ-015` because the action must
  be deterministic, explain failures clearly, and self-validate before release.
- `actions/dependabot-automerge/action.yml` and current self-CI/test files.

### Phase 3: Public Consumer Contract And Self-Validation

- Selected conventions: `system/conventions/Testing Strategy.md`,
  `system/conventions/Architecture Implementation Phase Gates.md`,
  `system/conventions/Git Commit and PR Standards.md`,
  `system/conventions/Subagent Review Operations.md`,
  `system/conventions/Architecture Decision Evidence Protocol.md`.
- `README.md`, `.github/workflows/dependabot-automerge.yml`,
  `tests/test_shared_ci_contract.py`, and Dependabot templates because they
  define the copyable public consumer contract.

### Phase 4: Release, Settings, And Pilot Smoke

- Selected conventions: `system/conventions/Security Service Principal and
  Workload Identity.md`, `system/conventions/Security Tool Authorization.md`,
  `system/conventions/Security Evidence and Audit Safety.md`,
  `system/conventions/Subagent Review Operations.md`.
- `docs/architecture.md#Release And Rollout Model` because `v1` movement is
  deliberate and separate from merging to `main`.
- Target-branch required-check inventory because the safety model relies on
  required checks or equivalent rulesets being present before `auto_approve`
  opt-in.
- GitHub official docs for auto-merge, Dependabot automation, and token
  permissions because the proof mode is external-smoke.

### Phase 5: Consumer Repo Rollout

- Selected conventions: `system/conventions/Git Commit and PR Standards.md`,
  `system/conventions/Testing Strategy.md`,
  `system/conventions/Architecture Implementation Phase Gates.md`,
  `system/conventions/Architecture Decision Evidence Protocol.md`,
  `system/conventions/Subagent Review Operations.md`.
- `notes/Alpha Apps Git and GitHub Process.md` because code repos target `dev`
  and control-plane repos target `main`.
- `templates/dependabot/*` and `actions/ci-dependabot-coverage` because
  consumers must reuse the standard templates and pass coverage validation.

## Plan Drift Reporting Contract

Allowed implementation choices:

- Small script/module names, test file names, and helper extraction details when
  they preserve the PDR decisions and source-truth boundaries.
- Equivalent deterministic tests that cover the required auto-approval,
  auto-merge, and denial behavior.
- Splitting consumer rollout PRs into smaller batches for reviewability.

Plan deviations requiring operator approval:

- Any switch from direct composite callers to reusable workflows.
- Any auto-approval default of `"true"` for existing `@v1` consumers.
- Any PAT or GitHub App token fallback.
- Any use of `pull_request_target`.
- Any major-update auto-approval or auto-merge.
- Any direct push to protected `dev`, `staging`, or `main`.
- Any decision to leave an active repo unmanaged without an explicit exception.

## Evidence And Rollout Planning

- Rollout control: `.github` PR merge to `main` does not roll consumers. Moving
  mutable `v1` is the release boundary.
- Observable signals: `.github` CI green, release tag moved to reviewed commit,
  pilot Dependabot PR receives bot approval, auto-merge is enabled, required
  checks remain pending/required until green, and final merge uses configured
  merge method.
- Kill switch: set `auto_approve: "false"` in a consumer workflow, disable repo
  auto-merge, or temporarily disable the Dependabot auto-merge workflow.
- Cleanup point: after consumer rollout, live inventory must show no missing
  caller, no reusable-workflow `404` references, and no disabled repo
  auto-merge where auto-approval is configured. It must also show required
  checks or an equivalent ruleset on every target branch that opts into
  auto-approval.
- Follow-up checkpoint: Linear `ALP-28` tracks the one-or-two-week post-rollout
  review. It checks whether Dependabot PRs auto-approved, waited for required
  checks, merged with the expected method, and avoided skipped required
  post-merge automation.
- Evidence persistence: record repo/ref/PR number/update-type/outcome only.
  Redact tokens and avoid raw private GitHub API payloads.

## Phase 1: Source Truth And Product Evidence Amendment

### Overview

Add the durable `.github` source-truth language that ALP-25 needs before
implementation relies on bot approval authority.

### Changes Required

#### 1. Requirements And Architecture

**Files**: `docs/requirements.md`, `docs/architecture.md`

**Changes**:

- Add a requirement under the Dependabot section for patch/minor Dependabot PRs
  to be eligible for explicit opt-in auto-approval and auto-merge after required
  checks.
- State that major updates remain manual.
- State that caller workflows must grant only job-scoped permissions and must
  not use `pull_request_target`.
- State honestly that the GitHub approval setting grants approval capability to
  any workflow with `pull-requests: write` in its scope; the standard narrows
  intended use through default-off opt-in, Dependabot-only guards, job-scoped
  permissions, no `pull_request_target`, and required target-branch checks.
- Add architecture wording that `auto_approve` is default-off in the shared
  action and opt-in per consumer.

#### 2. Product Evidence

**Files**: `docs/evidence/product-evidence.json`,
`docs/evidence/product-evidence-view.md`

**Changes**:

- Add or update evidence entries for the new Dependabot automation promise.
- Mark implementation evidence as planned until Phase 2/3 tests and Phase 4
  smoke evidence exist.

### Success Criteria

#### Automated Verification

- [ ] Product Evidence schema/view checks pass:
      `python3 -m unittest discover -s actions/ci-alphaapps-policy/tests`
- [ ] README/source-truth Markdown validates through self CI:
      `python3 -m unittest discover -s actions/ci-markdown/tests`
- [ ] Full-suite phase-close gate passes:
      `python3 -m unittest discover -s tests`
- [ ] Push-equivalent phase-close proof passes: the commands above plus
      `.github` CI are no weaker than the changed docs/evidence surfaces.
- [ ] Customer/web suite: n/a - control-plane docs/evidence phase with no
      customer/web surface.

#### Test Durability

- [ ] New/changed tests, if any, are durable because they protect approved
      `.github` source-truth and Product Evidence behavior.
- [ ] No retirement tests are introduced.

#### Manual Verification

- [ ] Requirement and architecture wording matches the user-approved policy:
      patch/minor only, major manual, explicit opt-in, no bypass.
- [ ] Requirement and architecture wording does not understate the broad blast
      radius of the GitHub Actions approval setting.
- [ ] No public `.github` doc includes private paths, tokens, or repo-specific
      private incident detail.

#### Plan Alignment Verification

- [ ] No implementation behavior is added before source truth/evidence is
      amended.
- [ ] No ALP-25 detail is treated as source truth without being represented in
      the durable docs or explicitly scoped as plan-local.

#### Agent Review Gates

- [ ] `reviewer-plan-compliance`
- [ ] `reviewer-definition-traceability`
- [ ] `reviewer-product-development-lifecycle`
- [ ] `reviewer-product-evidence`
- [ ] `reviewer-decision-evidence`
- [ ] `reviewer-knowledgebase-integrity`
- [ ] `reviewer-evidence-audit-safety`

#### Reviewer Execution Plan

- **Preflight:** verify listed reviewers exist in `system/agents/_INDEX.md` and
  the active opposite-runtime reviewer surface.
- **Wave 1 - phase validity:** `reviewer-plan-compliance`,
  `reviewer-definition-traceability`, `reviewer-product-development-lifecycle`,
  `reviewer-product-evidence`, `reviewer-decision-evidence`.
- **Wave 2 - docs/evidence integrity:** `reviewer-knowledgebase-integrity`,
  `reviewer-evidence-audit-safety`.
- **Wave 3 - domain specialists:** none beyond the above for this docs/evidence
  phase.
- **Concurrency:** default two reviewers at a time; never exceed four.

**Implementation Note:** After automated verification and review gates pass,
commit this phase before proceeding.

## Phase 2: Shared Composite Action Auto-Approve Implementation

### Overview

Make the shared action approve eligible Dependabot PRs only when the caller opts
in, and keep auto-merge behavior behind the existing update-type and merge-method
checks.

### Changes Required

#### 1. Action Inputs And Decision Logic

**File**: `actions/dependabot-automerge/action.yml`

**Changes**:

- Add `auto_approve` input with default `"false"`.
- Keep `allow_patch`, `allow_minor`, and `allow_major` gates.
- Validate boolean-like inputs deterministically and emit WHAT/WHY/HOW failures.
- Only approve when:
  - PR author is Dependabot by workflow guard,
  - `dependabot/fetch-metadata` succeeds,
  - update type is allowed,
  - `auto_approve == "true"`.
- Keep `gh pr merge --auto` after eligibility and merge-method validation.

#### 2. Testable Helper

**Files**: new helper/test files under `actions/dependabot-automerge/`

**Changes**:

- Extract update-type/input decision logic into a small script or otherwise add a
  deterministic local test seam.
- Cover patch, minor, major, unsupported update types, invalid booleans, invalid
  merge methods, default-off auto-approve, and approval-before-merge ordering.

### Success Criteria

#### Automated Verification

- [ ] Failing test written before implementation for default-off
      auto-approval and eligible opt-in approval.
- [ ] Focused Dependabot action tests pass:
      `python3 -m unittest discover -s actions/dependabot-automerge/tests`
- [ ] GitHub Actions safety tests pass:
      `python3 -m unittest discover -s actions/ci-github-actions/tests`
- [ ] Top-level shared contract tests pass:
      `python3 -m unittest discover -s tests`
- [ ] Full-suite phase-close gate passes:
      `python3 -m unittest discover -s tests &&
       python3 -m unittest discover -s actions/ci-github-actions/tests &&
       python3 -m unittest discover -s actions/ci-markdown/tests &&
       python3 -m unittest discover -s actions/ci-alphaapps-policy/tests &&
       python3 -m unittest discover -s actions/ci-dependency-review/tests &&
       python3 -m unittest discover -s actions/ci-dependabot-coverage/tests &&
       python3 -m unittest discover -s actions/ci-remote-probe-guard/tests`
- [ ] Push-equivalent phase-close proof passes: local commands above plus
      GitHub PR CI use the same or broader command set.
- [ ] Customer/web suite: n/a - GitHub Actions control-plane action only.

#### Test Durability

- [ ] New tests are durable; they protect `.github` Dependabot automation
      requirements and local action invariants.
- [ ] Assertion failures use WHAT/WHY/HOW messages.
- [ ] No retirement tests are introduced.

#### Manual Verification

- [ ] Review the action step order manually: metadata, eligibility, merge method
      validation, optional approval, auto-merge.
- [ ] Confirm no step logs token values or raw API payloads.

#### Plan Alignment Verification

- [ ] `auto_approve` default remains `"false"`.
- [ ] No `pull_request_target` is introduced.
- [ ] No PAT/GitHub App credential is introduced.
- [ ] Major updates remain denied by default.

#### Agent Review Gates

- [ ] `reviewer-plan-compliance`
- [ ] `reviewer-definition-traceability`
- [ ] `reviewer-decision-evidence`
- [ ] `reviewer-reuse-patterns`
- [ ] `reviewer-test-discipline`
- [ ] `reviewer-error-handling`
- [ ] `reviewer-code-quality`
- [ ] `reviewer-performance-efficiency`
- [ ] `reviewer-security-general`
- [ ] `reviewer-service-principal-authorization`
- [ ] `reviewer-tool-authorization`
- [ ] `reviewer-evidence-audit-safety`

#### Reviewer Execution Plan

- **Preflight:** verify reviewers exist in `system/agents/_INDEX.md` and the
  opposite-runtime reviewer surface.
- **Wave 1 - phase validity:** `reviewer-plan-compliance`,
  `reviewer-definition-traceability`, `reviewer-decision-evidence`,
  `reviewer-test-discipline`.
- **Wave 2 - implementation hygiene:** `reviewer-reuse-patterns`,
  `reviewer-error-handling`, `reviewer-code-quality`,
  `reviewer-performance-efficiency`.
- **Wave 3 - domain specialists:** `reviewer-security-general`,
  `reviewer-service-principal-authorization`, `reviewer-tool-authorization`,
  `reviewer-evidence-audit-safety`.
- **Concurrency:** default two reviewers at a time; never exceed four.

**Implementation Note:** After automated verification and review gates pass,
commit this phase before proceeding.

## Phase 3: Public Consumer Contract And Self-Validation

### Overview

Update the public `.github` consumer contract so every active repo can copy the
same direct-caller pattern with repo-class merge methods and explicit
auto-approval.

### Changes Required

#### 1. README And Templates

**Files**: `README.md`, `.github/workflows/dependabot-automerge.yml`,
`templates/dependabot/*` if needed

**Changes**:

- Add direct caller examples for code repos and control-plane repos.
- Code repo example: target default branch `dev`, `merge_method: squash`.
- Control-plane repo example: target default branch `main`,
  `merge_method: merge`.
- Include `auto_approve: "true"` only in the standard opt-in example.
- Keep `.github/workflows/dependabot-automerge.yml` at default
  `auto_approve: "false"` or omit the input in this phase. `.github` opts in
  only during Phase 5 after Phase 4 settings and smoke evidence.
- Preserve the weekly Tuesday Dependabot cadence and grouped update standard.
- Remove or explicitly reject the nonexistent reusable workflow caller pattern.

#### 2. Contract Tests

**Files**: `tests/test_shared_ci_contract.py`,
`tests/test_validate_github_actions.py`, or focused tests under an appropriate
existing suite

**Changes**:

- Parse README Dependabot caller examples.
- Assert the examples use `ForgingAlpha/.github/actions/dependabot-automerge@v1`.
- Assert no example references
  `.github/workflows/dependabot-automerge-reusable.yml`.
- Assert examples include explicit `auto_approve` and repo-class merge method
  guidance.

### Success Criteria

#### Automated Verification

- [ ] README example parsing tests fail before the docs change and pass after.
- [ ] Top-level shared contract tests pass:
      `python3 -m unittest discover -s tests`
- [ ] Markdown tests pass:
      `python3 -m unittest discover -s actions/ci-markdown/tests`
- [ ] GitHub Actions safety tests pass:
      `python3 -m unittest discover -s actions/ci-github-actions/tests`
- [ ] Dependabot coverage tests pass:
      `python3 -m unittest discover -s actions/ci-dependabot-coverage/tests`
- [ ] Full-suite phase-close gate passes with the same command set listed in
      Phase 2.
- [ ] Push-equivalent phase-close proof passes: local commands above plus
      GitHub PR CI use the same or broader command set.
- [ ] Customer/web suite: n/a - public control-plane docs/config only.

#### Test Durability

- [ ] New/changed tests are durable; they protect public consumer contract
      examples and required release-ref policy.
- [ ] No retirement tests are introduced.

#### Manual Verification

- [ ] README examples are copyable YAML.
- [ ] README does not imply that auto-approval bypasses branch protection.
- [ ] README clearly distinguishes required `@v1` automation from diagnostic
      probe `@main` exceptions.

#### Plan Alignment Verification

- [ ] No reusable-workflow caller is promoted as canonical.
- [ ] Code/control-plane merge methods match PDR-003.
- [ ] `.github` repo-owned caller does not enable `auto_approve` in this phase.
- [ ] No private Alpha Apps policy source is copied into this public repo.

#### Agent Review Gates

- [ ] `reviewer-plan-compliance`
- [ ] `reviewer-definition-traceability`
- [ ] `reviewer-decision-evidence`
- [ ] `reviewer-knowledgebase-integrity`
- [ ] `reviewer-reuse-patterns`
- [ ] `reviewer-test-discipline`
- [ ] `reviewer-code-quality`
- [ ] `reviewer-security-general`
- [ ] `reviewer-evidence-audit-safety`

#### Reviewer Execution Plan

- **Wave 1 - phase validity:** `reviewer-plan-compliance`,
  `reviewer-definition-traceability`, `reviewer-decision-evidence`,
  `reviewer-test-discipline`.
- **Wave 2 - docs/test hygiene:** `reviewer-knowledgebase-integrity`,
  `reviewer-reuse-patterns`, `reviewer-code-quality`.
- **Wave 3 - domain specialists:** `reviewer-security-general`,
  `reviewer-evidence-audit-safety`.
- **Concurrency:** default two reviewers at a time; never exceed four.

**Implementation Note:** After automated verification and review gates pass,
commit this phase before proceeding.

## Phase 4: Release, Settings, And Pilot Smoke

### Overview

After the `.github` PR merges, prove the external GitHub settings and release
boundary before enabling org-wide consumer auto-approval.

### Changes Required

#### 1. Release Tag Movement

**Surface**: `.github` GitHub release refs

**Changes**:

- Verify `.github` PR CI is green on `main`.
- Move the mutable `v1` tag to the reviewed merge commit using the established
  release process.
- Verify `v1` resolves to the expected commit before consumer rollout.

#### 2. GitHub Settings And Smoke

**Surface**: GitHub organization/repository settings, required-check inventory,
and one `alphaapps-docs` pilot Dependabot PR

**Changes**:

- Produce an org-wide target-branch required-check/ruleset inventory before
  opening Phase 5 consumer PRs. Record whether each active repo is eligible for
  auto-approval opt-in, needs ruleset work, or needs an operator-approved
  exception.
- Verify the org/repo setting allows GitHub Actions to create and approve PRs.
- Record whether that setting is enabled org-wide or only on selected repos.
- Verify repo auto-merge is enabled for `alphaapps-docs`.
- Use `alphaapps-docs` as the pilot. Do not use `.github` as the pilot because
  `.github` self-application is gated on Phase 4 evidence plus recorded
  operator acceptance.
- Enable `auto_approve: "true"` on the `alphaapps-docs` caller as a scoped
  Phase 4 pilot opt-in through the normal control-plane PR flow, after verifying
  the `main` branch requires at least one approval and required `CI` or
  equivalent checks.
- Run the pilot on a low-risk patch/minor Dependabot PR in `alphaapps-docs`.
- Confirm `github-actions[bot]` approval is accepted by the ruleset.
- Confirm auto-merge remains pending until required checks pass.
- Confirm post-merge `on: push` automation on the pilot target branch either
  does not exist or is not required for the intended dependency-update path,
  because `GITHUB_TOKEN`-attributed merges may not trigger downstream
  push-triggered workflows.

### Success Criteria

#### Automated Verification

- [ ] `.github` remote PR CI is green before tag movement.
- [ ] `git ls-remote --tags origin v1` or equivalent proves `v1` points to the
      reviewed commit after release.
- [ ] Live GitHub API/ruleset inventory classifies every active repo as
      auto-approval eligible, needs ruleset work, or operator-exception needed.
- [ ] Live GitHub API check confirms `alphaapps-docs` auto-merge is enabled.
- [ ] Live GitHub API/ruleset check confirms `alphaapps-docs` `main` requires
      approval and required checks before merge.
- [ ] External-smoke summary confirms eligible patch/minor PR got approval and
      auto-merge enabled in `alphaapps-docs`.
- [ ] External-smoke summary confirms auto-merge did not merge until required
      checks and required review were satisfied.
- [ ] Push-trigger summary confirms no required post-merge `on: push`
      automation is silently skipped by the bot-attributed merge.
- [ ] Full-suite phase-close gate: n/a - post-merge release/settings phase; the
      blocking automation is remote `.github` CI plus external-smoke evidence.
- [ ] Customer/web suite: n/a - no customer/web surface.

#### Test Durability

- [ ] No tests are introduced in this post-merge release/settings phase.

#### Manual Verification

- [ ] Operator or authorized maintainer confirms the org Actions setting
      exception is intentional.
- [ ] Operator or authorized maintainer confirms whether the approval setting is
      org-wide or per-repo, and accepts the resulting blast radius.
- [ ] Verify no PAT/GitHub App token was needed.
- [ ] If `GITHUB_TOKEN` cannot satisfy approval/ruleset requirements, stop and
      request a plan amendment before introducing any broader credential.

#### Plan Alignment Verification

- [ ] `v1` is moved only after reviewed `.github` merge and green CI.
- [ ] Pilot repo is `alphaapps-docs`; `.github` is not used as the pilot.
- [ ] `alphaapps-docs` has required checks/review on `main`; otherwise the
      pilot is invalid and Phase 5 must not start.
- [ ] Smoke evidence redacts tokens and raw API payloads.
- [ ] No consumer repo is updated before the shared release boundary is live.

#### Agent Review Gates

- [ ] `reviewer-plan-compliance`
- [ ] `reviewer-decision-evidence`
- [ ] `reviewer-security-general`
- [ ] `reviewer-service-principal-authorization`
- [ ] `reviewer-tool-authorization`
- [ ] `reviewer-evidence-audit-safety`

#### Reviewer Execution Plan

- **Wave 1 - phase validity:** `reviewer-plan-compliance`,
  `reviewer-decision-evidence`.
- **Wave 2 - security/evidence:** `reviewer-security-general`,
  `reviewer-service-principal-authorization`, `reviewer-tool-authorization`,
  `reviewer-evidence-audit-safety`.
- **Concurrency:** default two reviewers at a time; never exceed four.

**Implementation Note:** This phase is post-merge and may not create a normal
phase commit. Record the release and smoke evidence in the plan or a closeout
receipt before Phase 5 begins.

## Phase 5: Consumer Repo Rollout

### Overview

Bring every active ForgingAlpha repo onto the standard Dependabot config and
direct auto-merge caller.

### Changes Required

#### 1. Repos With Missing Dependabot Setup

**Repos**: `turnkeyleads-app`, `alphaapps-outliers`,
`alphaapps-adr-pipeline`

**Changes**:

- Create fresh worktrees from `origin/dev` for code repos.
- Add standard `.github/dependabot.yml` from the matching `.github` template,
  including GitHub Actions coverage and package ecosystem coverage for detected
  manifests.
- Add `.github/workflows/dependabot-automerge.yml` using the direct composite
  action caller.
- Use `merge_method: squash` for code repos.
- Verify the repo's Dependabot target branch has required checks or an
  equivalent ruleset before setting `auto_approve: "true"`; stop for operator
  decision if it does not.
- Enable repository auto-merge where currently disabled, or stop for operator
  approval if the repo is intentionally unmanaged.

#### 2. Repos With Broken Reusable Callers

**Repos**: `alphaapps-site`, `analyzingalpha-engine`,
`analyzingalpha-site`, `turnkeyleads-site`

**Changes**:

- Replace
  `ForgingAlpha/.github/.github/workflows/dependabot-automerge-reusable.yml@v1`
  with the direct composite-action caller.
- Preserve target default branch behavior (`dev`) and use
  `merge_method: squash`.
- Verify the target `dev` branch has required checks or an equivalent ruleset
  before setting `auto_approve: "true"`; stop for operator decision if it does
  not.

#### 3. Repos With Direct Callers

**Repos**: `.github`, `alphaapps-docs`, `alphaapps-composer`,
`analyzingalpha-vault`, `whosyouragent-app`

**Changes**:

- Add explicit `auto_approve: "true"` only after Phase 4 proves the shared
  release and settings.
- Ensure merge method matches repo class:
  - `.github` and `alphaapps-docs`: `merge_method: merge`
  - code repos: `merge_method: squash`
- Treat `.github` self-application as explicit operator acceptance: verify
  required review/checks on `main`, confirm no required post-merge `on: push`
  automation is skipped by bot-attributed merges, and record the acceptance
  before enabling `auto_approve`.

### Success Criteria

#### Automated Verification

- [ ] For each consumer repo, run that repo's normal CI/pre-push-equivalent
      local checks where available.
- [ ] For each consumer repo, run Dependabot coverage validation or the repo's
      shared CI action that includes it.
- [ ] Live inventory after rollout shows every active repo has an intended
      Dependabot config/caller state or an operator-approved unmanaged
      exception.
- [ ] Live inventory after rollout shows zero references to the missing reusable
      workflow path.
- [ ] Live branch-protection/ruleset inventory after rollout shows every repo
      with `auto_approve: "true"` has required checks or an equivalent ruleset
      on the Dependabot target branch; repos without one have an
      operator-approved exception and no opt-in.
- [ ] Customer/web suite: per consumer repo, run only when that repo's normal
      CI requires it; no customer/web product code is intentionally changed by
      this rollout.

#### Test Durability

- [ ] Consumer changes are config-only unless a repo-specific CI check requires
      tests.
- [ ] Any repo-specific test change is durable and cites source truth or local
      invariant, not this plan path.

#### Manual Verification

- [ ] PRs target the correct base: code repos to `dev`, control-plane repos to
      `main`.
- [ ] PR descriptions state whether repo auto-merge settings were already
      enabled, changed, or intentionally left disabled.
- [ ] At least one consumer Dependabot patch/minor PR demonstrates
      auto-approval plus auto-merge pending required checks.
- [ ] For repos where post-merge `on: push` automation matters, confirm the
      bot-attributed merge path does not skip a required release/deploy/validation
      step, or keep `auto_approve` disabled until that path is redesigned.
- [ ] Linear follow-up `ALP-28` remains linked to ALP-25 and this plan, with
      due date adjusted to one or two weeks after rollout reaches active repos
      if the placeholder date no longer fits.

#### Plan Alignment Verification

- [ ] No direct push to protected branches.
- [ ] No consumer PR changes product runtime behavior.
- [ ] No consumer PR introduces `pull_request_target`, PATs, or GitHub App
      credentials.
- [ ] No repo enables `auto_approve` without target-branch required checks or an
      explicit operator-approved exception.
- [ ] No active repo is skipped without an operator-approved exception.

#### Agent Review Gates

- [ ] `reviewer-plan-compliance`
- [ ] `reviewer-definition-traceability`
- [ ] `reviewer-decision-evidence`
- [ ] `reviewer-reuse-patterns`
- [ ] `reviewer-test-discipline`
- [ ] `reviewer-code-quality`
- [ ] `reviewer-security-general`
- [ ] `reviewer-service-principal-authorization`
- [ ] `reviewer-tool-authorization`
- [ ] `reviewer-evidence-audit-safety`

#### Reviewer Execution Plan

- **Wave 1 - phase validity:** `reviewer-plan-compliance`,
  `reviewer-definition-traceability`, `reviewer-decision-evidence`,
  `reviewer-test-discipline`.
- **Wave 2 - implementation hygiene:** `reviewer-reuse-patterns`,
  `reviewer-code-quality`.
- **Wave 3 - domain specialists:** `reviewer-security-general`,
  `reviewer-service-principal-authorization`, `reviewer-tool-authorization`,
  `reviewer-evidence-audit-safety`.
- **Concurrency:** default two reviewers at a time; never exceed four.

**Implementation Note:** Consumer rollout can be split into separate PRs by repo
or repo class. Each repo PR closes only after its own CI and reviewer gates pass.

## Testing Strategy

### Unit Tests

- Dependabot eligibility script/helper:
  - patch/minor allowed when configured
  - major denied by default
  - unsupported update types denied
  - invalid booleans fail with WHAT/WHY/HOW output
  - invalid merge methods fail with WHAT/WHY/HOW output
  - `auto_approve` default is false
- README/example contract tests:
  - canonical callers parse as YAML
  - direct composite action uses `@v1`
  - no reusable auto-merge workflow path appears
  - examples include repo-class merge-method guidance

### Integration / External-Smoke Tests

- Pilot Dependabot patch/minor PR:
  - workflow runs only for `dependabot[bot]`
  - `github-actions[bot]` approval is recorded when `auto_approve: "true"`
  - auto-merge is enabled
  - target branch requires approval and required checks
  - merge waits for required checks and required review
  - post-merge `on: push` automation is either absent or confirmed
    non-required for the dependency-update path
- Live org inventory after rollout:
  - active repos have expected configs and callers
  - missing reusable path is gone
  - auto-merge setting is enabled where auto-approval is configured
  - every auto-approval opt-in has target-branch required checks or an
    operator-approved exception

### Manual Testing Steps

1. Inspect `.github` source-truth diff and confirm it reflects operator policy.
2. Inspect shared action logs from a pilot run and confirm no secrets/raw API
   payloads are logged.
3. Inspect at least one code-repo consumer PR and one control-plane consumer PR
   for base branch and merge method.
4. Confirm major Dependabot PRs still require deliberate review.

## Known Pre-Existing Suite Failures

None known at plan creation. If a full-suite or CI failure is already present
when a phase starts, document it here with owner, command, failure summary, and
remediation checkpoint before continuing.

## Migration Notes

- Existing direct `@v1` callers are protected by `auto_approve` defaulting to
  `"false"`; consumer PRs explicitly opt in.
- Moving `.github@v1` is a deliberate release step after `.github` PR merge and
  CI success.
- Reusable-workflow callers are migrated to direct composite callers rather than
  being supported as a compatibility shim, because the referenced reusable
  workflow does not exist at `main` or `v1`.

## References

- Linear ALP-25:
  `https://linear.app/alpha-apps/issue/ALP-25/roll-out-dependabot-auto-approve-and-auto-merge`
- Linear ALP-28 follow-up:
  `https://linear.app/alpha-apps/issue/ALP-28/review-dependabot-auto-approve-rollout-after-first-update-cycle`
- GitHub Dependabot automation:
  `https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/automate-dependabot-with-actions`
- GitHub auto-merge:
  `https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request`
- GitHub Actions `GITHUB_TOKEN` permissions:
  `https://docs.github.com/en/actions/tutorials/authenticate-with-github_token`
- GitHub Actions secure use:
  `https://docs.github.com/en/actions/reference/security/secure-use`
- OpenSSF SCM best practice on workflow PR approval:
  `https://best.openssf.org/SCM-BestPractices/github/actions/actions_can_approve_pull_requests.html`
