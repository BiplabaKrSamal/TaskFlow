#!/bin/sh
set -e

# PORT and BACKEND_HOST are only set by a host (e.g. Render); docker-compose leaves
# them unset, which keeps the defaults below — the same nginx.conf serves both.
PORT="${PORT:-80}"
BACKEND_HOST="${BACKEND_HOST:-backend:8000}"

# Whatever DNS resolver this container itself was given (Docker's embedded one locally,
# the host's internal resolver when deployed) — nginx needs this told to it explicitly to
# resolve the backend at request time instead of once at boot. See nginx.conf for why.
RESOLVER="$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf)"
RESOLVER="${RESOLVER:-127.0.0.11}"

# --- temporary diagnostics: remove this block once the backend connection works ---
echo "[diag] BACKEND_HOST=$BACKEND_HOST"
echo "[diag] RESOLVER=$RESOLVER"
echo "[diag] /etc/resolv.conf:"
cat /etc/resolv.conf
echo "[diag] /etc/hosts:"
cat /etc/hosts
echo "[diag] end"
# --- end temporary diagnostics ---

sed "s|__PORT__|$PORT|g; s|__BACKEND_HOST__|$BACKEND_HOST|g; s|__RESOLVER__|$RESOLVER|g" \
  /etc/nginx/templates/default.conf.tmpl > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
