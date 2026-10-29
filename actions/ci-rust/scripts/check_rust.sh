#!/usr/bin/env bash
set -euo pipefail
mode="${1:?mode required}"
step="${2:?step required}"
case "$mode" in legacy|central) ;; *) exit 2 ;; esac
locked=()
if [[ "$mode" = central ]]; then locked=(--locked --workspace); fi
case "$step" in
  fmt) cargo fmt --all -- --check ;;
  clippy) cargo clippy "${locked[@]}" --all-targets --all-features -- -D warnings ;;
  check) RUSTFLAGS="-D dead_code" cargo check "${locked[@]}" --all-targets ;;
  test) cargo test "${locked[@]}" --all-targets --all-features ;;
  install-audit) cargo install cargo-audit --locked --version "${CARGO_AUDIT_VERSION:?trusted version required}" ;;
  audit) cargo audit ;;
  *) echo 'WHAT: Unknown Rust check. WHY: Only fixed steps are supported. HOW: Repair the checking source.' >&2; exit 2 ;;
esac
