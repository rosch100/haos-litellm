# LiteLLM App configuration and operations

## App setup

Install the GitHub repository `https://github.com/rosch100/haos-litellm` in Home Assistant **Settings → Apps → App store → ⋮ → Repositories**, then install `LiteLLM`. The app supports ARM64 (`aarch64`) only. Its port 4000 has no host port mapping and PostgreSQL is never published by the app.

The app image builds the verified LiteLLM source commit `10444df3a0173a99ab4e4858ce6777f31530e6c5` from `rosch100/litellm`, corresponding to production version `1.105.0`. Its proxy and extra-proxy dependency groups provide the server and Prisma tooling. The repository publishes the ARM64 image to `ghcr.io/rosch100/haos-litellm-litellm` on updates to `main`. At startup, the app checks the installed version and production Prisma schema SHA-256. A missing or changed version/schema prevents any database connection.

## Supervisor app options

Configure these in the Supervisor app options UI. Do not commit credentials to Git:

- `database_url`: authenticated URL for PostgreSQL `litellm` at `192.168.20.11:5432`, with username `litellm`.
- `master_key`: exact production LiteLLM master key.
- `salt_key`: the exact production salt key if the primary gateway defines one; otherwise leave empty.
- `config_file`: path to the existing production LiteLLM YAML config; default `/config/litellm.yaml` (prepare it before installation; no config file or credentials are included in this repository).
- `altanis_ai_azure_api_key`, `altanis_ai_deepseek_api_key`, `altanis_ai_openai_api_key`, `altanis_ai_openrouter_api_key`, `instanz2_azure_api_key`: provider API credentials referenced through matching environment variables in the local config file.

Place the local config at `/addon_configs/0bc5d9b8_litellm/litellm.yaml` on the Home Assistant host. The repository ID on this Home Assistant system is `0bc5d9b8`. The app mounts that directory at `/config`. Secure this file and the Supervisor backups as they may contain non-secret routing/model metadata. Remove the primary gateway's `general_settings.master_key` and replace it with `os.environ/LITELLM_MASTER_KEY`. Replace provider secret environment references with `os.environ/LITELLM_ALTANIS_AI_AZURE_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_DEEPSEEK_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_OPENAI_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_OPENROUTER_API_KEY`, and `os.environ/LITELLM_INSTANZ2_AZURE_API_KEY`, respectively. Preserve the rest of the existing model/routing settings.

## Shared production database safeguards

This instance intentionally accesses the existing live `litellm` PostgreSQL database, not a database clone. The database holds live model/deployment records, virtual keys, and configuration. The app sets `store_model_in_db=true` so LiteLLM loads its deployments from PostgreSQL. Use exactly the same master key and salt key as the primary deployment, because stored provider credentials may be encrypted using those values.

The primary host remains the sole Prisma schema writer. Startup verifies the exact production package/schema and sets LiteLLM's supported `DISABLE_SCHEMA_UPDATE=true` environment variable. In LiteLLM `1.105.0`, this makes `should_update_prisma_schema()` return `False`; the proxy CLI then selects `check_prisma_schema_diff()` rather than `PrismaManager.setup_database(...)`. The app rejects `general_settings.disable_prisma_schema_update: true` and removes that key because its inverted parameter semantics select the same diff path, while the environment variable enforces the invariant and is asserted at startup. It aborts before database access if the package version or Prisma schema does not match production. Do not remove either protection or point the app at a different database. The read-only diff path can still make metadata connections and require schema-inspection privileges. Verify its role requirements against a non-production clone first; if the role lacks privileges, keep this app stopped rather than grant the second instance schema-write privileges. Any migration requires a deliberate procedure: back up the database, stop or isolate all but the designated writer, validate migration and restoration, and only then resume both services.

A shared database does not provide request load balancing, session synchronization, coordinated rate limiting, or automatic failover. Do not use the Pi endpoint for production traffic until its network path, existing key decryption, model routes, quotas, and concurrent-write effects have been tested with non-production requests.

## Routing to PostgreSQL

No WireGuard software, tunnel or client is installed by this app. The app relies only on the pre-existing HAOS network routing over the already established site-to-site VPN. Before starting, verify forward and return routes between the actual HAOS app-container source and `192.168.20.11`, firewall rules, PostgreSQL listener and a narrow `pg_hba.conf` allowlist. The app checks TCP reachability before starting LiteLLM, but that check alone does not verify PostgreSQL authentication or query access. Do not open PostgreSQL to the public Internet.

## Health and diagnostics

Supervisor monitors `http://[HOST]:4000/health/liveliness`. Startup logs report only the target database host/name and guard state; connection strings and secret values must not be logged. A startup refusal for version/schema mismatch is intentional. A database reachability failure requires checking the existing routes, return route, firewall and PostgreSQL allowlist; it is not fixed by installing another VPN app.

## TLS and public API ingress

The API endpoint is intended to be published as `https://llm-mc.altanis.de/v1` by the existing Home Assistant NGINX proxy. The app publishes no host port. Do not route public traffic directly to LiteLLM or PostgreSQL.

The existing Home Assistant Let's Encrypt app is configured for `llm-mc.altanis.de`. The installed certificate was verified to contain `hassio.altanis.de`, `hassio.czenh250aq2g2h5d.myfritz.net`, and `llm-mc.altanis.de` as SAN entries and is valid through 6 January 2027. No certificate renewal is required now.

The installed NGINX proxy still has custom configuration disabled, and TLS connections to `llm-mc.altanis.de` currently fail with an unrecognized SNI name because its virtual host is not installed. After the app is configured and passes internal health checks, enable its supported custom server configuration and install a validated virtual host for `llm-mc.altanis.de`, proxying to the Supervisor-confirmed upstream `0bc5d9b8-litellm:4000`. Preserve `/v1`, verify authenticated API access, and test external access and the split-DNS local path. No NGINX or DNS setting has yet been changed.
