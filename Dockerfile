# Lince Investor Suite — all-in-one dashboard image.
#
# Build locally:
#   docker build -t borjatarraso/lynx-dashboard:latest .
#
# Run — drops you into the dashboard launcher that can open any of the
# Suite's 15 other tools:
#   docker run --rm -it -p 5000:5000 -v lynx-data:/data borjatarraso/lynx-dashboard:latest
#
# Run the portfolio REST API on the host:
#   docker run --rm -it -p 5000:5000 -v lynx-data:/data \
#       borjatarraso/lynx-dashboard:latest lynx-portfolio --api --port 5000
#
# Persistent portfolio / cache data lives at /data (pass a named
# volume or a bind mount to keep it across containers).

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------------------
# Builder — install the entire Suite into a single venv.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Core runtime deps pulled from Debian (weasyprint needs pango/cairo).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libglib2.0-0 \
        libxml2 \
        libxslt1.1 \
        libjpeg62-turbo \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip build

# Install the Suite from the published PyPI packages. When running
# against the local monorepo (for CI / dev), override with
# `docker build --build-arg INSTALL_FROM=local .` and mount the repo
# at /src.
ARG INSTALL_FROM=pypi
ARG SUITE_VERSION=5.1

# PyPI path
RUN if [ "$INSTALL_FROM" = "pypi" ]; then \
        pip install \
            "lynx-investor-core>=${SUITE_VERSION}" \
            "lynx-fundamental>=${SUITE_VERSION}" \
            "lynx-compare>=${SUITE_VERSION}" \
            "lynx-portfolio>=${SUITE_VERSION}" \
            "lynx-dashboard>=${SUITE_VERSION}" \
            "lynx-investor-basic-materials>=${SUITE_VERSION}" \
            "lynx-investor-energy>=${SUITE_VERSION}" \
            "lynx-investor-industrials>=${SUITE_VERSION}" \
            "lynx-investor-utilities>=${SUITE_VERSION}" \
            "lynx-investor-healthcare>=${SUITE_VERSION}" \
            "lynx-investor-financials>=${SUITE_VERSION}" \
            "lynx-investor-information-technology>=${SUITE_VERSION}" \
            "lynx-investor-communication-services>=${SUITE_VERSION}" \
            "lynx-investor-consumer-discretionary>=${SUITE_VERSION}" \
            "lynx-investor-consumer-staples>=${SUITE_VERSION}" \
            "lynx-investor-real-estate>=${SUITE_VERSION}" ; \
    fi

# Local path — build artifacts out of /src then install.
# Mount with `-v $(pwd)/..:/src` from a root checkout of the monorepo.
COPY . /tmp/context
RUN if [ "$INSTALL_FROM" = "local" ]; then \
        cd /tmp/context && \
        for d in lynx-investor-core lynx-investor/lynx-investor-* \
                 lynx-fundamental lynx-compare lynx-portfolio lynx-dashboard; do \
          [ -f "$d/pyproject.toml" ] && pip install "$d" || true ; \
        done ; \
    fi

# ---------------------------------------------------------------------------
# Runtime — minimal image with just the venv.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    LYNX_DATA_DIR="/data"

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libglib2.0-0 \
        libxml2 \
        libxslt1.1 \
        libjpeg62-turbo \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        tini \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r lynx && useradd -r -g lynx -u 1000 -m -d /home/lynx lynx \
    && mkdir -p /data && chown -R lynx:lynx /data

COPY --from=builder /opt/venv /opt/venv

WORKDIR /data
USER lynx

EXPOSE 5000

# Sensible default: start the Portfolio API bound to all interfaces
# (inside a container that's the only reasonable choice). Operators
# can override with `docker run ... lynx-mining -t AAPL`, etc.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["lynx-portfolio", "--api", "--unsafe-bind-all", "--port", "5000"]

LABEL org.opencontainers.image.title="Lince Investor Suite" \
      org.opencontainers.image.description="All-in-one image with every Suite agent, the dashboard launcher, and the Portfolio REST API + mobile web UI." \
      org.opencontainers.image.source="https://github.com/borjatarraso/lynx-dashboard" \
      org.opencontainers.image.licenses="BSD-3-Clause" \
      org.opencontainers.image.authors="Borja Tarraso <borja.tarraso@member.fsf.org>"
