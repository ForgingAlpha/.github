---
status: approved
tags:
  - org/alpha-apps
  - topic/github
---
# ForgingAlpha/.github - Intent

## Purpose

`ForgingAlpha/.github` is the public automation control plane for ForgingAlpha.
It gives every repository current, secure, reproducible CI and dependency
automation without copying workflow logic between repositories.

## Durable Outcomes

- Every repository exposes one required merge status named `CI`.
- A reviewed, green control-plane merge reaches consumers promptly through the
  internal `@v1` current channel.
- Every `v1` rollout is serialized, traceable, immutable-recorded, and
  operator-reversible.
- Normal dependency updates receive a deliberate cooldown; eligible security
  updates do not wait and automatically reach protected `main` and deployment
  after exact-commit CI succeeds.
- Every versioned dependency, runtime, tool, Action, image, and external plugin
  has exactly one discoverable update owner; unmanaged version literals fail
  required CI.
- Renovate owns normal updates across supported manifests, locks, and annotated
  literals. Cooled normal updates automatically integrate into code-repository
  `dev` after exact-head CI, but only security updates auto-promote to `main`.
- Dependabot owns security remediation only so privileged promotion can prove
  GitHub's official vulnerability-alert-to-pull-request association.
- Runtime and tool upgrades follow the same normal patch, minor, and major
  automation path while preserving exact committed locks and integrity data.
- Application security promotion carries the complete already-green,
  unreleased `dev` range so deployed code is always a real branch state.
- Static and cross-cutting checks run once; parallel test lanes remain lean.
- Runtime versions are repository-owned, exactly locked, and reproducible
  locally and in CI.
- External automation dependencies are immutable and integrity-verifiable.
- Required CI, rather than diagnostics or human memory, is merge authority.

## Boundaries

This repository owns shared composite actions, repo-owned automation, the
organization Renovate preset, security-only Dependabot policy, update-ownership
validation, release mechanics, templates, and public-safe cross-repository
enforcement.

Consumer repositories own product behavior, services, runtime commands,
deployment configuration, secrets, and data. Agents never receive operator SSH
keys or personal credentials. Privileged automation never executes untrusted
pull-request code.

## Invariants And Tradeoffs

- `@v1` is the current approved internal automation channel, not a SemVer
  backward-compatibility promise.
- Every control-plane change lands through a reviewed pull request with green
  `CI`; after merge, the exact merged commit and version-coherent consumer
  profiles are verified before rollout.
- Normal and security automation have disjoint authority. Renovate does not
  remediate vulnerability alerts, and Dependabot does not create normal version
  updates.
- Security urgency may bypass cooldown and release batching, never CI or
  exact-SHA verification.
- Inactive deployment tooling is removed instead of receiving new update
  automation.
- Fail closed when identity, classification, branch state, checks, or deployed
  SHA is ambiguous.
- Centralize only genuinely cross-repository behavior.
