FROM node:22-bookworm-slim AS ui-build

ARG GPUSTACK_UI_VERSION=v2.3.1
ARG GPUSTACK_UI_SHA256=a8c0fe680605951a5069a33c1db8f8d1c62d7dbdecdc5fab1284b34228bbf04b

ENV GPUSTACK_UI_VERSION=${GPUSTACK_UI_VERSION} \
    GPUSTACK_UI_COMMIT_ID=05c56d881e4426b28b842286d85f2510f0be227a

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

RUN curl --fail --location --silent --show-error \
      "https://github.com/gpustack/gpustack-ui/archive/refs/tags/${GPUSTACK_UI_VERSION}.tar.gz" \
      --output /tmp/gpustack-ui.tar.gz \
    && echo "${GPUSTACK_UI_SHA256}  /tmp/gpustack-ui.tar.gz" | sha256sum --check --strict \
    && tar --extract --gzip --file /tmp/gpustack-ui.tar.gz --strip-components=1 \
    && rm /tmp/gpustack-ui.tar.gz

COPY services/gpustack-ui/apply-branding.mjs /opt/insightsphere/apply-branding.mjs
COPY services/gpustack-ui/branding/insightsphere-branding.less /opt/insightsphere/insightsphere-branding.less
COPY app/frontend/public/insight_sphere_new.png /opt/insightsphere/insightsphere-wordmark.png
COPY app/frontend/src/assets/classic_icon-bg.png /opt/insightsphere/insightsphere-mark.png

RUN node /opt/insightsphere/apply-branding.mjs /work \
    && install -m 0644 /opt/insightsphere/insightsphere-branding.less /work/src/insightsphere-branding.less \
    && install -m 0644 /opt/insightsphere/insightsphere-wordmark.png /work/src/assets/images/gpustack-logo.png \
    && install -m 0644 /opt/insightsphere/insightsphere-mark.png /work/src/assets/images/small-logo-200x200.png \
    && install -m 0644 /opt/insightsphere/insightsphere-mark.png /work/public/favicon.png

RUN --mount=type=cache,id=insightsphere-gpustack-pnpm,target=/root/.local/share/pnpm/store \
    corepack enable \
    && corepack prepare pnpm@9.3.0 --activate \
    && pnpm install --frozen-lockfile

# Bound webpack's old-space heap. A constrained build host can still require a
# prebuilt image or temporarily stopped GPUStack container during an upgrade.
RUN NODE_OPTIONS=--max-old-space-size=1536 pnpm run build

FROM gpustack/gpustack:v2.3.1

LABEL org.opencontainers.image.title="InsightSphere Private AI Infrastructure" \
      org.opencontainers.image.description="GPUStack v2.3.1 with the InsightSphere administration theme" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/gpustack/gpustack-ui" \
      com.insightsphere.gpustack-ui.version="v2.3.1"

COPY --from=ui-build /work/dist/ /usr/local/lib/python3.11/dist-packages/gpustack/ui/
COPY --from=ui-build /work/LICENSE /usr/share/licenses/insightsphere-gpustack-ui/LICENSE
