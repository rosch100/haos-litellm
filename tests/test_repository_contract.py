from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "litellm"


class RepositoryContractTests(unittest.TestCase):
    def test_app_is_limited_to_arm64(self):
        manifest = (APP / "config.yaml").read_text()
        self.assertRegex(manifest, r"(?m)^arch:\s*\n\s+- aarch64\s*$")
        self.assertNotRegex(manifest, r"(?m)^\s+- (amd64|armhf|armv7)\s*$")

    def test_proxy_has_no_host_port_mapping(self):
        manifest = (APP / "config.yaml").read_text()
        self.assertRegex(manifest, r"(?m)^ports:\s*\n\s+4000/tcp:\s+null\s*$")

    def test_database_and_master_key_are_required_secrets(self):
        manifest = (APP / "config.yaml").read_text()
        schema = manifest.split("schema:", 1)[1]
        self.assertRegex(schema, r"(?m)^\s+database_url:\s+password$")
        self.assertRegex(schema, r"(?m)^\s+master_key:\s+password$")

    def test_startup_verifies_production_version_and_schema_before_db_access(self):
        entrypoint = (APP / "run.py").read_text()
        self.assertIn('EXPECTED_LITELLM_VERSION = "1.105.0"', entrypoint)
        self.assertIn("EXPECTED_SCHEMA_SHA256", entrypoint)
        self.assertIn("disable_prisma_schema_update", entrypoint)
        self.assertIn('os.environ["DISABLE_SCHEMA_UPDATE"] = "true"', entrypoint)
        self.assertIn("should_update_prisma_schema(False)", entrypoint)
        self.assertLess(entrypoint.index("verify_runtime_schema()"), entrypoint.index("wait_for_database("))
        self.assertIn("EXPECTED_PROVIDER_ENVIRONMENT", entrypoint)
        self.assertIn("[proxy,extra_proxy]", (APP / "Dockerfile").read_text())
        launcher = (APP / "Dockerfile").read_text()
        self.assertIn('CMD ["/run.sh"]', launcher)
        self.assertIn("DISABLE_SCHEMA_UPDATE=true", (APP / "run.sh").read_text())
        self.assertIn("export \"${environment_name}=${secret_value}\"", (APP / "run.sh").read_text())

    def test_app_does_not_install_or_configure_wireguard(self):
        manifest = (APP / "config.yaml").read_text().lower()
        dockerfile = (APP / "Dockerfile").read_text().lower()
        entrypoint = (APP / "run.py").read_text().lower()
        self.assertNotRegex(manifest + dockerfile, r"(wireguard|wireguard-tools|wg-quick)")
        self.assertNotIn("wireguard", entrypoint)

    def test_all_production_provider_secrets_are_required(self):
        import ast

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

    def test_docs_explain_multi_domain_certificate_and_shared_db_guard(self):
        readme = (ROOT / "README.md").read_text()
        docs = (APP / "DOCS.md").read_text()
        self.assertIn("llm-mc.altanis.de", readme)
        self.assertRegex(readme, r"(?i)(Let's Encrypt|Let’s Encrypt).{0,250}(domains|SAN|certificate)")
        self.assertIn("existing production database", readme)
        self.assertIn("version/schema mismatch", readme)
        self.assertIn("DISABLE_SCHEMA_UPDATE=true", docs)
        self.assertIn("No WireGuard software", docs)


if __name__ == "__main__":
    unittest.main()
