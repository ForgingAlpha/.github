# ForgingAlpha/.github

ForgingAlpha's public CI, dependency, security, and release automation control
plane.

## Consumer Contract

Every repository exposes one required job named `CI`. Shared checks run as
composite actions so the caller keeps that stable status name.

```yaml
name: CI
on:
  push:
    branches: [dev]
  pull_request:
    branches: [dev, staging, main]
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
      - uses: ForgingAlpha/.github/actions/ci-elixir@v1
```

Main-only control-plane repositories use `push` and `pull_request` on `main`.
Application repositories use feature/worktree pull requests into protected
`dev`; routine production releases use a separate governed `dev` to `main`
pull request. Security remediation uses the narrower exact-patch projection
described below and never carries unrelated `dev` work. Its CI admission reads
Git objects, pull requests and trusted checks, so callers retain all three
read-only token scopes shown above.

## Central Documentation Pilot

The organization-required entrypoint is
[org-baseline.yml](.github/workflows/org-baseline.yml). Its trusted
[enrollment](actions/ci-org-baseline/enrollment.json) initially selects only
`ForgingAlpha/layas-learning-lab-site`, repository ID `1420939261`, on `dev`.
This documentation profile supplies `CI` without a consumer workflow. Unknown
identities and application content fail; missing manifests never select bootstrap.
The defining `.github` repository is outside this consumer pilot. Its baseline
workflow is skipped; GitHub currently reports the skipped check using the
unevaluated job-name expression, distinct from `CI`. The existing required `CI`
workflow continues to validate this repository.

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
CodeQL and application builds remain separate. Qualification follows the enrolled
profile and affected shared behavior. A qualified profile can progress independently
of unrelated profiles; each additional repository or branch still needs explicit
enrollment and actual target-context checks. Shared-enforcement changes and broader
migrations require coverage across all affected profiles before reliance or common-call
retirement. The initial documentation and actual hosted Rust cases retain their own
execution, rejection, repair and recovery obligations. This policy does not expand the
current `dev`-only implementation or selectors. Existing language composites and
ordinary `ci-markdown` behavior are unchanged.

## Shared Actions

| Action | Contract |
| --- | --- |
| `ci-alphaapps-policy` | Source-truth baseline structure and fail-closed human CODEOWNERS boundaries |
| `ci-markdown` | Locked validation of tracked Markdown under repository policy on Linux |
| `ci-github-actions` | Actionlint, immutable refs, permissions, and trigger safety |
| `ci-dependabot-coverage` | Declared package coverage for Dependabot-managed consumers |
| `ci-update-ownership` | Sole normal-updater ownership and security-only Dependabot configuration |
| `ci-runtime-profile` | Exact consumer mise projection against the central assigned runtime tuple |
| `ci-foundation` | Approved exact foundation export and actual working-file integrity before its adapter |
| `ci-dependency-review` | Mandatory PR vulnerability review and central commercial-license allowlist |
| `ci-merge-flow` | Feature → `dev` and tested `dev` → `main` flow |
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
from Renovate and use `@v1`, the current approved control-plane rollout
channel.

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
| Patch | 3 days | Human-merged PR into protected `dev` |
| Minor | 7 days | Human-merged PR into protected `dev` |
| Major | 30 days | Human-merged PR into protected `dev` |
| Security | No cooldown | Classified source PR, then exact production projection; both human-merged |

Main-only control-plane proposals target protected `main`. Runtime projections
remain governed by their central assignments and exact locks; the current
preset disables direct mise, Node-engine and generic lock-maintenance writes.
Runtime update automation requires a qualified constrained writer.

The security lane classifies an exact Dependabot source, then reconstructs only
its verified manifest-and-lock patch on current `main` after the human source
merge. It creates a draft proposal; read-only verification checks that proposal
before human production approval and merge. It never promotes unrelated `dev`
work. Post-merge observation and deployment report the exact resulting revision.

Installations, hosted settings, caller enrollment and daily execution need
separate verification. An unrestricted Renovate run window permits daily
execution but does not prove it. Follow the
[operator checklist](docs/operator-checklist.md) for enrollment and rollout.

## `v1` Rollout

`v1` is a current channel, not a backward-compatibility promise. A successful
merged-commit `CI` run on the current `.github/main` commit triggers a serialized
rollout that:

1. verifies the approved workflow run and current `main` SHA;
2. atomically advances mutable `v1` with an expected-old raw-ref lease and
   creates an immutable `v1-rollout-<timestamp>-<sha>` tag;
3. leaves both refs unchanged if either update cannot be accepted;
4. records the transition in the workflow summary.

The version-coherent consumer-profile gate is required before step 2 wherever
it is enrolled; no `v1` movement may bypass an active gate.

The protected manual rollback workflow accepts only an immutable rollout tag
whose commit historically passed the approved `CI` workflow, restores `v1`
with an expected-old lease, and creates an immutable rollback record.

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

The durable policy is defined in [Intent](docs/intent.md),
[Requirements](docs/requirements.md), and [Architecture](docs/architecture.md).
