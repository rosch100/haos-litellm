# LiteLLM Home Assistant App

A Home Assistant App repository for deploying the existing LiteLLM gateway on an ARM64 Home Assistant OS host (Raspberry Pi 5). It uses the already-routed network path to PostgreSQL and does **not** install, configure or run WireGuard.

> The app source is available from the repository URL. The ARM64 image is published automatically by the repository's build workflow; do not start the app until the local database routing YAML, credentials, PostgreSQL access and ingress configuration have been supplied and verified.

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
- The production gateway currently stores its model deployments and `store_model_in_db` setting in PostgreSQL; its live YAML has `router_settings.model_group_alias` but no `model_list`. The app explicitly enables DB-backed model loading. Preserve this live YAML shape. The sensitive production YAML is **not included** in this public repository. Prepare it locally at `/addon_configs/0bc5d9b8_litellm/litellm.yaml` on the HA host (mounted as `/config/litellm.yaml` inside the app). The repository ID on this Home Assistant system is `0bc5d9b8`. Remove `general_settings.master_key`, preserve the rest of the routing configuration, and replace provider environment references with the variable names listed below. Never commit credentials/config to Git.
- Enter the exact existing production `master_key` and, if set on production, the exact matching `salt_key`. These may be necessary to decrypt encrypted provider credentials stored in the shared database.
- Enter these provider secret options in the Supervisor UI: `altanis_ai_azure_api_key`, `altanis_ai_deepseek_api_key`, `altanis_ai_openai_api_key`, `altanis_ai_openrouter_api_key`, and `instanz2_azure_api_key`. The corresponding config expressions must use `os.environ/LITELLM_ALTANIS_AI_AZURE_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_DEEPSEEK_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_OPENAI_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_OPENROUTER_API_KEY`, and `os.environ/LITELLM_INSTANZ2_AZURE_API_KEY`. The app does not copy provider secrets from the live host.

### Shared production database protection

This app connects directly to the existing production database. It does not clone/import data. The primary instance must remain the **only schema writer**. The app verifies the pinned runtime schema and sets the supported `DISABLE_SCHEMA_UPDATE=true` environment variable. In LiteLLM `1.105.0`, this makes `should_update_prisma_schema()` return `False`; the proxy CLI then selects `check_prisma_schema_diff()` rather than `PrismaManager.setup_database(...)`. The app rejects `general_settings.disable_prisma_schema_update: true` and removes that key because its inverted parameter semantics select the same diff path, while the environment variable enforces the invariant and is asserted at startup. A version/schema mismatch stops startup before DB access.

The read-only diff can still require metadata connections and schema-inspection privileges. Verify role requirements against a non-production clone first. If the shared DB role lacks suitable read permissions, leave this app stopped instead of granting it schema-write privileges. Apply future migrations once on the designated primary writer after backup and an explicit maintenance procedure. Protect Supervisor options and backups, which contain credentials.

Sharing the database does not itself configure load balancing, session synchronization, coordinated quotas or automatic failover. Keep `llm.altanis.de` as primary until the Pi's routes, database reads, credential decryption, model calls, keys, quotas and concurrent-write effects have been separately verified.

## Ingress and `llm-mc.altanis.de`

No extra WireGuard app/package/tunnel is installed. The app exposes no WAN-facing port; LiteLLM Admin UI is disabled. Configure the existing Home Assistant NGINX proxy to reach the Supervisor-internal app name and port 4000. The internal app hostname for this Home Assistant installation is `0bc5d9b8-litellm:4000` (repository ID `0bc5d9b8`, app slug `litellm`). Verify this generated Supervisor DNS name in the app info before configuring proxying.

The existing Home Assistant Let's Encrypt 6.5.0 app is already configured for `llm-mc.altanis.de`, and the installed certificate contains it as a SAN (expires 6 January 2027). No certificate renewal is required for this hostname now.

The Home Assistant NGINX proxy still has `customize.active: false`, and its certificate-bound virtual host is only configured for `hassio.altanis.de`. It needs an additional TLS server block for `llm-mc.altanis.de`, proxying to the confirmed internal app name `0bc5d9b8-litellm:4000` while preserving `/v1`. This is a separate operation from app installation and should happen only after the app is configured and its internal API passes health checks. Never directly publish LiteLLM or PostgreSQL ports.

See [`litellm/DOCS.md`](litellm/DOCS.md) for detailed configuration, operations and limits.

## Deployment state and required operator input

The repository is registered in the Pi's Home Assistant app store as `0bc5d9b8`, so the app appears there as **LiteLLM** (`0bc5d9b8_litellm`). The certificate SAN has also been verified. The production YAML and secrets are intentionally not copied into the public repository or unattended into Supervisor options. Prepare these locally before starting the app. The app container image must first be published by the repository's successful ARM64 build workflow. The NGINX virtual host remains disabled until the configured app passes health checks.
