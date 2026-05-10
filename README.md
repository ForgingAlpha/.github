# ForgingAlpha/.github

Org-wide CI, security configuration, and standards for all ForgingAlpha repositories.

## Composite Actions (CI Library)

CI logic is centralized in `actions/`. Each repo's `.github/workflows/ci.yml` is a thin wrapper (~8 lines) that calls the right action. Edit the action once — every repo picks up the change on the next CI run.

| Action | Ecosystem | What it checks |
|---|---|---|
| [`ci-rust`](actions/ci-rust/action.yml) | Rust | `cargo fmt --all`, `cargo clippy -D warnings`, dead-code check, `cargo test`, `cargo audit` |
| [`ci-elixir`](actions/ci-elixir/action.yml) | Elixir | `mix format`, `mix compile --warnings-as-errors`, optional repo strict checks, `mix credo --strict`, optional pre-test setup, test command |
| [`ci-astro`](actions/ci-astro/action.yml) | Astro | `prettier`, `eslint`, `astro check`, `npm run build` |
| [`ci-typescript`](actions/ci-typescript/action.yml) | TypeScript | `prettier`, `eslint`, `tsc --noEmit`, `npm test` (all conditional via inputs) |
| [`ci-shell`](actions/ci-shell/action.yml) | Shell | `shellcheck`, `bash -n` syntax validation |

### Add CI to a new repo

There are two repo classes:

- **Code repos**: `feature → dev` PRs, fast-forward `dev → main` promotion, deploy from `main`.
- **Infrastructure/control-plane repos**: `feature → main` PRs, no `dev`, no release promotion.

For both classes, the `CI` job name must be uppercase so it matches the org-wide
required status check.

**Code repos** use:

1. Create `.github/workflows/ci.yml` in the repo with the appropriate wrapper (examples below).
2. Triggers must be `push: [dev]` + `pull_request: [main, staging, dev]` to support the AI-first dev model (agents push directly to `dev`, feature PRs target `dev`, and promotion PRs or checks can still target `main`/`staging` when needed).

**Infrastructure/control-plane repos** use:

1. Create `.github/workflows/ci.yml`.
2. Triggers must be `push: [main]` + `pull_request: [main]`.
3. Keep the repo on `main` only. Do not add the fast-forward promotion caller.

**Rust:**
```yaml
name: CI
on:
  push:
    branches: [dev]
  pull_request:
    branches: [main, staging, dev]
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
    branches: [main, staging, dev]
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
        with:
          elixir-version: "1.19"
          otp-version: "28"
```

`ci-elixir` always runs `mix credo --strict`. Elixir repos should check in a
`.credo.exs` when they need explicit project policy, but missing config is not
an exemption from Credo.

Repos with stricter local gates should keep the shared action and pass explicit
commands instead of forking CI logic:

```yaml
      - uses: ForgingAlpha/.github/actions/ci-elixir@v1
        with:
          elixir-version: "1.19.5-otp-28"
          otp-version: "28.5"
          extra-checks-command: mix boundary.strict
          pre-test-command: psql -h localhost -U postgres -d postgres -v ON_ERROR_STOP=1 -f infrastructure/ci/init-users.sql
          test-command: mix test.core
```

`ci-rust` always runs every listed Rust check, including `cargo audit`. Missing
lint or audit readiness must be fixed in the consuming repo rather than skipped
in CI.

**Astro / TypeScript / Shell:** Same pattern — swap the action reference. See each action's `action.yml` header for the full usage example with available inputs.

### Modify CI for all repos of a language

1. Edit the composite action in `actions/ci-<language>/action.yml`.
2. Open a PR to this repo's `main` branch.
3. After merge, push a semver tag such as `v1.0.1`; the release workflow moves
   the `v1` tag so consumers pinned to `@v1` pick up the change on their next
   CI run.

No per-repo PRs needed unless a repository must pass new inputs or different
commands. One released change here = org-wide rollout.

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
release App ID/private key through GitHub Actions variables/secrets synced from
Doppler. The release App must be a bypass actor on the `code-release-branches`
ruleset only; `branch-safety` remains no-bypass so deletion and
non-fast-forward updates stay blocked.

### Why composite actions (not reusable workflows)

Reusable workflows produce a compound status check name (`CI / CI`) that doesn't match the required `CI` status check used in the org rulesets. Composite actions run inside the caller's job, so the check name stays `CI`. This was validated during the initial architecture setup and is documented in the Obsidian vault.

## Branch Protection (Org-Wide Rulesets)

Three rulesets enforce rules across all repos in the org:

| Ruleset | Branches | Rules |
|---|---|---|
| `branch-safety` | `main`, `staging`, `dev` | Block deletions + block force pushes |
| `code-release-branches` | `main`, `staging` on code repos | Require PR, CI, CodeQL, Copilot review; release App bypass allowed |
| `control-plane-main` | `main` on `.github` and `alphaapps-docs` | Require PR, CI, CodeQL; no release App bypass |

`dev` is intentionally excluded from `code-release-branches` so agents can push directly. The `branch-safety` ruleset still protects `dev` from deletion and force-push. `.github` and `alphaapps-docs` are infrastructure/control-plane repos and therefore use `feature → main` PRs under `control-plane-main`, not `dev → main` release promotion.

Bypass:
- `branch-safety`: none
- `code-release-branches`: Organization Admin + `forgingalpha-release` GitHub App
- `control-plane-main`: Organization Admin only

The bot (`forgingalpha-bot`) is an org member with write access and cannot bypass any rule.

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
`actions/dependabot-automerge`. Repos should keep only a thin caller workflow:

```yaml
name: Dependabot Auto-merge
on: pull_request
permissions:
  contents: read
jobs:
  skip-nondependabot:
    name: Skip non-Dependabot PR
    if: ${{ github.event.pull_request.user.login != 'dependabot[bot]' }}
    runs-on: ubuntu-latest
    steps:
      - name: Explain skip
        run: echo "Dependabot auto-merge only runs for Dependabot PRs."

  dependabot-automerge:
    name: Enable auto-merge
    if: ${{ github.event.pull_request.user.login == 'dependabot[bot]' }}
    permissions:
      contents: write
      pull-requests: write
    runs-on: ubuntu-latest
    steps:
      - name: Enable auto-merge
        uses: ForgingAlpha/.github/actions/dependabot-automerge@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          allow_patch: "true"
          allow_minor: "true"
          allow_major: "false"
          merge_method: merge
```

## Standards

- [Repo naming convention](docs/repo-naming.md)

## Full Architecture Documentation

The complete architectural context (why decisions were made, the bot permission model, authentication contract, deployment mapping) lives in the Obsidian vault:

**Alpha Apps Git and GitHub Process** in `alphaapps-docs`
