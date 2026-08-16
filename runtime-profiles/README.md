# Runtime Profiles

`catalog.json` is the control-plane source for approved runtime tuples and
repository assignments. A consumer remains reproducible because it commits an
exact `mise.toml` and checksum-bearing `mise.lock`; the shared
`ci-runtime-profile` action proves those files are an exact projection of the
consumer's active assignment before installation.

The initial active canary is `ForgingAlpha/alphaapps-site` on profile
`node-24-site`. Elixir repositories are intentionally not assigned until an
official mise release contains verified Linux Erlang prebuilt checksums. This
avoids publishing an approved profile that the current installer cannot enforce.

Runtime updates change a complete compatible tuple here first. Direct consumer
runtime changes fail required CI. Generic Renovate mise updates and lock-file
maintenance remain disabled until the constrained projection writer is active.
