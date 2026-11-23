"""Read the outcome of an ordinary native merge from its original GitHub PR."""

import argparse
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from eligibility import classify_change, security
from enrollment import SHA, load_policy, positive, require
import proof


def observe(api, repository, number, merge):
    require(re.fullmatch(r"ForgingAlpha/[A-Za-z0-9_.-]+", repository)
            and positive(number) and SHA.fullmatch(merge), "invalid merge subject")
    pull = api.get(f"repos/{repository}/pulls/{number}", fresh=True)
    base = pull["base"]
    require(pull["number"] == number and base["repo"]["full_name"] == repository
            and pull["state"] == "closed" and pull["merged"] is True and pull["merged_at"]
            and pull["merge_commit_sha"] == merge, "GitHub has not recorded this PR and merge")
    commit = security.git_commit(api, repository, merge)
    require(commit["sha"] == merge and [p["sha"] for p in commit["parents"]] == [base["sha"], pull["head"]["sha"]],
            "merge parents do not match the protected base and approved head")
    policy = load_policy(api, repository, base["sha"])
    require(policy and classify_change(api, repository, pull, policy) == "ordinary",
            "expected an enrolled ordinary change; security sources have their own observer")
    record = proof.completion_evidence(api, repository, pull, policy, commit["tree"]["sha"])
    require(record is not None, "missing a verified native completion; use the personal merge record")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository")
    parser.add_argument("pr", type=int)
    parser.add_argument("merge_commit")
    args = parser.parse_args()
    record = observe(security.GhApi(), args.repository, args.pr, args.merge_commit)
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (KeyError, IndexError, TypeError, ValueError, RuntimeError, OSError) as exc:
        sys.exit(f"Could not verify native merge: {exc}")
