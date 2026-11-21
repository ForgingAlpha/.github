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
  # Stable Cargo does not report the effective lock path. Verify that the
  # conventional location applies before handing that file to cargo-audit.
  python3 -I - <<'PY'
import os
from pathlib import Path
import sys

try:
    import tomllib
except ImportError:
    sys.exit("WHAT: Cargo config inspection requires Python 3.11+. "
             "WHY: The lockfile check must read TOML. HOW: Select a runner with Python 3.11 or newer.")

setting = "CARGO_RESOLVER_LOCKFILE_PATH"
unsupported = ("WHAT: Locked CI cannot verify a configured lockfile path. "
               "WHY: The audit requires the same committed lockfile as Cargo. "
               "HOW: Use locked CI with the conventional workspace lock or keep your repository's own checks.")
if setting in os.environ:
    sys.exit(unsupported)

seen = set()

def inspect(path):
    if path in seen:
        return
    seen.add(path)
    with path.open("rb") as source:
        config = tomllib.load(source)
    if "lockfile-path" in config.get("resolver", {}) or setting in config.get("env", {}):
        sys.exit(unsupported)
    for entry in config.get("include", []):
        include = path.parent / (entry if isinstance(entry, str) else entry["path"])
        if isinstance(entry, dict) and entry.get("optional") and not include.exists():
            continue
        inspect(include)

cwd = Path.cwd()
directories = [d / ".cargo" for d in (cwd, *cwd.parents)]
directories.append(Path(os.environ.get("CARGO_HOME") or Path.home() / ".cargo"))
try:
    for directory in directories:
        # Cargo prefers the extensionless name when both files exist.
        for name in ("config", "config.toml"):
            path = directory / name
            if path.exists():
                inspect(path)
                break
except tomllib.TOMLDecodeError:
    if sys.version_info < (3, 15):
        sys.exit("WHAT: python3 could not parse the Cargo configuration. "
                 "WHY: This Python supports TOML 1.0; Cargo also accepts TOML 1.1. "
                 "HOW: For TOML 1.1, select Python 3.15+ as python3 on PATH before ci-rust. "
                 "Otherwise check the TOML syntax.")
    sys.exit("WHAT: Cargo configuration is not valid TOML for this python3. "
             "WHY: The audit needs a known lockfile. HOW: Check the TOML syntax in config files and includes.")
except (OSError, ValueError, TypeError, KeyError, RecursionError):
    sys.exit("WHAT: Could not inspect Cargo configuration. WHY: The audit needs a known lockfile. "
             "HOW: Check that the Cargo config files and their includes are valid and readable.")
PY
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
