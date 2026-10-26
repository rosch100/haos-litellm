import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import update_litellm

ROOT = Path(__file__).resolve().parents[1]


class LiteLLMReleaseUpdateTests(unittest.TestCase):
    def test_latest_release_follows_annotated_upstream_tag_and_hashes_schema(self):
        tag_object_sha = "a" * 40
        commit_sha = "b" * 40
        responses = {
            f"{update_litellm.UPSTREAM_API}/releases/latest": b'{"tag_name":"v1.106.0"}',
            f"{update_litellm.UPSTREAM_RAW}/v1.106.0/pyproject.toml": (
                b'[project]\nname = "litellm"\nversion = "1.106.0"\n'
            ),
            f"{update_litellm.UPSTREAM_RAW}/v1.106.0/litellm/proxy/schema.prisma": b"schema\n",
            f"{update_litellm.UPSTREAM_API}/git/ref/tags/v1.106.0": (
                f'{{"object":{{"type":"tag","sha":"{tag_object_sha}"}}}}'.encode()
            ),
            f"{update_litellm.UPSTREAM_API}/git/tags/{tag_object_sha}": (
                f'{{"object":{{"type":"commit","sha":"{commit_sha}"}}}}'.encode()
            ),
        }
        with patch.object(update_litellm, "_fetch", side_effect=responses.__getitem__):
            release = update_litellm.latest_release()

        self.assertEqual(release.tag, "v1.106.0")
        self.assertEqual(release.version, "1.106.0")
        self.assertEqual(release.commit, commit_sha)
        self.assertEqual(release.schema_sha256, hashlib.sha256(b"schema\n").hexdigest())

    def test_latest_release_rejects_version_mismatch(self):
        with (
            patch.object(
                update_litellm,
                "_fetch_json",
                return_value={"tag_name": "v1.106.0"},
            ),
            patch.object(
                update_litellm,
                "_fetch",
                return_value=b'[project]\nversion = "1.105.0"\n',
            ),
        ):
            with self.assertRaisesRegex(ValueError, "does not match"):
                update_litellm.latest_release()

    def test_update_synchronizes_all_version_pins_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "litellm").mkdir()
            (root / "litellm/Dockerfile").write_text(
                "ENV LANG=C.UTF-8 \\\n"
                "    LITELLM_VERSION=1.105.0 \\\n"
                "    LITELLM_SOURCE_REPOSITORY=https://github.com/BerriAI/litellm.git \\\n"
                "    LITELLM_SOURCE_COMMIT=" + "a" * 40 + " \\\n"
                "    LITELLM_SOURCE_TAG=v1.105.0 \\\n"
                "    CARGO_BUILD_JOBS=2\n"
            )
            (root / "litellm/run.py").write_text(
                'EXPECTED_LITELLM_VERSION = "1.105.0"\n'
                'EXPECTED_SCHEMA_SHA256 = (\n    "' + "c" * 64 + '"\n)\n'
            )
            (root / "litellm/config.yaml").write_text('version: "1.105.0"\n')
            release = update_litellm.LiteLLMRelease(
                tag="v1.106.0",
                version="1.106.0",
                commit="b" * 40,
                schema_sha256="d" * 64,
            )

            self.assertTrue(update_litellm.update_repository(root, release))
            dockerfile = (root / "litellm/Dockerfile").read_text()
            runtime = (root / "litellm/run.py").read_text()
            manifest = (root / "litellm/config.yaml").read_text()
            self.assertIn("LITELLM_VERSION=1.106.0", dockerfile)
            self.assertIn("LITELLM_SOURCE_COMMIT=" + "b" * 40, dockerfile)
            self.assertIn("LITELLM_SOURCE_TAG=v1.106.0", dockerfile)
            self.assertIn('EXPECTED_LITELLM_VERSION = "1.106.0"', runtime)
            self.assertIn('"' + "d" * 64 + '"', runtime)
            self.assertIn('version: "1.106.0-ha.1"', manifest)
            self.assertFalse(update_litellm.update_repository(root, release))

    def test_same_upstream_release_increments_custom_app_revision(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "litellm").mkdir()
            (root / "litellm/Dockerfile").write_text(
                "ENV LANG=C.UTF-8 \\\n"
                "    LITELLM_VERSION=1.105.0 \\\n"
                "    LITELLM_SOURCE_REPOSITORY=https://github.com/BerriAI/litellm.git \\\n"
                "    LITELLM_SOURCE_COMMIT=" + "a" * 40 + " \\\n"
                "    LITELLM_SOURCE_TAG=v1.105.0 \\\n"
                "    CARGO_BUILD_JOBS=2\n"
            )
            (root / "litellm/run.py").write_text(
                'EXPECTED_LITELLM_VERSION = "1.105.0"\n'
                'EXPECTED_SCHEMA_SHA256 = (\n    "' + "c" * 64 + '"\n)\n'
            )
            (root / "litellm/config.yaml").write_text(
                'version: "1.105.0-ha.4"\n'
            )
            release = update_litellm.LiteLLMRelease(
                tag="v1.105.0",
                version="1.105.0",
                commit="b" * 40,
                schema_sha256="d" * 64,
            )

            self.assertTrue(update_litellm.update_repository(root, release))
            manifest = (root / "litellm/config.yaml").read_text()
            self.assertIn('version: "1.105.0-ha.5"', manifest)
            self.assertIn(
                "LITELLM_SOURCE_COMMIT=" + "b" * 40,
                (root / "litellm/Dockerfile").read_text(),
            )
            self.assertFalse(update_litellm.update_repository(root, release))

    def test_equal_upstream_version_repairs_old_fork_commit_and_schema_pins(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "litellm").mkdir()
            (root / "litellm/Dockerfile").write_text(
                "ENV LANG=C.UTF-8 \\\n"
                "    LITELLM_VERSION=1.105.0 \\\n"
                "    LITELLM_SOURCE_REPOSITORY=https://github.com/BerriAI/litellm.git \\\n"
                "    LITELLM_SOURCE_COMMIT=" + "a" * 40 + " \\\n"
                "    LITELLM_SOURCE_TAG=v1.105.0 \\\n"
                "    CARGO_BUILD_JOBS=2\n"
            )
            (root / "litellm/run.py").write_text(
                'EXPECTED_LITELLM_VERSION = "1.105.0"\n'
                'EXPECTED_SCHEMA_SHA256 = (\n    "' + "c" * 64 + '"\n)\n'
            )
            (root / "litellm/config.yaml").write_text('version: "1.105.0"\n')
            release = update_litellm.LiteLLMRelease(
                tag="v1.105.0",
                version="1.105.0",
                commit="b" * 40,
                schema_sha256="d" * 64,
            )

            self.assertTrue(update_litellm.update_repository(root, release))
            self.assertIn(
                "LITELLM_SOURCE_COMMIT=" + "b" * 40,
                (root / "litellm/Dockerfile").read_text(),
            )
            self.assertIn('"' + "d" * 64 + '"', (root / "litellm/run.py").read_text())
            self.assertFalse(update_litellm.update_repository(root, release))

    def test_update_rejects_non_release_version_or_malformed_hash(self):
        for release in (
            update_litellm.LiteLLMRelease(
                "v1.106.0rc1", "1.106.0rc1", "a" * 40, "b" * 64
            ),
            update_litellm.LiteLLMRelease("v1.106.0", "1.106.0", "a" * 40, "bad"),
        ):
            with self.subTest(release=release), self.assertRaises(ValueError):
                update_litellm.update_repository(ROOT, release)


if __name__ == "__main__":
    unittest.main()
