import sys
import tempfile
import types
import unittest
from pathlib import Path
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


def should_update_prisma_schema(disable_updates=None):
    if disable_updates is None:
        disable_updates = "false"
    if isinstance(disable_updates, str):
        disable_updates = disable_updates.lower() == "true"
    return not bool(disable_updates)


prisma_module.should_update_prisma_schema = should_update_prisma_schema
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
        self.assertIn(
            "FROM ghcr.io/home-assistant/base-python:3.13-alpine3.24", dockerfile
        )
        self.assertIn(
            "ln -s /opt/litellm-venv/bin/maturin /usr/local/bin/maturin", dockerfile
        )
        self.assertIn("cmake ninja", dockerfile)
        self.assertIn("libsndfile", dockerfile)
        self.assertIn("openssl", dockerfile)
        self.assertIn('source = "linux-musl-openssl-3.0.x"', dockerfile)
        self.assertIn('target = "linux-musl-arm64-openssl-3.0.x"', dockerfile)
        self.assertIn(
            'schema.replace(source, f"{source}, {target}")', dockerfile
        )
        self.assertIn("from prisma import client", dockerfile)
        self.assertIn("from prisma.engine.utils import ensure", dockerfile)
        self.assertIn("ensure(client.BINARY_PATHS.query_engine)", dockerfile)
        self.assertIn(
            "LITELLM_SOURCE_REPOSITORY=https://github.com/BerriAI/litellm.git",
            dockerfile,
        )
        self.assertIn(
            'git clone --filter=blob:none "${LITELLM_SOURCE_REPOSITORY}"', dockerfile
        )
        self.assertIn("scikit-build-core", dockerfile)
        self.assertIn("type: addon_config", (APP / "config.yaml").read_text())
        self.assertIn(
            "pip install maturin==1.15.0 numpy PyYAML scikit-build-core", dockerfile
        )
        self.assertIn(
            'pip install --no-build-isolation "/tmp/litellm-source[proxy,extra_proxy]"',
            dockerfile,
        )
        self.assertIn("PRISMA_BINARY_CACHE_DIR=/opt/litellm-prisma", dockerfile)
        self.assertIn(
            "prisma generate --schema=/tmp/litellm-source/litellm/proxy/schema.prisma", dockerfile
        )
        self.assertIn(
            'sed -i "/pyroscope-io>=0.8.16,<1.0/d" /tmp/litellm-source/pyproject.toml',
            dockerfile,
        )
        self.assertIn(
            'ENV IMAGE="ghcr.io/rosch100/haos-litellm-litellm:${BUILD_VERSION}"',
            dockerfile,
        )
        manifest_version = manifest["version"]
        dockerfile_version = dockerfile.split("LITELLM_VERSION=", 1)[1].split()[0]
        upstream_tag = dockerfile.split("LITELLM_SOURCE_TAG=", 1)[1].split()[0]
        upstream_version = upstream_tag[1:]
        self.assertRegex(manifest_version, rf"^{upstream_version}-ha\.[1-9][0-9]*$")
        self.assertEqual(run.EXPECTED_LITELLM_VERSION, upstream_version)
        self.assertEqual(run.EXPECTED_LITELLM_VERSION, dockerfile_version)
        self.assertIn("EXPECTED_SCHEMA_SHA256", (APP / "run.py").read_text())
        self.assertIn("platforms: linux/arm64", workflow)
        self.assertIn('      - "repository.yaml"', workflow)
        self.assertIn("push: true", workflow)
        self.assertIn("if: github.event_name == 'push'", workflow)
        self.assertIn("actions/runs?branch=$PR_BRANCH&event=push&per_page=100", workflow)
        self.assertIn("if length == 0 then empty else last", workflow)
        self.assertIn("timeout-minutes: 60", workflow)
        self.assertIn("for _ in {1..330}; do", workflow)
        self.assertIn('      - "**"', workflow)
        self.assertIn('      - "scripts/**"', workflow.split("  push:", 1)[1])
        push_paths = workflow.split("  push:", 1)[1].split("  pull_request:", 1)[0]
        pull_request_paths = workflow.split("  pull_request:", 1)[1].split(
            "    types:", 1
        )[0]
        for path in (
            '"tests/**"',
            '"scripts/**"',
            '".github/workflows/update-litellm.yaml"',
        ):
            with self.subTest(path=path):
                self.assertIn(f"      - {path}", push_paths)
                self.assertIn(f"      - {path}", pull_request_paths)
        self.assertIn("Build ARM64 image once on branch", workflow)
        self.assertIn(
            "if: github.event_name == 'push' && github.ref == 'refs/heads/main'",
            workflow,
        )
        self.assertIn(
            "if: github.event_name == 'push' && github.ref != 'refs/heads/main'",
            workflow,
        )
        self.assertIn("if: github.event_name == 'pull_request'", workflow)
        self.assertIn(
            'actions/runs?branch=$PR_BRANCH&event=push&per_page=100', workflow
        )
        self.assertIn(
            '.head_sha == $sha and .event == "push" and .path ==', workflow
        )
        self.assertNotIn("--jq --arg", workflow)
        self.assertIn(
            'gh run list --repo "$REPOSITORY" --workflow build.yaml --event push',
            workflow,
        )
        self.assertIn("docker buildx imagetools create", workflow)
        self.assertIn("sha-${{ github.sha }}", workflow)
        self.assertIn(
            'select(.name == "Build ARM64 image once on branch" and .conclusion == "success")',
            workflow,
        )
        self.assertIn("grep -Fqx 'Build ARM64 image once on branch'", workflow)
        self.assertNotIn("| rg -q", workflow)
        self.assertIn(
            "No successful branch image artifact is available", workflow
        )
        self.assertIn(
            "Build ARM64 image from merged main commit when branch artifact is unavailable",
            workflow,
        )
        self.assertIn("docker/setup-qemu-action@", workflow)
        self.assertIn(
            "SOURCE_DIGEST: ${{ steps.image.outputs.digest || steps.fallback_digest.outputs.digest }}",
            workflow,
        )
        self.assertIn("actions/upload-artifact@", workflow)
        self.assertIn("needs: promote", workflow)
        self.assertIn('releases_endpoint="repos/$REPOSITORY/releases?per_page=100"', workflow)
        self.assertIn('gh api --paginate --slurp "$releases_endpoint"', workflow)
        self.assertIn("select(.tag_name == $version)", workflow)
        self.assertIn('select(.tag_name == $version and .draft == false)', workflow)
        self.assertIn('--method PATCH', workflow)
        self.assertIn('test -n "$release"', workflow)
        self.assertIn('"tag_name=$VERSION"', workflow)
        self.assertIn('"name=LiteLLM $VERSION"', workflow)
        self.assertIn('test "${app_version%-ha.*}" = "$litellm_version"', workflow)
        update_workflow = (ROOT / ".github/workflows/update-litellm.yaml").read_text()
        update_script = (ROOT / "scripts/update_litellm.py").read_text()
        self.assertIn('cron: "23 6 * * *"', update_workflow)
        self.assertIn("python scripts/update_litellm.py", update_workflow)
        self.assertIn("peter-evans/create-pull-request@", update_workflow)
        self.assertIn('f"{UPSTREAM_API}/releases/latest"', update_script)
        self.assertIn("schema_sha256=hashlib.sha256(schema).hexdigest()", update_script)
        self.assertFalse((APP / "build.yaml").exists())

    def test_proxy_publishes_web_ui_on_host_port_and_keeps_config_read_only(self):
        manifest = yaml.safe_load((APP / "config.yaml").read_text())
        self.assertEqual(manifest["ports"]["4000/tcp"], 4000)
        self.assertFalse(manifest.get("ingress", False))
        self.assertEqual(
            manifest["map"],
            [
                {"type": "addon_config", "read_only": True},
                {"type": "ssl", "read_only": True},
            ],
        )
        self.assertIn("LAN", manifest["ports_description"]["4000/tcp"])

    def test_https_is_available_when_ssl_is_enabled(self):
        manifest = yaml.safe_load((APP / "config.yaml").read_text())
        self.assertFalse(manifest["options"]["ssl"])
        self.assertEqual(manifest["schema"]["ssl"], "bool")
        self.assertIn({"type": "ssl", "read_only": True}, manifest["map"])
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            certificate = root / "fullchain.pem"
            private_key = root / "privkey.pem"
            certificate.write_text("certificate")
            private_key.write_text("private key")
            with (
                patch.object(run, "SSL_CERTIFICATE", certificate),
                patch.object(run, "SSL_PRIVATE_KEY", private_key),
            ):
                command = run.build_litellm_command(root / "config.yaml", {"ssl": True})

        self.assertEqual(
            command[-4:],
            [
                "--ssl_certfile_path",
                str(certificate),
                "--ssl_keyfile_path",
                str(private_key),
            ],
        )
        http_command = run.build_litellm_command(
            root / "config.yaml", {"ssl": False}
        )
        self.assertEqual(http_command[-4:], ["--host", "0.0.0.0", "--port", "4000"])
        self.assertNotIn("--ssl_certfile_path", http_command)
        with (
            patch.object(run, "SSL_CERTIFICATE", root / "missing-cert.pem"),
            patch.object(run, "SSL_PRIVATE_KEY", root / "missing-key.pem"),
        ):
            with patch.object(run, "fail", side_effect=ValueError) as fail:
                with self.assertRaises(ValueError):
                    run.build_litellm_command(root / "config.yaml", {"ssl": True})
        fail.assert_called_once_with(
            "ssl=true requires /ssl/fullchain.pem and /ssl/privkey.pem"
        )

    def test_web_ui_is_enabled_for_direct_lan_access(self):
        entrypoint = (APP / "run.py").read_text()
        self.assertIn('environment["DISABLE_ADMIN_UI"] = "False"', entrypoint)

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

    def test_schema_update_guard_uses_litellm_disable_semantics(self):
        self.assertTrue(should_update_prisma_schema(False))
        self.assertFalse(should_update_prisma_schema(True))
        self.assertTrue(should_update_prisma_schema("false"))
        self.assertTrue(should_update_prisma_schema())
        self.assertFalse(should_update_prisma_schema("true"))
        entrypoint = (APP / "run.py").read_text()
        self.assertIn("not should_update_prisma_schema(False)", entrypoint)
        self.assertIn("should_update_prisma_schema(True)", entrypoint)
        self.assertIn('not should_update_prisma_schema("false")', entrypoint)
        self.assertIn("should_update_prisma_schema()", entrypoint)

    def test_startup_entrypoint_checks_version_schema_and_disable_flag(self):
        dockerfile = (APP / "Dockerfile").read_text()
        entrypoint = (APP / "run.py").read_text()
        launcher = (APP / "run.sh").read_text()
        self.assertIn(
            f'EXPECTED_LITELLM_VERSION = "{run.EXPECTED_LITELLM_VERSION}"', entrypoint
        )
        self.assertIn("EXPECTED_SCHEMA_SHA256", entrypoint)
        self.assertIn("not should_update_prisma_schema(False)", entrypoint)
        self.assertIn("should_update_prisma_schema(True)", entrypoint)
        self.assertIn('not should_update_prisma_schema("false")', entrypoint)
        self.assertIn("should_update_prisma_schema()", entrypoint)
        self.assertIn('os.environ["DISABLE_SCHEMA_UPDATE"] = "true"', entrypoint)
        self.assertIn('environment["STORE_MODEL_IN_DB"] = "true"', entrypoint)
        self.assertIn("run.py", dockerfile)
        self.assertIn("exec /opt/litellm-venv/bin/python /run.py", launcher)
        self.assertLess(
            entrypoint.index("verify_runtime_schema()"),
            entrypoint.index("wait_for_database("),
        )

    def test_database_url_accepts_configured_host_port_database_and_user(self):
        self.assertEqual(
            run.validate_database_url(
                "postgresql://gateway:secret@db.example:5433/models"
            ),
            ("db.example", 5433),
        )

    def test_database_url_rejects_non_postgres_and_incomplete_urls(self):
        for database_url in (
            "https://db.example:5432/models",
            "postgresql://db.example",
        ):
            with self.subTest(database_url=database_url), patch.object(
                run, "fail", side_effect=ValueError
            ):
                with self.assertRaises(ValueError):
                    run.validate_database_url(database_url)

    def test_optional_salt_key_is_passed_when_configured(self):
        self.assertIn(
            'salt_key = options.get("salt_key")', (APP / "run.py").read_text()
        )
        self.assertIn(
            'environment["LITELLM_SALT_KEY"] = salt_key', (APP / "run.py").read_text()
        )

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
            with self.subTest(name=reserved_name), patch.object(
                run, "fail", side_effect=ValueError
            ):
                with self.assertRaises(ValueError):
                    run.configure_provider_environment(
                        {
                            "environment_variables": [
                                {"name": reserved_name, "value": "secret"}
                            ]
                        },
                        {},
                    )

    def test_invalid_custom_environment_variable_name_is_rejected(self):
        with patch.object(run, "fail", side_effect=ValueError):
            with self.assertRaises(ValueError):
                run.configure_provider_environment(
                    {
                        "environment_variables": [
                            {"name": "BAD-NAME", "value": "secret"}
                        ]
                    },
                    {},
                )

    def test_app_config_accepts_database_backed_litellm_routing(self):
        entrypoint = (APP / "run.py").read_text()
        self.assertIn('general["store_model_in_db"] = True', entrypoint)

    def test_missing_or_null_general_settings_are_supported(self):
        for general_settings in ("missing", None):
            with self.subTest(general_settings=general_settings):
                config = {"router_settings": {}, "model_list": []}
                if general_settings != "missing":
                    config["general_settings"] = general_settings
                self.assertEqual(run._general_settings(config), {})
                self.assertEqual(config["general_settings"], {})

    def test_non_mapping_general_settings_are_rejected(self):
        for general_settings in ([], False, 0, ""):
            with self.subTest(general_settings=general_settings):
                with patch.object(run, "fail", side_effect=ValueError):
                    with self.assertRaises(ValueError):
                        run._general_settings({"general_settings": general_settings})

    def test_app_has_official_litellm_icon_and_logo(self):
        for asset in ("icon.png", "logo.png"):
            with self.subTest(asset=asset):
                self.assertTrue((APP / asset).is_file())
                self.assertEqual((APP / asset).read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_app_has_no_internal_network_or_company_references(self):
        files = [
            APP / "config.yaml",
            APP / "run.py",
            APP / "DOCS.md",
            ROOT / "README.md",
        ]
        for path in files:
            contents = path.read_text().lower()
            with self.subTest(path=path.name):
                self.assertNotRegex(contents, r"192\.168\.")
                self.assertNotIn("altanis", contents)
                self.assertNotIn("llm-mc", contents)
                self.assertNotIn("wireguard", contents)


if __name__ == "__main__":
    unittest.main()
