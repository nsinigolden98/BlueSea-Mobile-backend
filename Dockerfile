# Multi-stage build for the BlueSea Axum backend (Postgres only).
# Produces a slim runtime image with the binary + Askama templates.

FROM rust:1-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependency layer (cached unless manifests change).
COPY Cargo.toml Cargo.lock ./
RUN mkdir -p src templates && echo 'fn main() {}' > src/main.rs \
    && cargo build --release \
    && rm -rf src templates target/release/deps/bluesea_backend* target/release/bluesea-backend*

# Real build.
COPY src ./src
COPY templates ./templates
COPY migrations ./migrations
RUN cargo build --release

# Admin panel (React + Vite).
FROM node:24-slim AS frontend
WORKDIR /panel
COPY admin-panel/package.json admin-panel/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY admin-panel/ ./
RUN npm run build

FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 appuser \
    && mkdir -p /app/media /app/templates \
    && chown -R appuser:appuser /app

WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/target/release/bluesea-backend /app/bluesea-backend
COPY --from=builder --chown=appuser:appuser /app/templates /app/templates
COPY --from=frontend --chown=appuser:appuser /panel/dist /app/admin-panel/dist

USER appuser
ENV PORT=8000 \
    MEDIA_ROOT=/app/media \
    RUST_LOG=info

EXPOSE 8000

# bash /dev/tcp probe: no curl/wget in the slim image.
# Sends X-Forwarded-Proto like nginx does, so the SECURE_SSL_REDIRECT
# middleware (Django parity) lets the check through with a 200.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD bash -c 'exec 3<>/dev/tcp/127.0.0.1/${PORT:-8000} && echo -e "GET /health HTTP/1.0\r\nHost: localhost\r\nX-Forwarded-Proto: https\r\n\r\n" >&3 && grep -q "200" <&3'

CMD ["/app/bluesea-backend"]
