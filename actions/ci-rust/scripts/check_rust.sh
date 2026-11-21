#!/usr/bin/env bash
set -euo pipefail
mode="${1:?mode required}"
step="${2:?step required}"
case "$mode" in
  public)
    case "${3-}" in
      true) mode=locked ;;
      false) mode=legacy ;;
      *) echo "WHAT: Invalid locked input. WHY: Cargo lock policy must be explicit. HOW: Use true or false." >&2; exit 2 ;;
    esac ;;
  legacy|central) ;;
  *) exit 2 ;;
esac

locked=()
case "$mode" in
  locked) locked=(--locked) ;;
  central) locked=(--locked --workspace) ;;
esac

if [[ "$mode" = locked ]]; then
  if ! manifest=$(cargo locate-project --workspace --manifest-path Cargo.toml --message-format plain); then
    echo "WHAT: Cannot locate the selected workspace. WHY: Locked checks need an explicit manifest. HOW: Set working-directory to the directory containing Cargo.toml." >&2
    exit 1
  fi
  lockfile="${manifest%/*}/Cargo.lock"
  # Cargo 1.97+ can redirect resolution via resolver.lockfile-path.
  export CARGO_RESOLVER_LOCKFILE_PATH="$lockfile"
  if [[ ! -f "$lockfile" || -L "$lockfile" ]] ||
     ! git ls-files --error-unmatch -- "$lockfile" >/dev/null ||
     ! git -C "${manifest%/*}" cat-file blob HEAD:./Cargo.lock | cmp -s - "$lockfile"; then
    echo "WHAT: $lockfile is missing or differs from the checkout. WHY: Locked checks need the committed workspace lockfile. HOW: Commit the current Cargo.lock and run CI from a clean copy of that file." >&2
    exit 1
  fi
fi
case "$step" in
  verify-lock)
    if [[ "$mode" = locked ]]; then
      cargo metadata --locked --format-version 1 >/dev/null
    fi ;;
  fmt) cargo fmt --all -- --check ;;
  clippy) cargo clippy "${locked[@]}" --all-targets --all-features -- -D warnings ;;
  check) RUSTFLAGS="-D dead_code" cargo check "${locked[@]}" --all-targets ;;
  test) cargo test "${locked[@]}" --all-targets --all-features ;;
  install-audit) cargo install cargo-audit --locked --version "${CARGO_AUDIT_VERSION:?trusted version required}" ;;
  audit)
    if [[ "$mode" = locked ]]; then cargo audit --file "$lockfile"; else cargo audit; fi ;;
  *) echo 'WHAT: Unknown Rust check. WHY: Only fixed steps are supported. HOW: Repair the checking source.' >&2; exit 2 ;;
esac
