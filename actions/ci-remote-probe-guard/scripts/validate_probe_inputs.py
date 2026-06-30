#!/usr/bin/env python3
"""Validate constrained remote diagnostic probe inputs."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath


ALLOWED_MODES = {"exact", "file", "lane"}
COMMAND_INPUT_NAMES = {"command", "cmd", "script", "shell", "run"}
LANE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
COMMAND_LIKE_RE = re.compile(r"[;&|`$()<>{}\\\"']")
SHA_RE = re.compile(r"^[0-9A-Fa-f]{40}$")
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@/-]{0,255}$")
REF_FORBIDDEN_RE = re.compile(r"[\000-\037\177\s~^:?*\[\\]")


@dataclass(frozen=True)
class ValidationError(Exception):
    field: str
    what: str
    why: str
    how: str


def render_error(error: ValidationError) -> str:
    return "\n".join(
        [
            f"✗ Invalid remote probe input '{error.field}'.",
            f"  WHAT: {error.what}",
            f"  WHY: {error.why}",
            f"  HOW: {error.how}",
        ]
    )


def fail(field: str, what: str, why: str, how: str) -> None:
    raise ValidationError(field=field, what=what, why=why, how=how)


def stripped(inputs: dict[str, str], key: str) -> str:
    value = inputs.get(key, "")
    return "" if value is None else str(value).strip()


def reject_command_inputs(inputs: dict[str, str]) -> None:
    for key in sorted(COMMAND_INPUT_NAMES & set(inputs)):
        if stripped(inputs, key):
            fail(
                key,
                f"{key} was provided, but command-like inputs are not accepted.",
                "remote probes may select only reviewed modes, lanes, files, and lines.",
                "remove the command-like input and add repo-owned command mapping in the workflow.",
            )


def split_list(value: str) -> list[str]:
    result: list[str] = []
    for chunk in value.replace("\n", ",").split(","):
        token = chunk.strip()
        if token:
            result.append(token)
    return result


def validate_lane_token(field: str, value: str) -> None:
    if not value:
        fail(
            field,
            f"{field} was empty.",
            "each probe run must select an explicit repo-owned lane.",
            "set lane to a value from allowed-lanes.",
        )
    if COMMAND_LIKE_RE.search(value) or not LANE_RE.fullmatch(value):
        fail(
            field,
            f"{field} was {value!r}, expected a safe lane token.",
            "lane names are selectors used by reviewed workflow case branches, not shell text.",
            "use letters, numbers, dot, underscore, colon, or hyphen only.",
        )


def parse_allowed_lanes(raw: str) -> set[str]:
    lanes = split_list(raw)
    if not lanes:
        fail(
            "allowed_lanes",
            "allowed_lanes was empty.",
            "lane selection must be validated against a repo-defined allowlist.",
            "set allowed-lanes to the lane names supported by the consumer workflow.",
        )
    for lane in lanes:
        validate_lane_token("allowed_lanes", lane)
    return set(lanes)


def parse_suffixes(raw: str) -> tuple[str, ...]:
    suffixes = split_list(raw)
    if not suffixes:
        fail(
            "file_suffixes",
            "file_suffixes was empty.",
            "file selectors need explicit test suffixes to reject arbitrary files.",
            "set file-suffixes to repo-owned test suffixes such as .exs.",
        )
    for suffix in suffixes:
        if not suffix.startswith(".") or "/" in suffix or "\\" in suffix or COMMAND_LIKE_RE.search(suffix):
            fail(
                "file_suffixes",
                f"file suffix {suffix!r} was unsafe.",
                "file suffixes constrain probes to reviewed test file types.",
                "use suffixes such as .exs, .py, .rs, or .test.ts.",
            )
    return tuple(suffixes)


def normalize_file_root(raw: str) -> str:
    root = raw.strip()
    if not root:
        fail(
            "file_root",
            "file_root was empty.",
            "file selectors must be bounded to one repo-relative root.",
            "set file-root to a directory such as test.",
        )
    if root.startswith("/"):
        fail(
            "file_root",
            f"file_root was {raw!r}, expected a repo-relative directory.",
            "absolute-looking roots can make probe path bounds ambiguous.",
            "remove the leading slash and use a repo-relative directory such as test.",
        )
    root = root.rstrip("/")
    if not root:
        fail(
            "file_root",
            f"file_root was {raw!r}, expected a repo-relative directory.",
            "file selectors must be bounded to one concrete repo-relative root.",
            "set file-root to a directory such as test.",
        )
    if COMMAND_LIKE_RE.search(root) or not PATH_RE.fullmatch(root):
        fail(
            "file_root",
            f"file_root was {raw!r}, expected a safe repo-relative directory.",
            "file roots are path bounds and must not include shell metacharacters.",
            "use a simple repo-relative directory such as test.",
        )
    raw_parts = root.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        fail(
            "file_root",
            f"file_root was {raw!r}, expected no dot or parent segments.",
            "path traversal would let a probe select files outside the approved root.",
            "set file-root to a normalized repo-relative directory.",
        )
    return PurePosixPath(*raw_parts).as_posix()


def normalize_file(value: str, root: str, suffixes: tuple[str, ...], required: bool) -> str:
    file_value = value.strip()
    if not file_value:
        if required:
            fail(
                "file",
                "file was empty.",
                "exact and file probe modes require a test file selector.",
                "set file to a repo-relative test file under the configured file-root.",
            )
        return ""
    if COMMAND_LIKE_RE.search(file_value) or not PATH_RE.fullmatch(file_value):
        fail(
            "file",
            f"file was {value!r}, expected a safe repo-relative path.",
            "file selectors are later passed as array arguments and must not contain shell syntax.",
            "use a repo-relative test path under the configured file-root.",
        )
    raw_parts = file_value.split("/")
    path = PurePosixPath(file_value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in raw_parts):
        fail(
            "file",
            f"file was {value!r}, expected no absolute, dot, or parent segments.",
            "path traversal would let a probe select files outside the approved root.",
            "use a normalized repo-relative test path.",
        )
    normalized = path.as_posix()
    if normalized == root or not normalized.startswith(f"{root}/"):
        fail(
            "file",
            f"file was {value!r}, expected a path under {root!r}.",
            "remote probes may target only the configured test root.",
            f"set file to a path like {root}/example_test.exs or adjust file-root intentionally.",
        )
    if not normalized.endswith(suffixes):
        fail(
            "file",
            f"file was {value!r}, expected suffixes {', '.join(suffixes)}.",
            "remote probes should target test files rather than arbitrary repo files.",
            "set file to an allowed test file suffix or update file-suffixes intentionally.",
        )
    return normalized


def normalize_line(value: str, required: bool) -> str:
    line = value.strip()
    if not line:
        if required:
            fail(
                "line",
                "line was empty.",
                "exact probe mode requires a positive line selector.",
                "set line to the positive integer line number of the target test.",
            )
        return ""
    if not re.fullmatch(r"[1-9][0-9]{0,6}", line):
        fail(
            "line",
            f"line was {value!r}, expected a positive integer.",
            "line selectors must be data, not shell syntax or zero.",
            "set line to a positive integer less than 10000000.",
        )
    return str(int(line))


def normalize_label(value: str) -> str:
    label = value.strip()
    if not label:
        fail(
            "out_label",
            "out_label was empty.",
            "probe artifacts need a stable safe label.",
            "set out-label to letters, numbers, dots, underscores, or hyphens.",
        )
    if label in {".", ".."} or "/" in label or "\\" in label:
        fail(
            "out_label",
            f"out_label was {value!r}, expected no path separators.",
            "artifact labels must not change the output directory structure.",
            "remove path separators from out-label.",
        )
    if COMMAND_LIKE_RE.search(label) or not LABEL_RE.fullmatch(label):
        fail(
            "out_label",
            f"out_label was {value!r}, expected a safe artifact label.",
            "artifact labels are used in filesystem paths and summary text.",
            "use letters, numbers, dots, underscores, or hyphens only.",
        )
    return label


def normalize_checkout_ref(value: str) -> str:
    ref = value.strip()
    if not ref:
        fail(
            "checkout_ref",
            "checkout_ref was empty.",
            "the trusted workflow definition needs an explicit target code ref to inspect.",
            "set checkout-ref to a branch, tag, ref, or full commit SHA.",
        )
    if SHA_RE.fullmatch(ref):
        return ref.lower()
    if ref == "HEAD" or ref.startswith("-"):
        fail(
            "checkout_ref",
            f"checkout_ref was {value!r}, expected an explicit safe branch, tag, ref, or SHA.",
            "symbolic or flag-shaped refs make diagnostic target selection ambiguous.",
            "set checkout-ref to a concrete branch, tag, refs/* value, or full commit SHA.",
        )
    if COMMAND_LIKE_RE.search(ref) or REF_FORBIDDEN_RE.search(ref) or not REF_RE.fullmatch(ref):
        fail(
            "checkout_ref",
            f"checkout_ref was {value!r}, expected a safe Git ref token.",
            "checkout refs are workflow_dispatch data and must be validated before actions/checkout.",
            "remove shell metacharacters, whitespace, and Git-ref-forbidden characters.",
        )
    if any(marker in ref for marker in ("..", "@{", "//")) or ref.endswith(("/", ".")):
        fail(
            "checkout_ref",
            f"checkout_ref was {value!r}, expected no traversal or malformed ref segments.",
            "Git ref traversal and malformed segments can select an unintended target.",
            "use a normalized branch, tag, refs/* value, or full commit SHA.",
        )
    for part in ref.split("/"):
        if part in {"", ".", ".."} or part.startswith(".") or part.endswith(".lock"):
            fail(
                "checkout_ref",
                f"checkout_ref segment {part!r} was unsafe.",
                "Git ref segments must not be hidden, parent-traversal, or lock-file shaped.",
                "rename the target branch/tag/ref or pass a full commit SHA.",
            )
    return ref


def validate_inputs(inputs: dict[str, str]) -> dict[str, str]:
    reject_command_inputs(inputs)

    mode = stripped(inputs, "probe_mode")
    if mode not in ALLOWED_MODES:
        fail(
            "probe_mode",
            f"probe_mode was {mode!r}, expected one of {', '.join(sorted(ALLOWED_MODES))}.",
            "remote probes expose typed selectors only, not arbitrary execution modes.",
            "choose exact, file, or lane.",
        )

    allowed_lanes = parse_allowed_lanes(stripped(inputs, "allowed_lanes"))
    lane = stripped(inputs, "lane")
    validate_lane_token("lane", lane)
    if lane not in allowed_lanes:
        fail(
            "lane",
            f"lane was {lane!r}, but allowed_lanes were {', '.join(sorted(allowed_lanes))}.",
            "consumer workflows must map only reviewed lane names to commands.",
            "add the lane to allowed-lanes after reviewing the workflow case branch, or choose an allowed lane.",
        )

    root = normalize_file_root(stripped(inputs, "file_root") or "test")
    suffixes = parse_suffixes(stripped(inputs, "file_suffixes") or ".exs")
    label = normalize_label(stripped(inputs, "out_label") or "probe")
    checkout_ref = normalize_checkout_ref(stripped(inputs, "checkout_ref"))

    raw_file = stripped(inputs, "file")
    raw_line = stripped(inputs, "line")
    if mode == "lane":
        if raw_file:
            fail(
                "file",
                "file was provided for lane mode.",
                "lane probes should run the whole reviewed lane without a file selector.",
                "leave file empty for lane mode or choose file/exact mode.",
            )
        if raw_line:
            fail(
                "line",
                "line was provided for lane mode.",
                "lane probes should not carry a line selector.",
                "leave line empty for lane mode or choose exact mode.",
            )
        normalized_file = ""
        normalized_line = ""
    elif mode == "file":
        if raw_line:
            fail(
                "line",
                "line was provided for file mode.",
                "file probes should run a reviewed file selector without a line selector.",
                "leave line empty for file mode or choose exact mode.",
            )
        normalized_file = normalize_file(raw_file, root, suffixes, required=True)
        normalized_line = ""
    else:
        normalized_file = normalize_file(raw_file, root, suffixes, required=True)
        normalized_line = normalize_line(raw_line, required=True)

    return {
        "probe_mode": mode,
        "lane": lane,
        "file": normalized_file,
        "line": normalized_line,
        "out_label": label,
        "artifact_path": f"probe-output/{label}",
        "checkout_ref": checkout_ref,
    }


def write_outputs(outputs: dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")
    for key, value in outputs.items():
        print(f"{key}={value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-mode", required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--allowed-lanes", required=True)
    parser.add_argument("--file", default="")
    parser.add_argument("--line", default="")
    parser.add_argument("--out-label", default="probe")
    parser.add_argument("--checkout-ref", required=True)
    parser.add_argument("--file-root", default="test")
    parser.add_argument("--file-suffixes", default=".exs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = {
        "probe_mode": args.probe_mode,
        "lane": args.lane,
        "allowed_lanes": args.allowed_lanes,
        "file": args.file,
        "line": args.line,
        "out_label": args.out_label,
        "checkout_ref": args.checkout_ref,
        "file_root": args.file_root,
        "file_suffixes": args.file_suffixes,
    }
    try:
        outputs = validate_inputs(inputs)
    except ValidationError as error:
        print(render_error(error), file=sys.stderr)
        return 1

    write_outputs(outputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
