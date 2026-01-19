# Repo naming

## Rule

Use kebab-case and name repos by identity, not hosting.

Format:

<product-or-company>-<subbrand-or-service>-<surface>

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

## Examples

- turnkeyleads-app
- turnkeyleads-web
- turnkeyleads-whatismyhomeworth-web
- analyzingalpha-data
- analyzingalpha-vault
- forge-cli
- alphaapps-infra

## What goes where

App-specific deploy config (for example, `fly.toml`, `Dockerfile`) lives in the app repo.
Shared infrastructure and runbooks live in `alphaapps-infra` (for example, DNS IaC, shared DB/Redis, alerts, incident playbooks).

## Rationale

- DNS is configuration; repo names are identity.
- Names should answer "what is this?" at a glance.
- Consistent naming scales as we add products and surfaces.
