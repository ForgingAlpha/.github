# Consumer compatibility fixtures

Shared changes need evidence from affected consumers before merge. Shared checks
belong here; each consumer retains its product requirements, commands and tests.

`scripts/qualify_foundation.py` generates a disposable Foundation PR workflow from
an exact revision of Foundation's own CI workflow. It reads Git objects, preserves
the consumer's commands and final evaluator, and substitutes seven shared Action
references with one complete, verified candidate checkout. It adds source checks
and a distinct **Shared candidate compatibility** result. Foundation's normal
workflow remains unchanged.

The adapter supports Foundation's current single-job workflow contract. Changed
step order, conditions, inherited execution settings, extra stages, ambiguous YAML
or nested first-party Action references require a reviewed adapter update. It
refuses these inputs instead of guessing how to translate them. Public tests use
synthetic commands; actual consumer workflows and logs stay in their owning repo.

The generator uses Python and the existing shared CI PyYAML dependency. Supply
exact commit and tree identities from verified source bindings:

```bash
python3 -I -B scripts/qualify_foundation.py \
  --consumer-repo "$consumer_checkout" \
  --consumer-commit "$consumer_commit" --consumer-tree "$consumer_tree" \
  --candidate-repo "$shared_checkout" \
  --candidate-commit "$shared_commit" --candidate-tree "$shared_tree" \
  --branch "$fixture_branch" --output "$new_fixture_file"
```

The output path must not exist. The fixture branch must start with `test/`.
Publish the generated file as `.github/workflows/shared-candidate.yml` on a
disposable same-repository Foundation PR to `dev`. Never merge the fixture.
The tool itself performs no network operations, publication or credential setup.

Each acquisition verifies the shared commit, tree, actual files and repository.
The candidate is reacquired after the consumer's root checkout and removed before
product tests require a clean tree. Empty read-only Python cache directories prevent
isolated Python imports from changing the candidate. This is source hygiene, not
an execution sandbox. Candidate jobs must remain read-only and receive no
orchestration credentials.

A successful fixture proves compatibility only for its exact recorded inputs and
observed run. Automatic triggering, stale-result reconciliation and aggregation into
shared CI require a separately qualified trusted integration. This generator alone
does not provide those effects or merge authority.
