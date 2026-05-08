# ForgingAlpha/.github

Org-wide CI, security configuration, and standards for all ForgingAlpha repositories.

## Composite Actions (CI Library)

CI logic is centralized in `actions/`. Each repo's `.github/workflows/ci.yml` is a thin wrapper (~8 lines) that calls the right action. Edit the action once — every repo picks up the change on the next CI run.

| Action | Ecosystem | What it checks |
|---|---|---|
| [`ci-rust`](actions/ci-rust/action.yml) | Rust | `cargo fmt --all`, `cargo clippy -D warnings`, dead-code check, `cargo test`, `cargo audit` |
| [`ci-elixir`](actions/ci-elixir/action.yml) | Elixir | `mix format`, `mix compile --warnings-as-errors`, `mix credo --strict`, `mix test` |
| [`ci-astro`](actions/ci-astro/action.yml) | Astro | `prettier`, `eslint`, `astro check`, `npm run build` |
| [`ci-typescript`](actions/ci-typescript/action.yml) | TypeScript | `prettier`, `eslint`, `tsc --noEmit`, `npm test` (all conditional via inputs) |
| [`ci-shell`](actions/ci-shell/action.yml) | Shell | `shellcheck`, `bash -n` syntax validation |

### Add CI to a new repo

1. Create `.github/workflows/ci.yml` in the repo with the appropriate wrapper (examples below).
2. The `CI` job name must be uppercase — it matches the org-wide `release-branches` ruleset's required status check.
3. Triggers must be `push: [dev]` + `pull_request: [main, staging]` to support the AI-first dev model (agents push directly to `dev`, PRs gate promotion to `main`/`staging`).

**Rust:**
```yaml
name: CI
on:
  push:
    branches: [dev]
  pull_request:
    branches: [main, staging]
permissions:
  contents: read
jobs:
  CI:
    name: CI
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v6
      - uses: ForgingAlpha/.github/actions/ci-rust@v1
```

**Elixir** (requires Postgres service in the caller — composite actions cannot define services):
```yaml
name: CI
on:
  push:
    branches: [dev]
  pull_request:
    branches: [main, staging]
permissions:
  contents: read
jobs:
  CI:
    name: CI
    runs-on: ubuntu-latest
    timeout-minutes: 30
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      MIX_ENV: test
      DATABASE_URL: postgres://postgres:postgres@localhost:5432/test
    steps:
      - uses: actions/checkout@v6
      - uses: ForgingAlpha/.github/actions/ci-elixir@v1
```

**Astro / TypeScript / Shell:** Same pattern — swap the action reference. See each action's `action.yml` header for the full usage example with available inputs.

### Modify CI for all repos of a language

1. Edit the composite action in `actions/ci-<language>/action.yml`.
2. Open a PR to this repo's `main` branch.
3. Once merged, every repo using that action picks up the change on its next CI run.

No per-repo PRs needed. One change here = org-wide rollout.

## Reusable Workflows

### Fast-forward branch promotion

`promote-branch.yml` promotes one branch to another by fast-forward only. It is
used for the Alpha Apps release model:

```text
feature/* → dev by PR
dev → main by fast-forward promotion
main → deploy
```

The workflow:

- mints a short-lived token for the dedicated `forgingalpha-release` GitHub App
- verifies the target branch is an ancestor of the source branch
- verifies required checks passed on the source commit
- pushes the source branch to the target branch
- creates an annotated `prod-*` tag

Consumer repos should add a small `workflow_dispatch` caller and pass the
release App client ID/private key through GitHub Actions variables/secrets
synced from Doppler. The release App must be a bypass actor on the
`release-branches` ruleset only; `branch-safety` remains no-bypass so deletion
and non-fast-forward updates stay blocked.

### Why composite actions (not reusable workflows)

Reusable workflows produce a compound status check name (`CI / CI`) that doesn't match the `release-branches` ruleset's `required_status_checks: [{context: "CI"}]`. Composite actions run inside the caller's job, so the check name stays `CI`. This was validated during the initial architecture setup and is documented in the Obsidian vault.

## Branch Protection (Org-Wide Rulesets)

Two rulesets enforce rules across all repos in the org:

| Ruleset | Branches | Rules |
|---|---|---|
| `branch-safety` | `main`, `staging`, `dev` | Block deletions + block force pushes |
| `release-branches` | `main`, `staging` only | Require PR (1 approval), require CI, linear history, CodeQL, Copilot review |

`dev` is intentionally excluded from `release-branches` so agents can push directly. The `branch-safety` ruleset still protects `dev` from deletion and force-push.

Bypass: Organization Admin only (Leo). The bot (`forgingalpha-bot`) is an org member with write access and cannot bypass any rule.

## Security Baseline (`forgingalpha-secure`)

All security features are managed through a single org-wide Code Security Configuration:

- **Name:** `forgingalpha-secure`
- **Enforcement:** Enforced (cannot be overridden per-repo)
- **Default for new repos:** Yes
- **Features enabled:** GHAS, CodeQL default setup, secret scanning + push protection + validity checks, Dependabot alerts + security updates, private vulnerability reporting

Location: [Org Settings > Code security > Configurations](https://github.com/organizations/ForgingAlpha/settings/security_products/configurations)

## Dependabot

Every repo keeps its own `.github/dependabot.yml` because Dependabot update
configuration is repository-local. The standard schedule is weekly Tuesday,
grouped by security/minor-patch/major.

Dependabot auto-merge behavior is centralized in
`.github/workflows/dependabot-automerge-reusable.yml`. Repos should keep only a
thin caller workflow:

```yaml
name: Dependabot Auto-merge
on: pull_request
permissions:
  contents: write
  pull-requests: write
jobs:
  call-dependabot-automerge:
    name: Enable auto-merge
    if: github.actor == 'dependabot[bot]'
    uses: ForgingAlpha/.github/.github/workflows/dependabot-automerge-reusable.yml@v1
    with:
      allow_patch: true
      allow_minor: true
      allow_major: false
      merge_method: squash
    secrets:
      github_token: ${{ secrets.GITHUB_TOKEN }}

## Standards

- [Repo naming convention](docs/repo-naming.md)

## Full Architecture Documentation

The complete architectural context (why decisions were made, the bot permission model, authentication contract, deployment mapping) lives in the Obsidian vault:

**Alpha Apps Git and GitHub Process** in `alphaapps-docs`
