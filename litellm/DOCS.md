# LiteLLM App configuration and operations

## App setup

Install the repository `https://github.com/rosch100/haos-litellm` in Home Assistant **Settings → Apps → App store → ⋮ → Repositories**, then install `LiteLLM`. The app supports ARM64 (`aarch64`) only. Its API port has no host port mapping, and it does not publish a PostgreSQL port.

The image runs LiteLLM `1.105.0` built from a pinned upstream source commit. Startup checks the installed package version and Prisma schema SHA-256 before any database connection. A missing or changed version/schema prevents database access.

## App options

Set these under the installed app's **Configuration** tab. Never commit credentials to Git:

- `database_url`: authenticated PostgreSQL URL including host, port, database, username and password (for example `postgresql://USER:PASSWORD@HOST:5432/DATABASE`). The host and port are configurable; the app contains no fixed network endpoint.
- `master_key`: the LiteLLM API master key.
- `salt_key`: optional LiteLLM credential-encryption salt; use the same value as any instance sharing encrypted credentials.
- `config_file`: path to the LiteLLM YAML file; default `/config/litellm.yaml`.
- `environment_variables`: list of `{name, value}` entries for provider API keys and other LiteLLM environment variables. Reference them from YAML as `os.environ/VARIABLE_NAME`. Names must be shell-compatible identifiers and cannot override app-reserved database, key, or schema-protection variables.

Place the YAML in the Home Assistant app configuration directory for this repository. The directory is mounted read-only at `/config`. Include the models, router settings, and any desired LiteLLM configuration in this file. The app injects `general_settings.master_key` from `master_key` and enables DB-backed model storage, so these settings are controlled by the app to prevent divergence from the selected database.

## Database safeguards

The app sets LiteLLM's supported `DISABLE_SCHEMA_UPDATE=true` environment variable and checks this behavior against the pinned LiteLLM package. It aborts before database access if the package version or Prisma schema differs from the expected values. Do not remove either protection. Review the selected PostgreSQL role's privileges against your migration policy before using an existing database. Some startup schema checks may require database metadata read permissions; the app does not grant or request schema-write privileges itself.

Automatic startup will not migrate the schema. Apply required migrations deliberately on the database's designated schema writer, following backup and maintenance procedures. A shared database does not itself provide request load balancing, session synchronization, coordinated rate limiting, or automatic failover.

## Network and API access

No tunnel software or network route is installed by this app. PostgreSQL must be reachable through the network routing configured by the Home Assistant host. Allow access only from appropriate application networks and keep the database off public interfaces.

LiteLLM listens on container port 4000, but that port is not published on the host. To use the API from other networks or the Internet, configure a TLS-terminating reverse proxy or private network path separately. Preserve API authentication, validate health (`/health/liveliness`) and authenticated API behavior, and avoid exposing the admin interface or PostgreSQL publicly.

## Health and diagnostics

The image health check requests `http://127.0.0.1:4000/health/liveliness`. Startup logs include only the database host and port; they must not include the connection string or secret values. A startup refusal for version/schema mismatch is intentional.
