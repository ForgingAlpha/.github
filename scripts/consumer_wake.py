"""Read-only wake filtering. This hint never admits a candidate or grants access."""
import os
from pathlib import Path
import re
import urllib.parse
from consumer_compatibility import API, BRANCH, CONSUMER, CONSUMER_ID, WORKFLOW, decode, integer, sha


def owned(run, prs, bot):
    try:
        branch = run["head_branch"]
        if not (integer(bot) and re.fullmatch(BRANCH, branch) and run["event"] == "pull_request" and
                run["status"] == "completed" and run["path"] in (WORKFLOW, ".github/workflows/ci.yml") and
                run["repository"]["id"] == run["head_repository"]["id"] == CONSUMER_ID and
                run["actor"]["id"] == bot and run["actor"]["type"] == "Bot" and len(prs) == 1):
            return False
        pr = prs[0]
        return (pr["state"] == "open" and pr["user"]["id"] == bot and pr["user"]["type"] == "Bot" and
                pr["head"]["ref"] == branch and pr["head"]["sha"] == sha(run["head_sha"]) and
                pr["head"]["repo"]["id"] == pr["base"]["repo"]["id"] == CONSUMER_ID and
                pr["base"]["ref"] == "dev")
    except (KeyError, TypeError, ValueError):
        return False


def main():
    # Only adopted shared code runs here, with the private read-only job token.
    event = decode(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())
    number = event.get("workflow_run", {}).get("id")
    admitted = False
    if integer(number):
        api = API(CONSUMER, os.environ["CC_READ_TOKEN"])
        run = api.request("/actions/runs/" + str(number))
        branch = run.get("head_branch", "")
        if isinstance(branch, str) and re.fullmatch(BRANCH, branch):
            prs = api.listing("/pulls?state=open&head=" + urllib.parse.quote("ForgingAlpha:" + branch))
            admitted = owned(run, prs, int(os.environ["CC_FIXTURE_BOT_ID"]))
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write("admitted=" + str(admitted).lower() + "\n")


if __name__ == "__main__":
    main()
