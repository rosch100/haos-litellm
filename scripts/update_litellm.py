"""Update the HAOS app pins from the latest official LiteLLM release."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

UPSTREAM_API = "https://api.github.com/repos/BerriAI/litellm"
UPSTREAM_RAW = "https://raw.githubusercontent.com/BerriAI/litellm"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
USER_AGENT = "haos-litellm-release-updater"


@dataclass(frozen=True)
class LiteLLMRelease:
    tag: str
    version: str
    commit: str
    schema_sha256: str


def _fetch(url: str) -> bytes:
    request = Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=30) as response:
        return response.read()


def _fetch_json(url: str) -> dict[str, object]:
    value = json.loads(_fetch(url))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object from {url}")
    return value


def _parse_version(value: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(value)
    if match is None:
        raise ValueError(f"Expected a stable LiteLLM semantic version, got {value!r}")
    return tuple(int(part) for part in match.groups())


def _release_commit(tag: str) -> str:
    reference = _fetch_json(f"{UPSTREAM_API}/git/ref/tags/{tag}")
    target = reference.get("object")
    while isinstance(target, dict) and target.get("type") == "tag":
        sha = target.get("sha")
        if not isinstance(sha, str) or not COMMIT_SHA.fullmatch(sha):
            raise ValueError(f"Invalid annotated tag object for LiteLLM release {tag}")
        target = _fetch_json(f"{UPSTREAM_API}/git/tags/{sha}").get("object")
    if not isinstance(target, dict) or target.get("type") != "commit":
        raise ValueError(f"LiteLLM release tag {tag} does not resolve to a commit")
    commit = target.get("sha")
    if not isinstance(commit, str) or not COMMIT_SHA.fullmatch(commit):
        raise ValueError(f"Invalid commit SHA for LiteLLM release {tag}")
    return commit


def latest_release() -> LiteLLMRelease:
    release = _fetch_json(f"{UPSTREAM_API}/releases/latest")
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not tag.startswith("v"):
        raise ValueError("Latest LiteLLM release must have a v-prefixed tag")
    release_version = tag[1:]
    _parse_version(release_version)

    project = _fetch(f"{UPSTREAM_RAW}/{tag}/pyproject.toml").decode("utf-8")
    version_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', project)
    if version_match is None or version_match.group(1) != release_version:
        raise ValueError(
            f"LiteLLM release tag {tag} does not match its pyproject version"
        )

    schema = _fetch(f"{UPSTREAM_RAW}/{tag}/litellm/proxy/schema.prisma")
    return LiteLLMRelease(
        tag=tag,
        version=release_version,
        commit=_release_commit(tag),
        schema_sha256=hashlib.sha256(schema).hexdigest(),
    )


def _replace_once(contents: str, pattern: str, replacement: str, path: Path) -> str:
    updated, count = re.subn(
        pattern, replacement, contents, count=1, flags=re.MULTILINE
    )
    if count != 1:
        raise ValueError(
            f"Expected exactly one update target matching {pattern!r} in {path}"
        )
    return updated


def update_repository(root: Path, release: LiteLLMRelease) -> bool:
    release_version = _parse_version(release.version)
    if release.tag != f"v{release.version}" or not COMMIT_SHA.fullmatch(release.commit):
        raise ValueError("Invalid LiteLLM release metadata")
    if not re.fullmatch(r"[0-9a-f]{64}", release.schema_sha256):
        raise ValueError("Invalid LiteLLM Prisma schema SHA-256")

    dockerfile_path = root / "litellm/Dockerfile"
    run_path = root / "litellm/run.py"
    config_path = root / "litellm/config.yaml"
    dockerfile = dockerfile_path.read_text(encoding="utf-8")
    run_file = run_path.read_text(encoding="utf-8")
    config = config_path.read_text(encoding="utf-8")

    version_match = re.search(
        r"(?m)^\s*LITELLM_VERSION=(\d+\.\d+\.\d+)\s*\\?$", dockerfile
    )
    commit_match = re.search(
        r"(?m)^\s*LITELLM_SOURCE_COMMIT=([0-9a-f]{40})", dockerfile
    )
    tag_match = re.search(r"(?m)^\s*LITELLM_SOURCE_TAG=(v\d+\.\d+\.\d+)", dockerfile)
    schema_match = re.search(
        r'(?ms)^EXPECTED_SCHEMA_SHA256 = \(\s*"([0-9a-f]{64})"\s*\)', run_file
    )
    manifest_match = re.search(r'(?m)^version:\s*"([^"]+)"\s*$', config)
    if not all((version_match, commit_match, tag_match, schema_match, manifest_match)):
        raise ValueError("Unable to read all LiteLLM release pins from the repository")

    current_version = _parse_version(version_match.group(1))
    if release_version < current_version:
        return False
    if (
        release_version == current_version
        and commit_match.group(1) == release.commit
        and tag_match.group(1) == release.tag
        and schema_match.group(1) == release.schema_sha256
        and manifest_match.group(1) == release.version
    ):
        return False

    updated_dockerfile = _replace_once(
        dockerfile,
        r"(?m)^(\s*LITELLM_VERSION=)[^\s\\]+",
        rf"\g<1>{release.version}",
        dockerfile_path,
    )
    updated_dockerfile = _replace_once(
        updated_dockerfile,
        r"(?m)^(\s*LITELLM_SOURCE_COMMIT=)[0-9a-f]{40}",
        rf"\g<1>{release.commit}",
        dockerfile_path,
    )
    updated_dockerfile = _replace_once(
        updated_dockerfile,
        r"(?m)^(\s*LITELLM_SOURCE_TAG=)[^\s\\]+",
        rf"\g<1>{release.tag}",
        dockerfile_path,
    )
    updated_run_file = _replace_once(
        run_file,
        r'(?m)^(EXPECTED_LITELLM_VERSION = ")[^"]+("\s*)$',
        rf"\g<1>{release.version}\2",
        run_path,
    )
    updated_run_file = _replace_once(
        updated_run_file,
        r'(?ms)^EXPECTED_SCHEMA_SHA256 = \(\s*"[0-9a-f]{64}"\s*\)',
        f'EXPECTED_SCHEMA_SHA256 = (\n    "{release.schema_sha256}"\n)',
        run_path,
    )
    updated_config = _replace_once(
        config,
        r'(?m)^(version:\s*")[^"]+("\s*)$',
        rf"\g<1>{release.version}\2",
        config_path,
    )

    dockerfile_path.write_text(updated_dockerfile, encoding="utf-8")
    run_path.write_text(updated_run_file, encoding="utf-8")
    config_path.write_text(updated_config, encoding="utf-8")
    return True


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        release = latest_release()
        updated = update_repository(root, release)
    except (HTTPError, OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"LiteLLM release update failed: {exc}", file=sys.stderr)
        return 1

    if updated:
        print(
            f"Prepared LiteLLM {release.version} from {release.tag} ({release.commit})"
        )
    else:
        print(f"No LiteLLM release update is needed for {release.version}")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path is not None:
        with Path(output_path).open("a", encoding="utf-8") as output:
            output.write(f"updated={str(updated).lower()}\n")
            output.write(f"version={release.version}\n")
            output.write(f"tag={release.tag}\n")
            output.write(f"commit={release.commit}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
