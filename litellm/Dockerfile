FROM ghcr.io/home-assistant/base-python:3.13-alpine3.24

ARG TARGETARCH
ARG BUILD_VERSION
ARG BUILD_ARCH

ENV LANG=C.UTF-8 \
    LITELLM_VERSION=1.105.0 \
    LITELLM_SOURCE_COMMIT=10444df3a0173a99ab4e4858ce6777f31530e6c5 \
    CARGO_BUILD_JOBS=2 \
    PRISMA_CLI_QUERY_ENGINE_TYPE=binary \
    PATH="/opt/litellm-venv/bin:${PATH}"

RUN apk add --no-cache git nodejs npm curl build-base python3-dev linux-headers cargo rust cmake ninja

RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python3 -m venv /opt/litellm-venv && \
    /opt/litellm-venv/bin/pip install maturin==1.15.0 numpy PyYAML scikit-build-core && \
    ln -s /opt/litellm-venv/bin/maturin /usr/local/bin/maturin && \
    git clone --filter=blob:none https://github.com/rosch100/litellm.git /tmp/litellm-source && \
    git -C /tmp/litellm-source checkout --detach "${LITELLM_SOURCE_COMMIT}" && \
    sed -i "/pyroscope-io>=0.8.16,<1.0/d" /tmp/litellm-source/pyproject.toml && \
    /opt/litellm-venv/bin/pip install --no-build-isolation "/tmp/litellm-source[proxy,extra_proxy]" && \
    rm -rf /tmp/litellm-source

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
