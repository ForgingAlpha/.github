# Repo naming

## Rule

Use kebab-case and name repos by identity, not hosting.

Format:

`<product-or-company>-<subbrand-or-service>-<surface>`

Illustrative example: `example-product-api`.

Surface examples:

- web
- api
- worker
- cli
- infra
- docs
- sdk
- blog
- landing
- legacy

Find current repositories in the [ForgingAlpha repository directory](https://github.com/orgs/ForgingAlpha/repositories).

## What goes where

App-specific deploy config (for example, `fly.toml`, `Dockerfile`) lives in the app repo.
For shared infrastructure and runbooks (for example, DNS IaC, shared DB/Redis, alerts, incident playbooks), consult the accountable owning project's documentation to find the responsible repository and operating guidance.

## Rationale

- DNS is configuration; repo names are identity.
- Names should answer "what is this?" at a glance.
- Consistent naming scales as we add products and surfaces.
