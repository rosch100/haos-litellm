from pathlib import Path
import ast
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "litellm"


class RepositoryContractTests(unittest.TestCase):
    def test_app_is_limited_to_arm64(self):
        manifest = (APP / "config.yaml").read_text()
        self.assertRegex(manifest, r"(?m)^arch:\s*\n\s+- aarch64\s*$")
        self.assertNotRegex(manifest, r"(?m)^\s+- (amd64|armhf|armv7)\s*$")

    def test_app_image_is_built_for_required_architecture(self):
        manifest = (APP / "config.yaml").read_text()
        dockerfile = (APP / "Dockerfile").read_text()
        workflow = (ROOT / ".github/workflows/build.yaml").read_text()
        self.assertIn("image: ghcr.io/rosch100/haos-litellm-litellm", manifest)
        self.assertIn("FROM ghcr.io/home-assistant/base:latest", dockerfile)
        self.assertIn("ln -s /opt/litellm-venv/bin/maturin /usr/local/bin/maturin", dockerfile)
        self.assertIn('sed -i "/pyroscope-io>=0.8.16,<1.0/d" /tmp/litellm-source/pyproject.toml', dockerfile)
        self.assertIn('ENV IMAGE="ghcr.io/rosch100/haos-litellm-litellm:${BUILD_VERSION}"', dockerfile)
        self.assertIn("platforms: linux/arm64", workflow)
        self.assertFalse((APP / "build.yaml").exists())

    def test_proxy_has_no_host_port_mapping_and_read_only_config_mount(self):
        manifest = (APP / "config.yaml").read_text()
        self.assertRegex(manifest, r"(?m)^ports:\s*\n\s+4000/tcp:\s+null\s*$")
        self.assertRegex(manifest, r"(?m)^map:\s*\n\s+- type: addon_config\s*\n\s+read_only: true\s*$")

    def test_repository_manifest_exists(self):
        manifest = (ROOT / "repository.yaml").read_text()
        self.assertRegex(manifest, r"(?m)^name:\s+.+$")

    def test_database_and_master_key_are_required_secrets(self):
        manifest = (APP / "config.yaml").read_text()
        schema = manifest.split("schema:", 1)[1]
        self.assertRegex(schema, r"(?m)^\s+database_url:\s+password$")
        self.assertRegex(schema, r"(?m)^\s+master_key:\s+password$")

    def test_startup_entrypoint_checks_version_schema_and_disable_flag(self):
        dockerfile = (APP / "Dockerfile").read_text()
        entrypoint = (APP / "run.py").read_text()
        launcher = (APP / "run.sh").read_text()
        self.assertIn('EXPECTED_LITELLM_VERSION = "1.105.0"', entrypoint)
        self.assertIn("EXPECTED_SCHEMA_SHA256", entrypoint)
        self.assertIn('should_update_prisma_schema("false")', entrypoint)
        self.assertIn("should_update_prisma_schema()", entrypoint)
        self.assertIn('os.environ["DISABLE_SCHEMA_UPDATE"] = "true"', entrypoint)
        self.assertIn('environment["STORE_MODEL_IN_DB"] = "true"', entrypoint)
        self.assertIn("run.py", dockerfile)
        self.assertIn("exec /opt/litellm-venv/bin/python /run.py", launcher)
        self.assertLess(entrypoint.index("verify_runtime_schema()"), entrypoint.index("wait_for_database("))

    def test_all_production_provider_secrets_are_required(self):
        entrypoint = ast.parse((APP / "run.py").read_text())
        constants = next(
            node
            for node in entrypoint.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "EXPECTED_PROVIDER_ENVIRONMENT"
                for target in node.targets
            )
        )
        providers = ast.literal_eval(constants.value)
        schema = (APP / "config.yaml").read_text().split("schema:", 1)[1]
        for option_name in providers:
            self.assertRegex(schema, rf"(?m)^\s+{re.escape(option_name)}:\s+password$")

    def test_app_config_accepts_database_backed_production_routing(self):
        entrypoint = (APP / "run.py").read_text()
        self.assertIn('router.get("model_group_alias")', entrypoint)
        self.assertIn('general["store_model_in_db"] = True', entrypoint)
        self.assertNotIn('config.get("model_list")', entrypoint)

    def test_app_does_not_install_or_configure_wireguard(self):
        manifest = (APP / "config.yaml").read_text().lower()
        dockerfile = (APP / "Dockerfile").read_text().lower()
        entrypoint = (APP / "run.py").read_text().lower()
        self.assertNotRegex(manifest + dockerfile, r"(wireguard|wireguard-tools|wg-quick)")
        self.assertNotIn("wireguard", entrypoint)

    def test_docs_explain_certificate_and_shared_database_guard(self):
        readme = (ROOT / "README.md").read_text()
        docs = (APP / "DOCS.md").read_text()
        self.assertIn("llm-mc.altanis.de", readme)
        self.assertIn("SAN", readme)
        self.assertIn("existing production database", readme)
        self.assertIn("version/schema mismatch", readme)
        self.assertIn("DISABLE_SCHEMA_UPDATE=true", docs)
        self.assertIn("No WireGuard software", docs)


if __name__ == "__main__":
    unittest.main()
