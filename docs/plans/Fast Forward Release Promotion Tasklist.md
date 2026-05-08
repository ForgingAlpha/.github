---
tags:
  - org/alpha-apps
  - topic/git
  - topic/github
  - topic/release-management
---
# Fast Forward Release Promotion Tasklist

## Goal

Replace routine `dev → main` pull request merges with a fast-forward-only
promotion workflow:

```text
feature/* → dev by PR
dev → main by fast-forward promotion
main → deploy
```

This keeps `dev` as the default integration branch for agents, developers, and
Dependabot, while keeping `main` as the production pointer. The promotion step
must not use `forgingalpha-bot`; release authority belongs to a dedicated
GitHub App.

## Current Validated Facts

- `branch-safety` ruleset targets `main`, `staging`, and `dev`.
- `branch-safety` enforces `deletion` and `non_fast_forward`.
- `branch-safety` has no bypass actors.
- `code-release-branches` ruleset targets `main` and `staging` for code repos.
- `code-release-branches` excludes infrastructure/control-plane repos (`.github`, `alphaapps-docs`).
- `code-release-branches` enforces required PR, strict `CI`, Copilot review, and CodeQL.
- `code-release-branches` has `OrganizationAdmin` and `forgingalpha-release` bypass.
- `control-plane-main` targets `main` on `.github` and `alphaapps-docs`.
- `control-plane-main` enforces required PR, strict `CI`, and CodeQL.
- `control-plane-main` does not include the `forgingalpha-release` bypass.
- `analyzingalpha-vault` currently has no GitHub Environments.
- `GITHUB_TOKEN` pushes do not trigger downstream `push` workflows, so promotion
  must use a dedicated GitHub App or equivalent release identity.

## Tasklist

### Phase 1: Admin Design Lock

- [ ] Pick release identity name: `forgingalpha-release`.
- [ ] Confirm GitHub App is the release identity, not a PAT.
- [ ] Confirm App will be installed only on selected repos.
- [ ] Confirm App will not be used by agents or `fa-agent`.
- [ ] Confirm Doppler project name for release secrets.
  - Recommended: `alphaapps-github`.
- [ ] Confirm Doppler config for release secrets.
  - Recommended: `prd`.
- [ ] Confirm GitHub secret/var target.
  - Recommended: org-level Actions secret/var scoped to selected repos.
- [ ] Confirm whether Doppler official GitHub Actions sync is available.
- [ ] If Doppler sync is unavailable, choose manual GitHub secret copy for v1.

### Phase 2: Create Release GitHub App

- [ ] In GitHub org/admin UI, create GitHub App `forgingalpha-release`.
- [ ] Set repository permissions:
  - [ ] Contents: Read and write.
  - [ ] Checks: Read.
  - [ ] Metadata: Read (automatic).
  - [ ] Actions: Read only if the workflow validates workflow runs rather than
        check runs.
- [ ] Set organization permissions: none.
- [ ] Set user permissions: none.
- [ ] Subscribe to events: none.
- [ ] Install App on `analyzingalpha-vault` only for the pilot.
- [ ] Record App client ID.
- [ ] Generate private key.
- [ ] Store private key in Doppler as source of truth.
- [ ] Store client ID in Doppler as source of truth.

### Phase 3: Configure Doppler to GitHub Secrets

- [ ] Create Doppler project `alphaapps-github` if it does not exist.
- [ ] Create config `prd` if it does not exist.
- [ ] Add Doppler secrets:
  - [ ] `FORGINGALPHA_RELEASE_APP_CLIENT_ID`.
  - [ ] `FORGINGALPHA_RELEASE_APP_PRIVATE_KEY`.
- [ ] Preserve PEM format exactly.
  - If sync mangles newlines, switch to base64 encoding and document decode.
- [ ] Configure Doppler GitHub Actions sync to GitHub org.
- [ ] Scope synced secret/var to selected repositories only.
  - Pilot scope: `analyzingalpha-vault`.
- [ ] Verify GitHub org variable exists:
  - [ ] `FORGINGALPHA_RELEASE_APP_CLIENT_ID`.
- [ ] Verify GitHub org secret exists:
  - [ ] `FORGINGALPHA_RELEASE_APP_PRIVATE_KEY`.
- [ ] Do not add these secrets to `alphaapps-composer`.
- [ ] Do not reuse `GITHUB_FORGINGALPHA_BOT_TOKEN`.

### Phase 4: Ruleset Configuration

- [ ] Keep `branch-safety` unchanged.
  - [ ] `deletion` stays enabled.
  - [ ] `non_fast_forward` stays enabled.
  - [ ] bypass actors stays empty.
- [ ] Add `forgingalpha-release` as a bypass actor to `code-release-branches`.
- [ ] Verify bypass actor type is `Integration` / GitHub App.
- [ ] Verify the App bypass applies to `code-release-branches`.
- [ ] Verify the App does not bypass `branch-safety`.
- [ ] Verify `forgingalpha-bot` is not a bypass actor on any release ruleset.
- [ ] Audit `forgingalpha-bot` repo permission.
  - Expected: no `main` bypass, no admin-level release control.
- [ ] Document the final ruleset shape in `Alpha Apps Git and GitHub Process.md`.

### Phase 5: Central Reusable Workflow

Repo: `.github`

- [ ] Create reusable workflow:
  - `.github/workflows/promote-branch.yml`.
- [ ] Trigger:
  - `workflow_call`.
- [ ] Inputs:
  - [ ] `source_branch`, default `dev`.
  - [ ] `target_branch`, default `main`.
  - [ ] `required_checks`, default `CI`.
  - [ ] `tag_prefix`, default `prod`.
- [ ] Secrets:
  - [ ] `FORGINGALPHA_RELEASE_APP_PRIVATE_KEY`.
- [ ] Variables:
  - [ ] `FORGINGALPHA_RELEASE_APP_CLIENT_ID`.
- [ ] Add concurrency:
  - `promote-${{ github.repository }}-${{ inputs.target_branch }}`.
  - `cancel-in-progress: false`.
- [ ] Mint release App token with `actions/create-github-app-token`.
- [ ] Use pinned action SHAs, matching org workflow policy.
- [ ] Checkout full history.
- [ ] Fetch source and target branches.
- [ ] Validate fast-forward:
  - `git merge-base --is-ancestor origin/$target origin/$source`.
- [ ] Validate required checks on source SHA.
  - [ ] Support comma-separated required check names.
  - [ ] Fail if any required check is missing or not `success`.
- [ ] Configure git identity for `forgingalpha-release`.
- [ ] Push source to target:
  - `git push origin refs/remotes/origin/$source:refs/heads/$target`.
- [ ] Create annotated release tag:
  - `prod-YYYYMMDDTHHMMSSZ`.
- [ ] Push tag.
- [ ] Write workflow summary:
  - [ ] repository.
  - [ ] source branch and SHA.
  - [ ] target branch old SHA and new SHA.
  - [ ] tag name.
  - [ ] actor.
- [ ] Add failure message that links to the runbook section for divergence.

### Phase 6: Repo Caller Workflow for Pilot

Repo: `analyzingalpha-vault`

- [ ] Add `.github/workflows/promote-dev-to-main.yml`.
- [ ] Trigger:
  - `workflow_dispatch`.
- [ ] Permissions:
  - `contents: read`.
  - `checks: read`.
- [ ] Call reusable workflow:
  - `ForgingAlpha/.github/.github/workflows/promote-branch.yml@v1`.
- [ ] Inputs:
  - `source_branch: dev`.
  - `target_branch: main`.
  - `required_checks: CI`.
  - `tag_prefix: prod`.
- [ ] Secrets:
  - `FORGINGALPHA_RELEASE_APP_PRIVATE_KEY`.
- [ ] Ensure workflow is inert until App secret/var exists.
- [ ] Open PR to `dev`.
- [ ] Merge to `dev` after CI.

### Phase 7: Pilot Promotion

- [ ] Confirm no open `dev → main` PR is required for the pilot.
- [ ] Confirm `origin/main` is ancestor of `origin/dev`:
  - `git merge-base --is-ancestor origin/main origin/dev`.
- [ ] Run `Promote dev to main` workflow manually.
- [ ] Verify workflow passes.
- [ ] Verify `origin/main` SHA equals `origin/dev` SHA after promotion.
- [ ] Verify `prod-*` tag was created.
- [ ] Verify `deploy.yml` triggered from `push: main`.
- [ ] Verify `deploy-history.log` updated on Ironhide.
- [ ] Verify deployed image revision matches promoted SHA.
- [ ] Verify no back-merge is needed.

### Phase 8: Failure Runbook

Add to `Notes/Alpha Apps Git and GitHub Process.md`.

- [ ] Document normal promotion command flow.
- [ ] Document failed fast-forward diagnosis:

```bash
git fetch origin main dev
git log origin/main..origin/dev
git log origin/dev..origin/main
```

- [ ] If `origin/dev..origin/main` is empty:
  - [ ] Re-run promotion; prior fetch may have been stale.
- [ ] If `origin/dev..origin/main` has commits:
  - [ ] Treat as an incident.
  - [ ] Inspect commits on `main`.
  - [ ] Determine how direct `main` change happened.
  - [ ] If commits belong on `dev`, open a reconciliation PR from `main` to `dev`.
  - [ ] Do not force-push `main`.
  - [ ] Fix ruleset/bypass root cause.
- [ ] Document rollback:
  - redeploy prior `prod-*` tag or prior image, not force-push branch history.
- [ ] Document release App private-key rotation.

### Phase 9: Environment Support

For repos with staging/prod environments, for example `turnkeyleads-app`:

- [ ] Create GitHub Environment `staging`.
  - [ ] No required reviewers.
  - [ ] Deployment branches restricted to `main`.
- [ ] Create GitHub Environment `production`.
  - [ ] Required reviewer(s).
  - [ ] Deployment branches restricted to `main`.
  - [ ] Optional wait timer.
- [ ] Update deploy workflow:
  - [ ] `push: main` builds artifact once.
  - [ ] deploy staging automatically.
  - [ ] deploy production after `environment: production` approval.
- [ ] Confirm production approval is release approval, not code review.

### Phase 10: Cross-Repo Rollout

- [ ] Roll out after `analyzingalpha-vault` pilot succeeds.
- [ ] Candidate repos:
  - [ ] `turnkeyleads-app`.
  - [ ] `whosyouragent-app`.
  - [ ] `alphaapps-composer`.
  - [ ] other production repos using `dev + main`.
- [ ] For each repo:
  - [ ] Install `forgingalpha-release` App.
  - [ ] Add repo to Doppler GitHub secret sync scope.
  - [ ] Add caller workflow.
  - [ ] Validate ruleset coverage.
  - [ ] Run one promotion.
  - [ ] Verify `main == dev` after promotion.

## Success Criteria

- [ ] No routine `dev → main` PRs.
- [ ] No routine `main → dev` back-merges.
- [ ] `main` and `dev` share identical SHA immediately after promotion.
- [ ] Deploys still trigger from `push: main`.
- [ ] Promotion creates `prod-*` tags.
- [ ] Agents cannot bypass `main`.
- [ ] `forgingalpha-bot` has no release promotion authority.
- [ ] Release authority is isolated to `forgingalpha-release`.
- [ ] Production approval, when needed, happens through GitHub Environments.

## Open Questions

- [x] Does the GitHub UI/API accept the new App as `Integration` bypass actor on
      the existing org-level `code-release-branches` ruleset?
- [ ] Does Doppler's official GitHub Actions sync support selected org repos in
      the current plan tier?
- [ ] Should `prod-*` tags be annotated or lightweight?
  - Recommendation: annotated.
- [ ] Should promotion require only `CI`, or `CI` plus CodeQL?
  - Recommendation for v1: require `CI`; keep CodeQL on `main` deploy branch
    until promotion workflow can query CodeQL state reliably.

<!-- Migration provenance: moved from `alphaapps-docs/Workspaces/_Shared/Plans/Fast Forward Release Promotion Tasklist.md` to `.github/docs/plans/Fast Forward Release Promotion Tasklist.md` on 2026-05-08. -->
