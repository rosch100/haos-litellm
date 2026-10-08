FROM ghcr.io/home-assistant/base:latest

ARG BUILD_VERSION
ARG BUILD_ARCH

ENV LANG=C.UTF-8 \
    LITELLM_VERSION=1.105.0 \
    LITELLM_SOURCE_COMMIT=10444df3a0173a99ab4e4858ce6777f31530e6c5 \
    PIP_NO_BUILD_ISOLATION=0 \
    CARGO_BUILD_JOBS=2

RUN apk add --no-cache python3 py3-pip py3-yaml py3-cryptography git nodejs npm curl build-base python3-dev linux-headers cargo rust~=1.98

RUN python3 -m venv /opt/litellm-venv && \
    /opt/litellm-venv/bin/pip install --no-cache-dir maturin==1.15.0 PyYAML && \
    git clone https://github.com/rosch100/litellm.git /tmp/litellm-source && \
    git -C /tmp/litellm-source checkout --detach "${LITELLM_SOURCE_COMMIT}" && \
    /opt/litellm-venv/bin/pip install --no-cache-dir "/tmp/litellm-source[proxy,extra_proxy]" && \
    rm -rf /tmp/litellm-source

ENV PATH="/opt/litellm-venv/bin:${PATH}" \
    PRISMA_CLI_QUERY_ENGINE_TYPE=binary

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

CMD ["/run.sh"]
