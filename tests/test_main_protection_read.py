"""Requirement-derived refusals and observation preservation, without GitHub access."""

import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "main_protection_read", Path(__file__).parents[1] / "tools/main-protection-read.py")
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)


def response(value, status=200, extra_headers="", raw=False):
    body = value if raw else json.dumps(value)
    return subprocess.CompletedProcess([], 0 if status == 200 else 1,
                                       f"HTTP/2.0 {status} Status\r\n{extra_headers}\r\n{body}",
                                       "PRIVATE_ERROR_NEVER_RETAIN")


class Fixture:
    def __init__(self):
        self.calls = []
        self.responses = {"user": response({"login": "leosmigel", "type": "User", "id": 42})}
        for name, identity in reader.REPOSITORIES.items():
            root = f"repos/ForgingAlpha/{name}"
            self.responses[root] = response({
                "id": identity, "full_name": f"ForgingAlpha/{name}",
                "default_branch": "dev" if name == "container-foundation" else "main",
                "allow_auto_merge": name == "control-plane",
            })
            self.responses[f"{root}/branches/main"] = response({
                "name": "main", "protected": True, "commit": {"sha": "a" * 40}})
            self.responses[f"{root}/rules/branches/main"] = response([])
            self.responses[f"{root}/rulesets?includes_parents=true&per_page=100"] = response([])

    def run(self, command, **kwargs):
        self.calls.append(command)
        if command[1:8] != ["api", "--hostname", "github.com", "--method", "GET", "--include", "--header"]:
            raise AssertionError("Unexpected command/method/host")
        if kwargs.get("shell"):
            raise AssertionError("Shell must not be used")
        return self.responses.get(command[-1], response({"message": "PRIVATE_ERROR"}, 403))

    def collect(self):
        with patch.object(reader.subprocess, "run", side_effect=self.run):
            return reader.collect(reader.Reader("/usr/bin/gh"))


class MainProtectionReadTests(unittest.TestCase):
    def test_wrong_human_or_nonhuman_stops_before_repository_reads(self):
        for user in ({"login": "someone-else", "type": "User"},
                     {"login": "leosmigel", "type": "Bot"}, {}):
            with self.subTest(user=user):
                fixture = Fixture()
                fixture.responses["user"] = response(user)
                with self.assertRaises(ValueError):
                    fixture.collect()
                self.assertEqual([call[-1] for call in fixture.calls], ["user"])

    def test_wrong_repository_id_refuses_all_dependent_reads(self):
        fixture = Fixture()
        root = "repos/ForgingAlpha/.github"
        fixture.responses[root] = response({"id": 123})
        report = fixture.collect()
        self.assertIn("mismatched", report["repositories"]["ForgingAlpha/.github"]["identity"])
        self.assertFalse(any(call[-1].startswith(root + "/") for call in fixture.calls))

    def test_forbidden_missing_and_malformed_responses_remain_unknown(self):
        cases = [(response({}, 403), "http_error"), (response({}, 404), "http_error"),
                 (response("{broken", raw=True), "invalid_json"),
                 (response([], 200), "invalid_schema"),
                 (subprocess.CompletedProcess([], 1, "", "secret"), "unavailable")]
        for value, status in cases:
            with self.subTest(status=status):
                with patch.object(reader.subprocess, "run", return_value=value):
                    observed, payload = reader.Reader("gh").get("user")
                self.assertEqual(observed["status"], status)
                self.assertIsNone(payload)
                self.assertNotIn("value", observed)
                self.assertNotIn("secret", json.dumps(observed))

    def test_valid_observations_preserve_dev_human_permission_and_auto_merge(self):
        report = Fixture().collect()
        core = report["repositories"]["ForgingAlpha/container-foundation"]
        self.assertEqual(core["repository"]["value"]["default_branch"], "dev")
        self.assertTrue(report["repositories"]["ForgingAlpha/control-plane"]
                        ["repository"]["value"]["allow_auto_merge"])
        self.assertIn("unqualified", report["qualification"])
        self.assertNotIn("PRIVATE_ERROR", json.dumps(report))

    def test_ruleset_observations_keep_human_and_nonhuman_bypass_and_missing_distinction(self):
        fixture = Fixture()
        root = "repos/ForgingAlpha/.github"
        fixture.responses[f"{root}/rulesets?includes_parents=true&per_page=100"] = response([
            {"id": index, "source_type": "Repository", "source": "ForgingAlpha/.github"}
            for index in (1, 2, 3)])
        actors = [{"actor_type": "Integration", "actor_id": 4249954, "bypass_mode": "always"},
                  {"actor_type": "OrganizationAdmin", "actor_id": 1, "bypass_mode": "pull_request"}]
        fixture.responses[f"{root}/rulesets/1"] = response({
            "id": 1, "bypass_actors": actors, "current_user_can_bypass": "always"})
        fixture.responses[f"{root}/rulesets/2"] = response({"id": 2})
        fixture.responses[f"{root}/rulesets/3"] = response({"id": 3, "bypass_actors": []})
        details = fixture.collect()["repositories"]["ForgingAlpha/.github"]["ruleset_details"]
        self.assertEqual(details[0]["value"]["bypass_actors"], actors)
        self.assertEqual(details[0]["value"]["current_user_can_bypass"], "always")
        self.assertEqual(details[1]["bypass_actors_visibility"], "unknown")
        self.assertNotIn("bypass_actors", details[1]["value"])
        self.assertEqual(details[2]["value"]["bypass_actors"], [])
        self.assertEqual(details[2]["bypass_actors_visibility"], "observed")

    def test_inherited_rules_use_only_observed_fixed_owner_endpoints(self):
        fixture = Fixture()
        root = "repos/ForgingAlpha/.github"
        rows = [{"type": "update", "ruleset_id": 7, "ruleset_source_type": "Organization",
                 "ruleset_source": "ForgingAlpha"},
                {"type": "update", "ruleset_id": 8, "ruleset_source_type": "Enterprise",
                 "ruleset_source": "alphaapps"},
                {"type": "update", "ruleset_id": 9, "ruleset_source_type": "Organization",
                 "ruleset_source": "other"}]
        fixture.responses[f"{root}/rules/branches/main"] = response(rows)
        report = fixture.collect()
        endpoints = [call[-1] for call in fixture.calls]
        self.assertIn("orgs/ForgingAlpha/rulesets/7", endpoints)
        self.assertIn("enterprises/alphaapps/rulesets/8", endpoints)
        self.assertNotIn("orgs/other/rulesets/9", endpoints)
        details = report["repositories"]["ForgingAlpha/.github"]["ruleset_details"]
        self.assertTrue(all(detail["bypass_actors_visibility"] == "unknown" for detail in details))
        self.assertEqual(report["repositories"]["ForgingAlpha/.github"]
                         ["effective_rules"]["value"][0]["ruleset_id"], 7)

    def test_pagination_never_follows_server_supplied_links_or_claims_complete(self):
        for items, headers in (([], 'Link: <https://evil.example/next>; rel="next"\r\n'),
                               ([{"id": index, "source_type": "Repository",
                                  "source": "ForgingAlpha/.github"} for index in range(1, 101)], "")):
            with self.subTest(count=len(items)):
                fixture = Fixture()
                root = "repos/ForgingAlpha/.github"
                fixture.responses[f"{root}/rulesets?includes_parents=true&per_page=100"] = response(
                    items, extra_headers=headers)
                report = fixture.collect()
                self.assertFalse(report["repositories"]["ForgingAlpha/.github"]
                                 ["ruleset_inventory"]["inventory_complete"])
                self.assertFalse(any("evil.example" in call[-1] for call in fixture.calls))

    def test_no_graphql_arbitrary_repo_url_or_mutating_cli_argument(self):
        fixture = Fixture()
        fixture.collect()
        self.assertTrue(all(call[5] == "GET" for call in fixture.calls))
        for endpoint in ("graphql", "repos/other/private", "https://github.com/", "user?anything",
                         "orgs/ForgingAlpha/rulesets/0", "repos/ForgingAlpha/.github/rulesets/-1"):
            with self.subTest(endpoint=endpoint), patch.object(reader.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    reader.Reader("gh").get(endpoint)
                run.assert_not_called()

    def test_private_report_permissions_and_content(self):
        with tempfile.TemporaryDirectory() as root:
            original = reader.tempfile.mkdtemp
            with patch.object(reader.tempfile, "mkdtemp", side_effect=lambda **kwargs: original(dir=root, **kwargs)):
                path = reader.write_report({"qualification": "unqualified"})
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(json.loads(path.read_text())["qualification"], "unqualified")

    def test_timeout_preserves_unavailable_without_error_text(self):
        with patch.object(reader.subprocess, "run", side_effect=subprocess.TimeoutExpired("secret", 30)):
            observed, payload = reader.Reader("gh").get("user")
        self.assertEqual(observed, {"status": "unavailable"})
        self.assertIsNone(payload)

    def test_malformed_nested_main_metadata_does_not_crash_or_invent_sha(self):
        fixture = Fixture()
        fixture.responses["repos/ForgingAlpha/.github/branches/main"] = response({"commit": "invalid"})
        report = fixture.collect()
        self.assertIsNone(report["repositories"]["ForgingAlpha/.github"]["main"]["value"]["sha"])

    def test_repository_transfer_or_rename_is_not_silently_followed(self):
        fixture = Fixture()
        root = "repos/ForgingAlpha/.github"
        fixture.responses[root] = response({"id": reader.REPOSITORIES[".github"],
                                            "full_name": "another-owner/.github"})
        fixture.collect()
        self.assertFalse(any(call[-1].startswith(root + "/") for call in fixture.calls))

    def test_complete_cli_uses_only_fake_gh_and_returns_private_report(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            fixture = Fixture()
            responses = {key: {"stdout": value.stdout, "code": value.returncode}
                         for key, value in fixture.responses.items()}
            (root / "responses.json").write_text(json.dumps(responses))
            gh = root / "gh"
            gh.write_text('''#!/usr/bin/python3
import json, os, pathlib, sys
root = pathlib.Path(os.environ["TMPDIR"])
with (root / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\\n")
responses = json.loads((root / "responses.json").read_text())
response = responses.get(sys.argv[-1], {"stdout": "HTTP/2.0 403 Forbidden\\n\\n{}", "code": 1})
print(response["stdout"])
raise SystemExit(response["code"])
''')
            gh.chmod(0o700)
            completed = subprocess.run(
                [sys.executable, "-I", str(Path(reader.__file__))], capture_output=True,
                text=True, timeout=10, check=False,
                env={"PATH": str(root), "TMPDIR": str(root), "HOME": str(root)})
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Protection remains unqualified", completed.stdout)
            reports = list(root.glob("alphaapps-shared-main-read-*/REPORT.json"))
            self.assertEqual(len(reports), 1)
            self.assertEqual(stat.S_IMODE(reports[0].stat().st_mode), 0o600)
            calls = [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()]
            self.assertEqual(calls[0][-1], "user")
            self.assertTrue(all(call[4] == "GET" for call in calls))
            self.assertTrue(all(call[2] == "github.com" for call in calls))

    def test_real_quality_parameters_remain_distinguishable(self):
        # Parameter names come from retained GitHub effective-rule readback and REST docs.
        def observed(required):
            value = [{"type": "pull_request", "ruleset_id": 7,
                      "ruleset_source_type": "Repository", "ruleset_source": "ForgingAlpha/.github",
                      "parameters": {"dismiss_stale_reviews_on_push": required,
                                     "require_code_owner_review": required,
                                     "required_review_thread_resolution": required,
                                     "require_extra_approval_for_unattributed_changes": required,
                                     "required_reviewers": [],
                                     "dismissal_restriction": {"enabled": True, "allowed_actors": []}}},
                     {"type": "required_status_checks", "ruleset_id": 7,
                      "ruleset_source_type": "Repository", "ruleset_source": "ForgingAlpha/.github",
                      "parameters": {"strict_required_status_checks_policy": required,
                                     "required_status_checks": [{"context": "CI", "integration_id": 15368}]}}]
            with patch.object(reader.subprocess, "run", return_value=response(value)):
                return reader.Reader("gh").get("repos/ForgingAlpha/.github/rules/branches/main", list)[0]
        strong, weak = observed(True), observed(False)
        self.assertNotEqual(strong["value"], weak["value"])
        self.assertTrue(strong["value"][0]["parameters"]["require_code_owner_review"])
        self.assertTrue(strong["value"][1]["parameters"]["strict_required_status_checks_policy"])
        self.assertEqual(strong["value"][0]["parameters"]["required_reviewers"], [])
        self.assertTrue(strong["projection_complete"])

    def test_malformed_or_mismatched_rulesets_are_unknown_not_empty_safe(self):
        bad_details = [{"id": 999, "bypass_actors": []},
                       {"id": 7, "bypass_actors": [{}]}, {"id": 7, "bypass_actors": [123]},
                       {"id": 7, "bypass_actors": {"token": "PRIVATE_SENTINEL"}},
                       {"id": 7, "bypass_actors": [{"actor_type": "Integration", "actor_id": -4,
                                                     "bypass_mode": "anything"}]}]
        for value in bad_details:
            with self.subTest(value=value), patch.object(reader.subprocess, "run", return_value=response(value)):
                observed, payload = reader.Reader("gh").get("repos/ForgingAlpha/.github/rulesets/7")
                self.assertEqual(observed["status"], "invalid_schema")
                self.assertIsNone(payload)
                self.assertNotIn("PRIVATE_SENTINEL", json.dumps(observed))
        for invalid_id in ("7", True, -1):
            with self.subTest(invalid_id=invalid_id), patch.object(reader.subprocess, "run", return_value=response([
                    {"id": invalid_id, "source_type": "Repository", "source": "ForgingAlpha/.github"}])):
                observed, payload = reader.Reader("gh").get(
                    "repos/ForgingAlpha/.github/rulesets?includes_parents=true&per_page=100", list, limit=100)
                self.assertEqual(observed["status"], "invalid_schema")
                self.assertFalse(observed["inventory_complete"])
                self.assertIsNone(payload)

    def test_malformed_selected_metadata_never_copies_raw_objects(self):
        fixture = Fixture()
        fixture.responses["repos/ForgingAlpha/.github"] = response({
            "id": reader.REPOSITORIES[".github"], "full_name": "ForgingAlpha/.github",
            "default_branch": {"token": "PRIVATE_SENTINEL"}})
        report = fixture.collect()
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(report))
        self.assertEqual(report["repositories"]["ForgingAlpha/.github"]
                         ["repository"]["status"], "invalid_schema")

    def test_unrecognized_settings_are_reported_as_unprojected_not_silently_discarded(self):
        value = [{"type": "future_rule", "ruleset_id": 7, "ruleset_source_type": "Repository",
                  "ruleset_source": "ForgingAlpha/.github", "parameters": {"new_quality_control": True}}]
        with patch.object(reader.subprocess, "run", return_value=response(value)):
            observed, _ = reader.Reader("gh").get("repos/ForgingAlpha/.github/rules/branches/main", list, limit=30)
        self.assertEqual(observed["unreported_fields"], ["new_quality_control"])
        self.assertFalse(observed["projection_complete"])
        self.assertFalse(observed["inventory_complete"])

    def test_unhashable_actor_enum_containers_are_invalid_schema_not_exceptions(self):
        for field in ("actor_type", "bypass_mode"):
            for invalid in ([], {}, ["Integration"]):
                actor = {"actor_type": "Integration", "actor_id": 4249954, "bypass_mode": "always"}
                actor[field] = invalid
                with self.subTest(field=field, invalid=invalid), patch.object(
                        reader.subprocess, "run", return_value=response({"id": 7, "bypass_actors": [actor]})):
                    observed, payload = reader.Reader("gh").get("repos/ForgingAlpha/.github/rulesets/7")
                    self.assertEqual(observed["status"], "invalid_schema")
                    self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()
