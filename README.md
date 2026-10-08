# LiteLLM Home Assistant App

A Home Assistant App repository for deploying the existing LiteLLM gateway on an ARM64 Home Assistant OS host (Raspberry Pi 5). It uses the already-routed network path to PostgreSQL and does **not** install, configure or run WireGuard.

> The repository provides the app source only. It does not install/start LiteLLM on the Pi or alter live HAOS DNS, NGINX, or Let's Encrypt settings.

## Installation

1. In Home Assistant, open **Settings → Apps → App store → ⋮ → Repositories**.
2. Add `https://github.com/rosch100/haos-litellm`.
3. Install the `LiteLLM` app.

The app is ARM64-only. No PostgreSQL port or host port for the LiteLLM API is published. The existing Home Assistant NGINX proxy must reach it over Supervisor's internal network.

## Required before first start

The app intentionally fails closed unless its production package, Prisma schema, configuration, secrets and routed database endpoint are prepared:

- The app image builds the exact LiteLLM `1.105.0` source commit `10444df3a0173a99ab4e4858ce6777f31530e6c5` from `rosch100/litellm`. Runtime startup verifies package version `1.105.0` and Prisma schema SHA-256 `2f2c5a491170f1387e4bdda2921599c0991859ba8154b0d587e9521dbf8277f3` before database access.
- `database_url` must target the existing authenticated `litellm` user/database at `192.168.20.11:5432/litellm`.
- PostgreSQL must be reachable from inside the app container using the already-existing HAOS/site-to-site VPN routing. Forward and return routes, firewall rules and the narrow PostgreSQL allowlist must permit the actual container source address.
- The local LiteLLM config must contain the existing production `model_list`, aliases and routing settings. The sensitive production YAML is **not included** in this public repository. Prepare it locally at `/addon_configs/<repository-id>_litellm/litellm.yaml` on the HA host (mounted as `/config/litellm.yaml` inside the app). Find `<repository-id>` in Supervisor's `GET http://supervisor/addons` response. Remove `general_settings.master_key`, preserve the rest of the model/routing configuration, and replace provider environment references with the variable names listed below. Never commit credentials/config to Git.
- Enter the exact existing production `master_key` and, if set on production, the exact matching `salt_key`. These may be necessary to decrypt encrypted provider credentials stored in the shared database.
- Enter these provider secret options in the Supervisor UI: `altanis_ai_azure_api_key`, `altanis_ai_deepseek_api_key`, `altanis_ai_openai_api_key`, `altanis_ai_openrouter_api_key`, and `instanz2_azure_api_key`. The corresponding config expressions must use `os.environ/LITELLM_ALTANIS_AI_AZURE_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_DEEPSEEK_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_OPENAI_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_OPENROUTER_API_KEY`, and `os.environ/LITELLM_INSTANZ2_AZURE_API_KEY`. The app does not copy provider secrets from the live host.

### Shared production database protection

This app connects directly to the existing production database. It does not clone/import data. The primary instance must remain the **only schema writer**. The app verifies the pinned runtime schema and sets the supported `DISABLE_SCHEMA_UPDATE=true` environment variable to perform a schema-diff check without applying migrations. In LiteLLM `1.105.0`, do **not** set `general_settings.disable_prisma_schema_update: true`: that configuration path selects database setup/migration rather than read-only mode. The app refuses that setting and removes it from the runtime config. A version/schema mismatch stops startup before DB access.

The read-only diff can still require metadata connections and schema-inspection privileges. Verify role requirements against a non-production clone first. If the shared DB role lacks suitable read permissions, leave this app stopped instead of granting it schema-write privileges. Apply future migrations once on the designated primary writer after backup and an explicit maintenance procedure. Protect Supervisor options and backups, which contain credentials.

Sharing the database does not itself configure load balancing, session synchronization, coordinated quotas or automatic failover. Keep `llm.altanis.de` as primary until the Pi's routes, database reads, credential decryption, model calls, keys, quotas and concurrent-write effects have been separately verified.

## Ingress and `llm-mc.altanis.de`

No extra WireGuard app/package/tunnel is installed. The app exposes no WAN-facing port; LiteLLM Admin UI is disabled. Configure the existing Home Assistant NGINX proxy to reach the Supervisor-internal app name and port 4000. The internal app name is `{REPO}_litellm`, with the generated repository identifier obtainable from `GET http://supervisor/addons`; replace underscores with hyphens for DNS (`<repo-id>-litellm`). Verify this target rather than assuming the ID.

A separate certificate/key is not inherently required. The existing Home Assistant Let's Encrypt 6.5.0 app supports multiple names in its `domains` list, and one SAN certificate can cover `hassio.altanis.de` and `llm-mc.altanis.de`. Add the new name while preserving the current domains and cert paths. However, public HTTP-01 challenge access to `llm-mc.altanis.de` on port 80 was **not reachable when inspected**, so certificate issuance is unverified. Do not force renewal until public DNS, forwarding/firewall and the challenge listener have been verified. Use DNS-01 only if the installed ACME app/provider supports it and its credentials can be stored securely.

The current NGINX customization option was `customize.active: false`. Before public exposure, enable the supported custom server block for `llm-mc.altanis.de`, proxy to the confirmed internal app name on port 4000, preserve the `/v1` path, verify the SAN certificate and test both external ingress and internal split DNS. Never directly publish LiteLLM or PostgreSQL ports.

See [`litellm/DOCS.md`](litellm/DOCS.md) for detailed configuration, operations and limits.

## What has not been applied

The Pi app has not been installed or started. No change was made to the running HAOS instance, live LiteLLM, WireGuard, DNS, Let's Encrypt or NGINX settings. The Home Assistant add-on repository and app source are published here; build, network, database-read privileges and certificate challenge still need on-device verification.
