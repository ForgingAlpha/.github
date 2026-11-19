# Dependabot Templates

Use these security-only templates after Renovate enrollment is verified through
the [operator checklist](../../docs/operator-checklist.md#dependency-proposal-enrollment).
For each new repository with a managed dependency, add the thin root
`renovate.json` and matching `.github/update-policy.json` with its governed
ordinary target. Use [this repository's Renovate config](../../renovate.json)
and [owner declaration](../../.github/update-policy.json) as examples.
Use `ci-update-ownership` and `ci-dependabot-coverage` in required CI.
The shared preset owns scheduling, grouping and release ages.

Copy the closest template into `.github/dependabot.yml`, then delete update
blocks for ecosystems that are not present. Keep normal-update capacity at zero;
Renovate owns normal updates. The shared
`ci-dependabot-coverage` action validates that obvious dependency surfaces are
covered or explicitly documented as unmanaged.

Use `directories` when one ecosystem appears in repeated manifest directories.
Dependabot does not update hardcoded versions in shell commands, workflow run
blocks, or custom scripts; those require separate validation or audit coverage
when they are part of the public contract.

If a dependency surface is intentionally unmanaged, add a documented comment to
`.github/dependabot.yml`:

```yaml
# alphaapps-dependabot-unmanaged: pip / - runtime image owns Python updates
```

## Templates

- `github-actions-only.yml` - workflows and shared composite actions only.
- `rust-cargo.yml` - Rust/Cargo plus GitHub Actions.
- `npm.yml` - npm/Astro/TypeScript plus GitHub Actions.
- `elixir-mix.yml` - Elixir/Mix plus GitHub Actions.
- `mixed-app.yml` - mixed app repos with root and nested npm manifests.
- `python.yml` - Python dependency manifests plus GitHub Actions.
