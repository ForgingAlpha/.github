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
described below and never carries unrelated `dev` work.

## Shared Actions

| Action | Contract |
| --- | --- |
| `ci-alphaapps-policy` | Approved source truth and fail-closed human CODEOWNERS boundaries |
| `ci-markdown` | Pinned validation of every tracked Markdown file |
| `ci-github-actions` | Actionlint, immutable refs, permissions, and trigger safety |
| `ci-dependabot-coverage` | Current pre-cutover update coverage; replaced by the updater-neutral gate in the Renovate plan |
| `ci-update-ownership` | Sole normal-updater ownership and security-only Dependabot cutover |
| `ci-runtime-profile` | Exact consumer mise projection against the central assigned runtime tuple |
| `ci-dependency-review` | Mandatory PR vulnerability review and central commercial-license allowlist |
| `ci-merge-flow` | Feature → `dev` and tested `dev` → `main` flow |
| `ci-elixir` | Locked runtime, strict static analysis, and repo-owned tests |
| `ci-rust` | Format, Clippy, dead code, tests, and audit |
| `ci-astro` | Format, lint, Astro type checking, and build |
| `ci-typescript` | Format, lint, type checking, and tests |
| `ci-shell` | ShellCheck at style severity and Bash syntax |
| `security-patch-source` | Dependabot-safe read-only proof and exact protected `dev` source merge |
| `security-patch-projection` | Exact manifest/lock patch reconstruction on current `main` |
| `security-patch-activation` | Independent production re-proof and exact-SHA protected merge |

External Actions are Renovate-owned and use immutable full SHAs with adjacent
release comments. Internal `ForgingAlpha/.github` shared Actions are excluded
from Renovate and use `@v1`, the current approved control-plane rollout
channel.

## Elixir Profiles

`ci-elixir` supports:

- `full`: all cross-cutting/static checks plus the caller's tests;
- `static`: all cross-cutting/static checks once, without tests;
- `test`: locked setup plus one caller-owned test lane only.

Small applications use `full`. Fanned-out applications run one `static` job,
parallel `test` jobs, and one required `CI` fan-in.

Runtime versions come from committed `mise.toml` and `mise.lock`; workflow YAML
does not duplicate Elixir, OTP, Node, or npm versions.

## Dependency Automation Rollout

The approved target architecture makes Renovate the owner of normal version
updates through one organization preset and a thin repository-local
configuration. Dependabot remains enabled only for security updates with
official GitHub vulnerability-alert association. The implementation is tracked
in
[`docs/plans/renovate-normal-dependency-automation.md`](docs/plans/renovate-normal-dependency-automation.md).
The first implementation tranche publishes the central Renovate preset, the
updater-ownership gate, and a read-only runtime-profile canary for
`alphaapps-site`. Renovate's mise manager, npm-managed Node engine declarations,
and generic lock maintenance remain disabled until the constrained writer is
available. Required CI on the canary rejects overlapping update ownership and a
runtime declaration or lock that is not the exact assigned projection.

The hosted service may evaluate the repository more than once per day; the
unrestricted run window satisfies the policy's at-least-daily evaluation
requirement. Release eligibility remains governed by the exact 3/7/30-day
minimum ages rather than by scan frequency.

Installing the hosted Renovate App and changing ruleset bypass actors are
operator actions, not consequences of publishing this repository. Until those
actions are separately approved and verified, Renovate may propose eligible
normal updates but cannot complete unattended protected merges.

For the first canary, install the App while the canonical consumer config PR is
green but unmerged. Use Renovate's generated onboarding PR and job log to prove
App access, the default branch, and manager discovery, then close that generated
PR. Merge the canonical reviewed config to activate proposal creation. Inspect
the first post-merge hosted job for the resolved central preset, cooldowns,
disabled vulnerability/mise/Node-engine lanes, and first-party Action exclusion. Merging
the canonical config before App installation would skip the onboarding safety
gate.

| Update | Minimum age | Merge policy |
| --- | ---: | --- |
| Patch | 3 days | Automatic into code-repository `dev` after exact-head `CI` |
| Minor | 7 days | Automatic into code-repository `dev` after exact-head `CI` |
| Major | 30 days | Automatic into code-repository `dev` after exact-head `CI` |
| Runtime family | Applicable age | Automatic through the repository's normal-update branch after exact lock refresh and `CI` |

Normal dependency updates never auto-promote from `dev` to `main`. Main-only
control-plane repositories use protected pull requests and their complete local
gates. `.github` advances `v1` only after version-coherent consumer profiles
pass on the exact candidate.

Officially classified security updates do not wait for cooldown and merge into
`dev` only after full exact-head CI. The approved production target is to
reconstruct only the verified dependency manifest-and-lock patch on current
`main`, run fresh strict `main` CI and CodeQL, and use protected exact-SHA merge
authority. That production path is not active until the central implementation
and `alphaapps-site` observation canary complete. Any divergence, conflict,
ambiguity, or unrelated path fails closed; the entire `dev` branch is never
promoted by the security lane.

## `v1` Rollout

`v1` is a current channel, not a backward-compatibility promise. A successful
merged-commit `CI` run on the current `.github/main` commit triggers a serialized
rollout that:

1. verifies the approved workflow run and current `main` SHA;
2. atomically advances mutable `v1` with an expected-old raw-ref lease and
   creates an immutable `v1-rollout-<timestamp>-<sha>` tag;
3. leaves both refs unchanged if either update cannot be accepted;
4. records the transition in the workflow summary.

This describes the initial rollout gate. Phase 6 of the Renovate plan adds the
mandatory version-coherent consumer-profile gate before step 2; after that gate
is activated, no `v1` movement may bypass it.

The protected manual rollback workflow accepts only an immutable rollout tag
whose commit historically passed the approved `CI` workflow, restores `v1`
with an expected-old lease, and creates an immutable rollback record.

## Security Boundary

- Root workflow permissions are read-only; write permissions are job-scoped.
- Every repository keeps an authorized human as code owner for `.github/` and
  detected production controls; control-plane repositories require authorized
  human ownership of the complete tree.
- Privileged workflows never check out or execute pull-request code.
- Agents receive no operator SSH key or personal credential.
- Direct deployment and release writes belong only to the scoped release
  identity and operator.
- Ambiguous identity, classification, checks, branch state, or SHA fails closed.
- The security automation identity is dedicated and isolated from general agent
  credentials; an exact completed source merge is adopted after a lost response
  only when every immutable postcondition still matches.

The durable policy is defined in [Intent](docs/intent.md),
[Requirements](docs/requirements.md), and [Architecture](docs/architecture.md).
