# Consumer qualification

The [Foundation implementation transition](requirements.md#foundation-implementation-transition)
preserves the specified existing controller and result obligations until qualified
source replacement. The target qualification duties below govern its acceptance.

Shared changes need evidence from affected consumers before merge. Shared checks
belong here; each consumer retains its product requirements, commands and tests.

## Standards rejection and consumer remediation

A correct rule rejection can expose a consumer violation. Diagnose it against
the exact rule, consumer configuration and inputs. The responsible shared-CI or
consumer maintainer retains that evidence in the owning change record, with
private material kept in consumer custody. Fix the consumer when it violates
the selected contract; fix the checker when it misapplies that contract.
Unknown causes remain unresolved. Diagnosis never changes the required result.

A passing negative assertion leaves the underlying consumer workflow failed.
A remediated consumer revision must conform to its selected rule. Preserve every
required workflow and exact checking source applicable to that consumer and
change. A separate candidate workflow is required only where its adopted
qualification contract selects one. An incompatible rule replacement requires
resolution by its governing owner; failed evidence remains failed.

## Exact evidence

Qualification binds the shared candidate, consumer revision, selected checking
source, actual required workflows and their complete outcomes. Required product
steps and post-job hooks are part of the observed result. A changed input requires
its affected qualification to be reconciled before evidence is reused.

Record which observations execute actual consumers and which use synthetic
inputs or captured provider responses. Keep private source, commands, logs and
artifacts in their owning consumer custody. Shared reporting preserves the exact
subject and the limitations of the evidence.

Existing CI, CodeQL, human review and human merge requirements remain mandatory.
Source publication and local tests do not grant credentials, settings, private
execution or deployment authority. Required-result enforcement follows its
applicable native qualification and authorized operating procedure.
