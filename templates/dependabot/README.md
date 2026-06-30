# Dependabot Templates

Copy the closest template into `.github/dependabot.yml`, then delete update
blocks for ecosystems that are not present in the repo. The shared
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
