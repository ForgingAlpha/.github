# Shared CI Policy Baseline Implementation Plan

## Overview

Implement the first strict, uniform ForgingAlpha shared CI policy layer in
`ForgingAlpha/.github` so Elixir/Phoenix, Rust, TypeScript, Astro/HTML,
Obsidian/Markdown, and shell-heavy repos inherit the same AI-agent-friendly
baseline through the existing single `CI` status.

The plan adds cross-cutting CI actions for Alpha Apps source-truth policy,
Markdown linting, GitHub Actions safety, dependency review, and Dependabot
coverage validation; tightens shell linting to the strictest useful ShellCheck
severity; removes `@main` drift from internal shared-action calls; and documents
a manual, non-required remote diagnostic probe workflow pattern for CI-only
failures that agents cannot reproduce locally.

## Definition Sources

- Intent: `docs/intent.md`
- Requirements: `docs/requirements.md`
- Glossary: `n/a - no product/domain vocabulary introduced.`
- Architecture: `docs/architecture.md`
- ADRs: `n/a - no architecture decision record currently exists for this
  exact CI policy rollout; add one only if implementation reverses the
  composite-action architecture.`
- Design: `n/a - control-plane shared-action implementation; no product or UI
  workflow design artifact required.`
- Stories: `n/a - control-plane infrastructure change; no product story slice.`

## Current State Analysis

`ForgingAlpha/.github` already owns language-specific composite actions and a
single-status CI strategy. `README.md` lists the current shared actions,
requires a job named `CI`, records the composite-action choice, and documents
the org security baseline.

The language gates are already strict, and this branch has already tightened the
foundation-level pieces that were simple and low-risk to apply before adding new
reusable actions:

- `actions/ci-elixir/action.yml` runs `mix format --check-formatted`,
  `mix compile --warnings-as-errors`, optional repo strict checks, and
  `mix credo --strict`.
- `actions/ci-rust/action.yml` runs `cargo fmt`,
  `cargo clippy -- -D warnings`, dead-code-denying `cargo check`,
  `cargo test`, and `cargo audit`.
- `actions/ci-astro/action.yml` runs Prettier, ESLint with
  `--max-warnings 0`, `astro check`, and build.
- `actions/ci-typescript/action.yml` runs Prettier, ESLint with
  `--max-warnings 0`, `tsc --noEmit`, and tests by default.
- `actions/ci-shell/action.yml` runs direct ShellCheck and `bash -n`; this
  branch updates the default ShellCheck severity to `style`.
- TypeScript and Astro shared checks no longer expose inputs that can disable
  their standard format, lint, type, test, or build gates.
- External action pins have been refreshed to current checked releases and
  pinned to full SHAs where this repo's validation policy requires it.
- Internal shared-action references now use `@v1` instead of `@main`.

The gaps are cross-cutting:

- There is no parent `ci-alphaapps-policy` action yet.
- There is no parent `ci-markdown` action yet.
- There is no parent `ci-github-actions` action yet, although this branch adds
  a local self-validation script and pinned actionlint to `.github`'s own CI.
- There is no parent dependency-review action yet.
- There is no parent Dependabot coverage action yet.
- There are no shared Dependabot templates yet.

`alphaapps-docs` already defines the lifecycle policy and validator shape:

- The current alphaapps-docs source-truth policy notes say
  `alphaapps-docs` owns lifecycle policy and `.github` owns the shared GitHub
  composite actions that run enforcement in other repos.
- `notes/Alpha Apps Git and GitHub Process.md` defines the intended
  `ci-alphaapps-policy` action inputs.
- `system/scripts/validate-product-lifecycle-baseline.py` validates approved
  baseline source truth, definition/backfill-only work, lifecycle evidence
  freshness, and changed lifecycle file coverage.
- `system/scripts/validate-durable-evidence-references.py` rejects durable
  plan, phase, PR, handoff, and audit citations.
- `system/scripts/render-product-evidence.py` defines the current lean Product
  Evidence taxonomy. The operator has superseded the previous cross-repo
  `if-present` rollout policy: Product Evidence is required for every active
  ForgingAlpha repository. Because that changes upstream lifecycle policy,
  `alphaapps-docs` source truth and validators must be amended before this
  public `.github` plan can close phases that implement the stricter CI
  enforcement.

Important implementation constraint:

- `ForgingAlpha/.github` is public and `ForgingAlpha/alphaapps-docs` is
  private. A public shared action must not require every consuming repo to
  carry a broad private-repo checkout token only to run baseline policy.
  Therefore the parent CI action should be self-contained in `.github`, with
  the policy contract kept in sync with `alphaapps-docs` through tests and
  review, not through a runtime checkout of the private repo.

## Desired End State

Every standard ForgingAlpha repo can keep a thin `.github/workflows/ci.yml`
that checks out code and calls a language or policy composite action while
receiving:

- merge-flow enforcement;
- approved baseline source-truth enforcement;
- durable-reference validation;
- required Product Evidence validation for active ForgingAlpha repositories;
- Markdown linting for Obsidian and repo docs;
- GitHub Actions workflow/action linting and safety checks;
- dependency-review blocking for newly introduced vulnerable dependencies;
- standard Dependabot coverage templates and validation for repo dependency
  surfaces;
- language-specific strict checks for Elixir/Phoenix, Rust, TypeScript,
  Astro/HTML, and shell scripts;
- manual remote diagnostic probes for CI-only failures, with constrained typed
  inputs and artifact upload;
- one required GitHub status named `CI`.

### Key Discoveries

- Existing language actions are strict, but cross-cutting policy is missing.
- Phase 1 makes `ci-shell` stricter by defaulting ShellCheck severity to
  `style` and running the local `shellcheck` binary directly.
- Phase 1 moves internal shared-action calls to `@v1`, not `@main`, to match
  the release process in `README.md`.
- `ci-alphaapps-policy` must be self-contained because `.github` is public and
  `alphaapps-docs` is private.
- GitHub's official guidance supports minimum `GITHUB_TOKEN` permissions;
  parent examples should preserve `permissions: contents: read` and elevate
  only per job.
- GitHub Dependency Review can block vulnerable newly introduced dependencies
  on pull requests; use it for code/package repos, not docs-only repos by
  default.
- Dependabot cannot be inherited from this repo the way composite actions can.
  Each repo still needs `.github/dependabot.yml`, so centralization means
  templates, validation, and sync PRs rather than a single org-wide config.
- A root-only GitHub Actions Dependabot entry misses nested composite
  `action.yml` manifests; shared-action repos need directory coverage for both
  workflow files and action manifest directories.
- Remote diagnostic probes should be manual `workflow_dispatch` workflows, not
  required checks. GitHub requires manually dispatched workflows to exist on
  the default branch, supports typed inputs, and documents the risk of
  privileged triggers that process untrusted checkout content.
- Prior art does not show a single universal "remote probe" standard. Mature
  repositories combine the same primitives locally: manual dispatch, typed
  inputs, resolved checkout refs, least-privilege permissions, and artifacts on
  failure. Therefore `.github` should standardize the safety contract and helper
  patterns while each repo owns its runtime-specific probe command.

### Remote Probe Evidence Review

Official guidance:

- GitHub manual workflow docs support `workflow_dispatch`, branch/ref
  selection, and `gh workflow run`, with the workflow present on the default
  branch before it can be dispatched.
- GitHub workflow syntax supports typed manual inputs such as `choice`,
  `boolean`, `number`, and `string`.
- GitHub security docs recommend least-privilege `GITHUB_TOKEN` permissions and
  warn against unsafe handling of untrusted context values in shell scripts.
- GitHub artifact docs support uploading logs and output packets for later
  inspection.
- GitHub required-check docs warn that skipped required workflows can leave pull
  requests blocked, so diagnostic probes should not be required checks.

GitHub prior art reviewed:

- `nextstrain/nextstrain.org` uses `workflow_dispatch` with a `choice` input,
  explicit bash defaults, build/test runtime staging, and `if: always()`
  artifact uploads for build, test, and deploy diagnostics.
- `kreuzberg-dev/tree-sitter-language-pack` uses a manual release workflow with
  typed `string` and `boolean` inputs, `permissions: contents: read`, an
  explicit checkout-ref resolution step, and downstream jobs that checkout the
  resolved ref.
- `quarto-dev/quarto-web` uses workflow inputs to control checkout `ref`,
  showing the common pattern of separating workflow control from target code
  checkout.
- `actions/upload-artifact` dogfoods failure-only artifact upload in its own
  workflow, reinforcing that diagnostic artifacts are first-class CI evidence.

First-principles conclusion:

- A remote probe observes CI-only state; it must not grant merge permission.
- Inputs are data, not code; command construction must be allowlisted and
  array-based.
- The workflow definition should come from a trusted default branch. The target
  code under test should be a separate checkout ref.
- The parent `.github` repo should provide a reusable guard/template and
  documentation. Each consumer repo should own the runtime-specific command,
  lane allowlist, environment variables, and artifact paths.
- Failed probes are usually the most valuable probes; artifact upload must run
  with `if: always()`.
- Public `.github` plans and docs must not include local absolute paths,
  private-worktree paths, secrets, tokens, or repo-specific failure details that
  are not intended for public disclosure. Keep private evidence in
  `alphaapps-docs` or sanitize it before committing to `.github`.
- Product Evidence is required for every active ForgingAlpha repository. Missing
  `docs/evidence/product-evidence.json` blocks ordinary code, test, dependency,
  runtime, maintenance, release, and broad planning work while allowing
  source-truth/evidence-backfill-only changes that create or repair the
  required evidence artifacts.
- Current dependency and action version review already refreshed existing
  action refs in the Phase 1 foundation. Newly introduced actions in later
  phases must still use current releases and full SHAs where this repo's
  security policy requires SHA pinning.

## What We're NOT Doing

- Not adding OpenSSF Scorecard as a blocking gate in this first wave.
- Not adding org-wide OIDC/deployment environment rules for repos that do not
  deploy.
- Not adding merge queue requirements until the org chooses merge queue.
- Not changing GitHub org rulesets in this plan.
- Not modifying every consuming repo in this plan.
- Not adding a broad private `alphaapps-docs` checkout token to every repo.
- Not treating absent Product Evidence as a clean pass state in active
  ForgingAlpha repositories.
- Not burying Markdown linting inside any one language action only.
- Not pretending Dependabot config is inherited org-wide; every repo keeps a
  local `.github/dependabot.yml`.
- Not relaxing language checks to preserve compatibility with legacy code.
- Not making remote diagnostic probes a required merge check.
- Not accepting arbitrary shell commands as probe inputs.
- Not adding `pull_request_target` or privileged automatic probe triggers.
- Not committing local absolute worktree paths or private diagnostic details to
  the public `.github` repository.

## Prerequisites

- **Current parent base** - implementation must start from
  `ForgingAlpha/.github@origin/main` so merged `ci-elixir` command hooks and
  current release docs are present. Status: done at commit
  `88e829133b37d08a6daf5a61bed3c0a5e5b8c6b4` in this worktree.
- **Upstream Product Evidence policy amendment** - `alphaapps-docs` currently
  records cross-repo Product Evidence as `if-present`. The operator has changed
  the target policy to required for all active ForgingAlpha repositories.
  Status: operator-confirmed done out of band on 2026-06-30 for this
  implementation run; `.github` implements the approved required-baseline
  policy rather than inventing CI policy locally.
- **Policy source-truth backfill** - `.github` must have approved
  `docs/intent.md`, `docs/requirements.md`, and `docs/architecture.md` before
  the new baseline policy is dogfooded in `.github` CI. Status: implemented in
  the Phase 1 foundation; update the source-truth wording for required Product
  Evidence after the upstream amendment, then commit after automated checks and
  reviewer gates.
- **Product Evidence backfill** - `.github` itself must carry
  `docs/evidence/product-evidence.json` and generated
  `docs/evidence/product-evidence-view.md` before the required policy is
  dogfooded. Status: implemented in Phase 1 after upstream policy approval.
- **Active repo adoption decision** - wiring `ci-alphaapps-policy` into all
  language composites will freeze ordinary work in repos missing approved
  baseline docs. Status: operator-confirmed during implementation on
  2026-06-30; language composites should enforce the shared baseline, but
  `v1` must not move until active repo baseline and Product Evidence backfill
  is ready or the operator explicitly approves release.
- **Remote probe default-branch landing** - `workflow_dispatch` probe workflows
  must exist on the default branch before they can be manually run. Status:
  TODO in consumer repos; Phase 6 documents the shared standard and private
  consumer-repo pilot path.
- **Public disclosure review** - because `ForgingAlpha/.github` is public,
  implementation must remove or relocate private worktree paths, private
  branch/test details, and non-public operational notes before any PR branch is
  pushed. Status: required for every phase closeout.

## Implementation Approach

Use small composite actions and local scripts under `actions/<action>/`.
Composite actions preserve the caller's single required `CI` status while still
centralizing policy. Where a check needs non-trivial logic, place the script in
the action directory and call it through `$GITHUB_ACTION_PATH/scripts/...`
rather than inlining large shell/Python in `action.yml`.

Keep the policy action self-contained in `.github`. The canonical human policy
stays in `alphaapps-docs`, but the public parent action must not require a
private checkout token at runtime. Parity is enforced by explicit tests,
README references, and reviewer-definition-traceability.

## Phase Context Packets

### Phase 1: Foundation source truth and self-validation

- `README.md` because it is the current local source for the parent CI
  architecture and release process.
- `docs/repo-naming.md` because shared policy must preserve repo naming
  conventions.
- `docs/intent.md`, `docs/requirements.md`, and `docs/architecture.md` because
  they are now the approved repo-local source truth for this control-plane repo.
- `notes/Alpha Apps Git and GitHub Process.md#CI Pipeline (Universal CI
  Contract)` from `alphaapps-docs` because it owns the universal CI contract.
- The current alphaapps-docs source-truth policy notes because they record the
  ownership split between `alphaapps-docs` and `.github`.
- The approved alphaapps-docs Product Evidence required-baseline amendment
  because `.github` must implement the upstream Product Evidence policy rather
  than preserve the older `if-present` rollout.

### Phase 2: Alpha Apps policy action

- `actions/ci-merge-flow/action.yml` because it is the existing cross-cutting
  policy action pattern.
- `system/scripts/validate-product-lifecycle-baseline.py` from
  `alphaapps-docs` because it defines the baseline/evidence behavior to mirror.
- `system/scripts/validate-durable-evidence-references.py` from
  `alphaapps-docs` because it defines durable-reference enforcement.
- `system/scripts/render-product-evidence.py` from `alphaapps-docs` because it
  defines Product Evidence manifest and generated-view validation.

### Phase 3: Markdown and reusable GitHub Actions safety actions

- `scripts/validate-github-actions.py` and `tests/test_validate_github_actions.py`
  because Phase 1 already created the local safety contract that this phase may
  extract into a reusable action.
- `.github/workflows/ci.yml` because it already runs local validation and
  actionlint in the parent repo.
- `.markdownlint-cli2.yaml` from `alphaapps-docs` because it is the current
  Obsidian/Markdown lint baseline.
- `system/scripts/pre-push.sh` from `alphaapps-docs` because it already mirrors
  changed Markdown validation locally.
- GitHub Actions secure-use docs because the action must flag high-risk
  workflow patterns such as `pull_request_target` and broad permissions.

### Phase 4: Dependency review and Dependabot coverage

- `actions/ci-rust/action.yml`, `actions/ci-elixir/action.yml`,
  `actions/ci-astro/action.yml`, `actions/ci-typescript/action.yml`, and
  `actions/ci-shell/action.yml` because Phase 5 will wire dependency checks
  into shared language composites.
- `.github/dependabot.yml` because shared-action dependencies and GitHub Action
  pins must stay updateable.
- GitHub Dependabot configuration docs because update configuration is
  repo-local and nested composite action manifests require explicit directory
  coverage.
- GitHub Dependency Review docs because the new shared dependency gate must
  block newly introduced vulnerable dependencies without replacing language
  package managers.

### Phase 5: Dogfood, documentation, and rollout controls

- `.github/workflows/ci.yml` because parent CI must dogfood the new shared
  actions locally before release.
- `README.md` because it is the public contract for consuming repos.
- `.github/workflows/release.yml` because shared action consumers receive
  changes through semver tags and the moving `v1` tag.
- `docs/plans/shared-ci-policy-baseline.md` because phase closeout must report
  plan drift and rollout decisions.

### Phase 6: Remote diagnostic probe standard

- The private consumer-repo remote-probe source plan because it records the
  concrete CI-only failure mode that motivated the probe.
- The pilot consumer repo's required CI workflow because the probe must match
  the same runner/runtime setup as required CI.
- GitHub manual workflow dispatch docs because `workflow_dispatch` workflows
  must live on the default branch and can be launched with `gh workflow run`.
- GitHub workflow syntax docs because probe inputs should use typed
  `choice`, `number`, and `string` fields rather than free-form commands.
- GitHub secure-use docs because the probe must avoid privileged automatic
  triggers and untrusted checkout patterns.
- GitHub workflow artifact docs because failed probes must still upload
  result packets and logs.

## Plan Drift Reporting Contract

Allowed implementation choices:

- Exact script language and file layout inside each action, as long as the
  public action contract and success criteria remain intact.
- Minor input naming improvements that make action contracts clearer, if README
  and tests are updated in the same phase.
- Adding stricter checks that are deterministic and documented in the phase
  checklist.
- Replacing draft version pins with newer current pins discovered during
  implementation, if the README and tests record the chosen version.

Plan deviations requiring operator approval:

- Making Product Evidence optional or `if-present` for active ForgingAlpha
  repositories.
- Requiring a private `alphaapps-docs` checkout token in consuming repos.
- Changing the single required status away from `CI`.
- Introducing reusable workflows for ordinary CI checks.
- Turning off or softening existing language checks.
- Keeping any internal `@main` shared-action dependency.
- Adding org-wide OIDC/deployment/merge-queue/Scorecard gates in this plan.
- Making remote diagnostic probes required for merge.
- Allowing arbitrary remote command execution through workflow inputs.
- Publishing this plan or README updates with local machine paths or private
  repo evidence that belongs in `alphaapps-docs`.

## Evidence And Rollout Planning

The rollout control is the `v1` tag. Implementation may add and dogfood local
actions in the `.github` PR without immediately changing all consumers. The
blast-radius moment is the semver release that moves `v1`, especially after
language composites call the new policy actions.

Phase closeout evidence must include:

- local `.github` CI-equivalent checks;
- action unit/fixture tests where scripts are introduced;
- actionlint proof;
- ShellCheck proof at `style` severity;
- Markdown lint proof;
- README consumer examples;
- public-disclosure review for files that will land in the public `.github`
  repository;
- explicit note whether the release should move `v1` immediately or wait for
  repo baseline and Product Evidence backfill.

Reviewer escalation evidence standard:

- Phase escalations for GitHub Actions behavior, security guidance,
  dependency-review behavior, Dependabot behavior, shell/CI portability, or
  mature CI design patterns must produce a short evidence packet before the
  plan or implementation changes.
- The packet must include authoritative/current vendor documentation when the
  question is about platform behavior or supported API shape.
- The packet must include mature GitHub prior art when the question is about
  reusable CI design, workflow composition, portability patterns, or common
  ecosystem practice. Prefer official project repositories, canonical
  ecosystem repositories, and widely adopted projects with visible CI history.
- The packet must separate official documentation, GitHub prior art, and the
  implementation conclusion. If those sources conflict, escalate the conflict
  to the operator instead of choosing silently.
- Internal lifecycle or policy-source disputes still route to the operator for
  the decision; external research informs the recommendation but does not
  override approved Alpha Apps source truth.

## Phase 1: Foundation Source Truth And Self-Validation

### Overview

Create `.github` repo-local source truth and the first deterministic
self-validation layer so later phases can add reusable actions without
carrying stale bootstrap assumptions. This phase is the foundation checkpoint
for the work already present in this branch.

### Changes Required

#### 1. Parent CI source truth

**Files**:

- `docs/intent.md`
- `docs/requirements.md`
- `docs/architecture.md`

**Changes**:

- Describe why `.github` exists: shared CI, release promotion, ruleset
  documentation, Dependabot automation, and strict uniform automation for AI
  agents.
- Define observable requirements for single `CI` status, composite-action reuse,
  strict language gates, baseline source-truth enforcement, Markdown/GitHub
  Actions safety, required Product Evidence, dependency review, Dependabot
  coverage, no internal `@main` action drift, and least-privilege workflow
  permissions.
- Document the shared action architecture, release tag model, public `.github`
  plus private `alphaapps-docs` boundary, repo-local Dependabot model, and why
  policy actions must be self-contained.
- Update Product Evidence source-truth wording to match the approved upstream
  required-baseline policy.

#### 2. Parent Product Evidence baseline

**Files**:

- `docs/evidence/product-evidence.json`
- `docs/evidence/product-evidence-view.md`

**Changes**:

- Add `.github`'s Product Evidence manifest and generated view.
- Include product promises for shared CI status preservation, deliberate release
  tag rollout, public/private boundary safety, required baseline source truth,
  required Product Evidence, and self-validation before release.
- Generate the view using the approved `alphaapps-docs` Product Evidence
  renderer with explicit manifest/output paths; do not copy private renderer
  internals into the public `.github` repo.
- Treat missing Product Evidence as a blocking gap for this repo once the
  upstream required-baseline policy is approved.

#### 3. README source-truth and release-boundary alignment

**File**: `README.md`

**Changes**:

- Point to the repo-local source truth.
- Replace private-vault architecture wording with public-safe local docs.
- Clarify that merge to `main` does not roll out shared action changes; moving
  the released major tag such as `v1` is the rollout boundary.
- Update examples to current action tags and runtime baselines.
- Document the Dependabot cadence and nested shared-action coverage.
- Document that active ForgingAlpha repositories need approved source truth and
  Product Evidence before the strict shared policy action can pass.

#### 4. Parent self-validation

**Files**:

- `scripts/validate-github-actions.py`
- `tests/test_validate_github_actions.py`
- `.github/workflows/ci.yml`
- `.gitignore`

**Changes**:

- Add deterministic validation for workflow and composite-action contracts:
  permissions, high-risk triggers, action references, internal branch refs,
  third-party SHA pins, direct curl-to-shell patterns, and standard-check
  opt-out inputs.
- Add fixture tests for the validator.
- Run the validator and its tests from this repo's own `CI` workflow.
- Install pinned `actionlint` with checksum verification in self CI.
- Ignore Python bytecode generated by validator tests.

#### 5. Foundation strictness and pin cleanup

**Files**:

- `.github/dependabot.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/promote-branch.yml`
- `.github/workflows/release.yml`
- `actions/ci-astro/action.yml`
- `actions/ci-elixir/action.yml`
- `actions/ci-rust/action.yml`
- `actions/ci-shell/action.yml`
- `actions/ci-typescript/action.yml`
- `actions/dependabot-automerge/action.yml`

**Changes**:

- Refresh existing external action references to current checked releases and
  full SHAs.
- Replace existing internal shared-action `@main` refs with released `@v1`
  refs.
- Tighten ShellCheck default severity to `style` and run local ShellCheck
  directly.
- Remove TypeScript and Astro inputs that can skip standard checks.
- Correct this control-plane repo's self-CI triggers to `main`.
- Require release-tag movement to verify the tagged commit's `CI` check.
- Expand this repo's Dependabot GitHub Actions coverage to both `/` and
  `/actions/*`.

### Success Criteria

#### Automated Verification

- [x] GitHub Actions contract validator passes:
  `python3 scripts/validate-github-actions.py`
- [x] Validator tests pass: `python3 -m unittest discover -s tests`
- [x] YAML/action files remain parseable:
  `find actions -name action.yml -print -exec python3 -c 'import yaml,sys; yaml.safe_load(open(sys.argv[1]))' {} \;`
- [x] Parent workflow lint passes with pinned actionlint and checksum
  verification.
- [x] Markdown lint passes for changed Markdown:
  `ALPHAAPPS_MARKDOWNLINT_CONFIG=<approved-config-path>; npx --yes markdownlint-cli2@0.22.1 --config "$ALPHAAPPS_MARKDOWNLINT_CONFIG" README.md docs/intent.md docs/requirements.md docs/architecture.md docs/evidence/product-evidence-view.md docs/plans/shared-ci-policy-baseline.md`
- [x] Product Evidence view is current after generation with the approved
  `alphaapps-docs` renderer.
- [x] Git diff whitespace check passes: `git diff --check`
- [x] Public disclosure sweep passes:
  `mapfile -t changed < <({ git diff --name-only --diff-filter=ACMR HEAD -- README.md docs actions .github; git ls-files --others --exclude-standard -- README.md docs actions .github; } | sort -u); ((${#changed[@]} == 0)) || ! rg '[/]home/[^ ]+|~[/]wt|[D]OPPLER|[P]RIVATE KEY|[G]ITHUB_FORGINGALPHA|[B]EGIN [A-Z ]*[P]RIVATE KEY' "${changed[@]}"`
- [x] No internal `@main` shared-action refs remain:
  `! rg 'ForgingAlpha/.github/actions/.+@main' actions .github README.md`
- [x] Dependabot config parses and covers `/` plus `/actions/*`.
- [x] `.github` source truth and Product Evidence wording matches the approved
  alphaapps-docs required-baseline policy.
- [x] Full-suite phase-close gate passes: `.github` self CI-equivalent command
  set above.
- [x] Push-equivalent proof passes: same as `.github` self CI-equivalent
  command set.
- [x] Customer/web suite: `n/a - control-plane foundation only; no customer/web
  surface changed`.

#### Test Durability

- [x] Validator tests are durable contract tests for the parent CI safety
  contract.
- [x] Assertions include clear failure messages.
- [x] No retirement tests are introduced.

#### Manual Verification

- [x] Operator approves or confirms source-truth status as `approved`.
- [x] Operator confirms Product Evidence is required for active ForgingAlpha
  repos and `.github` has no repo-specific waiver.
- [x] Confirm docs do not invent product behavior for consuming repos beyond
  the agreed shared CI policy.
- [x] Confirm public `.github` docs contain no local paths, secrets, private
  branch diagnostics, or private repo evidence that belongs in `alphaapps-docs`.

#### Plan Alignment Verification

- [x] Source truth exists before reusable policy enforcement is introduced.
- [x] Required Product Evidence exists before reusable policy enforcement is
  introduced.
- [x] No private token or per-repo secret rollout is introduced.
- [x] Completed foundation items are not duplicated in later phases.

#### Agent Review Gates

- [x] `reviewer-plan-compliance` - verify Phase 1 matches this rebaselined
  foundation scope.
- [x] `reviewer-product-development-lifecycle` - verify changed lifecycle
  source truth, the active plan, and review evidence freshness.
- [x] `reviewer-definition-traceability` - verify source truth is derived from
  README and Alpha Apps Git/GitHub process, not from implementation convenience.
- [x] `reviewer-product-evidence` - verify `.github` Product Evidence promises,
  evidence statuses, and generated view honesty.
- [x] `reviewer-knowledgebase-integrity` - verify docs live in the right repo
  and do not duplicate vault-only process docs unnecessarily.
- [x] `reviewer-naming-sweep` - verify action, status, and artifact names match
  Alpha Apps naming conventions.
- [x] `reviewer-test-discipline` - verify validator tests cover the new
  deterministic safety contract.
- [x] `reviewer-reuse-patterns` - verify validator/workflow changes reuse local
  action and test patterns.
- [x] `reviewer-test-runtime-isolation` - verify self-CI/test execution remains
  isolated and does not depend on private runtime state.
- [x] `reviewer-security-general` - verify public action/workflow changes do not
  create secret, pinning, permission, or injection risks.
- [x] `reviewer-error-handling` - waived for Phase 1 unless Elixir code changes;
  the current reviewer is Elixir/CQRS-specific and does not provide meaningful
  Python/Bash/YAML failure-output review.
- [x] `reviewer-code-quality` - verify validator and workflow changes are
  maintainable and scoped.
- [x] `reviewer-performance-efficiency` - verify validator scans are bounded
  and avoid obviously wasteful traversal.
- [x] `reviewer-greenfield-scope` - verify the new baseline docs do not carry
  legacy exceptions or compatibility shims.

#### Reviewer Execution Plan

- **Preflight**: verify listed reviewers exist in `alphaapps-docs/system/agents/_INDEX.md`
  and the active runtime.
- **Model policy**: use opposite-runtime reviewer agents where available; same-runtime
  fallback is reduced-independence evidence.
- **Wave 1 - phase validity**: `reviewer-plan-compliance`,
  `reviewer-product-development-lifecycle`,
  `reviewer-definition-traceability`, `reviewer-product-evidence`,
  `reviewer-test-discipline`, `reviewer-test-runtime-isolation`.
- **Wave 2 - implementation and documentation integrity**:
  `reviewer-knowledgebase-integrity`, `reviewer-naming-sweep`,
  `reviewer-reuse-patterns`, `reviewer-code-quality`.
- **Wave 3 - scope and efficiency discipline**: `reviewer-greenfield-scope`,
  `reviewer-performance-efficiency`, `reviewer-security-general`.
- **Concurrency**: default two reviewers at a time; hard cap four.
- **Escalations**: policy-source disputes route to `web-search-researcher` or
  `github-researcher` only when current external evidence is needed, using the
  reviewer escalation evidence standard above.

**Implementation Note**: Commit Phase 1 after automated checks and reviewer
gates pass. Do not tag/release `v1` from this foundation commit.

#### Phase 1 Close Receipt

- **Status**: implementation complete; do not push until the lifecycle audit is
  refreshed against the post-receipt commit.
- **Foundation content checkpoint**:
  `e4b75fd30548b00c0f2a995b395a9c5c904caae3`.
- **Definition sources loaded**: `docs/intent.md`, `docs/requirements.md`,
  `docs/architecture.md`, `README.md`, Alpha Apps Git/GitHub process notes,
  Product Evidence renderer contract, lifecycle baseline validator contract,
  durable evidence reference validator contract.
- **Operator decisions applied**: source-truth docs are `status: approved`;
  Product Evidence is required for every active ForgingAlpha repo; a missing
  Product Evidence manifest blocks ordinary work; `.github` has no
  repo-specific Product Evidence waiver; ShellCheck default severity remains
  the strict `style` setting.
- **Automated proof**: the Phase 1 closeout command set passed on 2026-06-30:
  GitHub Actions contract validator, validator unit tests, action YAML parsing,
  pinned actionlint `v1.7.12` with checksum verification, markdownlint-cli2
  `0.22.1` with the approved Alpha Apps config, Product Evidence render
  `--check`, `git diff --check`, public-disclosure sweep, internal `@main`
  shared-action sweep, Dependabot `/` plus `/actions/*` coverage assertion, and
  ShellCheck `0.11.0` availability at `style` severity.
- **Corrections during closeout**: Product Evidence rows were narrowed to avoid
  overclaiming coverage, validator tests added remote script-execution
  fixtures and WHAT/WHY/HOW assertion messages, docs tags were normalized to
  canonical `topic/github`, the stale handoff Product Evidence wording was
  corrected, and `ci-shell` now fails fast when ShellCheck is absent while
  reusing one tracked shell-file list for ShellCheck and `bash -n`.
- **Reviewer proof**: all Phase 1 reviewers passed after reruns, with
  `reviewer-error-handling` waived because no Elixir code changed.
- **Reduced-independence note**: same-runtime reviewer fallback was used as
  reduced-independence evidence.
- **Lifecycle audit handling**: the existing lifecycle audit passed against the
  foundation checkpoint. Because this receipt changes the active lifecycle plan,
  refresh `docs/audits/2026-06-30-product-lifecycle-review-shared-policy-baseline.md`
  against the post-receipt Head SHA before push.

---

## Phase 2: Add Alpha Apps Policy Composite Action

### Overview

Add the public, self-contained parent action that enforces Alpha Apps baseline
source-truth policy, durable-reference policy, and required Product Evidence
validation for active ForgingAlpha repositories.

### Changes Required

#### 1. Policy action metadata

**File**: `actions/ci-alphaapps-policy/action.yml`

**Changes**:

- Add inputs:
  - `product-lifecycle`: `required | off`, default `required`.
  - `durable-evidence-references`: `required | off`, default `required`.
  - `base-ref`: default `auto`.
  - `repo-kind`: `auto | code | control-plane`, default `auto`.
- Do not expose a normal `product-evidence` opt-out input. Product Evidence is
  required when the policy action runs. Bounded operator waivers belong in
  repo-local/source-truth instructions, not in the shared action's default
  contract.
- Run scripts from `$GITHUB_ACTION_PATH/scripts`.
- Fail closed for invalid input values.
- Emit WHAT/WHY/HOW failure output.

#### 2. Baseline lifecycle validator

**Files**:

- `actions/ci-alphaapps-policy/scripts/validate_product_lifecycle_baseline.py`
- `actions/ci-alphaapps-policy/tests/test_validate_product_lifecycle_baseline.py`

**Changes**:

- Enforce approved `docs/intent.md`, `docs/requirements.md`, and
  `docs/architecture.md`.
- Allow only definition/backfill paths while the baseline is missing,
  malformed, or `status: provisional`.
- Detect active ForgingAlpha repos by remote URL first, path second.
- Use repo-aware base-ref selection: `main` for control-plane repos, `dev` for
  code repos unless overridden.
- Preserve the approved/provisional frontmatter contract.
- Keep lifecycle review evidence behavior compatible with the
  `alphaapps-docs` validator contract.

#### 3. Durable-reference validator

**Files**:

- `actions/ci-alphaapps-policy/scripts/validate_durable_evidence_references.py`
- `actions/ci-alphaapps-policy/tests/test_validate_durable_evidence_references.py`

**Changes**:

- Reject plan, phase, PR, handoff, and audit citations as durable rationale in
  code comments, docstrings, and assertion messages.
- Ignore execution-artifact folders such as `docs/plans`, `docs/handoffs`,
  `docs/audits`, and `docs/research`.
- Support Elixir, Rust, TypeScript/JavaScript, shell, Python, and common
  source suffixes.

#### 4. Required Product Evidence validator

**Files**:

- `actions/ci-alphaapps-policy/scripts/validate_product_evidence.py`
- `actions/ci-alphaapps-policy/tests/test_validate_product_evidence.py`

**Changes**:

- Require `docs/evidence/product-evidence.json` for ordinary code, test,
  dependency, runtime, maintenance, release, and broad planning changes.
- Allow source-truth/evidence-backfill-only changes that create or repair
  required Product Evidence artifacts when the manifest is missing.
- Validate lean Product Evidence schema and status taxonomy.
- Require the generated view to be current when
  `docs/evidence/product-evidence-view.md` exists.
- Fail when the generated view exists without a manifest.

### Success Criteria

#### Automated Verification

- [x] Unit tests for policy scripts pass:
  `python3 -m unittest discover -s actions/ci-alphaapps-policy/tests`
- [x] Action YAML parses:
  `python3 -c 'import yaml; yaml.safe_load(open("actions/ci-alphaapps-policy/action.yml"))'`
- [x] Local fixture repos prove:
  - approved baseline passes;
  - missing baseline plus code change fails;
  - missing baseline plus definition-only change passes;
  - provisional baseline plus code change fails;
  - durable plan citation in source comments fails;
  - missing Product Evidence plus ordinary changes fails;
  - missing Product Evidence plus source-truth/evidence-backfill-only changes
    passes;
  - malformed Product Evidence fails.
- [x] Parent workflow lint passes with actionlint.
- [x] Git diff whitespace check passes: `git diff --check`
- [x] Full-suite phase-close gate passes:
  `.github` self CI-equivalent plus the new policy action tests.
- [x] Push-equivalent proof passes: same as full-suite phase-close gate.
- [x] Customer/web suite: `n/a - control-plane CI action only`.

#### Test Durability

- [x] New tests are durable contract tests for parent CI enforcement.
- [x] Assertions include WHAT/WHY/HOW-style failure messages.
- [x] No retirement tests are introduced.

#### Manual Verification

- [x] Confirm public `.github` action content contains no private repository
  secrets, tokens, or non-public operational details.
- [x] Confirm the action does not require consuming repos to configure a
  private `alphaapps-docs` checkout token.
- [x] Confirm there is no normal Product Evidence opt-out path in the shared
  action contract.

#### Plan Alignment Verification

- [x] The action remains self-contained.
- [x] Product Evidence is required by default for active ForgingAlpha repos.
- [x] The action preserves a single caller job status named `CI`.
- [x] No language-specific checks are weakened.

#### Agent Review Gates

- [x] `reviewer-plan-compliance`
- [x] `reviewer-definition-traceability`
- [x] `reviewer-product-development-lifecycle`
- [x] `reviewer-product-evidence`
- [x] `reviewer-reuse-patterns`
- [x] `reviewer-test-discipline`
- [x] `reviewer-error-handling` - waived unless Elixir code changes; the
  current reviewer is Elixir/CQRS-specific.
- [x] `reviewer-code-quality`
- [x] `reviewer-performance-efficiency`
- [x] `reviewer-test-runtime-isolation`
- [x] `reviewer-security-general`
- [x] `reviewer-greenfield-scope`

#### Reviewer Execution Plan

- **Preflight**: verify reviewer availability in `system/agents/_INDEX.md` and
  active runtime.
- **Model policy**: opposite-runtime reviewers preferred; same-runtime fallback
  must be recorded as reduced independence.
- **Wave 1 - phase validity**: `reviewer-plan-compliance`,
  `reviewer-product-development-lifecycle`,
  `reviewer-definition-traceability`, `reviewer-product-evidence`,
  `reviewer-test-discipline`, `reviewer-test-runtime-isolation`.
- **Wave 2 - implementation hygiene**: `reviewer-reuse-patterns`,
  `reviewer-code-quality`, `reviewer-performance-efficiency`.
- **Wave 3 - domain specialists**: `reviewer-security-general`,
  `reviewer-greenfield-scope`.
- **Concurrency**: default two reviewers at a time; hard cap four.
- **Escalations**: unresolved dependency on private-repo policy source routes to
  operator decision; current GitHub behavior questions route to
  `web-search-researcher` and, when design/prior-art validation is relevant,
  `github-researcher`, using the reviewer escalation evidence standard above.

**Implementation Note**: Commit Phase 2 after policy action tests and reviewer
gates pass.

#### Phase 2 Close Receipt

- **Status**: implementation complete; do not push until lifecycle review
  evidence is refreshed against the post-receipt commit.
- **Implemented files**:
  - `actions/ci-alphaapps-policy/action.yml`
  - `actions/ci-alphaapps-policy/scripts/validate_product_lifecycle_baseline.py`
  - `actions/ci-alphaapps-policy/scripts/validate_durable_evidence_references.py`
  - `actions/ci-alphaapps-policy/scripts/validate_product_evidence.py`
  - `actions/ci-alphaapps-policy/tests/test_validate_product_lifecycle_baseline.py`
  - `actions/ci-alphaapps-policy/tests/test_validate_durable_evidence_references.py`
  - `actions/ci-alphaapps-policy/tests/test_validate_product_evidence.py`
  - `.github/workflows/ci.yml`
  - `README.md`
  - `docs/evidence/product-evidence.json`
  - `docs/evidence/product-evidence-view.md`
- **Contract decisions applied**: the public action is self-contained; it runs
  bundled scripts from `$GITHUB_ACTION_PATH/scripts`; `product-lifecycle` and
  `durable-evidence-references` can be `required` or `off`; there is no normal
  Product Evidence opt-out input; Product Evidence is required when the action
  runs; invalid action inputs emit WHAT/WHY/HOW diagnostics.
- **Validator proof**: lifecycle baseline validation enforces approved
  `docs/intent.md`, `docs/requirements.md`, and `docs/architecture.md`, allows
  only missing-file definition/backfill work before approval, rejects malformed
  or unsupported-status baselines, and mirrors the approved leading-comment and
  diagnostic-redaction frontmatter behavior. Durable-reference validation scans
  tracked source files by default and rejects plan, phase, PR, handoff, and
  audit citations in durable comments, docstrings, tags, and assertion
  messages. Product Evidence validation requires the manifest for ordinary
  active-repo work, allows source-truth/evidence creation or repair, rejects
  deletion of required evidence artifacts, validates the lean manifest schema,
  and checks generated view freshness.
- **Automated proof**: the Phase 2 closeout command set passed on 2026-06-30:
  `python3 -m unittest discover -s actions/ci-alphaapps-policy/tests` (23
  tests), action YAML parse, `.github` contract validator, parent validator
  tests, all three policy validators on this repo, action metadata YAML parse
  sweep, Python bytecode compile, pinned actionlint `v1.7.12` with checksum
  verification, markdownlint-cli2 `0.22.1` with the approved Alpha Apps config,
  Product Evidence render `--check`, `git diff --check`, internal `@main`
  shared-action sweep, Dependabot `/` plus `/actions/*` coverage assertion, and
  public-disclosure sweep with local `docs/handoffs/` resume context excluded
  from the intended commit set.
- **Reviewer proof**: all Phase 2 reviewer gates passed after reruns:
  `reviewer-plan-compliance`, `reviewer-definition-traceability`,
  `reviewer-product-development-lifecycle`, `reviewer-product-evidence`,
  `reviewer-reuse-patterns`, `reviewer-test-discipline`,
  `reviewer-code-quality`, `reviewer-performance-efficiency`,
  `reviewer-test-runtime-isolation`, `reviewer-security-general`, and
  `reviewer-greenfield-scope`. `reviewer-error-handling` is waived because no
  Elixir code changed.
- **Reduced-independence note**: same-runtime reviewer fallback was used as
  reduced-independence evidence.
- **Scope note**: `docs/handoffs/2026-06-30 12-13 shared-policy-baseline.md`
  remains local resume context and is intentionally excluded from the Phase 2
  commit.
- **Lifecycle audit handling**: because this receipt changes the active
  lifecycle plan, refresh
  `docs/audits/2026-06-30-product-lifecycle-review-shared-policy-baseline.md`
  against the post-receipt Head SHA before push.

---

## Phase 3: Add Markdown And Reusable GitHub Actions Safety Actions

### Overview

Add reusable cross-repo actions for Markdown/Obsidian linting and GitHub
Actions workflow safety so agents get consistent feedback outside any one
language ecosystem. Phase 1 already added local `.github` self-validation;
this phase extracts or wraps that contract for consumer repositories without
duplicating divergent policy.

### Changes Required

#### 1. Markdown action

**Files**:

- `actions/ci-markdown/action.yml`
- `actions/ci-markdown/scripts/changed_markdown.sh`
- `actions/ci-markdown/tests/test_ci_markdown.py`

**Changes**:

- Run pinned `npx --yes markdownlint-cli2@0.22.1`.
- Inputs:
  - `mode`: `all | changed`, default `changed`.
  - `config-path`: default `.markdownlint-cli2.yaml`.
  - `base-ref`: default `auto`.
  - `ignore`: optional newline-delimited path prefixes.
- New/clean repos should use `mode: all`.
- Legacy repos may start with `mode: changed` until cleanup.
- Fail with a clear message if the config is missing while action is enabled.

#### 2. Parent Markdown config

**File**: `.markdownlint-cli2.yaml`

**Changes**:

- Add a strict parent repo Markdown config compatible with README and docs/plans.
- Keep any Obsidian-specific exclusions explicit rather than implicit.
- Update any alphaapps-docs reference commands in the same PR or a paired
  private control-plane PR if the org Markdown lint pin moves from the previous
  documented version.

#### 3. GitHub Actions safety action

**Files**:

- `actions/ci-github-actions/action.yml`
- `actions/ci-github-actions/scripts/check_workflows.py`
- `actions/ci-github-actions/tests/test_check_workflows.py`

**Changes**:

- Reuse or wrap the Phase 1 workflow/action validator contract.
- Install pinned actionlint `v1.7.12`.
- Run actionlint against workflow files.
- Validate composite `action.yml` files as YAML.
- Scan both `.github/workflows/*.yml` and `actions/**/action.yml` for `uses:`
  references so composite-action dependencies are covered too.
- Fail broad root-level workflow permissions unless explicitly allowlisted with
  a reason.
- Flag `pull_request_target` usage unless allowlisted with a reason.
- Flag unpinned third-party action refs unless allowlisted with a reason.
- Allow local `./actions/...` and internal `ForgingAlpha/.github/actions/...@v1`
  references; fail internal `@main` references.
- Treat local `./actions/...` references as valid in `.github` self tests.
- Preserve first-party GitHub action version/SHA policy explicitly, and make
  the allowlist data-driven so stricter SHA-pinning can be rolled out without
  rewriting the checker.
- Do not reintroduce branch refs, broad permissions, standard-check opt-out
  inputs, or curl-to-shell installation patterns already blocked by the Phase 1
  self-validator.

### Success Criteria

#### Automated Verification

- [x] Markdown action tests pass:
  `python3 -m unittest discover -s actions/ci-markdown/tests`
- [x] GitHub Actions safety tests pass:
  `python3 -m unittest discover -s actions/ci-github-actions/tests`
- [x] Parent Markdown lint passes:
  `npx --yes markdownlint-cli2@0.22.1 --config .markdownlint-cli2.yaml README.md docs/**/*.md`
- [x] Parent actionlint passes through the new action.
- [x] Existing parent YAML validation still passes.
- [x] Fixture tests prove composite `action.yml` `uses:` references are scanned,
  not only workflow files.
- [x] Fixture tests prove allowlist entries require a reason.
- [x] Git diff whitespace check passes: `git diff --check`
- [x] Full-suite phase-close gate passes:
  `.github` self CI-equivalent plus new action tests.
- [x] Push-equivalent proof passes: same as full-suite phase-close gate.
- [x] Customer/web suite: `n/a - control-plane CI action only`.

#### Test Durability

- [x] New tests are durable contract tests for Markdown and workflow safety
  enforcement.
- [x] Assertions include clear failure messages.
- [x] No retirement tests are introduced.

#### Manual Verification

- [x] Review allowlists for `pull_request_target`, unpinned refs, and
  permissions exceptions; every exception must have a reason.
- [x] Confirm Markdown config does not encode alphaapps-docs-only vault rules
  that would be inappropriate for code repos.

#### Plan Alignment Verification

- [x] Markdown action is not hidden inside one language action.
- [x] GitHub Actions safety action is reusable by all repos.
- [x] No broad workflow permissions are introduced.

#### Agent Review Gates

- [x] `reviewer-plan-compliance`
- [x] `reviewer-definition-traceability`
- [x] `reviewer-reuse-patterns`
- [x] `reviewer-test-discipline`
- [x] `reviewer-error-handling` - waived unless Elixir code changes; the
  current reviewer is Elixir/CQRS-specific.
- [x] `reviewer-code-quality`
- [x] `reviewer-performance-efficiency`
- [x] `reviewer-test-runtime-isolation`
- [x] `reviewer-security-general`
- [x] `reviewer-greenfield-scope`

#### Reviewer Execution Plan

- **Preflight**: verify reviewer availability before implementation.
- **Model policy**: opposite-runtime reviewers preferred; same-runtime fallback
  must be recorded as reduced independence.
- **Wave 1 - phase validity**: `reviewer-plan-compliance`,
  `reviewer-definition-traceability`, `reviewer-test-discipline`,
  `reviewer-test-runtime-isolation`.
- **Wave 2 - implementation hygiene**: `reviewer-reuse-patterns`,
  `reviewer-code-quality`, `reviewer-performance-efficiency`.
- **Wave 3 - domain specialists**: `reviewer-security-general`,
  `reviewer-greenfield-scope`.
- **Concurrency**: default two reviewers at a time; hard cap four.
- **Escalations**: actionlint or GitHub workflow behavior uncertainty routes to
  `web-search-researcher` and, when workflow-design prior art is relevant,
  `github-researcher`, using the reviewer escalation evidence standard above.

**Implementation Note**: Commit Phase 3 after deterministic checks and reviewer
gates pass.

#### Phase 3 Close Receipt

- **Status**: implementation complete; do not push until lifecycle review
  evidence is refreshed against the post-receipt commit.
- **Implemented files**:
  - `.markdownlint-cli2.yaml`
  - `actions/ci-markdown/action.yml`
  - `actions/ci-markdown/scripts/changed_markdown.sh`
  - `actions/ci-markdown/tests/test_ci_markdown.py`
  - `actions/ci-github-actions/action.yml`
  - `actions/ci-github-actions/scripts/check_workflows.py`
  - `actions/ci-github-actions/tests/test_check_workflows.py`
  - `.github/workflows/ci.yml`
  - `scripts/validate-github-actions.py`
  - `README.md`
  - `docs/evidence/product-evidence.json`
  - `docs/evidence/product-evidence-view.md`
- **Contract decisions applied**: `ci-markdown` runs pinned
  `markdownlint-cli2@0.22.1`, defaults to `mode: changed`, supports `mode:
  all`, requires an explicit Markdown config, uses the existing pinned
  `actions/setup-node` pattern, and enumerates tracked Markdown files instead
  of filesystem globs. `ci-github-actions` runs pinned actionlint `v1.7.12`
  with checksum verification and reuses the Phase 1 validator contract through
  `actions/ci-github-actions/scripts/check_workflows.py`; the parent
  `scripts/validate-github-actions.py` remains as a compatibility wrapper.
- **Manual proof**: the allowlist review found no active
  `pull_request_target`, unpinned-ref, or broad-permission exceptions in this
  change. The parent `.markdownlint-cli2.yaml` is repo-generic and explicit;
  it does not import alphaapps-docs-only Obsidian/vault defaults.
- **Automated proof**: the Phase 3 closeout command set passed on 2026-06-30:
  `python3 scripts/validate-github-actions.py`, `python3 -m unittest discover
  -s tests` (11 tests), `python3 -m unittest discover -s
  actions/ci-alphaapps-policy/tests` (23 tests), `python3 -m unittest discover
  -s actions/ci-markdown/tests` (10 tests), `python3 -m unittest discover -s
  actions/ci-github-actions/tests` (9 tests), all three Alpha Apps policy
  validators, parent Markdown lint with `markdownlint-cli2@0.22.1`, action
  metadata YAML parse sweep, Python bytecode compile, pinned actionlint
  `v1.7.12` with checksum verification, Product Evidence render `--check`,
  `git diff --check`, internal `@main` shared-action sweep, and public
  disclosure sweep with local `docs/handoffs/` resume context excluded from the
  intended commit set.
- **Reviewer proof**: Phase 3 reviewers passed after reruns:
  `reviewer-definition-traceability`, `reviewer-reuse-patterns`,
  `reviewer-test-discipline`, `reviewer-code-quality`,
  `reviewer-performance-efficiency`, `reviewer-test-runtime-isolation`,
  `reviewer-security-general`, `reviewer-greenfield-scope`, and
  `reviewer-plan-compliance`.
  `reviewer-error-handling` is waived because no Elixir code changed.
- **Reduced-independence note**: same-runtime reviewer fallback was used as
  reduced-independence evidence.
- **Scope note**: `docs/handoffs/2026-06-30 12-13 shared-policy-baseline.md`
  remains local resume context and is intentionally excluded from the Phase 3
  commit.
- **Lifecycle audit handling**: because this receipt changes the active
  lifecycle plan, refresh
  `docs/audits/2026-06-30-product-lifecycle-review-shared-policy-baseline.md`
  against the post-receipt Head SHA before push.

---

## Phase 4: Add Dependency Review And Dependabot Coverage

### Overview

Add the remaining dependency safety surfaces: a pull-request dependency-review
wrapper for newly introduced vulnerable dependencies, and a deterministic
Dependabot coverage validator plus templates. ShellCheck strictness, existing
action pin refresh, and existing `@main` to `@v1` cleanup are part of the
Phase 1 foundation and are not repeated here.

### Changes Required

#### 1. Dependency review action

**Files**:

- `actions/ci-dependency-review/action.yml`
- `actions/ci-dependency-review/tests/test_ci_dependency_review.py`

**Changes**:

- Wrap GitHub's official dependency-review action for PRs.
- Inputs:
  - `enabled`: default `true`.
  - `fail-on-severity`: default `low`.
  - `fail-on-scopes`: default `runtime,development,unknown`.
  - `allow-licenses`: optional.
  - `deny-licenses`: avoid by default because the official action marks it as
    deprecated; use only for a documented repo-specific reason.
  - `allow-dependencies-licenses`: optional.
- Skip cleanly outside `pull_request` events with an explanatory message.
- Document that Rust keeps `cargo audit` in addition to dependency review.

#### 2. Dependabot coverage standard and validator

**Files**:

- `actions/ci-dependabot-coverage/action.yml`
- `actions/ci-dependabot-coverage/scripts/check_dependabot_coverage.py`
- `actions/ci-dependabot-coverage/tests/test_check_dependabot_coverage.py`
- `templates/dependabot/README.md`
- `templates/dependabot/*.yml`
- `.github/dependabot.yml`

**Changes**:

- Add a public template set for common repo classes:
  - GitHub Actions only;
  - Rust/Cargo plus GitHub Actions;
  - npm/Astro/TypeScript plus GitHub Actions;
  - Elixir/Mix plus GitHub Actions;
  - mixed app repos with nested npm assets;
  - optional Python dependency manifests.
- Add a deterministic coverage validator that detects obvious dependency
  surfaces:
  - `.github/workflows/*.yml` and `.github/workflows/*.yaml`;
  - nested composite action manifests such as `actions/*/action.yml` and
    `.github/actions/*/action.yml`;
  - `Cargo.toml`;
  - `package.json`;
  - `mix.exs`;
  - `requirements.txt`, `pyproject.toml`, or `Pipfile`.
- Fail or report when `.github/dependabot.yml` is missing coverage for a
  detected surface.
- Support explicit repo-local ignore comments or configuration only when a
  dependency surface is intentionally unmanaged and the reason is documented.
- Use `directories` for repo classes with multiple manifest directories rather
  than duplicating update blocks unnecessarily.
- Keep the root `.github` repo's Dependabot config covering `/` and
  `/actions/*` so both workflow files and shared composite action manifests are
  updateable.
- Document that Dependabot does not update hardcoded versions in shell commands
  or scripts; those require separate validation or audit coverage when part of
  the public contract.

### Success Criteria

#### Automated Verification

- [x] Dependency review wrapper tests pass:
  `python3 -m unittest discover -s actions/ci-dependency-review/tests`
- [x] Dependabot coverage validator tests pass:
  `python3 -m unittest discover -s actions/ci-dependabot-coverage/tests`
- [x] Fixture tests prove missing Dependabot config fails when workflows,
  action manifests, Cargo, npm, Mix, or Python manifests are present.
- [x] Fixture tests prove nested composite action manifests require matching
  GitHub Actions directory coverage.
- [x] Fixture tests prove intentionally unmanaged dependency surfaces require a
  documented reason.
- [x] Parent actionlint passes.
- [x] Git diff whitespace check passes: `git diff --check`
- [x] Full-suite phase-close gate passes:
  `.github` self CI-equivalent plus new/updated action tests.
- [x] Push-equivalent proof passes: same as full-suite phase-close gate.
- [x] Customer/web suite: `n/a - control-plane CI action only`.

#### Test Durability

- [x] New tests are durable contract tests for dependency review and Dependabot
  coverage behavior.
- [x] Assertions include clear messages.
- [x] No retirement tests are introduced.

#### Manual Verification

- [x] Confirm dependency-review severity aligns with the org security posture.
- [x] Confirm the Dependabot templates cover the known ForgingAlpha repo
  classes without forcing ecosystems that are not present.

#### Plan Alignment Verification

- [x] Dependency review does not replace language-specific checks.
- [x] Dependabot validation reports missing update coverage; it does not
  replace dependency review or language-specific audit tools.

#### Agent Review Gates

- [x] `reviewer-plan-compliance`
- [x] `reviewer-definition-traceability`
- [x] `reviewer-reuse-patterns`
- [x] `reviewer-test-discipline`
- [x] `reviewer-error-handling` - waived unless Elixir code changes; the
  current reviewer is Elixir/CQRS-specific.
- [x] `reviewer-code-quality`
- [x] `reviewer-performance-efficiency`
- [x] `reviewer-test-runtime-isolation`
- [x] `reviewer-security-general`
- [x] `reviewer-greenfield-scope`

#### Reviewer Execution Plan

- **Preflight**: verify reviewer availability before implementation.
- **Model policy**: opposite-runtime reviewers preferred; same-runtime fallback
  must be recorded as reduced independence.
- **Wave 1 - phase validity**: `reviewer-plan-compliance`,
  `reviewer-definition-traceability`, `reviewer-test-discipline`,
  `reviewer-test-runtime-isolation`.
- **Wave 2 - implementation hygiene**: `reviewer-reuse-patterns`,
  `reviewer-code-quality`, `reviewer-performance-efficiency`.
- **Wave 3 - domain specialists**: `reviewer-security-general`,
  `reviewer-greenfield-scope`.
- **Concurrency**: default two reviewers at a time; hard cap four.
- **Escalations**: dependency-review policy questions route to
  `web-search-researcher`; shell portability disputes route to
  `github-researcher` only if mature CI prior art is needed; both follow the
  reviewer escalation evidence standard above.

**Implementation Note**: Commit Phase 4 after deterministic checks and reviewer
gates pass.

#### Phase 4 Close Receipt

- **Status**: implementation complete. Do not push until lifecycle review
  evidence is refreshed against the post-receipt commit.
- **Implemented files**:
  - `actions/ci-dependency-review/action.yml`
  - `actions/ci-dependency-review/tests/test_ci_dependency_review.py`
  - `actions/ci-dependabot-coverage/action.yml`
  - `actions/ci-dependabot-coverage/scripts/check_dependabot_coverage.py`
  - `actions/ci-dependabot-coverage/tests/test_check_dependabot_coverage.py`
  - `templates/dependabot/README.md`
  - `templates/dependabot/*.yml`
  - `.github/workflows/ci.yml`
  - `README.md`
  - `docs/evidence/product-evidence.json`
  - `docs/evidence/product-evidence-view.md`
  - `docs/plans/shared-ci-policy-baseline.md`
- **Definition sources loaded**: `docs/intent.md`, `docs/requirements.md`,
  `docs/architecture.md`, Product Evidence view, and the Phase 4 context
  packet in this plan.
- **Contract decisions applied**: `ci-dependency-review` wraps GitHub's
  official `actions/dependency-review-action@v5` only on pull requests, keeps
  `fail-on-severity: low`, extends scopes to
  `runtime,development,unknown`, leaves deprecated `deny-licenses` empty by
  default, and documents that Rust/Cargo audit remains additive. The official
  action defaults and deprecation note were checked during Phase 4 before
  choosing these defaults. `ci-dependabot-coverage` detects the planned
  workflow, composite-action, Cargo, npm, Mix, and Python surfaces, accepts
  `fail` or `report`, and restricts `config-path` to canonical
  `.github/dependabot.yml` or `.github/dependabot.yaml` so the check cannot
  pass against a non-Dependabot file.
- **Template proof**: the public templates cover GitHub Actions-only, Rust,
  npm/Astro/TypeScript, Elixir/Mix, mixed nested npm, and Python repo shapes
  without forcing absent ecosystems; consumers delete blocks for surfaces that
  do not exist. Hardcoded versions in shell commands or scripts are documented
  as requiring separate validation or audit coverage when part of the public
  contract.
- **Manual proof**: dependency-review severity `low` is the strictest
  supported severity threshold and matches the approved strict-by-default
  security posture. The template set covers the known ForgingAlpha repo
  classes without requiring unavailable ecosystems.
- **Automated proof**: the Phase 4 closeout command set passed on
  2026-06-30: `python3 scripts/validate-github-actions.py`,
  `python3 -m unittest discover -s tests` (11 tests),
  `python3 -m unittest discover -s actions/ci-alphaapps-policy/tests` (23
  tests), `python3 -m unittest discover -s actions/ci-markdown/tests` (10
  tests), `python3 -m unittest discover -s actions/ci-github-actions/tests`
  (9 tests), `python3 -m unittest discover -s
  actions/ci-dependency-review/tests` (4 tests), `python3 -m unittest
  discover -s actions/ci-dependabot-coverage/tests` (9 tests), Dependabot
  coverage validation, durable evidence reference validation, Product Evidence
  validation, Product Evidence render `--check`, parent Markdown lint with
  `markdownlint-cli2@0.22.1`, action/template/workflow YAML parse sweep,
  Python bytecode compile, pinned actionlint `v1.7.12` with checksum
  verification, `git diff --check`, internal `@main` shared-action sweep on
  runtime/public surfaces, and targeted public-disclosure sweep.
- **Reviewer proof**: Phase 4 reviewers passed after fixes and reruns:
  `reviewer-plan-compliance`, `reviewer-definition-traceability`,
  `reviewer-reuse-patterns`, `reviewer-test-discipline`,
  `reviewer-code-quality`, `reviewer-performance-efficiency`,
  `reviewer-test-runtime-isolation`, `reviewer-security-general`, and
  `reviewer-greenfield-scope`. `reviewer-error-handling` is waived because no
  Elixir code changed.
- **Reviewer findings fixed**: dependency-review test rationale no longer cites
  Phase 4 as durable authority; README/template hardcoded-version wording no
  longer relies on reviewer closeout; Dependabot fallback discovery prunes
  generated dependency trees; unmanaged-surface comments reject whitespace-only
  reasons; CI dogfoods `./actions/ci-dependabot-coverage`; coverage action
  inputs emit WHAT/WHY/HOW diagnostics before Python; `config-path` is
  restricted to canonical Dependabot config paths.
- **Reduced-independence note**: same-runtime reviewer fallback was used as
  reduced-independence evidence.
- **Scope note**: `docs/handoffs/2026-06-30 12-13
  shared-policy-baseline.md` remains local resume context and is intentionally
  excluded from the Phase 4 commit.
- **Lifecycle audit handling**: because this receipt changes the active
  lifecycle plan, refresh
  `docs/audits/2026-06-30-product-lifecycle-review-shared-policy-baseline.md`
  against the post-receipt Head SHA before push.

---

## Phase 5: Wire Standard Checks And Update Public Contract

### Overview

Dogfood the new shared checks in `.github` and update the public README so
consuming repos have one canonical strict CI shape. Phase 1 already corrected
the control-plane trigger shape, refreshed existing pins, and aligned source
truth; this phase wires only the new reusable actions that earlier phases add.

### Changes Required

#### 1. Parent CI dogfood

**File**: `.github/workflows/ci.yml`

**Changes**:

- Keep `permissions: contents: read`.
- Preserve the Phase 1 control-plane trigger shape:
  `push: [main]` and `pull_request: [main]`.
- Call local paths for the new shared actions created in earlier phases:
  - `./actions/ci-github-actions`
  - `./actions/ci-markdown`
  - `./actions/ci-alphaapps-policy`
  - `./actions/ci-dependabot-coverage`
  - `./actions/ci-shell` if shell scripts are present
- Preserve local `./actions/ci-merge-flow` dogfood.
- Avoid remote `@v1` calls for branch-local self validation.

#### 2. Language composite wiring

**Files**:

- `actions/ci-rust/action.yml`
- `actions/ci-elixir/action.yml`
- `actions/ci-astro/action.yml`
- `actions/ci-typescript/action.yml`
- `actions/ci-shell/action.yml`

**Changes**:

- Leave the existing `ci-merge-flow@v1` step in place.
- Add new cross-cutting checks in a consistent order after merge-flow:
  1. `ci-alphaapps-policy@v1`
  2. `ci-markdown@v1`
  3. `ci-github-actions@v1` when workflow/action files changed or when
     explicitly enabled
  4. `ci-dependabot-coverage@v1`
  5. `ci-dependency-review@v1` for code/package repos on PRs
  6. language-specific checks
- Preserve one caller job named `CI`.
- Add inputs only where a consuming repo needs controlled rollout, such as
  Markdown `mode`.

#### 3. README and examples

**File**: `README.md`

**Changes**:

- Add the new actions to the composite-action table.
- Preserve the already-updated source-truth and release-tag wording.
- Show canonical code repo and control-plane repo workflow examples.
- Document strict defaults:
  - ShellCheck severity `style`.
  - Markdown `all` for new/clean repos and `changed` for legacy repos.
  - Product Evidence required for active ForgingAlpha repos.
  - Dependabot coverage validation for detected dependency surfaces.
  - Dependency review on PRs for code repos.
  - `permissions: contents: read` unless a job requires elevation.
- Document rollout warning: moving `v1` after language composite wiring will
  enforce baseline docs and Product Evidence in consuming repos.

### Success Criteria

#### Automated Verification

- [x] Parent CI-equivalent command passes locally.
- [x] New local actions run successfully from `.github/workflows/ci.yml`.
- [x] Parent Dependabot coverage validation passes for workflow files and
  nested shared composite action manifests.
- [x] `.github/workflows/ci.yml` uses the control-plane trigger shape:
  `push` to `main` and `pull_request` to `main`.
- [x] README examples parse as valid YAML snippets where practical.
- [x] Parent Markdown lint passes.
- [x] Parent actionlint passes.
- [x] No internal `@main` shared-action refs remain after adding the new
  cross-cutting action calls.
- [x] Git diff whitespace check passes: `git diff --check`
- [x] Full-suite phase-close gate passes: all available `.github` tests and
  self CI-equivalent checks.
- [x] Push-equivalent proof passes: same as full-suite phase-close gate.
- [x] Customer/web suite: `n/a - control-plane CI action only`.

#### Test Durability

- [x] New/changed tests are durable contract tests.
- [x] No retirement tests are introduced.

#### Manual Verification

- [x] Operator decides whether to tag/release `v1` immediately or wait for
  active repo baseline and Product Evidence backfill.
- [x] Operator confirms language composite wiring should enforce baseline policy
  across consuming repos.

#### Plan Alignment Verification

- [x] README accurately describes what CI enforces.
- [x] `.github` dogfoods the same checks it publishes.
- [x] No extra org-wide standards outside this plan were added.

#### Agent Review Gates

- [x] `reviewer-plan-compliance`
- [x] `reviewer-definition-traceability`
- [x] `reviewer-product-development-lifecycle`
- [x] `reviewer-product-evidence`
- [x] `reviewer-reuse-patterns`
- [x] `reviewer-test-discipline`
- [x] `reviewer-error-handling` - waived unless Elixir code changes; the
  current reviewer is Elixir/CQRS-specific.
- [x] `reviewer-code-quality`
- [x] `reviewer-performance-efficiency`
- [x] `reviewer-test-runtime-isolation`
- [x] `reviewer-security-general`
- [x] `reviewer-knowledgebase-integrity`
- [x] `reviewer-greenfield-scope`

#### Reviewer Execution Plan

- **Preflight**: verify reviewer availability before implementation.
- **Model policy**: opposite-runtime reviewers preferred; same-runtime fallback
  must be recorded as reduced independence.
- **Wave 1 - phase validity**: `reviewer-plan-compliance`,
  `reviewer-product-development-lifecycle`,
  `reviewer-definition-traceability`, `reviewer-product-evidence`,
  `reviewer-test-discipline`, `reviewer-test-runtime-isolation`.
- **Wave 2 - implementation hygiene**: `reviewer-reuse-patterns`,
  `reviewer-code-quality`, `reviewer-performance-efficiency`.
- **Wave 3 - domain specialists**: `reviewer-security-general`,
  `reviewer-knowledgebase-integrity`, `reviewer-greenfield-scope`.
- **Concurrency**: default two reviewers at a time; hard cap four.
- **Escalations**: release-tag timing and org-wide rollout risk route to
  operator decision, with external evidence gathered under the reviewer
  escalation evidence standard above when the recommendation depends on current
  GitHub behavior or mature rollout prior art.

**Implementation Note**: Commit Phase 5 after deterministic checks and reviewer
gates pass. Do not tag/release `v1` without explicit operator approval.

### Phase Close Receipt

- **Phase**: Phase 5 - Wire Standard Checks And Update Public Contract.
- **Commit**: pending.
- **Definition Sources Loaded**: `docs/intent.md`, `docs/requirements.md`,
  `docs/architecture.md`, Product Evidence View, Phase 5 context packet, and
  Phase 5 operator decisions.
- **Phase Context Packet Loaded**: Phase 5 context packet and reviewer
  execution plan.
- **Automated Verification**: final Phase 5 proof passed on 2026-06-30:
  `python3 -m unittest discover -s tests` (17 tests), alphaapps-policy tests
  (23), markdown tests (10), GitHub Actions safety tests (9),
  dependency-review tests (4), Dependabot coverage tests (9), Dependabot
  coverage validation, GitHub Actions safety validation, Product Evidence
  validation, durable evidence reference validation, Product Evidence render
  `--check`, README/docs/template Markdown lint, action/workflow/template YAML
  parse sweep (24 YAML files), Python bytecode compile, ShellCheck plus
  `bash -n` for tracked shell scripts, pinned actionlint `v1.7.12` with
  checksum verification, `git diff --check`, runtime/public `@main` reference
  sweep, and reviewer-transport disclosure sweep.
- **Full-Suite / Push-Equivalent Proof**: the full-suite command set above is
  the push-equivalent proof for this control-plane CI action repo; customer/web
  suite is not applicable.
- **Reviewer Gates**: passed after fixes and reruns:
  `reviewer-plan-compliance`, `reviewer-definition-traceability`,
  `reviewer-product-development-lifecycle`, `reviewer-product-evidence`,
  `reviewer-reuse-patterns`, `reviewer-test-discipline`,
  `reviewer-code-quality`, `reviewer-performance-efficiency`,
  `reviewer-test-runtime-isolation`, `reviewer-security-general`,
  `reviewer-knowledgebase-integrity`, and `reviewer-greenfield-scope`.
  `reviewer-error-handling` is waived because no Elixir code changed.
- **Reviewer Findings Fixed And Rerun**: definition traceability required the
  active repo rollout decision to be recorded; code quality and test discipline
  required durable assertion rationale and stronger README/dependency ordering
  tests; performance required composite-level gating so `ci-github-actions@v1`
  and dependency review are not unnecessarily resolved; greenfield scope
  required removal of an unauthorized `skip` mode; knowledgebase integrity
  required conditional GitHub Actions safety wording and scrubbing exact
  reviewer transport failure details from public docs; code quality required
  changed-mode `git diff` handling to fail closed; performance required
  pathspec-limited workflow/action diff detection; code quality required
  explicit test lookup helpers instead of raw `next(...)` calls.
- **Reduced-Independence Fallbacks**: same-runtime reviewer fallback was used as
  reduced-independence evidence for Phase 5 reviewer gates.
- **Manual Verification**: operator confirmed waiting to move `v1` until active
  repo baseline/Product Evidence backfill is ready or explicitly approved, and
  confirmed language composites should enforce the shared baseline across
  consuming repos.
- **Plan Checkboxes Updated**: automated verification, test durability, manual
  verification, plan alignment, and all Phase 5 reviewer gates are checked.
- **Upstream Amendments / Backfills**: Product Evidence now records Phase 5
  contract-test coverage for REQ-001, REQ-003, and REQ-015. Public docs were
  aligned to the approved source-truth boundary; no intent, requirements, or
  architecture source-truth changes were made in Phase 5.

#### Deviations From Plan And Definition Sources

- **Planned**: language composites run `ci-github-actions@v1` when
  workflow/action files changed or when explicitly enabled.
- **Implemented**: language composites expose `github-actions-mode:
  changed|all`; `changed` performs a local fail-closed, pathspec-limited diff
  planner before resolving the remote action, and `all` forces the safety gate.
- **Difference**: `github-actions-mode` is a controlled implementation input
  for the plan-approved changed-file/explicit-enable behavior; no `skip` mode is
  exposed.
- **Evidence Used**: README contract, `tests/test_shared_ci_contract.py`,
  GitHub Actions safety validation, reviewer-performance-efficiency,
  reviewer-greenfield-scope, reviewer-knowledgebase-integrity, and
  reviewer-code-quality reruns.
- **Classification**: allowed implementation choice.
- **Resolution**: contract tests and README/Product Evidence now describe the
  conditional behavior precisely.

---

## Phase 6: Add Remote Diagnostic Probe Standard

### Overview

Document and template the GitHub-native remote probe pattern for failures that
only reproduce on GitHub runners or in required CI runtime. The probe is a
manual diagnostic workflow, not a merge gate. Required CI remains authoritative.

The first pilot is a private consumer-repo CI-only failure that cannot be
queried quickly from local worktrees. Public `.github` docs record the probe
safety contract only; repo-specific failure details stay in private evidence.

### Changes Required

#### 1. Remote probe README contract

**File**: `README.md`

**Changes**:

- Add a "Manual Remote Diagnostic Probes" section.
- State the probe contract:
  - `workflow_dispatch` only;
  - non-required status;
  - `permissions: contents: read`;
  - descriptive `run-name` including mode, lane, and checkout ref;
  - bounded `timeout-minutes`;
  - explicit `concurrency` group so duplicate probes are visible and controlled;
  - trusted workflow definition selected by `gh workflow run --ref <default>`;
  - target code checked out from a separate `checkout_ref` input;
  - no arbitrary shell command input;
  - typed modes such as `exact`, `file`, and `lane`;
  - artifacts uploaded with `if: always()` and short retention;
  - `GITHUB_STEP_SUMMARY` includes the exact normalized probe inputs and
    artifact path.
- Document that probes are for diagnostics and evidence collection, not merge
  permission.

#### 2. Shared probe template or helper

**Files**:

- `workflow-templates/ci-probe.yml` or
  `actions/ci-remote-probe-guard/action.yml`
- `actions/ci-remote-probe-guard/scripts/validate_probe_inputs.py` if a helper
  action is used
- `actions/ci-remote-probe-guard/tests/test_validate_probe_inputs.py` if a
  helper action is used

**Changes**:

- Provide a reusable reference implementation that consumer repos can copy, plus
  a small guard action if useful. The guard action validates and normalizes
  probe inputs; it does not own repo-specific test execution.
- Validate probe inputs before checkout-dependent execution:
  - `probe_mode`: choice-style allowlist such as `exact`, `file`, `lane`;
  - `lane`: repo-defined allowlist;
  - `file`: repo-relative path under `test/`, ending in a test suffix such as
    `.exs` for Elixir repos;
  - `line`: positive integer when required by `exact`;
  - `out_label`: safe artifact label with no path separators.
- Build commands in the consumer workflow with shell arrays and repo-owned
  `case` branches. Do not use `eval`.
- Upload probe output artifacts on success and failure.
- Set a repo-appropriate timeout. The default should be shorter than full CI
  and longer than the expected target lane runtime.
- Set artifact `retention-days` low by default because probe artifacts are
  diagnostic packets, not permanent records.
- Keep repo-specific runtime details, such as repo-owned test commands, lane
  names, and runtime environment, in the consumer repo.

#### 3. Consumer adoption note

**File**: `README.md`

**Changes**:

- Document the input schema and two-ref model without publishing concrete
  branch names, lane names, test paths, line numbers, or repo-specific command
  examples.
- State that a consumer repo must land its concrete
  `.github/workflows/ci-probe.yml` on its default/development branch before
  operators run manual probes.
- State that repo-specific invocation examples and failure evidence belong in
  the consumer repo or private evidence, not this public parent repo.

### Success Criteria

#### Automated Verification

- [x] Probe workflow/template YAML parses.
- [x] Probe input validator tests pass:
  `python3 -m unittest discover -s actions/ci-remote-probe-guard/tests` if a
  helper action is added.
- [x] Fixture tests prove invalid mode, lane, file path, line, label, and
  command-like inputs fail before command construction.
- [x] Fixture tests prove valid exact/file/lane inputs produce expected command
  output fields for the consumer workflow to assemble into arrays.
- [x] Fixture tests prove the guard action does not accept or emit arbitrary
  shell commands.
- [x] Parent actionlint passes.
- [x] Parent Markdown lint passes.
- [x] Git diff whitespace check passes: `git diff --check`
- [x] Full-suite phase-close gate passes:
  `.github` self CI-equivalent plus new probe helper tests.
- [x] Push-equivalent proof passes: same as full-suite phase-close gate.
- [x] Customer/web suite: `n/a - control-plane CI template/action only`.

#### Test Durability

- [x] Probe tests encode the security contract, not consumer-specific current
  failures.
- [x] Assertions include clear failure messages.
- [x] No retirement tests are introduced.

#### Manual Verification

- [ ] Confirm the probe workflow is not listed as a required status check.
- [ ] Confirm the pilot consumer repo uses the same runtime setup as required
  CI.
- [ ] Confirm the workflow lands on the default branch before operators attempt
  `gh workflow run`.

#### Plan Alignment Verification

- [x] Required CI remains the merge gate.
- [x] `.github` owns the shared safety contract, not repo-specific runtime
  commands.
- [x] Probe implementation uses constrained typed inputs only.
- [x] Probe implementation uses read-only permissions.
- [x] Probe implementation has explicit `timeout-minutes`, `concurrency`, and
  human-readable `run-name`.
- [x] Probe output is captured as diagnostic artifact evidence.
- [x] Probe output artifacts use intentionally short retention.
- [x] No consumer repo receives arbitrary remote shell execution capability.

#### Agent Review Gates

- [x] `reviewer-plan-compliance`
- [x] `reviewer-definition-traceability`
- [x] `reviewer-reuse-patterns`
- [x] `reviewer-test-discipline`
- [x] `reviewer-error-handling` - waived unless Elixir code changes; the
  current reviewer is Elixir/CQRS-specific.
- [x] `reviewer-code-quality`
- [x] `reviewer-performance-efficiency`
- [x] `reviewer-test-runtime-isolation`
- [x] `reviewer-security-general`
- [x] `reviewer-knowledgebase-integrity`
- [x] `reviewer-greenfield-scope`

#### Reviewer Execution Plan

- **Preflight**: verify reviewer availability before implementation.
- **Model policy**: opposite-runtime reviewers preferred; same-runtime fallback
  must be recorded as reduced independence.
- **Wave 1 - phase validity**: `reviewer-plan-compliance`,
  `reviewer-definition-traceability`, `reviewer-test-discipline`,
  `reviewer-test-runtime-isolation`.
- **Wave 2 - implementation hygiene**: `reviewer-reuse-patterns`,
  `reviewer-code-quality`, `reviewer-performance-efficiency`.
- **Wave 3 - domain specialists**: `reviewer-security-general`,
  `reviewer-knowledgebase-integrity`, `reviewer-greenfield-scope`.
- **Concurrency**: default two reviewers at a time; hard cap four.
- **Escalations**: GitHub workflow-dispatch or Actions security uncertainty
  routes to official GitHub documentation research and mature GitHub prior-art
  review under the reviewer escalation evidence standard above.

**Implementation Note**: Commit Phase 6 only after the diagnostic contract is
documented and any reusable helper/template tests pass. Do not wire the probe
as a required check.

### Phase Close Receipt

- **Phase**: Phase 6 - Add Remote Diagnostic Probe Standard.
- **Commit**: `b63de2a8b411183d52139a875fc7b918a3d41405`.
- **Definition Sources Loaded**: `docs/intent.md`, `docs/requirements.md`,
  `docs/architecture.md`, Product Evidence manifest/view, Phase 6 context
  packet, and the private consumer-probe context waiver summarized in this
  public plan.
- **Phase Context Packet Loaded**: Phase 6 context packet and reviewer
  execution plan.
- **Automated Verification**: final Phase 6 proof passed on 2026-06-30:
  `python3 -m unittest discover -s tests` (17 tests),
  `python3 -m unittest discover -s actions/ci-github-actions/tests` (9),
  `python3 -m unittest discover -s actions/ci-markdown/tests` (10),
  `python3 -m unittest discover -s actions/ci-alphaapps-policy/tests` (23),
  `python3 -m unittest discover -s actions/ci-dependency-review/tests` (4),
  `python3 -m unittest discover -s actions/ci-dependabot-coverage/tests` (9),
  `python3 -m unittest discover -s actions/ci-remote-probe-guard/tests` (5),
  `python3 scripts/validate-github-actions.py`,
  `python3 actions/ci-alphaapps-policy/scripts/validate_product_lifecycle_baseline.py`,
  `python3 actions/ci-alphaapps-policy/scripts/validate_durable_evidence_references.py`,
  `python3 actions/ci-alphaapps-policy/scripts/validate_product_evidence.py`,
  `python3 actions/ci-dependabot-coverage/scripts/check_dependabot_coverage.py`,
  README/docs Markdown lint with pinned `markdownlint-cli2@0.22.1`, pinned
  actionlint `v1.7.12` with checksum verification for `.github/workflows/*.yml`
  and `workflow-templates/ci-probe.yml`, ShellCheck `style` plus `bash -n` for
  tracked shell scripts, action/template YAML parse checks, Product Evidence
  JSON parse check, public/private disclosure grep for changed public
  surfaces, and `git diff --check && git diff --cached --check`.
- **Full-Suite / Push-Equivalent Proof**: the full-suite command set above is
  the push-equivalent proof for this control-plane CI action repo; customer/web
  suite is not applicable.
- **Reviewer Gates**: passed after fixes and reruns:
  `reviewer-plan-compliance`, `reviewer-definition-traceability`,
  `reviewer-product-evidence` (additional evidence-relevant gate),
  `reviewer-reuse-patterns`, `reviewer-test-discipline`,
  `reviewer-code-quality`, `reviewer-performance-efficiency`,
  `reviewer-test-runtime-isolation`, `reviewer-security-general`,
  `reviewer-knowledgebase-integrity`, and `reviewer-greenfield-scope`.
  `reviewer-error-handling` is waived because no Elixir code changed.
- **Reviewer Findings Fixed And Rerun**: definition traceability and plan
  compliance required `checkout_ref` validation before checkout and durable test
  rationale that cites requirements instead of the phase; test discipline
  required exact `workflow_dispatch` trigger coverage and shell-array/case-branch
  assertions; performance required shallow target checkout by default; code
  quality required rejecting absolute-looking and dot-segment file roots/paths
  and actionable WHAT/WHY/HOW output for the unexpected validated mode branch;
  knowledgebase integrity required README wording to distinguish dispatch
  `run-name` context from normalized summary values and to name file selector
  bounds as consumer-adaptable.
- **Reduced-Independence Fallbacks**: opposite-runtime reviewer transport was
  unavailable earlier in this session, so Phase 6 reviewer gates used
  same-runtime reduced-independence fallback reviews. The public plan records
  only the reduced-independence fact, not exact transport failure details.
- **Manual Verification**: still awaiting operator confirmation for required
  check status configuration, pilot consumer runtime parity, and default-branch
  landing before `gh workflow run`; manual checkboxes remain unchecked.
- **Plan Checkboxes Updated**: automated verification, test durability, plan
  alignment, and all Phase 6 reviewer gates are checked. Manual verification
  remains unchecked.
- **Upstream Amendments / Backfills**: no intent, requirements, architecture,
  glossary, design, story, or ADR changes were made. Product Evidence was
  updated downstream for REQ-011, REQ-012, REQ-014, and REQ-015 to cover the
  diagnostic probe guard/template contract.

#### Deviations From Plan And Definition Sources

- **Planned**: provide a workflow template or helper action for manual remote
  diagnostic probes.
- **Implemented**: provided both
  `workflow-templates/ci-probe.yml` and
  `actions/ci-remote-probe-guard`, with guard validation running before target
  checkout and the template using repo-owned shell-array `case` branches.
- **Difference**: using both surfaces makes the safety contract executable while
  keeping consumer runtime commands in consuming repos.
- **Evidence Used**: REQ-011, REQ-012, `docs/architecture.md` Diagnostic
  Workflow Model, guard tests, actionlint, security review, plan compliance
  review, test discipline review, and knowledgebase integrity review.
- **Classification**: allowed implementation choice.
- **Resolution**: README, Product Evidence, tests, and template now describe and
  verify the two-ref diagnostic probe model without adding merge authority.

- **Planned**: validate probe mode, lane, file, line, and output label before
  checkout-dependent execution.
- **Implemented**: additionally validates `checkout_ref`, `file_root`, and
  allowed file suffixes before checkout-dependent execution.
- **Difference**: the broader guard covers the requirement fit statement for
  invalid refs and the public template's configurable selector bounds.
- **Evidence Used**: REQ-012, reviewer-definition-traceability,
  reviewer-security-general, reviewer-code-quality, and guard invalid-input
  fixtures.
- **Classification**: allowed implementation choice.
- **Resolution**: invalid refs, absolute-looking roots, dot segments,
  command-like inputs, path traversal, invalid modes, lanes, files, lines, and
  labels fail before checkout or command construction.

---

## Testing Strategy

### Unit Tests

- Policy validator fixtures for baseline status, definition-only work,
  blocked code changes, stale lifecycle evidence, durable-reference citations,
  missing required Product Evidence, Product Evidence backfill-only work, and
  malformed Product Evidence.
- Markdown action fixtures for changed/all mode, missing config, ignored paths,
  and clean/no-change behavior.
- GitHub Actions safety fixtures for actionlint invocation, broad permissions,
  `pull_request_target`, unpinned refs, local action refs, and allowlisted
  exceptions.
- Shell action fixtures for ShellCheck severity and Bash syntax failure.
- Dependency-review wrapper tests for PR-only behavior and input validation.
- Dependabot coverage fixtures for repo-local config discovery, nested action
  manifests, package manifest detection, and documented unmanaged surfaces.
- Remote probe fixtures for allowed probe modes, safe path/line/label
  validation, command-array construction, and rejection of command-like input.

### Integration Tests

- `.github` self CI-equivalent run from the worktree.
- Local action invocation from `.github/workflows/ci.yml` using `./actions/...`
  paths where possible.
- `rg` sweeps proving no internal `@main` shared-action refs remain.
- Probe template/action YAML and actionlint validation.
- Probe guard/template tests proving safe input validation and no command
  passthrough.

### Manual Testing Steps

1. Review the final README examples as a consumer repo maintainer.
2. Confirm whether moving `v1` should happen immediately.
3. Confirm ShellCheck `style` severity is accepted as the org default.
4. Confirm baseline enforcement freezing non-backfilled repos is intentional
   before release.
5. Confirm remote probe workflows remain diagnostic and non-required.

## Migration Notes

New or clean repos should adopt the full strict defaults immediately:

- approved baseline source truth;
- Markdown `mode: all`;
- ShellCheck `style`;
- Dependabot coverage for detected dependency surfaces;
- dependency review on PRs;
- GitHub Actions safety checks;
- one `CI` job.

Legacy repos can start with Markdown `mode: changed`, but baseline
source-truth enforcement is intentionally hard. If a legacy repo lacks approved
`docs/intent.md`, `docs/requirements.md`, and `docs/architecture.md`, ordinary
code, test, dependency, and runtime changes should fail until definition
backfill lands.

## References

- Original task: operator request to create a strict shared `.github` CI policy
  plan for Alpha Apps projects.
- Private consumer-repo remote probe source plan reviewed locally; do not
  publish the local path or private failing test details in `.github`.
- Prior art - Nextstrain CI workflow dispatch and artifacts:
  <https://github.com/nextstrain/nextstrain.org/blob/master/.github/workflows/ci.yml>
- Prior art - tree-sitter-language-pack manual workflow, read-only
  permissions, and checkout-ref resolution:
  <https://github.com/kreuzberg-dev/tree-sitter-language-pack/blob/main/.github/workflows/publish.yaml>
- Prior art - Quarto workflow input-driven checkout ref:
  <https://github.com/quarto-dev/quarto-web/blob/main/.github/workflows/publish.yml>
- Prior art - upload-artifact failure diagnostic artifact:
  <https://github.com/actions/upload-artifact/blob/main/.github/workflows/check-dist.yml>
- GitHub composite actions:
  <https://docs.github.com/actions/creating-actions/creating-a-composite-action>
- GitHub manual workflow dispatch:
  <https://docs.github.com/actions/managing-workflow-runs/manually-running-a-workflow>
- GitHub workflow syntax:
  <https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions>
- GitHub `GITHUB_TOKEN` permissions:
  <https://docs.github.com/actions/security-for-github-actions/security-guides/automatic-token-authentication>
- GitHub Actions secure use:
  <https://docs.github.com/en/actions/reference/security/secure-use>
- GitHub script injection guidance:
  <https://docs.github.com/en/actions/concepts/security/script-injections>
- GitHub workflow artifacts:
  <https://docs.github.com/en/actions/tutorials/store-and-share-data>
- GitHub required status check troubleshooting:
  <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks>
- GitHub Dependency Review:
  <https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/about-dependency-review>
- Dependency Review Action:
  <https://github.com/actions/dependency-review-action>
- GitHub Dependabot configuration file:
  <https://docs.github.com/en/code-security/concepts/supply-chain-security/about-the-dependabot-yml-file>
- GitHub Dependabot version-update configuration:
  <https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference>
- actionlint:
  <https://github.com/rhysd/actionlint>
- markdownlint-cli2:
  <https://github.com/DavidAnson/markdownlint-cli2>
- ShellCheck:
  <https://www.shellcheck.net/>
