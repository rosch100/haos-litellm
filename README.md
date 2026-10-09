# LiteLLM Home Assistant App

A configurable ARM64 Home Assistant App for the LiteLLM AI Gateway. Database connection details, gateway keys, provider credentials, and the LiteLLM routing configuration are supplied by the app's own settings or its app configuration directory. The app does not install or configure network tunnels.

## Installation

1. In Home Assistant, open **Settings → Apps → App store → ⋮ → Repositories**.
2. Add `https://github.com/rosch100/haos-litellm`.
3. Install the `LiteLLM` app.
4. Open the app's **Configuration** tab and set the required values described in [`litellm/DOCS.md`](litellm/DOCS.md).

The app supports ARM64 (`aarch64`). Its API port is not published on the host; configure a trusted reverse proxy or private network route if clients need access. Do not expose the API or database directly to the public Internet.

## Configuration

Set `database_url` to the PostgreSQL URL for the LiteLLM database and `master_key` to the gateway key you intend to use. Configure optional `salt_key` where required by your LiteLLM deployment. Put the LiteLLM YAML file in the app's configuration directory (mounted at `/config`) and set `config_file` to its path. Define provider credentials and other runtime variables as entries in `environment_variables`; the values are injected into the proxy process and should be referenced using LiteLLM's `os.environ/VARIABLE_NAME` syntax.

Protect app options, configuration files, and backups because they may contain credentials. The app validates PostgreSQL URL structure, requires authenticated DB access, verifies its pinned LiteLLM version/schema compatibility before connecting, and disables automatic schema changes. Review the chosen database role's read/write privileges and schema migration policy before connecting to an existing database.

## Build and verification

The GitHub Actions workflow validates the app manifest and regression tests, then builds and publishes the ARM64 image to `ghcr.io/rosch100/haos-litellm-litellm`.
