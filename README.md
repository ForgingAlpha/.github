# ForgingAlpha/.github

Org-wide CI, security configuration, and standards for all ForgingAlpha repositories.

## Composite Actions (CI Library)

CI logic is centralized in `actions/`. Each repo's `.github/workflows/ci.yml`
is a thin wrapper that calls the right action. Required CI uses released refs
such as `@v1`, so moving the released major tag remains the rollout boundary for
merge authority. Manual diagnostic probes are intentionally different: they use
central reusable workflows on `.github@main` so every repo runs the latest
approved probe platform on the next manual probe.

| Action | Ecosystem | What it checks |
| --- | --- | --- |
| [`ci-alphaapps-policy`](actions/ci-alphaapps-policy/action.yml) | Alpha Apps | approved source truth, durable evidence references, required Product Evidence |
| [`ci-markdown`](actions/ci-markdown/action.yml) | Markdown | pinned `markdownlint-cli2`, all-file or changed-file docs linting |
| [`ci-github-actions`](actions/ci-github-actions/action.yml) | GitHub Actions | pinned actionlint, workflow permissions, trigger, action ref, and composite metadata safety |
| [`ci-dependabot-coverage`](actions/ci-dependabot-coverage/action.yml) | Dependabot | detected dependency-surface coverage in `.github/dependabot.yml` |
| [`ci-dependency-review`](actions/ci-dependency-review/action.yml) | Dependencies | PR dependency vulnerability and license review |
| [`ci-remote-probe-guard`](actions/ci-remote-probe-guard/action.yml) | Diagnostics | constrained remote probe input validation before repo-owned command assembly |
| [`ci-rust`](actions/ci-rust/action.yml) | Rust | `cargo fmt --all`, `cargo clippy -D warnings`, dead-code check, `cargo test`, `cargo audit` |
| [`ci-elixir`](actions/ci-elixir/action.yml) | Elixir | `mix format`, `mix compile --warnings-as-errors`, optional repo strict checks, `mix credo --strict`, optional pre-test setup, test command |
| [`ci-astro`](actions/ci-astro/action.yml) | Astro | `prettier`, `eslint`, `astro check`, `npm run build` |
| [`ci-typescript`](actions/ci-typescript/action.yml) | TypeScript | `prettier`, `eslint`, `tsc --noEmit`, `npm test` |
| [`ci-shell`](actions/ci-shell/action.yml) | Shell | `shellcheck`, `bash -n` syntax validation |

### Add CI to a new repo

There are two repo classes:

- **Code repos**: `feature → dev` PRs, fast-forward `dev → main` promotion, deploy from `main`.
- **Infrastructure/control-plane repos**: `feature → main` PRs, no `dev`, no release promotion.

For both classes, the `CI` job name must be uppercase so it matches the org-wide
required status check.

Every workflow that uses `ci-alphaapps-policy` directly or through a language
composite should checkout with `fetch-depth: 0`; the policy validators compare
the branch against the appropriate base ref.

**Code repos** use:

1. Create `.github/workflows/ci.yml` in the repo with the appropriate wrapper (examples below).
2. Triggers must be `push: [dev]` + `pull_request: [main, staging, dev]` to support the AI-first dev model (agents push directly to `dev`, feature PRs target `dev`, and promotion PRs or checks can still target `main`/`staging` when needed).

**Canonical code repo workflow** (Rust shown; swap the language wrapper as needed):

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
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: ForgingAlpha/.github/actions/ci-rust@v1
        with:
          markdown-mode: all
```

**Infrastructure/control-plane repos** use:

1. Create `.github/workflows/ci.yml`.
2. Triggers must be `push: [main]` + `pull_request: [main]`.
3. Keep the repo on `main` only. Do not add the fast-forward promotion caller.

**Canonical control-plane repo workflow**:

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
permissions:
  contents: read
jobs:
  CI:
    name: CI
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: ForgingAlpha/.github/actions/ci-alphaapps-policy@v1
      - uses: ForgingAlpha/.github/actions/ci-markdown@v1
        with:
          mode: all
      - uses: ForgingAlpha/.github/actions/ci-github-actions@v1
      - uses: ForgingAlpha/.github/actions/ci-dependabot-coverage@v1
```

Strict defaults:

- ShellCheck runs at `style` severity.
- Markdown uses `all` for new or clean repos; legacy repos may start with
  `changed` plus an explicit ignore list while docs are cleaned up.
- Active ForgingAlpha repos require approved source truth and Product Evidence.
- Dependabot coverage validation fails when detected dependency surfaces are
  missing update coverage or a documented unmanaged reason.
- GitHub Actions safety runs for changed workflow/action files by default in
  language composites; set `github-actions-mode: all` to force every run.
- Dependency review runs on pull requests for code/package repos.
- Keep `permissions: contents: read` unless a job has a specific elevated
  permission requirement.

Moving `v1` after the language composite wiring lands will enforce baseline
docs and Product Evidence in consuming repos. Do not move `v1` until active
repo baseline and Product Evidence backfill is ready for rollout.

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
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
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
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: ForgingAlpha/.github/actions/ci-elixir@v1
        with:
          elixir-version: "1.20"
          otp-version: "29"
```

`ci-elixir` always runs `mix credo --strict`. Elixir repos should check in a
`.credo.exs` when they need explicit project policy, but missing config is not
an exemption from Credo.

Repos with stricter local gates should keep the shared action and pass explicit
commands instead of forking CI logic:

```yaml
      - uses: ForgingAlpha/.github/actions/ci-elixir@v1
        with:
          elixir-version: "1.20"
          otp-version: "29"
          extra-checks-command: "<repo-owned extra check command>"
          pre-test-command: "<repo-owned pre-test setup command>"
          test-command: "<repo-owned test command>"
```

`ci-rust` always runs every listed Rust check, including `cargo audit`. Missing
lint or audit readiness must be fixed in the consuming repo rather than skipped
in CI.

**Markdown:** clean repos should run all-file linting with a checked-in
`.markdownlint-cli2.yaml`:

```yaml
      - uses: ForgingAlpha/.github/actions/ci-markdown@v1
        with:
          mode: all
```

Legacy repos may start with `mode: changed` and a documented `ignore` list
while existing docs are cleaned up. The action fails if the configured
Markdown lint config is missing.

**GitHub Actions safety:** repos with workflows or composite actions should run
the reusable safety gate directly, or let a language composite run it when
workflow/action files change:

```yaml
      - uses: ForgingAlpha/.github/actions/ci-github-actions@v1
```

Language composites default to `github-actions-mode: changed`, which compares
workflow and composite-action files before resolving `ci-github-actions@v1`.
Use `github-actions-mode: all` when a repo needs the safety gate on every CI
run.

Reviewed exceptions for `pull_request_target`, broad root permissions, or
unpinned third-party action refs live in
`.github/alphaapps-github-actions-allowlist.yml`; every exception entry must
carry a non-empty reason.

**Astro / TypeScript / Shell:** Same pattern — swap the action reference. See
each action's `action.yml` header for the usage example and supported inputs.
Language composites run the shared policy, Markdown, and Dependabot coverage
checks before their language-specific checks. They also run GitHub Actions
safety when workflow/action files changed or `github-actions-mode: all` is set;
code/package composites run dependency review on pull requests.

### Modify CI for all repos of a language

1. Edit the composite action in `actions/ci-<language>/action.yml`.
2. Open a PR to this repo's `main` branch.
3. After merge, push a semver tag such as `v1.0.1`; the release workflow moves
   the `v1` tag so consumers pinned to `@v1` pick up the change on their next
   CI run.

No per-repo PRs needed unless a repository must pass new inputs or different
commands. One released change here = org-wide rollout.

### Modify diagnostic probes for all repos

1. Edit the reusable probe workflow under `.github/workflows/ci-probe-*.yml` or
   the shared guard under `actions/ci-remote-probe-guard/`.
2. Open a PR to this repo's `main` branch.
3. After merge, every consumer workflow that calls
   `ForgingAlpha/.github/.github/workflows/ci-probe-*.yml@main` uses the new
   probe behavior on its next manual run.

No tag movement is required for probes. Probe workflows are diagnostic-only and
non-required, so `.github@main` keeps the internal agent-debugging surface
standardized without changing merge authority.

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

Reusable workflows produce a compound status check name (`CI / CI`) that doesn't match the required `CI` status check used in the org rulesets. Composite actions run inside the caller's job, so the check name stays `CI`. The architecture source is [docs/architecture.md](docs/architecture.md).

## Manual Remote Diagnostic Probes

Remote diagnostic probes are manual evidence collectors for failures that only
reproduce on GitHub runners or in required CI runtime. They are not merge
authority and must not be configured as required status checks. Required `CI`
remains the merge gate.

Consumer repos install a thin `.github/workflows/ci-probe.yml` on their default
branch. That wrapper calls one of this repo's centralized reusable workflows on
`@main`, passes repo-owned allowlists and version pins, and forwards manual
selector inputs. The consuming repo owns an executable `bin/ci-probe` adapter
that maps validated selectors to reviewed local commands.

The shared reusable workflows are:

- `.github/workflows/ci-probe-elixir-postgres.yml`
- `.github/workflows/ci-probe-rust.yml`
- `.github/workflows/ci-probe-docs.yml`

The shared [`ci-remote-probe-guard`](actions/ci-remote-probe-guard/action.yml)
action validates selector inputs before any target ref is checked out or
repo-owned command adapter runs. Probe wrappers and the shared guard use
`ForgingAlpha/.github@main` by design; manual probes are the latest-on-main
internal diagnostic surface, not a semver compatibility line.

Probe workflows follow this contract:

- `workflow_dispatch` only; no `push`, `pull_request`, or
  `pull_request_target` trigger.
- The workflow status is diagnostic-only and non-required.
- `permissions: contents: read` unless the consumer repo has a reviewed,
  documented diagnostic need for more.
- `run-name` includes the selected dispatch mode, lane, and target checkout ref.
- `timeout-minutes` is bounded and shorter than broad CI while still long
  enough for the selected diagnostic lane.
- `concurrency` is explicit in the reusable workflow so duplicate probes are
  visible and controlled.
- Operators run the trusted workflow definition with
  `gh workflow run --ref <trusted-default-branch>`, while target code is
  validated and checked out from the separate `checkout_ref` input.
- Inputs are constrained selectors: `probe_mode` (`exact`, `file`, `lane`),
  allowlisted `lane`, bounded repo-relative `file`, positive `line` for
  `exact`, safe `checkout_ref`, and safe `out_label`.
- The workflow accepts no arbitrary shell command input. Consumer repos expose
  an executable `bin/ci-probe` adapter that maps validated selectors to reviewed
  commands.
- Probe output artifacts upload with `if: always()` and short retention.
- `GITHUB_STEP_SUMMARY` records the exact normalized selector inputs and the
  artifact path.

Before operators run a probe, the concrete `.github/workflows/ci-probe.yml`
must already be landed on the trusted default or development branch that owns
the workflow definition. The probe job should use the centralized reusable
workflow that matches the required CI runtime it is diagnosing. Repo-specific
lane names, target test paths, line numbers, invocation examples, and failure
evidence belong in the consuming repo or private evidence, not this public
parent repo.

## Branch Protection (Org-Wide Rulesets)

Three rulesets enforce rules across all repos in the org:

| Ruleset | Branches | Rules |
| --- | --- | --- |
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
with grouped ecosystem updates and one open version-update PR at a time.
In this repo, Dependabot checks both workflow files and shared composite action
manifests under `actions/*`.

This cadence keeps update review predictable and early in the week. It also
limits noise in this public control-plane repo, where a merged action update can
affect every consuming repository after the `v1` rollout. Patch and minor
Dependabot PRs may auto-merge through the shared helper; major updates require
deliberate review.

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

## Dependency Review And Coverage

`ci-dependency-review` wraps GitHub dependency review for pull requests. It
does not replace language-specific checks: Rust repos still keep `cargo audit`
inside `ci-rust`, and other ecosystems keep their native audit/test gates when
available.

`ci-dependabot-coverage` validates that detected dependency surfaces have
matching `.github/dependabot.yml` update coverage. Standard starting points live
under [`templates/dependabot`](templates/dependabot/). Dependabot updates
manifest and GitHub Actions dependencies; hardcoded versions in shell commands,
workflow run blocks, and custom scripts require separate validation or audit
coverage when they are part of the public contract.

## Standards

- [Repo naming convention](docs/repo-naming.md)
- [Intent](docs/intent.md)
- [Requirements](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [Product Evidence](docs/evidence/product-evidence-view.md)

## Source Truth

The public source truth for this repository lives in `docs/intent.md`,
`docs/requirements.md`, and `docs/architecture.md`. Repo-local Product
Evidence under `docs/evidence/` is downstream verification evidence; it does
not create or change source truth. Active ForgingAlpha repositories need
approved baseline source truth and Product Evidence before the strict shared
policy action can pass ordinary code, test, dependency, runtime, maintenance,
release, or broad planning changes. Private Alpha Apps process and operator
guidance remains in `alphaapps-docs`.
