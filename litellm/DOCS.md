# LiteLLM App configuration and operations

## App setup

Install the GitHub repository `https://github.com/rosch100/haos-litellm` in Home Assistant **Settings → Apps → App store → ⋮ → Repositories**, then install `LiteLLM`. The app supports ARM64 (`aarch64`) only. Its port 4000 has no host port mapping and PostgreSQL is never published by the app.

The app image builds the verified LiteLLM source commit `10444df3a0173a99ab4e4858ce6777f31530e6c5` from `rosch100/litellm`, corresponding to production version `1.105.0`. Its proxy and extra-proxy dependency groups provide the server and Prisma tooling. At startup, the app checks the installed version and production Prisma schema SHA-256. A missing or changed version/schema prevents any database connection.

## Supervisor app options

Configure these in the Supervisor app options UI. Do not commit credentials to Git:

- `database_url`: authenticated URL for PostgreSQL `litellm` at `192.168.20.11:5432`, with username `litellm`.
- `master_key`: exact production LiteLLM master key.
- `salt_key`: the exact production salt key if the primary gateway defines one; otherwise leave empty.
- `config_file`: path to the existing production LiteLLM YAML config; default `/config/litellm.yaml` (prepare it before installation; no config file or credentials are included in this repository).
- `altanis_ai_azure_api_key`, `altanis_ai_deepseek_api_key`, `altanis_ai_openai_api_key`, `altanis_ai_openrouter_api_key`, `instanz2_azure_api_key`: provider API credentials referenced through matching environment variables in the local config file.

Place the local config at `/addon_configs/<repository-id>_litellm/litellm.yaml` on the Home Assistant host. Supervisor exposes the GitHub repository identifier through its `GET http://supervisor/addons` endpoint; replace `<repository-id>` with its actual value. The app mounts that directory read-only at `/config`. Secure this file and the Supervisor backups as they may contain non-secret routing/model metadata. Remove the primary gateway's `general_settings.master_key` and replace it with `os.environ/LITELLM_MASTER_KEY`. Replace provider secret environment references with `os.environ/LITELLM_ALTANIS_AI_AZURE_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_DEEPSEEK_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_OPENAI_API_KEY`, `os.environ/LITELLM_ALTANIS_AI_OPENROUTER_API_KEY`, and `os.environ/LITELLM_INSTANZ2_AZURE_API_KEY`, respectively. Preserve the rest of the existing `model_list`, aliases and routing settings.

## Shared production database safeguards

This instance intentionally accesses the existing live `litellm` PostgreSQL database, not a database clone. The database holds live model/deployment records, virtual keys, and configuration. Use exactly the same master key and salt key as the primary deployment, because stored provider credentials may be encrypted using those values.

The primary host remains the sole Prisma schema writer. Startup verifies the exact production package/schema and sets LiteLLM's supported `DISABLE_SCHEMA_UPDATE=true` environment variable, which runs a schema-diff check without applying migrations. **Do not set** `general_settings.disable_prisma_schema_update: true`: in LiteLLM `1.105.0` that option selects the database-setup/migration path rather than acting as a read-only switch, so the app rejects it and removes it from the runtime config. It aborts before database access if the package version or Prisma schema does not match production. Do not remove either protection or point the app at a different database. The read-only diff path can still make metadata connections and require schema-inspection privileges. Verify its role requirements against a non-production clone first; if the role lacks privileges, keep this app stopped rather than grant the second instance schema-write privileges. Any migration requires a deliberate procedure: back up the database, stop or isolate all but the designated writer, validate migration and restoration, and only then resume both services.

A shared database does not provide request load balancing, session synchronization, coordinated rate limiting, or automatic failover. Do not use the Pi endpoint for production traffic until its network path, existing key decryption, model routes, quotas, and concurrent-write effects have been tested with non-production requests.

## Routing to PostgreSQL

No WireGuard software, tunnel or client is installed by this app. The app relies only on the pre-existing HAOS network routing over the already established site-to-site VPN. Before starting, verify forward and return routes between the actual HAOS app-container source and `192.168.20.11`, firewall rules, PostgreSQL listener and a narrow `pg_hba.conf` allowlist. The app checks TCP reachability before starting LiteLLM, but that check alone does not verify PostgreSQL authentication or query access. Do not open PostgreSQL to the public Internet.

## Health and diagnostics

Supervisor monitors `http://[HOST]:4000/health/liveliness`. Startup logs report only the target database host/name and guard state; connection strings and secret values must not be logged. A startup refusal for version/schema mismatch is intentional. A database reachability failure requires checking the existing routes, return route, firewall and PostgreSQL allowlist; it is not fixed by installing another VPN app.

## TLS and public API ingress

The API endpoint is intended to be published as `https://llm-mc.altanis.de/v1` by the existing Home Assistant NGINX proxy. The app publishes no host port. Do not route public traffic directly to LiteLLM or PostgreSQL.

The installed Home Assistant Let's Encrypt app supports multiple domain entries and can issue one SAN certificate for `hassio.altanis.de` plus `llm-mc.altanis.de`. Add the second name to the existing app's `domains` list, retain the current names and certificate paths, and do not request a forced renewal until public HTTP-01 challenge reachability is verified. The inspected `llm-mc.altanis.de` HTTP/port-80 challenge path was not reachable, so certificate issuance remains unverified. DNS-01 is an alternative if the configured Let's Encrypt app/provider supports it and credentials can be stored securely.

The installed NGINX proxy currently has custom configuration disabled. Before exposing this endpoint, enable its supported custom server configuration, install a validated virtual host for `llm-mc.altanis.de`, and proxy to the exact Supervisor-generated internal LiteLLM hostname and port 4000. Internal service hostnames follow `{REPO}_{SLUG}` and use hyphens instead of underscores in DNS, so obtain the repository identifier from Supervisor's `/addons` endpoint. Preserve `/v1`, verify upstream TLS termination and authenticated API access, and test both external access and the split-DNS local path. No live DNS, Let's Encrypt, or NGINX settings were changed when this repository was created.
