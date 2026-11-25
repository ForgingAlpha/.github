# Dependabot Templates

Use these security-only templates when enrolling a repository through the
[operator checklist](../../docs/operator-checklist.md#dependency-proposal-enrollment).
For a new repository with a managed dependency, review the root `renovate.json`
that extends the [organization's weekly preset](../../renovate-config.json).
The [consumer configuration in this repository](../../renovate.json) uses GitHub's actual default branch.
Keep `.github/update-policy.json` when it carries a runtime profile assignment.
Include any missing ecosystem blocks or coverage exceptions in the enrollment
PR so required `ci-update-ownership` and `ci-dependabot-coverage` can check them.

Copy the closest template into `.github/dependabot.yml`, then delete update
blocks for ecosystems that are not present. Set `open-pull-requests-limit: 0`
and omit `target-branch` in every retained block. Renovate owns normal updates. The shared
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
