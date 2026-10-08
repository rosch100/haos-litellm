"""Validate HA Supervisor settings and launch the pinned LiteLLM proxy."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit

import litellm
import yaml
from litellm.proxy.db.prisma_client import should_update_prisma_schema

EXPECTED_LITELLM_VERSION = "1.105.0"
EXPECTED_SCHEMA_SHA256 = "2f2c5a491170f1387e4bdda2921599c0991859ba8154b0d587e9521dbf8277f3"
OPTIONS_FILE = Path("/data/options.json")
EXPECTED_PROVIDER_ENVIRONMENT = {
    "altanis_ai_azure_api_key": "LITELLM_ALTANIS_AI_AZURE_API_KEY",
    "altanis_ai_deepseek_api_key": "LITELLM_ALTANIS_AI_DEEPSEEK_API_KEY",
    "altanis_ai_openai_api_key": "LITELLM_ALTANIS_AI_OPENAI_API_KEY",
    "altanis_ai_openrouter_api_key": "LITELLM_ALTANIS_AI_OPENROUTER_API_KEY",
    "instanz2_azure_api_key": "LITELLM_INSTANZ2_AZURE_API_KEY",
}


def fail(message: str) -> None:
    print(f"[LiteLLM HA app] ERROR: {message}", file=sys.stderr, flush=True)
    raise SystemExit(1)


def required_secret(options: dict[str, object], name: str) -> str:
    value = options.get(name)
    if not isinstance(value, str) or not value.strip():
        fail(f"Required secret option {name!r} is empty")
    return value


def validate_database_url(database_url: str) -> tuple[str, int]:
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        fail("database_url must use PostgreSQL")
    if parsed.hostname != "192.168.20.11" or parsed.port != 5432:
        fail("database_url must target the existing PostgreSQL host 192.168.20.11 on port 5432")
    if parsed.path != "/litellm":
        fail("database_url must target the existing litellm database")
    if parsed.username != "litellm" or not parsed.password:
        fail("database_url must use the existing authenticated litellm database user")
    return parsed.hostname, parsed.port


def verify_runtime_schema() -> None:
    if (
        should_update_prisma_schema(False)
        or not should_update_prisma_schema(True)
        or should_update_prisma_schema("false")
        or should_update_prisma_schema()
    ):
        fail("LiteLLM schema update guard failed its runtime safety assertion")

    actual_version = version("litellm")
    if actual_version != EXPECTED_LITELLM_VERSION:
        fail(f"LiteLLM version mismatch; expected {EXPECTED_LITELLM_VERSION}, got {actual_version}")
    schema_path = Path(litellm.__file__).parent / "proxy" / "schema.prisma"
    try:
        actual_schema = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    except OSError:
        fail("LiteLLM Prisma schema is missing from the runtime image")
    if actual_schema != EXPECTED_SCHEMA_SHA256:
        fail("LiteLLM Prisma schema differs from the production schema; refusing shared database access")


def load_litellm_config(options: dict[str, object]) -> Path:
    config_path = Path(str(options.get("config_file", "/config/litellm.yaml"))).resolve()
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        fail(f"Unable to load LiteLLM config file: {exc}")
    if not isinstance(config, dict):
        fail("LiteLLM config must be a YAML mapping")
    router = config.get("router_settings")
    if not isinstance(router, dict) or not isinstance(router.get("model_group_alias"), dict):
        fail("LiteLLM router_settings.model_group_alias must be present in the app config")
    general = config.setdefault("general_settings", {})
    if not isinstance(general, dict):
        fail("LiteLLM general_settings must be a YAML mapping")
    general["master_key"] = "os.environ/LITELLM_MASTER_KEY"
    general.pop("database_url", None)
    if general.get("disable_prisma_schema_update") is True:
        fail("disable_prisma_schema_update=true conflicts with the pinned environment schema guard")
    general.pop("disable_prisma_schema_update", None)
    if general.get("store_model_in_db") is False:
        fail("store_model_in_db=false conflicts with the production database-backed model configuration")
    general["store_model_in_db"] = True

    runtime_dir = Path("/tmp/litellm-haos")
    runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    runtime_config = runtime_dir / "config.yaml"
    runtime_config.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    runtime_config.chmod(0o600)
    os.chmod(runtime_dir, 0o700)
    return runtime_config


def wait_for_database(host: str, port: int) -> None:
    try:
        with socket.create_connection((host, port), timeout=5):
            return
    except OSError as exc:
        fail(
            "PostgreSQL is unreachable over the existing routed network; check HAOS routing, "
            "the return route, firewall and PostgreSQL allowlist "
            f"(connection error: {type(exc).__name__})"
        )


def main() -> None:
    try:
        options = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Unable to read Home Assistant Supervisor options: {exc}")
    if not isinstance(options, dict):
        fail("Home Assistant Supervisor options must be a JSON mapping")

    database_url = required_secret(options, "database_url")
    master_key = required_secret(options, "master_key")
    os.environ["DISABLE_SCHEMA_UPDATE"] = "true"
    verify_runtime_schema()
    database_host, database_port = validate_database_url(database_url)
    runtime_config = load_litellm_config(options)

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["LITELLM_MASTER_KEY"] = master_key
    environment["DISABLE_ADMIN_UI"] = "true"
    environment["STORE_MODEL_IN_DB"] = "true"

    salt_key = options.get("salt_key")
    if salt_key:
        if not isinstance(salt_key, str):
            fail("salt_key must be a string")
        environment["LITELLM_SALT_KEY"] = salt_key

    for option_name, environment_name in EXPECTED_PROVIDER_ENVIRONMENT.items():
        environment[environment_name] = required_secret(options, option_name)

    wait_for_database(database_host, database_port)
    print(
        f"[LiteLLM HA app] Starting LiteLLM {EXPECTED_LITELLM_VERSION} against "
        f"{database_host}:{database_port}/litellm; schema migrations disabled and Admin UI disabled",
        flush=True,
    )
    os.execvpe(
        "/opt/litellm-venv/bin/litellm",
        ["litellm", "--config", str(runtime_config), "--host", "0.0.0.0", "--port", "4000"],
        environment,
    )


if __name__ == "__main__":
    main()
