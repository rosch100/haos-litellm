#!/usr/bin/with-contenv bashio
set -Eeuo pipefail

readonly EXPECTED_LITELLM_VERSION="1.105.0"
readonly EXPECTED_SCHEMA_SHA256="2f2c5a491170f1387e4bdda2921599c0991859ba8154b0d587e9521dbf8277f3"
CONFIG_FILE="$(bashio::config 'config_file')"
DATABASE_URL="$(bashio::config 'database_url')"
MASTER_KEY="$(bashio::config 'master_key')"
SALT_KEY="$(bashio::config 'salt_key')"
readonly CONFIG_FILE DATABASE_URL MASTER_KEY SALT_KEY
readonly LITELLM_BIN="/opt/litellm-venv/bin/litellm"
readonly PYTHON_BIN="/opt/litellm-venv/bin/python"

for secret_name in DATABASE_URL MASTER_KEY; do
    if [[ -z "${!secret_name}" ]]; then
        bashio::log.fatal "Required LiteLLM secret ${secret_name} is empty"
        exit 1
    fi
done

actual_version="$("${PYTHON_BIN}" -c 'import importlib.metadata; from litellm.proxy.db.prisma_client import should_update_prisma_schema; assert should_update_prisma_schema(False) is False; assert should_update_prisma_schema(True) is False; print(importlib.metadata.version("litellm"))')"
if [[ "${actual_version}" != "${EXPECTED_LITELLM_VERSION}" ]]; then
    bashio::log.fatal "Installed LiteLLM version mismatch; refusing to connect to the shared database"
    exit 1
fi

RUNTIME_SCHEMA_HASH="$("${PYTHON_BIN}" -c 'import hashlib, importlib.util, pathlib; spec=importlib.util.find_spec("litellm"); print(hashlib.sha256((pathlib.Path(spec.origin).parent / "proxy" / "schema.prisma").read_bytes()).hexdigest())')"
readonly RUNTIME_SCHEMA_HASH
if [[ "${RUNTIME_SCHEMA_HASH}" != "${EXPECTED_SCHEMA_SHA256}" ]]; then
    bashio::log.fatal "LiteLLM Prisma schema mismatch; refusing to connect to the shared database"
    exit 1
fi

if [[ ! -r "${CONFIG_FILE}" ]]; then
    bashio::log.fatal "LiteLLM config file is not readable: ${CONFIG_FILE}"
    exit 1
fi

export DATABASE_URL
export LITELLM_MASTER_KEY="${MASTER_KEY}"
if [[ -n "${SALT_KEY}" ]]; then
    export LITELLM_SALT_KEY="${SALT_KEY}"
fi
export DISABLE_ADMIN_UI=true
export DISABLE_SCHEMA_UPDATE=true

readonly PROVIDER_OPTIONS=(
    "altanis_ai_azure_api_key:LITELLM_ALTANIS_AI_AZURE_API_KEY"
    "altanis_ai_deepseek_api_key:LITELLM_ALTANIS_AI_DEEPSEEK_API_KEY"
    "altanis_ai_openai_api_key:LITELLM_ALTANIS_AI_OPENAI_API_KEY"
    "altanis_ai_openrouter_api_key:LITELLM_ALTANIS_AI_OPENROUTER_API_KEY"
    "instanz2_azure_api_key:LITELLM_INSTANZ2_AZURE_API_KEY"
)
for provider_option in "${PROVIDER_OPTIONS[@]}"; do
    option_name="${provider_option%%:*}"
    environment_name="${provider_option#*:}"
    secret_value="$(bashio::config "${option_name}")"
    if [[ -z "${secret_value}" ]]; then
        bashio::log.fatal "Required provider secret ${option_name} is empty"
        exit 1
    fi
    export "${environment_name}=${secret_value}"
done
unset secret_value

DATABASE_HOST="$(${PYTHON_BIN} -c 'import os, urllib.parse; print(urllib.parse.urlparse(os.environ["DATABASE_URL"]).hostname or "")')"
DATABASE_PORT="$(${PYTHON_BIN} -c 'import os, urllib.parse; print(urllib.parse.urlparse(os.environ["DATABASE_URL"]).port or 5432)')"
DATABASE_NAME="$(${PYTHON_BIN} -c 'import os, urllib.parse; print(urllib.parse.urlparse(os.environ["DATABASE_URL"]).path.lstrip("/"))')"
DATABASE_USER="$(${PYTHON_BIN} -c 'import os, urllib.parse; print(urllib.parse.unquote(urllib.parse.urlparse(os.environ["DATABASE_URL"]).username or ""))')"
if [[ "${DATABASE_HOST}" != "192.168.20.11" || "${DATABASE_PORT}" != "5432" || "${DATABASE_NAME}" != "litellm" || "${DATABASE_USER}" != "litellm" ]]; then
    bashio::log.fatal "DATABASE_URL must target the existing litellm user/database at 192.168.20.11:5432/litellm"
    exit 1
fi

if ! "${PYTHON_BIN}" -c 'import os, socket, urllib.parse; u=urllib.parse.urlparse(os.environ["DATABASE_URL"]); s=socket.create_connection((u.hostname, u.port or 5432), timeout=5); s.close()'; then
    bashio::log.fatal "PostgreSQL is unreachable over the existing routed network; check HAOS routes, return routing, firewall and PostgreSQL allowlist"
    exit 1
fi

RUNTIME_CONFIG="$(mktemp /tmp/litellm-runtime-config.XXXXXX.yaml)"
chmod 0600 "${RUNTIME_CONFIG}"
trap 'rm -f "${RUNTIME_CONFIG}"' EXIT
"${PYTHON_BIN}" - "${CONFIG_FILE}" "${RUNTIME_CONFIG}" <<'PY'
import sys
from pathlib import Path
import yaml

source, destination = map(Path, sys.argv[1:])
config = yaml.safe_load(source.read_text(encoding="utf-8"))
if not isinstance(config, dict) or not isinstance(config.get("model_list"), list) or not config["model_list"]:
    raise SystemExit("LiteLLM config must contain the existing production model_list")
general = config.setdefault("general_settings", {})
if not isinstance(general, dict):
    raise SystemExit("LiteLLM general_settings must be a YAML mapping")
general["master_key"] = "os.environ/LITELLM_MASTER_KEY"
if general.get("disable_prisma_schema_update") is True:
    raise SystemExit("disable_prisma_schema_update=true enables setup/migrations in LiteLLM 1.105.0; refusing startup")
general.pop("disable_prisma_schema_update", None)
general.pop("database_url", None)
from litellm.proxy.db.prisma_client import should_update_prisma_schema
if should_update_prisma_schema(False) or should_update_prisma_schema(True):
    raise SystemExit("LiteLLM schema update safety assertion failed; refusing startup")
destination.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
destination.chmod(0o600)
PY

bashio::log.info "Starting verified LiteLLM ${EXPECTED_LITELLM_VERSION}; Prisma schema updates are disabled"
exec "${LITELLM_BIN}" --config "${RUNTIME_CONFIG}" --host 0.0.0.0 --port 4000
