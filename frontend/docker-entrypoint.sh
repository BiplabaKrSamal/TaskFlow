#!/bin/sh
set -e

# PORT and BACKEND_HOST are only set by a host (e.g. Render); docker-compose leaves
# them unset, which keeps the defaults below — the same nginx.conf serves both.
PORT="${PORT:-80}"
BACKEND_HOST="${BACKEND_HOST:-backend:8000}"

sed "s|__PORT__|$PORT|g; s|__BACKEND_HOST__|$BACKEND_HOST|g" \
  /etc/nginx/templates/default.conf.tmpl > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
