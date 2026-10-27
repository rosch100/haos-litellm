FROM ghcr.io/home-assistant/base-python:3.14-alpine3.24

ARG TARGETARCH
ARG BUILD_VERSION
ARG BUILD_ARCH

ENV LANG=C.UTF-8 \
    LITELLM_VERSION=1.106.4 \
    LITELLM_SOURCE_REPOSITORY=https://github.com/BerriAI/litellm.git \
    LITELLM_SOURCE_COMMIT=ea7ca16dbc3904d9e59a9505f379a2ca3091821f \
    LITELLM_SOURCE_TAG=v1.106.4 \
    CARGO_BUILD_JOBS=2 \
    PRISMA_BINARY_CACHE_DIR=/opt/litellm-prisma \
    PRISMA_CLI_QUERY_ENGINE_TYPE=binary \
    PATH="/opt/litellm-venv/bin:${PATH}"

# hadolint ignore=DL3018
RUN apk add --no-cache git nodejs npm curl build-base python3-dev linux-headers cargo rust cmake ninja libsndfile openssl

RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    set -eu && \
    python3 -m venv /opt/litellm-venv && \
    git clone --filter=blob:none "${LITELLM_SOURCE_REPOSITORY}" /tmp/litellm-source && \
    git -C /tmp/litellm-source checkout --detach "${LITELLM_SOURCE_COMMIT}" && \
    test "$(git -C /tmp/litellm-source describe --tags --exact-match "${LITELLM_SOURCE_COMMIT}")" = "${LITELLM_SOURCE_TAG}" && \
    python3 -c 'import tomllib; from pathlib import Path; data = tomllib.loads(Path("/tmp/litellm-source/pyproject.toml").read_text()); dependencies = data["project"]["dependencies"] + data["project"]["optional-dependencies"]["proxy"] + data["project"]["optional-dependencies"]["extra_proxy"]; Path("/tmp/litellm-requirements.txt").write_text("\n".join(dependency for dependency in dependencies if not dependency.startswith("pyroscope-io")) + "\n")' && \
    test -s /tmp/litellm-requirements.txt && \
    ! grep -Fq "pyroscope-io" /tmp/litellm-requirements.txt && \
    /opt/litellm-venv/bin/pip install --only-binary=litellm "litellm==${LITELLM_VERSION}" -r /tmp/litellm-requirements.txt && \
    prisma_cache_dir="$(python3 -c 'import os; print(os.environ["PRISMA_BINARY_CACHE_DIR"])')" && \
    python_site_packages="$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" && \
    mkdir -p "$prisma_cache_dir" && \
    python3 -c 'from pathlib import Path; path = Path("/tmp/litellm-source/litellm/proxy/schema.prisma"); schema = path.read_text(); source = "linux-musl-openssl-3.0.x"; target = "linux-musl-arm64-openssl-3.0.x"; assert schema.count(f"\"{source}\"") == 1 and target not in schema; path.write_text(schema.replace(f"\"{source}\"", f"\"{source}\", \"{target}\""))' && \
    grep -Fq '"linux-musl-arm64-openssl-3.0.x"' /tmp/litellm-source/litellm/proxy/schema.prisma && \
    grep -Fq '"linux-musl-openssl-3.0.x", "linux-musl-arm64-openssl-3.0.x"' /tmp/litellm-source/litellm/proxy/schema.prisma && \
    /opt/litellm-venv/bin/prisma generate --schema=/tmp/litellm-source/litellm/proxy/schema.prisma && \
    for binary in "$python_site_packages"/prisma/binaries/*; do \
      case "$binary" in \
        *.py) ;; \
        *) binary_name="${binary##*/}" && mv "$binary" "$prisma_cache_dir/$binary_name" && ln -s "$prisma_cache_dir/$binary_name" "$binary" ;; \
      esac; \
    done && \
    /opt/litellm-venv/bin/python -c 'from prisma import client, config; config.binary_platform = "linux-musl-arm64-openssl-3.0.x"; from prisma.engine.utils import ensure; ensure(client.BINARY_PATHS.query_engine)' && \
    rm -rf /tmp/litellm-source /tmp/litellm-requirements.txt

COPY run.py /run.py
COPY run.sh /run.sh
RUN chmod 0755 /run.sh /run.py

ENV IMAGE="ghcr.io/rosch100/haos-litellm-litellm:${BUILD_VERSION}"

LABEL \
    io.hass.name="LiteLLM" \
    io.hass.description="LiteLLM AI Gateway" \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.url="https://github.com/rosch100/haos-litellm"

EXPOSE 4000/tcp

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD ["/opt/litellm-venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4000/health/liveliness', timeout=5)"]

CMD ["/run.sh"]
