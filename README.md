---
status: approved
tags:
  - org/alpha-apps
  - topic/github
---
# ForgingAlpha/.github

ForgingAlpha's public CI, dependency, security, and release automation control
plane.

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
- Shared baseline and complete applicable product checks can be required by an organization ruleset without
  depending on each consumer to install a caller. Enrollment, actual execution
  and preservation of product-specific checks are verified before reliance.
- Protected, human-merged `.github/main` is the active shared automation source.
  Required checks and exact-revision human review precede the merge; no later tag
  promotion, source acceptance or recurring ruleset repin makes it active.
- Authored changes use nonpersistent branches in assigned task worktrees.
  Every repository uses reviewed disposable exploration and whole-unit refactoring,
  task pull requests to protected `dev`, whole-batch consolidation from frozen
  `dev` on a task branch and a reviewed pull request back to `dev`, then a fixed
  integrated snapshot proposed to protected `staging`,
  integrated qualification and a separate `staging` to `main` promotion pull request.
  Feature and batch refactoring reassess representations and affected downstream
  logic against combined requirements. Reviewed reconciliation preserves newer dev
  work while returning release refinements.
  The shared control-plane owns this route and its bounded migration; repository
  content does not create exceptions. Complete applicable checks and human approval
  and merge apply on every supported path. Existing adopted routes remain available
  until their replacements are qualified; missing branches grant no creation authority.
- Every shared execution retains its exact resolved source revision and consumer
  revision. Recovery uses the protected human-reviewed source-change path and
  preserves earlier execution evidence.
- Normal dependency proposals receive a deliberate cooldown; eligible security
  proposals receive immediate classification and exact-patch verification.
  An authorized human performs every pull-request merge after its required gates.
- Every versioned dependency, runtime, tool, Action, image, and external plugin
  has exactly one discoverable update owner; unmanaged version literals fail
  required CI.
- Renovate owns normal external updates across supported manifests, locks, and
  annotated literals. Internal `ForgingAlpha/.github@main` references follow
  the protected human-merge path. Cooled normal updates follow the repository's
  ordinary integration route through human-merged pull requests with exact-head
  CI; an updater's configured target does not create a route exception.
- Dependabot owns security remediation only. Every eligible security proposal,
  whether its source targets `main` or `dev`, retains trusted classification of
  GitHub's official vulnerability-alert-to-pull-request association and the exact
  approved dependency patch before a human merges it.
- Runtime and tool upgrades follow the same normal patch, minor, and major
  automation path while preserving exact committed locks and integrity data.
- Where security remediation uses a separate `dev` source, production promotion
  projects only the exact independently
  verified dependency patch from its merged `dev` security change onto the
  current production base. It never carries unrelated unreleased `dev` work.
  Direct security proposals to `main` retain the same source-classification and
  patch-proof obligations, required checks, human review and human merge without
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
  by central policy: an approved SPDX allowlist covering permissive licenses and
  `LGPL-3.0-or-later`, or a reviewed exception for one repository and immutable
  artifact. License eligibility and actual-use compliance are separate: product
  release owners address applicable notice, source and distribution obligations.
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
  `CI`, authorized-human approval of the exact current revision, and human
  execution of the merge. Coherent candidate and affected-consumer validation
  belongs before merge. No existing required check or enrolled consumer gate may
  be deferred. Main membership makes the resulting source active; execution
  observations do not add another activation decision.
- Normal and security automation have disjoint authority. Renovate does not
  remediate vulnerability alerts, and Dependabot does not create normal version
  updates.
- Security urgency may bypass cooldown and release batching, never CI, source
  provenance, exact-patch verification, current-base verification, CodeQL or
  human merge authority. Cross-branch projection additionally reconstructs only
  that proved patch on the current production base.
- Inactive deployment tooling is removed instead of receiving new update
  automation.
- Fail closed when identity, classification, branch state, checks, or deployed
  SHA is ambiguous.
- Centralize only genuinely cross-repository behavior.
- Qualify centrally required CI on explicitly selected consumers before broader
  enrollment. A document-only bootstrap profile is explicit and cannot be
  selected merely because expected application inputs are missing.

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

Every repository follows the shared route: reviewed disposable exploration and
unit refactoring; task PR to `dev`; whole-batch consolidation from frozen `dev`
and reviewed PR back into `dev`; fixed-snapshot PR to `staging`; integrated qualification; then a
`staging` to `main` PR and reviewed reconciliation to dev. Every persistent merge
is human. Main remains the active shared automation source. See
[REQ-027](docs/requirements.md#req-027---uniform-proposal-admission).

This source is an enabling amendment, not completed route migration. Each
repository retains its known adopted predecessor route until replacement tools,
CI, protections and actual consumers qualify. This repository's transition owner
and retirement conditions are in
[Uniform proposal targets](docs/architecture.md#uniform-proposal-targets).
Missing branches do not authorize creation or fallback; unknown/conflicting route
evidence stops the dependent proposal. The caller example above describes an
existing dev/main consumer, not the final unified route's complete trigger set.
The legacy merge-flow wrapper still has
its known dev-only promotion behavior; central schema-2 admission uses the explicit
owner-declared route and does not infer it from branch existence. Security remediation
retains its separately governed classification and exact-patch proof; a separate-dev
source additionally requires production projection and never carries unrelated `dev`
work. Its CI admission reads
Git objects, pull requests and trusted checks, so callers retain all three
read-only token scopes shown above.

## Central Documentation Pilot

The organization-required entrypoint is
[org-baseline.yml](.github/workflows/org-baseline.yml). Its trusted
[enrollment](actions/ci-org-baseline/enrollment.json) selects only
`ForgingAlpha/layas-learning-lab-site`, repository ID `1420939261`, on `dev` and `main`.
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
qualify this candidate. Protected main is active at human merge. Any consumer
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
needs explicit enrollment and actual target-context checks. Shared-enforcement changes
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
the caller and scopes already adopted on protected `dev`. Verify the hosted
`CI` run on the consumer PR. When introducing executable code, extend the
repository workflow with the applicable product checks.

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
| `ci-merge-flow` | Existing dev/main guard and source-repo bridge; successor consolidation/promotion admission remains unqualified |
| `ci-elixir` | Locked runtime, strict static analysis, and repo-owned tests |
| `ci-rust` | Format, Clippy, dead code, tests, and audit |
| `ci-astro` | Format, lint, Astro type checking, and build |
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

Renovate proposes normal updates through the central preset and a thin consumer
configuration. This repository uses `renovate.json` with base branch `main`.
Dependabot prepares officially associated security remediation.
An applicable authorized human performs every PR merge. Bot and platform
auto-merge are disabled; classification or a green check does not authorize a merge.

| Update | Minimum age | Target and merge |
| --- | ---: | --- |
| Patch | 3 days | Human-merged PR to the ordinary target under REQ-027 |
| Minor | 7 days | Human-merged PR to the ordinary target under REQ-027 |
| Major | 30 days | Human-merged PR to the ordinary target under REQ-027 |
| Security | No cooldown | Human-merged classified source PR; separate-dev sources additionally require an exact, human-merged production projection |

Eligible npm minor and patch updates for the named lint tools share a `linting`
proposal; Prettier and its Astro plugin share a separate `formatting` proposal.
The exact members are defined in [the central preset](renovate-config.json).
Major updates remain outside these groups. Each release retains its own minimum
age and the existing Renovate buffer; a pending member cannot bypass eligibility
through a group. Grouped packages still require combined checks and human review;
a shared proposal does not establish compatibility.

During their retained predecessor route, control-plane proposals target protected
`main`; after migration ordinary proposals follow REQ-027's dev/staging/main route.
Runtime projections
remain governed by their central assignments and exact locks; the current
preset disables direct mise, Node-engine and generic lock-maintenance writes.
Runtime update automation requires a qualified constrained writer.

Every eligible security source retains trusted classification, exact dependency-patch
proof, required CI/CodeQL and human approval and merge under REQ-013/014. For a
separate-dev source, the projector reconstructs only its verified manifest-and-lock
patch on current `main` after the human source merge. It creates a draft proposal;
read-only verification precedes human production approval and merge. An eligible
direct-main source instead has one human merge and read-only source observation;
it does not create a second PR or use a projection-only attestation. Applicable
deployment evidence binds the exact resulting revision; shared-source activation
does not prove product deployment. The direct-source caller and observer remain
implementation/qualification obligations described in Architecture; this contract
does not establish that either security path is operational in a consumer.

Installations, hosted settings, caller enrollment and daily execution need
separate verification. An unrestricted Renovate run window permits daily
execution but does not prove it. Follow the
[operator checklist](docs/operator-checklist.md) for enrollment and rollout.

## Active Shared Source And Recovery

Protected, human-merged `.github/main` is the active shared source. Complete
exact-head source CI, coherent candidate and affected-consumer validation, and
authorized human review precede the human merge. There is no recurring tag
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
and human merge into main. Record the new exact source and affected outcomes;
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

The durable policy is defined in [Intent](#intent),
[Requirements](docs/requirements.md), and [Architecture](docs/architecture.md).

## Application development containers

The control-plane [container procedure](https://github.com/ForgingAlpha/control-plane/blob/main/system/runbooks/operate-local-containers.md)
owns the Compose convention and container responsibilities. Applications own their
product commands, tests and deployment configuration. Shared mandatory checks
remain shared-CI owned.
