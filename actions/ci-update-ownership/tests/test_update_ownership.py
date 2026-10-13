from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "actions" / "ci-update-ownership" / "scripts" / "validate_update_ownership.py"
PRESET = ROOT / "renovate-config.json"
ACTION = ROOT / "actions" / "ci-update-ownership" / "action.yml"

spec = importlib.util.spec_from_file_location("update_ownership", SCRIPT)
assert spec and spec.loader
update_ownership = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_ownership)


class UpdateOwnershipTest(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "schema_version": 1,
            "normal_update_owner": "renovate",
            "base_branch": "dev",
            "runtime_profile": "node-24-site",
        }
        self.renovate = {
            "$schema": "https://docs.renovatebot.com/renovate-schema.json",
            "extends": [update_ownership.CENTRAL_PRESET],
            "baseBranchPatterns": ["dev"],
        }
        self.dependabot = {
            "version": 2,
            "updates": [
                {
                    "package-ecosystem": "npm",
                    "directory": "/",
                    "open-pull-requests-limit": 0,
                }
            ],
        }

    def test_central_preset_contract(self):
        update_ownership.validate_central_preset(update_ownership.load_json(PRESET))
        action = ACTION.read_text(encoding="utf-8")
        self.assertIn(".github/update-policy.json", action)
        self.assertIn("--repository-root .", action)
        self.assertIn("UPDATE_POLICY_DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}", action)
        self.assertIn("renovate.json", action)
        self.assertIn(".github/dependabot.yml", action)
        self.assertNotIn("github.token", action)
        self.assertNotIn("secrets.", action)

    def run_owned_action(self, root, default_branch="main"):
        step = yaml.safe_load(ACTION.read_text())["runs"]["steps"][0]
        env = dict(
            os.environ,
            GITHUB_ACTION_PATH=str(ACTION.parent),
            UPDATE_POLICY_DEFAULT_BRANCH=default_branch,
            PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
        )
        return subprocess.run(
            ["bash", "-c", step["run"]], cwd=root, env=env,
            capture_output=True, text=True, timeout=15,
        )

    def test_repository_config_assigns_normal_and_security_owners(self):
        # Exercise REQ-018 through the same policy-selection path as required CI.
        workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
        job = workflow["jobs"]["CI"]
        selected = [step for step in job["steps"] if step.get("uses") == "./actions/ci-update-ownership"]
        self.assertEqual(len(selected), 1, "Required CI must consume the ownership declaration")
        for boundary in (job, selected[0]):
            self.assertNotIn("if", boundary)
            self.assertNotIn("continue-on-error", boundary)
        result = self.run_owned_action(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_owned_action_rejects_absent_or_conflicting_consumer_policy(self):
        policy = {"schema_version": 1, "normal_update_owner": "renovate", "base_branch": "main"}
        cases = [
            ("missing-file", None),
            ("missing-owner", {key: value for key, value in policy.items() if key != "normal_update_owner"}),
            ("other-owner", dict(policy, normal_update_owner="dependabot")),
            ("wrong-base", dict(policy, base_branch="dev")),
            ("unknown-field", dict(policy, skip_validation=True)),
            ("invalid-profile", dict(policy, runtime_profile=None)),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github").mkdir()
            (root / "renovate.json").write_text(json.dumps(dict(self.renovate, baseBranchPatterns=["main"])))
            (root / ".github" / "dependabot.yml").write_text(yaml.safe_dump(self.dependabot))
            declaration = root / ".github" / "update-policy.json"
            declaration.write_text(json.dumps(policy))
            result = self.run_owned_action(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name, invalid in cases:
                with self.subTest(case=name):
                    if invalid is None:
                        declaration.unlink()
                    else:
                        declaration.write_text(json.dumps(invalid))
                    result = self.run_owned_action(root)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("Update ownership validation failed", result.stderr)

    def test_runtime_profile_is_optional_only_for_the_update_gate(self):
        policy = {key: value for key, value in self.policy.items() if key != "runtime_profile"}
        self.assertEqual(update_ownership.validate_policy(policy), ("renovate", "dev", None))
        for invalid in (None, "", [], 7):
            with self.subTest(profile=invalid), self.assertRaises(update_ownership.OwnershipError):
                update_ownership.validate_policy(dict(policy, runtime_profile=invalid))

    def test_copyable_templates_preserve_security_only_dependabot(self):
        templates = sorted((ROOT / "templates" / "dependabot").glob("*.yml"))
        self.assertTrue(templates, "No dependency templates found")
        for template in templates:
            with self.subTest(template=template.name):
                update_ownership.validate_security_only_dependabot(
                    update_ownership.load_yaml(template)
                )

    def test_renovate_ownership_contract_passes(self):
        owner, base, profile = update_ownership.validate_policy(self.policy)
        self.assertEqual((owner, base, profile), ("renovate", "dev", "node-24-site"))
        update_ownership.validate_renovate(self.renovate, base)
        update_ownership.validate_security_only_dependabot(self.dependabot)

    def test_policy_rejects_another_normal_update_owner(self):
        with self.assertRaisesRegex(update_ownership.OwnershipError, "normal_update_owner must be renovate"):
            update_ownership.validate_policy(dict(self.policy, normal_update_owner="dependabot"))

    def test_local_renovate_policy_override_fails(self):
        # Even a local disable is an override of centrally owned policy.
        for key, value in (
            ("automerge", False),
            ("automerge", True),
            ("platformAutomerge", False),
            ("packageRules", [{"automerge": True}]),
        ):
            with self.subTest(key=key, value=value):
                config = copy.deepcopy(self.renovate)
                config[key] = value
                with self.assertRaisesRegex(update_ownership.OwnershipError, "forbidden policy overrides"):
                    update_ownership.validate_renovate(config, "dev")

    def test_wrong_preset_or_base_fails(self):
        config = copy.deepcopy(self.renovate)
        config["extends"] = ["config:recommended"]
        with self.assertRaisesRegex(update_ownership.OwnershipError, "must extend only"):
            update_ownership.validate_renovate(config, "dev")
        config = copy.deepcopy(self.renovate)
        config["baseBranchPatterns"] = ["main"]
        with self.assertRaisesRegex(update_ownership.OwnershipError, "baseBranchPatterns"):
            update_ownership.validate_renovate(config, "dev")
        update_ownership.validate_default_branch("dev", "dev")
        with self.assertRaisesRegex(update_ownership.OwnershipError, "must equal repository default branch"):
            update_ownership.validate_default_branch("dev", "main")

    def test_dependabot_normal_update_capacity_or_explicit_target_fails(self):
        config = copy.deepcopy(self.dependabot)
        config["updates"][0]["open-pull-requests-limit"] = 1
        with self.assertRaisesRegex(update_ownership.OwnershipError, "must have open-pull-requests-limit: 0"):
            update_ownership.validate_security_only_dependabot(config)
        config = copy.deepcopy(self.dependabot)
        config["updates"][0]["target-branch"] = "dev"
        with self.assertRaisesRegex(update_ownership.OwnershipError, "must omit target-branch"):
            update_ownership.validate_security_only_dependabot(config)

    def test_duplicate_dependabot_block_fails(self):
        config = copy.deepcopy(self.dependabot)
        config["updates"].append(copy.deepcopy(config["updates"][0]))
        with self.assertRaisesRegex(update_ownership.OwnershipError, "repeats update block"):
            update_ownership.validate_security_only_dependabot(config)

    def test_central_preset_keeps_mise_projection_read_only(self):
        config = update_ownership.load_json(PRESET)
        mise_rule = next(rule for rule in config["packageRules"] if rule.get("matchManagers") == ["mise"])
        self.assertIs(mise_rule["enabled"], False)
        self.assertEqual(config["lockFileMaintenance"], {"enabled": False})

        for key, value in (("enabled", True), ("matchManagers", ["mise", "npm"]), ("enabled", 0)):
            with self.subTest(key=key, value=value):
                changed = copy.deepcopy(config)
                changed["packageRules"][0][key] = value
                with self.assertRaises(update_ownership.OwnershipError):
                    update_ownership.validate_central_preset(changed)

    def test_central_preset_permits_proposals_with_merging_disabled(self):
        config = update_ownership.load_json(PRESET)
        self.assertIs(config["automerge"], False)
        self.assertIs(config["platformAutomerge"], False)
        self.assertEqual(
            {rule["matchUpdateTypes"][0]: rule["minimumReleaseAge"]
             for rule in config["packageRules"] if "matchUpdateTypes" in rule},
            {"patch": "3 days", "minor": "7 days", "major": "30 days"},
        )
        update_ownership.validate_central_preset(config)

        # Descriptive prose and the order of non-overlapping cooldowns do not
        # change policy. Keep the two final ownership exclusions in place.
        config.pop("$schema")
        config["description"] = "Normal update proposals for human review and merge"
        for rule in config["packageRules"]:
            rule.pop("description", None)
        config["packageRules"][:4] = reversed(config["packageRules"][:4])
        update_ownership.validate_central_preset(config)

    def test_central_preset_requires_explicit_boolean_merge_disables(self):
        valid = update_ownership.load_json(PRESET)
        for key in ("automerge", "platformAutomerge"):
            config = copy.deepcopy(valid)
            config.pop(key)
            with self.subTest(key=key, missing=True), self.assertRaises(update_ownership.OwnershipError):
                update_ownership.validate_central_preset(config)
            for value in (True, 0, 1, None, "false", [], {}):
                with self.subTest(key=key, value=value):
                    config = copy.deepcopy(valid)
                    config[key] = value
                    with self.assertRaises(update_ownership.OwnershipError):
                        update_ownership.validate_central_preset(config)

    def test_central_preset_rejects_merge_overrides_in_every_rule_scope(self):
        valid = update_ownership.load_json(PRESET)
        controls = {
            "automerge": True,
            "platformAutomerge": True,
            "automergeType": "branch",
            "automergeSchedule": ["at any time"],
            "automergeStrategy": "merge-commit",
            "autoApprove": True,
        }
        for key, value in controls.items():
            for scope in ("cooldown", "exclusion", "catch-all", "manager", "multiple-update-types"):
                with self.subTest(key=key, scope=scope):
                    config = copy.deepcopy(valid)
                    if scope == "cooldown":
                        config["packageRules"][1][key] = value
                    elif scope == "exclusion":
                        config["packageRules"][0][key] = value
                    else:
                        rule = {key: value}
                        if scope == "manager":
                            rule["matchManagers"] = ["npm"]
                        elif scope == "multiple-update-types":
                            rule["matchUpdateTypes"] = ["patch", "minor"]
                        # Insert before the final exclusions so their ordering
                        # cannot be the reason an unsafe rule fails.
                        config["packageRules"].insert(-2, rule)
                    with self.assertRaises(update_ownership.OwnershipError):
                        update_ownership.validate_central_preset(config)
            if key not in {"automerge", "platformAutomerge"}:
                config = copy.deepcopy(valid)
                config[key] = value
                with self.subTest(key=key, scope="root"), self.assertRaises(update_ownership.OwnershipError):
                    update_ownership.validate_central_preset(config)

        for key in ("automerge", "platformAutomerge"):
            config = copy.deepcopy(valid)
            config["packageRules"][1][key] = False
            with self.subTest(key=key, local_disable=True), self.assertRaises(update_ownership.OwnershipError):
                update_ownership.validate_central_preset(config)

    def test_central_preset_rejects_nested_and_inherited_overrides(self):
        valid = update_ownership.load_json(PRESET)
        mutations = [
            ("extends", ["config:recommended", ":automergeAll"]),
            ("npm", {"automerge": True}),
            ("patch", {"platformAutomerge": True}),
            ("vulnerabilityAlerts", {"enabled": False, "automerge": True}),
            ("lockFileMaintenance", {"enabled": False, "extends": [":automergeAll"]}),
        ]
        for key, value in mutations:
            with self.subTest(key=key):
                config = copy.deepcopy(valid)
                config[key] = value
                with self.assertRaises(update_ownership.OwnershipError):
                    update_ownership.validate_central_preset(config)
        for key, value in (
            ("extends", [":automergeAll"]),
            ("packageRules", [{"automerge": True}]),
            ("patch", {"automerge": True}),
        ):
            with self.subTest(rule_key=key):
                config = copy.deepcopy(valid)
                config["packageRules"][1][key] = value
                with self.assertRaises(update_ownership.OwnershipError):
                    update_ownership.validate_central_preset(config)

    def test_central_preset_rejects_missing_duplicate_and_weakened_cooldowns(self):
        valid = update_ownership.load_json(PRESET)
        for index in (1, 2, 3):
            for mutation in ("missing", "duplicate", "age", "restricted-matcher", "multiple-types"):
                with self.subTest(index=index, mutation=mutation):
                    config = copy.deepcopy(valid)
                    if mutation == "missing":
                        config["packageRules"].pop(index)
                    elif mutation == "duplicate":
                        config["packageRules"].insert(-2, copy.deepcopy(config["packageRules"][index]))
                    elif mutation == "age":
                        config["packageRules"][index]["minimumReleaseAge"] = "0 days"
                    elif mutation == "restricted-matcher":
                        config["packageRules"][index]["matchManagers"] = ["npm"]
                    else:
                        config["packageRules"][index]["matchUpdateTypes"] = ["patch", "minor", "major"]
                    with self.assertRaises(update_ownership.OwnershipError):
                        update_ownership.validate_central_preset(config)

    def test_central_preset_rejects_unadmitted_and_trailing_rules(self):
        valid = update_ownership.load_json(PRESET)
        for rule in (None, [], {}, {"enabled": True}, {"matchUpdateTypes": ["digest"], "automerge": True}):
            for insertion in (-2, len(valid["packageRules"])):
                with self.subTest(rule=rule, insertion=insertion):
                    config = copy.deepcopy(valid)
                    config["packageRules"].insert(insertion, rule)
                    with self.assertRaises(update_ownership.OwnershipError):
                        update_ownership.validate_central_preset(config)

    def test_central_preset_keeps_node_engine_on_runtime_profile_authority(self):
        valid = update_ownership.load_json(PRESET)
        matching = [
            rule
            for rule in valid["packageRules"]
            if rule.get("matchManagers") == ["npm"]
            and rule.get("matchDepTypes") == ["engines"]
            and rule.get("matchPackageNames") == ["node"]
        ]
        self.assertEqual(len(matching), 1)
        self.assertIs(matching[0]["enabled"], False)
        self.assertEqual(valid["packageRules"].index(matching[0]), len(valid["packageRules"]) - 2)

        mutations = []
        enabled = copy.deepcopy(valid)
        enabled["packageRules"][-2]["enabled"] = True
        mutations.append(enabled)
        missing = copy.deepcopy(valid)
        missing["packageRules"].pop(-2)
        mutations.append(missing)
        duplicate = copy.deepcopy(valid)
        duplicate["packageRules"].insert(-1, copy.deepcopy(duplicate["packageRules"][-2]))
        mutations.append(duplicate)
        early = copy.deepcopy(valid)
        early["packageRules"].insert(0, early["packageRules"].pop(-2))
        mutations.append(early)
        later_override = copy.deepcopy(valid)
        later_override["packageRules"].insert(
            -1,
            {
                "matchManagers": ["npm"],
                "matchDepTypes": ["engines"],
                "enabled": True,
            },
        )
        mutations.append(later_override)

        for config in mutations:
            with self.subTest(config=config), self.assertRaises(update_ownership.OwnershipError):
                update_ownership.validate_central_preset(config)

    def test_central_preset_keeps_first_party_actions_on_v1_rollout(self):
        valid = update_ownership.load_json(PRESET)
        matching = [
            rule
            for rule in valid["packageRules"]
            if rule.get("matchManagers") == ["github-actions"]
            and rule.get("matchPackageNames") == ["ForgingAlpha/.github"]
        ]
        self.assertEqual(len(matching), 1)
        self.assertIs(matching[0]["enabled"], False)

        mutations = []
        enabled = copy.deepcopy(valid)
        enabled["packageRules"][-1]["enabled"] = True
        mutations.append(enabled)
        missing = copy.deepcopy(valid)
        missing["packageRules"].pop()
        mutations.append(missing)
        duplicate = copy.deepcopy(valid)
        duplicate["packageRules"].append(copy.deepcopy(duplicate["packageRules"][-1]))
        mutations.append(duplicate)
        early = copy.deepcopy(valid)
        early["packageRules"].insert(0, early["packageRules"].pop())
        mutations.append(early)
        later_override = copy.deepcopy(valid)
        later_override["packageRules"].append(
            {
                "matchManagers": ["github-actions"],
                "enabled": True,
            }
        )
        mutations.append(later_override)

        for config in mutations:
            with self.subTest(config=config), self.assertRaises(update_ownership.OwnershipError):
                update_ownership.validate_central_preset(config)

    def test_central_preset_rejects_weakened_pinning_cadence_and_bounds(self):
        valid = update_ownership.load_json(PRESET)
        mutations = {
            "extends": [],
            "dependencyDashboard": False,
            "timezone": "UTC",
            "schedule": ["before 4am on monday"],
            "prConcurrentLimit": 50,
            "prHourlyLimit": 20,
            "rebaseWhen": "never",
            "rangeStrategy": "auto",
            "pinDigests": False,
            "semanticCommits": "disabled",
            "internalChecksFilter": "flexible",
        }
        for key, value in mutations.items():
            with self.subTest(key=key):
                config = copy.deepcopy(valid)
                config[key] = value
                with self.assertRaises(update_ownership.OwnershipError):
                    update_ownership.validate_central_preset(config)

    def test_exactly_one_canonical_repository_config_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "renovate.json"
            canonical.write_text(json.dumps(self.renovate), encoding="utf-8")
            update_ownership.validate_config_files(root, canonical)

            alternate = root / ".github" / "renovate.json5"
            alternate.parent.mkdir()
            alternate.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(update_ownership.OwnershipError, "alternate Renovate config files"):
                update_ownership.validate_config_files(root, canonical)

    def test_every_official_alternate_config_name_is_rejected(self):
        for relative in update_ownership.ALTERNATE_RENOVATE_CONFIGS:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                canonical = root / "renovate.json"
                canonical.write_text(json.dumps(self.renovate), encoding="utf-8")
                alternate = root / relative
                alternate.parent.mkdir(parents=True, exist_ok=True)
                alternate.write_text("{}", encoding="utf-8")
                with self.assertRaisesRegex(update_ownership.OwnershipError, relative.replace(".", r"\.")):
                    update_ownership.validate_config_files(root, canonical)

    def test_package_json_renovate_key_and_symlinked_canonical_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "renovate.json"
            canonical.write_text(json.dumps(self.renovate), encoding="utf-8")
            (root / "package.json").write_text('{"renovate": {}}', encoding="utf-8")
            with self.assertRaisesRegex(update_ownership.OwnershipError, "package.json renovate"):
                update_ownership.validate_config_files(root, canonical)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "config-target.json"
            target.write_text(json.dumps(self.renovate), encoding="utf-8")
            canonical = root / "renovate.json"
            canonical.symlink_to(target)
            with self.assertRaisesRegex(update_ownership.OwnershipError, "one regular file"):
                update_ownership.validate_config_files(root, canonical)


if __name__ == "__main__":
    unittest.main()
