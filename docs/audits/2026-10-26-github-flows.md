# GitHub Flows — October 26, 2026

Observed2026-10-26 11:17–11:23UTC through the designated scoped GitHub operator; .github main/v1=3a8b7989f71088ef5242906e59a80d61881e8bfa; control-plane main=843056c78c7c7cc40cc5c721334bbd72fa090224. Evidence is retained in the implementation task record; exact consumer bindings are listed below. This is a dated audit, not policy or live execution certification.

| Concern | Observed now | Target / next action |
| --- | --- | --- |
| Human/agent separation | Sampled site main/dev/staging, control mains and app main carry team approval plus update restriction. Global selectors, bypass actors, team access/membership and denied-App-write behavior are not qualified. | Preserve human-only approval/merge; qualify full named-branch scope through operator. |
| Team vs CODEOWNERS | Sampled teamID20299307 requires1 approval, stale dismissal and the observed literal* pattern; actual root/nested coverage is unqualified. CODEOWNER review is false. Released full policy action still checks CODEOWNERS for unmigrated consumers. | New explicit central team bootstrap profile; do not delete all CODEOWNERS before consumer qualification. |
| CI pilot | PR75 adopted contract only; org-baseline.yml was absent at observation; this candidate now supplies its first documentation profile. | Implement first docs profile; exact human source merge + current green push CI, protected operator activation and actual hosted tests follow. |
| Current-base / check producer | Laya dev has CI with strict=false. Site main/staging, app/control-plane main strict=true, CI context has no producer field. .github main additionally binds CI producer15368. | Qualify strictness/producer binding per named branch during activation; preserve existing controls. |
| Normal upgrades | Shared Renovate disables bot/platform auto-merge; patch/minor/major minimum age3/7/30days. Unrestricted run window permits execution; no central scheduler source found. | Daily automatic PR preparation into code dev; main-only control planes into main. Humans merge, followed by separately governed production release. Verify actual hosted daily runs. |
| Security | Released classification → exact projection proposal → read-only verification interfaces exist. Full enrollment/actual executions unverified here. | No cooldown regardless of patch/minor/major SemVer. Qualified source PR human merge then isolated exact manifest/lock production PR, human merge and exact deployment observation. Never promote unrelated dev. |
| Dependabot scheduling | Central .github security-only config declares daily09:00 America/New_York and normal capacity0. | Distinguish this declaration from hosted execution. Security fixes are not routed by normal SemVer cooldowns. |
| Legacy ForgingAlpha/alphaapps-site (ID1151008489) | main/dev reference absent approved-automerge@v1; main absent dependabot-automerge@v1. Dev references absent security-patch-source@v1 and security-patch-activation@v1. Dev uses Renovate/security-only config; main still legacy normal Dependabot. | One owned consumer migration preserving complete security successor coverage and sole updater ownership; then retire obsolete callers. No proof old merge actions currently run. |
| Legacy ForgingAlpha/turnkeyleads-site (ID960093720) | main/dev reference absent dependabot-automerge@v1; no Renovate/update-policy config. CI also uses floating checkout@v6. | Separate owned consumer migration to current shared interfaces/pinned actions, without duplicate updater or unmanaged gap. |
| Lint / product checks | Shared Markdown, workflow-safety and language actions exist. Ordinary Markdown CLI supports executable plugins/config. | Bootstrap central data-only lint; preserve language checks and foundation-before-helper. No broad suppression or duplicate static checks. |
| Rust pilot | Turnkey Platform local dev is unborn/no origin; hosted alpha-data is docs-only at235f28c5… | Qualify actual hosted Rust source. Do not claim full two-consumer pilot or retire application common calls until it is real. |

Order by unblock: (1) docs-baseline implementation and independent checks, (2) human source merge/current-main CI, (3) protected operator activation plus existing/App-created PR pass/fail/repair and protection qualification, (4) merge Laya governing PR and resume website work under its actual product lane, (5) migrate proven stale AlphaAppsSite and TurnkeySite callers, with security coverage preserved, (6) qualify actual Rust consumer and source restoration tests before pilot expansion/common-call retirement. Consumer cleanup is independently preparable; missing Rust should not pretend to be a hosted app or block source implementation for the first docs profile.

No repository setting, merge, v1 movement, installation/grant or deployment was changed in this audit. Actual source publication, human merge and protected activation are separate evidence states.

The Laya site default branch was still `main` at11:37UTC. The application updater validator requires its declared update base to match the actual default branch; application enrollment must reconcile that with the adopted `dev` flow. This documentation-only pilot does not change the default branch or claim updater enrollment.

Concrete legacy callers, read at11:20–11:21UTC:

- `ForgingAlpha/alphaapps-site` main `b8fcca98994001838a595701ed3e4b3b0373717f` and dev `df2ec4240f206aff68e3b2c544db58906b26b961`: `.github/workflows/approved-auto-activation.yml` calls absent `approved-automerge@v1`.
- Its main `.github/workflows/dependabot-automerge.yml` calls absent `dependabot-automerge@v1`.
- Its dev `.github/workflows/security-patch-source.yml` and `.github/workflows/security-patch-observation.yml` call absent `security-patch-source@v1` and `security-patch-activation@v1`, respectively.
- `ForgingAlpha/turnkeyleads-site` main `bea943b7db560662cf4ef1ac8fd3bfc90e37864c` and dev `8d7c3461827e530a79bd5ee14d095e22ba1b64f0`: `.github/workflows/dependabot-automerge.yml` calls the absent action; `.github/workflows/ci.yml` retains floating `actions/checkout@v6`.

These are source defects at those revisions. They do not establish actual bot-merge execution. Migrate complete successor coverage and sole-updater ownership before retiring the old callers.
