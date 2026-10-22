#!/usr/bin/env python3
"""Trusted, offline admission of selected foundation exports; no candidate imports."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import signal
import stat
import subprocess
import sys
import time


REPOSITORY = "https://github.com/ForgingAlpha/container-foundation"
REPOSITORY_ID = 1428636846
FORMAT = "foundation-source-v1"
CATALOG = Path(__file__).absolute().parent.parent / "approved.json"
METADATA_LIMIT = 1024 * 1024
FILE_LIMIT = 16 * 1024 * 1024
TOTAL_LIMIT = 64 * 1024 * 1024
ENTRY_LIMIT = 4096
RECORD_LIMIT = 256
GIT_TIMEOUT = 30
GIT_ID = re.compile(r"[a-f0-9]{40}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
IDENTITY_KEYS = {"repository", "repository_id", "format", "commit", "tree"}


class Refused(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def unique_pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON property")
        result[key] = value
    return result


def decode(data):
    def invalid_constant(_):
        raise Refused("non-JSON numeric constant")
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_pairs,
                      parse_constant=invalid_constant)


def read_regular(path, limit):
    # NONBLOCK avoids hanging on a special file swapped in before open.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), "nonregular or linked evidence")
        require(before.st_size <= limit, "supported input size exceeded")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    require(len(data) <= limit and len(data) == before.st_size,
            "input size changed or supported limit exceeded")
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
             before.st_ctime_ns, before.st_mode) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
             after.st_ctime_ns, after.st_mode), "evidence changed during read")
    return data, before


def identity(value):
    require(isinstance(value, dict), "source identity is not an object")
    require(value.get("repository") == REPOSITORY and
            type(value.get("repository_id")) is int and
            value["repository_id"] == REPOSITORY_ID and value.get("format") == FORMAT,
            "unsupported source identity or format")
    for name in ("commit", "tree"):
        require(isinstance(value.get(name), str) and GIT_ID.fullmatch(value[name]),
                "full canonical Git identity required")


def catalog(data):
    value = decode(data)
    require(isinstance(value, dict) and set(value) == {"schema_version", "records"}
            and type(value["schema_version"]) is int and value["schema_version"] == 1,
            "unsupported catalog schema")
    records = value["records"]
    require(isinstance(records, list) and len(records) <= RECORD_LIMIT,
            "invalid or oversized catalog")
    commits, digests = set(), set()
    for row in records:
        require(isinstance(row, dict) and set(row) == IDENTITY_KEYS | {"lock_sha256"},
                "invalid catalog record shape")
        identity(row)
        require(isinstance(row["lock_sha256"], str) and SHA256.fullmatch(row["lock_sha256"]),
                "invalid manifest fingerprint")
        require(row["commit"] not in commits and row["lock_sha256"] not in digests,
                "duplicate or conflicting catalog records")
        commits.add(row["commit"])
        digests.add(row["lock_sha256"])
    return records


def relative_path(value):
    require(isinstance(value, str) and value and "\\" not in value and "\x00" not in value,
            "invalid inventory path")
    path = PurePosixPath(value)
    require(path.parts and not path.is_absolute() and str(path) == value and
            all(part not in (".", "..") for part in path.parts),
            "inventory path escape or alias")
    return path


def manifest(data):
    value = decode(data)
    require(isinstance(value, dict) and set(value) == IDENTITY_KEYS | {"files"},
            "unsupported manifest shape")
    identity(value)
    files = value["files"]
    require(isinstance(files, list) and 0 < len(files) <= ENTRY_LIMIT,
            "invalid inventory count")
    previous, total, names = "", 0, set()
    for row in files:
        require(isinstance(row, dict) and set(row) == {"path", "mode", "size", "sha256"},
                "invalid inventory entry")
        path = relative_path(row["path"])
        require(row["path"] > previous, "unsorted or duplicate inventory")
        previous = row["path"]
        require(row["mode"] in ("100644", "100755") and
                type(row["size"]) is int and 0 <= row["size"] <= FILE_LIMIT and
                isinstance(row["sha256"], str) and SHA256.fullmatch(row["sha256"]),
                "invalid inventory representation")
        require(not any(str(parent) in names for parent in path.parents),
                "inventory file/directory collision")
        names.add(row["path"])
        total += row["size"]
    require(total <= TOTAL_LIMIT, "supported payload size exceeded")
    return value


def inventory(root):
    require(root.is_dir() and not root.is_symlink(), "payload directory missing or linked")
    files, directories, total = [], set(), 0
    pending, examined = [root], 0
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                examined += 1
                require(examined <= ENTRY_LIMIT * 2, "supported payload entry count exceeded")
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                relative_path(relative)
                require(not entry.is_symlink(), "linked payload entry")
                if entry.is_dir(follow_symlinks=False):
                    directories.add(relative)
                    pending.append(path)
                    continue
                require(len(files) < ENTRY_LIMIT, "supported payload file count exceeded")
                data, info = read_regular(path, min(FILE_LIMIT, TOTAL_LIMIT - total))
                executable = info.st_mode & 0o111
                require(executable in (0, 0o111), "unsupported executable mode")
                total += len(data)
                files.append({"path": relative, "mode": "100755" if executable else "100644",
                              "size": len(data), "sha256": sha256(data)})
    expected_dirs = {str(parent) for row in files for parent in
                     PurePosixPath(row["path"]).parents if str(parent) != "."}
    require(directories == expected_dirs, "unexpected empty payload directory")
    return sorted(files, key=lambda row: row["path"])


def root_path(raw):
    root = Path(raw).absolute()
    require(root == root.resolve() and root.is_dir() and not root.is_symlink(),
            "explicit canonical checkout root required")
    return root


def verify(root, records, evidence):
    state = root / ".foundation-state"
    if os.path.lexists(state):
        require(state.is_dir() and not state.is_symlink(), "invalid selection state")
        require(not os.path.lexists(state / "transaction.json"), "incomplete source import")
    raw, _ = read_regular(root / "foundation.lock", METADATA_LIMIT)
    digest = sha256(raw)
    evidence["lock_sha256"] = digest
    approved = [row for row in records if row["lock_sha256"] == digest]
    require(len(approved) == 1, "manifest is not admitted by the resolved shared policy")
    value = manifest(raw)
    require(all(value[name] == approved[0][name] for name in IDENTITY_KEYS),
            "manifest identity differs from approved record")
    require(inventory(root / ".foundation") == value["files"],
            "actual working payload differs from approved manifest")
    return {"result": "working_pair_matches_approved_export",
            "source_commit": value["commit"], "source_tree": value["tree"],
            "lock_sha256": digest}


def git(source, *args, limit=METADATA_LIMIT):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
    command = ["git", "--no-replace-objects", "-c", "core.fsmonitor=false", "-C", str(source), *args]
    output, counts, deadline = bytearray(), {"stdout": 0, "stderr": 0}, time.monotonic() + GIT_TIMEOUT
    with subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, start_new_session=True) as process:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, ("stdout", limit))
                selector.register(process.stderr, selectors.EVENT_READ, ("stderr", METADATA_LIMIT))
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    require(remaining > 0, "canonical Git operation timed out")
                    events = selector.select(remaining)
                    require(events, "canonical Git operation timed out")
                    for key, _ in events:
                        name, cap = key.data
                        data = os.read(key.fd, min(65536, cap - counts[name] + 1))
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        counts[name] += len(data)
                        require(counts[name] <= cap, "supported Git output size exceeded")
                        if name == "stdout":
                            output.extend(data)
            remaining = deadline - time.monotonic()
            require(remaining > 0, "canonical Git operation timed out")
            require(process.wait(timeout=remaining) == 0, "canonical Git object unavailable")
        finally:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
    return bytes(output)


def derive(source, revision):
    """Independent export representation; local Git alone proves no hosted eligibility."""
    require(isinstance(revision, str) and GIT_ID.fullmatch(revision), "full source commit required")
    require(git(source, "rev-parse", "--show-toplevel").decode().strip() == str(source),
            "explicit source repository root required")
    origin = git(source, "remote", "get-url", "origin").decode().strip().lower()
    require(origin.removesuffix(".git") in (REPOSITORY.lower(),
            "git@github.com:forgingalpha/container-foundation"), "noncanonical source origin")
    require(git(source, "rev-parse", revision + "^{commit}").decode().strip() == revision,
            "source commit mismatch")
    tree = git(source, "rev-parse", revision + ":payload").decode().strip()
    files, total = [], 0
    entries = git(source, "ls-tree", "-rz", revision + ":payload").split(b"\0")
    require(len(entries) - (entries[-1] == b"") <= ENTRY_LIMIT,
            "supported export entry count exceeded")
    for entry in entries:
        if not entry:
            continue
        header, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split()
        path = raw_path.decode("utf-8")
        relative_path(path)
        require(kind == "blob" and mode in ("100644", "100755"), "unsupported Git export entry")
        size = int(git(source, "cat-file", "-s", oid))
        require(0 <= size <= FILE_LIMIT, "supported source file size exceeded")
        total += size
        require(total <= TOTAL_LIMIT, "supported source payload size exceeded")
        body = git(source, "cat-file", "blob", oid, limit=FILE_LIMIT)
        require(len(body) == size, "source blob size mismatch")
        files.append({"path": path, "mode": mode, "size": size, "sha256": sha256(body)})
        require(len(files) <= ENTRY_LIMIT, "supported export entry count exceeded")
    value = {"repository": REPOSITORY, "repository_id": REPOSITORY_ID, "format": FORMAT,
             "commit": revision, "tree": tree, "files": sorted(files, key=lambda row: row["path"])}
    raw = encode(value)
    require(len(raw) <= METADATA_LIMIT, "supported manifest size exceeded")
    manifest(raw)
    record = {name: value[name] for name in IDENTITY_KEYS}
    record["lock_sha256"] = sha256(raw)
    return raw, record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for name in ("verify", "update-owner"):
        child = sub.add_parser(name)
        child.add_argument("--root", required=True)
    sub.add_parser("catalog")
    child = sub.add_parser("derive")
    child.add_argument("--source", required=True)
    child.add_argument("--revision", required=True)
    child.add_argument("--lock-output", required=True,
                       help="New private file only; never publish its inventory")
    args = parser.parse_args()
    evidence = {"policy_catalog_sha256": None, "verifier_sha256": None,
                "lock_sha256": None,
                "action_ref": os.environ.get("FOUNDATION_ACTION_REF") or "local-candidate",
                "policy_commit_evidence": "same-job native action acquisition log required"}
    try:
        if args.operation == "derive":
            raw, record = derive(root_path(args.source), args.revision)
            with open(args.lock_output, "xb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(raw)
            print(json.dumps({"candidate_record": record,
                              "eligibility": "not_established_by_local_derivation"}, sort_keys=True))
            return 0
        evidence["verifier_sha256"] = sha256(read_regular(Path(__file__), FILE_LIMIT)[0])
        policy_bytes, _ = read_regular(CATALOG, METADATA_LIMIT)
        evidence["policy_catalog_sha256"] = sha256(policy_bytes)
        records = catalog(policy_bytes)
        if args.operation == "catalog":
            print(json.dumps(dict(evidence, result="catalog_schema_valid", records=len(records)), sort_keys=True))
            return 0
        root = root_path(args.root)
        if args.operation == "update-owner" and not any(
                os.path.lexists(root / name) for name in (".foundation", "foundation.lock")):
            print(json.dumps(dict(evidence, result="foundation_not_applicable"), sort_keys=True))
            return 0
        decision = verify(root, records, evidence)
        result = dict(evidence, **decision)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError, subprocess.SubprocessError) as error:
        if args.operation != "derive":
            # Null records no collected digest, without asserting why it is absent.
            print(json.dumps(dict(evidence, result="refused"), sort_keys=True))
        # Do not disclose paths, private inventory, source bytes or resolved environment.
        print("WHAT: Foundation source verification or derivation failed.", file=sys.stderr)
        reason = str(error) if isinstance(error, Refused) else "Required evidence is unavailable or malformed."
        print("WHY: " + reason, file=sys.stderr)
        print("HOW: Restore a complete approved pair; resolve the shared catalog/source evidence before retrying.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
