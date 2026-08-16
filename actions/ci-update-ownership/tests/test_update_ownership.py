from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

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
                    "target-branch": "dev",
                    "open-pull-requests-limit": 0,
                }
            ],
        }

    def test_central_preset_contract(self):
        update_ownership.validate_central_preset(update_ownership.load_json(PRESET))
        action = ACTION.read_text(encoding="utf-8")
        self.assertIn(".github/update-policy.json", action)
        self.assertIn("--repository-root .", action)
        self.assertIn("renovate.json", action)
        self.assertIn(".github/dependabot.yml", action)
        self.assertNotIn("github.token", action)
        self.assertNotIn("secrets.", action)

    def test_renovate_destination_contract_passes(self):
        owner, base, profile = update_ownership.validate_policy(self.policy)
        self.assertEqual((owner, base, profile), ("renovate", "dev", "node-24-site"))
        update_ownership.validate_renovate(self.renovate, base)
        update_ownership.validate_security_only_dependabot(self.dependabot, base)

    def test_local_renovate_policy_override_fails(self):
        config = copy.deepcopy(self.renovate)
        config["automerge"] = False
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

    def test_dependabot_normal_update_capacity_or_wrong_base_fails(self):
        config = copy.deepcopy(self.dependabot)
        config["updates"][0]["open-pull-requests-limit"] = 1
        with self.assertRaisesRegex(update_ownership.OwnershipError, "must have open-pull-requests-limit: 0"):
            update_ownership.validate_security_only_dependabot(config, "dev")
        config = copy.deepcopy(self.dependabot)
        config["updates"][0]["target-branch"] = "main"
        with self.assertRaisesRegex(update_ownership.OwnershipError, "target branch"):
            update_ownership.validate_security_only_dependabot(config, "dev")

    def test_duplicate_dependabot_block_fails(self):
        config = copy.deepcopy(self.dependabot)
        config["updates"].append(copy.deepcopy(config["updates"][0]))
        with self.assertRaisesRegex(update_ownership.OwnershipError, "repeats update block"):
            update_ownership.validate_security_only_dependabot(config, "dev")

    def test_central_preset_keeps_mise_projection_read_only(self):
        config = update_ownership.load_json(PRESET)
        mise_rule = next(rule for rule in config["packageRules"] if rule.get("matchManagers") == ["mise"])
        self.assertIs(mise_rule["enabled"], False)
        self.assertEqual(config["lockFileMaintenance"], {"enabled": False})

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
