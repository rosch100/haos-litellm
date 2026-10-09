from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "litellm"
sys.path.insert(0, str(APP))

litellm_module = types.ModuleType("litellm")
litellm_module.__file__ = str(APP / "__init__.py")
proxy_module = types.ModuleType("litellm.proxy")
proxy_module.__path__ = []
db_module = types.ModuleType("litellm.proxy.db")
db_module.__path__ = []
prisma_module = types.ModuleType("litellm.proxy.db.prisma_client")
prisma_module.should_update_prisma_schema = lambda value=None: value is True
sys.modules.update(
    {
        "litellm": litellm_module,
        "litellm.proxy": proxy_module,
        "litellm.proxy.db": db_module,
        "litellm.proxy.db.prisma_client": prisma_module,
    }
)

import run


class RepositoryContractTests(unittest.TestCase):
    def test_app_is_limited_to_arm64(self):
        manifest = yaml.safe_load((APP / "config.yaml").read_text())
        self.assertEqual(manifest["arch"], ["aarch64"])

    def test_app_image_is_built_for_required_architecture(self):
        manifest = yaml.safe_load((APP / "config.yaml").read_text())
        dockerfile = (APP / "Dockerfile").read_text()
        workflow = (ROOT / ".github/workflows/build.yaml").read_text()
        self.assertEqual(manifest["image"], "ghcr.io/rosch100/haos-litellm-litellm")
        self.assertIn("FROM ghcr.io/home-assistant/base-python:3.13-alpine3.24", dockerfile)
        self.assertIn("ln -s /opt/litellm-venv/bin/maturin /usr/local/bin/maturin", dockerfile)
        self.assertIn("cmake ninja", dockerfile)
        self.assertIn("scikit-build-core", dockerfile)
        self.assertIn('pip install --no-build-isolation "/tmp/litellm-source[proxy,extra_proxy]"', dockerfile)
        self.assertIn('sed -i "/pyroscope-io>=0.8.16,<1.0/d" /tmp/litellm-source/pyproject.toml', dockerfile)
        self.assertIn('ENV IMAGE="ghcr.io/rosch100/haos-litellm-litellm:${BUILD_VERSION}"', dockerfile)
        self.assertIn("platforms: linux/arm64", workflow)
        self.assertIn('      - "repository.yaml"', workflow)
        self.assertFalse((APP / "build.yaml").exists())

    def test_proxy_has_no_host_port_mapping_and_read_only_config_mount(self):
        manifest = yaml.safe_load((APP / "config.yaml").read_text())
        self.assertIsNone(manifest["ports"]["4000/tcp"])
        self.assertEqual(manifest["map"], ["app_config:ro"])

    def test_database_and_master_key_are_required_secrets(self):
        manifest = yaml.safe_load((APP / "config.yaml").read_text())
        self.assertIsNone(manifest["options"]["database_url"])
        self.assertIsNone(manifest["options"]["master_key"])
        self.assertEqual(manifest["schema"]["database_url"], "password")
        self.assertEqual(manifest["schema"]["master_key"], "password")
        self.assertEqual(manifest["schema"]["salt_key"], "password?")
        self.assertNotIn("salt_key", manifest["options"])
        self.assertEqual(
            manifest["schema"]["environment_variables"],
            [{"name": "str", "value": "password"}],
        )

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

    def test_database_url_accepts_configured_host_port_database_and_user(self):
        self.assertEqual(
            run.validate_database_url("postgresql://gateway:secret@db.example:5433/models"),
            ("db.example", 5433),
        )

    def test_database_url_rejects_non_postgres_and_incomplete_urls(self):
        for database_url in ("https://db.example:5432/models", "postgresql://db.example"):
            with self.subTest(database_url=database_url), patch.object(run, "fail", side_effect=ValueError):
                with self.assertRaises(ValueError):
                    run.validate_database_url(database_url)

    def test_optional_salt_key_is_passed_when_configured(self):
        self.assertIn('salt_key = options.get("salt_key")', (APP / "run.py").read_text())
        self.assertIn('environment["LITELLM_SALT_KEY"] = salt_key', (APP / "run.py").read_text())

    def test_custom_environment_variables_are_applied_and_reserved_names_rejected(self):
        environment = {}
        run.configure_provider_environment(
            {"environment_variables": [{"name": "OPENAI_API_KEY", "value": "secret"}]},
            environment,
        )
        self.assertEqual(environment, {"OPENAI_API_KEY": "secret"})
        for reserved_name in (
            "DATABASE_URL",
            "LITELLM_MASTER_KEY",
            "DISABLE_SCHEMA_UPDATE",
            "DISABLE_ADMIN_UI",
            "STORE_MODEL_IN_DB",
        ):
            with self.subTest(name=reserved_name), patch.object(run, "fail", side_effect=ValueError):
                with self.assertRaises(ValueError):
                    run.configure_provider_environment(
                        {"environment_variables": [{"name": reserved_name, "value": "secret"}]},
                        {},
                    )

    def test_invalid_custom_environment_variable_name_is_rejected(self):
        with patch.object(run, "fail", side_effect=ValueError):
            with self.assertRaises(ValueError):
                run.configure_provider_environment(
                    {"environment_variables": [{"name": "BAD-NAME", "value": "secret"}]},
                    {},
                )

    def test_app_config_accepts_database_backed_litellm_routing(self):
        entrypoint = (APP / "run.py").read_text()
        self.assertIn('general["store_model_in_db"] = True', entrypoint)

    def test_app_has_official_litellm_icon_and_logo(self):
        for asset in ("icon.png", "logo.png"):
            with self.subTest(asset=asset):
                self.assertTrue((APP / asset).is_file())
                self.assertEqual((APP / asset).read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_app_has_no_internal_network_or_company_references(self):
        files = [APP / "config.yaml", APP / "run.py", APP / "DOCS.md", ROOT / "README.md"]
        for path in files:
            contents = path.read_text().lower()
            with self.subTest(path=path.name):
                self.assertNotRegex(contents, r"192\.168\.")
                self.assertNotIn("altanis", contents)
                self.assertNotIn("llm-mc", contents)
                self.assertNotIn("wireguard", contents)


if __name__ == "__main__":
    unittest.main()
