# Exact source observation

Use this read-only action from a trusted `push` caller on `main` when the
repository's actual default is `main`. The caller supplies only its existing
read-only security proof token. The helper reads `GITHUB_EVENT_PATH`,
`GITHUB_EVENT_NAME`, `GITHUB_REF` and `GITHUB_SHA`; workflow inputs cannot
substitute a push or select a historical merge.

The event must identify this repository and `refs/heads/main`, with `forced`
and `deleted` false. Its `after` must equal both the runner SHA and current main;
its `before` must equal the classified base. A branch-creation push cannot
satisfy this base binding. The unique merged Dependabot PR must retain the fixed
App's successful classification completed strictly before its human merge,
ordered parents `[classified base, source head]`, the source-head tree, the
approved manifest/lock delta and the complete official advisory proof. The
observer rechecks canonical default and current main after proof reconciliation.

Required CI and CodeQL belong to the existing pre-merge classification path.
Observation does not rerun post-merge CI, create classification, mint a token,
write a check, approve or merge a PR, or gate an independently starting deployment.
Its outputs report the exact observed repository, kind, ref, branch, PR, hashes,
human attribution and advisories; attribution alone does not prove authorization.

The caller needs existing contents, pull-request, checks and official vulnerability
alert read capabilities. A missing capability stops observation. Keep the token
in the authorized security boundary; never check out or execute candidate code
there. Actual caller installation, protected defaults, environment restrictions,
required checks, authorization and deployment remain separate qualifications.

For a separate `dev` security source, retain `security-patch-projection` and the
projection operations in `security-patch-verification`. Historical `verify-source`
remains immutable source proof and intentionally tolerates later dev movement;
it does not establish a current-main push.
