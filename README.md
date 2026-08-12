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
`dev`; deployed `main` receives tested fast-forward promotions.

## Shared Actions

| Action | Contract |
| --- | --- |
| `ci-alphaapps-policy` | Approved source truth and fail-closed human CODEOWNERS boundaries |
| `ci-markdown` | Pinned validation of every tracked Markdown file |
| `ci-github-actions` | Actionlint, immutable refs, permissions, and trigger safety |
| `ci-dependabot-coverage` | Current pre-cutover update coverage; replaced by the updater-neutral gate in the Renovate plan |
| `ci-dependency-review` | Mandatory PR vulnerability review and central commercial-license allowlist |
| `ci-merge-flow` | Feature → `dev` and tested `dev` → `main` flow |
| `ci-elixir` | Locked runtime, strict static analysis, and repo-owned tests |
| `ci-rust` | Format, Clippy, dead code, tests, and audit |
| `ci-astro` | Format, lint, Astro type checking, and build |
| `ci-typescript` | Format, lint, type checking, and tests |
| `ci-shell` | ShellCheck at style severity and Bash syntax |

External Actions use immutable full SHAs with adjacent release comments.
Internal shared Actions use `@v1`, the current approved control-plane channel.

## Elixir Profiles

`ci-elixir` supports:

- `full`: all cross-cutting/static checks plus the caller's tests;
- `static`: all cross-cutting/static checks once, without tests;
- `test`: locked setup plus one caller-owned test lane only.

Small applications use `full`. Fanned-out applications run one `static` job,
parallel `test` jobs, and one required `CI` fan-in.

Runtime versions come from committed `mise.toml` and `mise.lock`; workflow YAML
does not duplicate Elixir, OTP, Node, or npm versions.

## Target Dependency Automation

The approved target architecture makes Renovate the owner of normal version
updates through one organization preset and a thin repository-local
configuration. Dependabot remains enabled only for security updates with
official GitHub vulnerability-alert association. The implementation is tracked
in
[`docs/plans/renovate-normal-dependency-automation.md`](docs/plans/renovate-normal-dependency-automation.md).
When the cutover is complete, required CI rejects missing coverage, overlapping
ownership, and unmanaged version literals.

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

Officially classified security updates do not wait for cooldown. They merge
only after full exact-head CI and then promote the exact tested branch state to
protected `main` and deployment.

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

The durable policy is defined in [Intent](docs/intent.md),
[Requirements](docs/requirements.md), and [Architecture](docs/architecture.md).
