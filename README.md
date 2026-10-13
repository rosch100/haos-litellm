# LiteLLM Home Assistant App

A configurable ARM64 Home Assistant App for the LiteLLM AI Gateway. Database connection details, gateway keys, provider credentials, and the LiteLLM routing configuration are supplied by the app's own settings or its app configuration directory. The app does not install or configure network tunnels.

## Installation

1. In Home Assistant, open **Settings → Apps → App store → ⋮ → Repositories**.
2. Add `https://github.com/rosch100/haos-litellm`.
3. Install the `LiteLLM` app.
4. Open the app's **Configuration** tab and set the required values described in [`litellm/DOCS.md`](litellm/DOCS.md).

The app supports ARM64 (`aarch64`). Its LiteLLM Web UI and API are available on the Home Assistant host at port 4000. Set the app's `ssl` option to enable HTTPS at `https://<HOME_ASSISTANT_HOST>:4000/ui` using Home Assistant's managed certificate; otherwise use `http://<HOME_ASSISTANT_LAN_IP>:4000/ui`. Keep this port restricted to trusted devices and do not forward it from the public Internet; it includes the administrative UI. The PostgreSQL port is not published.

## Configuration

Set `database_url` to the PostgreSQL URL for the LiteLLM database and `master_key` to the gateway key you intend to use. Configure optional `salt_key` where required by your LiteLLM deployment. Put the LiteLLM YAML file in the app's configuration directory (mounted at `/config`) and set `config_file` to its path. Define provider credentials and other runtime variables as entries in `environment_variables`; the values are injected into the proxy process and should be referenced using LiteLLM's `os.environ/VARIABLE_NAME` syntax.

Protect app options, configuration files, and backups because they may contain credentials. The app validates PostgreSQL URL structure, requires authenticated DB access, verifies its pinned LiteLLM version/schema compatibility and disabled-schema-update behavior before connecting, and prevents automatic schema changes. Review the chosen database role's read/write privileges and schema migration policy before connecting to an existing database.

## Build and verification

The GitHub Actions workflow validates the app manifest with the official [`frenck/action-app-linter`](https://github.com/frenck/action-app-linter) GitHub Action and runs regression tests, then builds and publishes the ARM64 image to `ghcr.io/rosch100/haos-litellm-litellm`. App versions use `<LiteLLM-version>.<revision>` (for example, `1.105.0.2`) so Home Assistant can distinguish this app build from the upstream LiteLLM release while recognizing it as an update to the upstream version. Increase the final numeric revision when publishing a custom app-only change against the same LiteLLM release. The updater resets it to `1` for a new upstream release and increments it when upstream pins need a same-release correction; the installed LiteLLM package remains pinned and checked against the plain upstream version.
