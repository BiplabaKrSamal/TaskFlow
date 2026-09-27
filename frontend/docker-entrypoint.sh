#!/bin/sh
set -e

PORT="${PORT:-80}"

if [ -n "$BACKEND_HOST" ]; then
  # Explicitly set (e.g. on Render): the backend's own public hostname, reached over HTTPS —
  # see nginx.conf and DEPLOYMENT.md for why this is a public address rather than a private one.
  BACKEND_URL="https://$BACKEND_HOST"
else
  # Docker Compose default: the backend container, over plain HTTP on the compose network.
  BACKEND_URL="http://backend:8000"
fi

RESOLVER="$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf)"
RESOLVER="${RESOLVER:-127.0.0.11}"

sed "s|__PORT__|$PORT|g; s|__BACKEND_URL__|$BACKEND_URL|g; s|__RESOLVER__|$RESOLVER|g" \
  /etc/nginx/templates/default.conf.tmpl > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
