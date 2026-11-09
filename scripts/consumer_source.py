"""Source hygiene for a disposable, read-only consumer compatibility job.

Embedded by qualify_foundation.py; this is not a sandbox for candidate code.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess


CANDIDATE_PATH = "shared-ci-candidate"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *args):
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        stderr=subprocess.PIPE,
    )


def verify(root, commit, tree, *, prepared):
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "invalid candidate commit")
    require(re.fullmatch(r"[0-9a-f]{40}", tree), "invalid candidate tree")
    require(root.is_dir() and not root.is_symlink(), "candidate path is not an owned directory")
    require((root / ".git").is_dir() and not (root / ".git").is_symlink(), "candidate must be a standalone clone")
    origin = git(root, "remote", "get-url", "origin").decode().strip()
    require(origin in ("https://github.com/ForgingAlpha/.github", "https://github.com/ForgingAlpha/.github.git"), "wrong candidate repository")
    require(git(root, "rev-parse", "HEAD").decode().strip() == commit, "wrong candidate commit")
    require(git(root, "rev-parse", "HEAD^{tree}").decode().strip() == tree, "wrong candidate tree")
    require(not git(root, "status", "--porcelain=v1", "--untracked-files=all", "--ignored"), "candidate has modified, untracked or ignored files")
    files, directories, caches = {}, set(), set()
    for item in git(root, "ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if not item:
            continue
        metadata, raw_path = item.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        path = Path(raw_path.decode("utf-8"))
        require(mode in ("100644", "100755") and kind == "blob", "candidate contains a symlink or submodule")
        require(not path.is_absolute() and ".." not in path.parts and "__pycache__" not in path.parts, "unsupported candidate path")
        files[path] = (mode, blob)
        directories.update(p for p in path.parents if p != Path("."))
        if path.suffix == ".py":
            caches.add(path.parent / "__pycache__")
    # Inspect the actual filesystem, including ignored entries and empty directories.
    for current, dirs, names in os.walk(root, followlinks=False):
        relative = Path(current).relative_to(root)
        if relative == Path("."):
            dirs.remove(".git")
        for name in dirs:
            path = relative / name
            require(not (root / path).is_symlink(), "candidate contains a directory symlink")
            require(path in directories or (prepared and path in caches), "unexpected candidate directory")
        for name in names:
            require(relative / name in files, "unexpected candidate file")
    for path, (mode, blob) in files.items():
        actual = root / path
        info = actual.lstat()
        require(stat.S_ISREG(info.st_mode), "candidate file is not regular")
        require(bool(info.st_mode & stat.S_IXUSR) == (mode == "100755"), "candidate executable mode changed")
        content = actual.read_bytes()
        digest = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        require(digest == blob, "candidate content differs from the bound tree")
    for path in caches:
        actual = root / path
        if prepared:
            require(actual.is_dir() and not actual.is_symlink(), "prepared cache directory was replaced")
            require(stat.S_IMODE(actual.stat().st_mode) == 0o555 and not any(actual.iterdir()), "prepared cache directory changed")
        else:
            require(not os.path.lexists(actual), "candidate cache path already exists")
    return caches


def operate(workspace, operation, commit, tree):
    workspace = Path(workspace).resolve(strict=True)
    root = workspace / CANDIDATE_PATH
    caches = verify(root, commit, tree, prepared=operation == "cleanup")
    if operation == "prepare":
        for path in sorted(caches):
            target = root / path
            target.mkdir()
            target.chmod(0o555)
        verify(root, commit, tree, prepared=True)
    elif operation == "cleanup":
        shutil.rmtree(root)
        require(not os.path.lexists(root), "candidate cleanup incomplete")
        require(not git(workspace, "status", "--porcelain=v1", "--untracked-files=all", "--ignored"), "consumer is not clean after candidate cleanup")
    else:
        raise ValueError("unknown source operation")
    print(json.dumps({"operation": operation, "candidate_commit": commit, "candidate_tree": tree, "source_verified": True}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "cleanup"))
    parser.add_argument("commit")
    parser.add_argument("tree")
    args = parser.parse_args()
    operate(os.environ["GITHUB_WORKSPACE"], args.operation, args.commit, args.tree)


if __name__ == "__main__":
    main()
