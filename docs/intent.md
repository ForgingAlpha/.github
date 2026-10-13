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
- Every control-plane and protected production-control change is approved by
  an authorized human code owner on its exact current revision; an agent or
  authoring-bot identity cannot substitute for that approval.
- A reviewed, green control-plane merge reaches consumers promptly through the
  internal `@v1` current channel.
- Every `v1` rollout is serialized, traceable, immutable-recorded, and
  operator-reversible.
- Normal dependency proposals receive a deliberate cooldown; eligible security
  proposals receive immediate classification and exact-patch verification.
  An authorized human performs every pull-request merge after its required gates.
- Every versioned dependency, runtime, tool, Action, image, and external plugin
  has exactly one discoverable update owner; unmanaged version literals fail
  required CI.
- Renovate owns normal external updates across supported manifests, locks, and
  annotated literals. Internal `ForgingAlpha/.github@v1` movement remains
  owned by the protected control-plane rollout. Cooled normal updates enter
  code-repository `dev` through human-merged pull requests with exact-head CI.
- Dependabot owns security remediation only so trusted classification can prove
  GitHub's official vulnerability-alert-to-pull-request association.
- Runtime and tool upgrades follow the same normal patch, minor, and major
  automation path while preserving exact committed locks and integrity data.
- Application security promotion projects only the exact independently
  verified dependency patch from its merged `dev` security change onto the
  current production base. It never carries unrelated unreleased `dev` work.
- Static and cross-cutting checks run once; parallel test lanes remain lean.
- Organization runtime profiles and compatible version tuples have one
  control-plane owner. Every consumer commits an exact, integrity-bearing mise
  projection of its assigned approved profile so local and CI execution remain
  reproducible, and required CI rejects unapproved or internally inconsistent
  projections.
- External automation dependencies are immutable and integrity-verifiable.
- Required CI supplies technical evidence; it does not grant merge authority.
- Every introduced or updated third-party package has license evidence approved
  by central policy: a permissive commercial-use SPDX allowlist or a reviewed
  exception for one repository and immutable artifact. Fixed first-party actions
  have governed ownership and release provenance; unknown evidence fails closed.

## Boundaries

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

## Invariants And Tradeoffs

- `@v1` is the current approved internal automation channel, not a SemVer
  backward-compatibility promise.
- The control plane publishes one strict current contract. Obsolete rollout
  exceptions, incremental Markdown enforcement, and compatibility entrypoints
  are removed rather than carried forward.
- Every control-plane change lands through a reviewed pull request with green
  `CI`, authorized-human approval of the exact current revision, and human
  execution of the merge; after
  merge, the exact merged commit and version-coherent consumer profiles are
  verified before rollout.
- Normal and security automation have disjoint authority. Renovate does not
  remediate vulnerability alerts, and Dependabot does not create normal version
  updates.
- Security urgency may bypass cooldown and release batching, never CI or
  source provenance, exact-patch reconstruction, current-base verification,
  CodeQL, or human merge authority.
- Inactive deployment tooling is removed instead of receiving new update
  automation.
- Fail closed when identity, classification, branch state, checks, or deployed
  SHA is ambiguous.
- Centralize only genuinely cross-repository behavior.
