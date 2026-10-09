"""Validate Home Assistant app options and launch the pinned LiteLLM proxy."""

from __future__ import annotations

import hashlib
import json
import os
import re
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
ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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
    if not parsed.hostname or not parsed.path.strip("/"):
        fail("database_url must include a host, port and database name")
    if not parsed.username or parsed.password is None:
        fail("database_url must include an authenticated database user")
    try:
        port = parsed.port
    except ValueError:
        fail("database_url contains an invalid port")
    if port is None:
        fail("database_url must include a port")
    return parsed.hostname, port


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
        fail("LiteLLM Prisma schema differs from the pinned runtime schema; refusing database access")


def load_litellm_config(options: dict[str, object]) -> Path:
    config_path = Path(str(options.get("config_file", "/config/litellm.yaml"))).resolve()
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        fail(f"Unable to load LiteLLM config file: {exc}")
    if not isinstance(config, dict):
        fail("LiteLLM config must be a YAML mapping")
    general = config.setdefault("general_settings", {})
    if not isinstance(general, dict):
        fail("LiteLLM general_settings must be a YAML mapping")
    general["master_key"] = "os.environ/LITELLM_MASTER_KEY"
    general.pop("database_url", None)
    if general.get("disable_prisma_schema_update") is True:
        fail("disable_prisma_schema_update=true conflicts with the pinned environment schema guard")
    general.pop("disable_prisma_schema_update", None)
    if general.get("store_model_in_db") is False:
        fail("store_model_in_db=false conflicts with database-backed model configuration")
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
            "PostgreSQL is unreachable; check routing, firewall and database access rules "
            f"(connection error: {type(exc).__name__})"
        )


def configure_provider_environment(options: dict[str, object], environment: dict[str, str]) -> None:
    variables = options.get("environment_variables", [])
    if not isinstance(variables, list):
        fail("environment_variables must be a list of name/value entries")

    for item in variables:
        if not isinstance(item, dict):
            fail("Each environment_variables entry must be a mapping")
        name = item.get("name")
        value = item.get("value")
        if not isinstance(name, str) or not ENVIRONMENT_NAME.fullmatch(name):
            fail("Environment variable names must use shell-compatible identifier syntax")
        if name in {
            "DATABASE_URL",
            "LITELLM_MASTER_KEY",
            "LITELLM_SALT_KEY",
            "DISABLE_SCHEMA_UPDATE",
            "DISABLE_ADMIN_UI",
            "STORE_MODEL_IN_DB",
        }:
            fail(f"Environment variable {name!r} is reserved by the app")
        if not isinstance(value, str) or not value:
            fail(f"Environment variable value for {name!r} must not be empty")
        environment[name] = value


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
    if salt_key is not None:
        if not isinstance(salt_key, str) or not salt_key:
            fail("salt_key must be a non-empty string when provided")
        environment["LITELLM_SALT_KEY"] = salt_key

    configure_provider_environment(options, environment)
    wait_for_database(database_host, database_port)
    print(
        f"[LiteLLM HA app] Starting LiteLLM {EXPECTED_LITELLM_VERSION} against "
        f"{database_host}:{database_port}; schema migrations disabled and Admin UI disabled",
        flush=True,
    )
    os.execvpe(
        "/opt/litellm-venv/bin/litellm",
        ["litellm", "--config", str(runtime_config), "--host", "0.0.0.0", "--port", "4000"],
        environment,
    )


if __name__ == "__main__":
    main()
