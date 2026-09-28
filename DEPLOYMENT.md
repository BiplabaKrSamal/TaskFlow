# Deploying TaskFlow

`render.yaml` in the repo root is a [Render](https://render.com) Blueprint that deploys the whole
app: two Docker web services (backend, frontend) plus a managed Postgres database. This isn't the
only way to run it — anywhere that runs `docker compose up` (a VM, Fly.io, Railway, ECS) works
too, using the existing `docker-compose.yml` unmodified.

## Why this shape

The frontend (nginx) is the only service the browser talks to. nginx serves the built React app
and proxies `/api/*` (including the WebSocket at `/api/ws`) to the backend, so the browser sees a
single origin and the refresh-cookie auth design (`SameSite=Strict`, same-origin fetches) needs no
changes to deploy.

The frontend reaches the backend over the backend's own **public HTTPS address**
(`https://<BACKEND_HOST>`), not Render's private network — a private hostname isn't reliably
resolvable for a service of type `web`. Every backend route enforces auth itself, so the network
path doesn't weaken security.

## Deploy

1. Push this repo to GitHub.
2. On Render: **New → Blueprint**, connect the repo, click **Apply**. `JWT_SECRET` is generated
   automatically and the backend gets its database URL automatically.
3. Once the backend service exists, copy its hostname (e.g. `taskflow-backend-xxxx.onrender.com`).
4. Open the **frontend** service → **Environment** and set `BACKEND_HOST` to that hostname:
   **no `https://`, no port, no trailing slash.** It is declared with `sync: false` in
   `render.yaml`, so the Blueprint never overwrites it on later syncs. Save; the frontend redeploys.
5. First boot of the backend is slower: it runs migrations and, with `SEED_ON_START=true`, seeds
   the demo accounts (see the main README).
6. Open the frontend service's `.onrender.com` URL. That's the whole app.

## How the proxy is configured

`frontend/docker-entrypoint.sh` runs at container start and fills the placeholders in
`frontend/nginx.conf`:

| Placeholder | Filled with |
|---|---|
| `__PORT__` | `$PORT` (Render) or `80` |
| `__BACKEND_HOST__` | `$BACKEND_HOST`, default `backend:8000` (docker-compose) |
| `__BACKEND_URL__` | `https://$BACKEND_HOST`, or `http://backend:8000` locally |
| `__RESOLVER__` | the container's DNS resolver from `/etc/resolv.conf` |

nginx sends `Host: <backend host>` upstream. **It must not forward the incoming `$host`:** Render
routes by Host header, so the frontend's own hostname would send the request straight back to the
frontend, which would proxy it again — a loop that ends in a `508 Loop Detected`.

## Free vs. always-on

`render.yaml` defaults every resource to `plan: free`:

- **Cold starts:** a free web service sleeps after 15 minutes idle and takes ~30–60s to wake.
- **The free Postgres database expires 30 days after creation** unless upgraded.

Change `plan: free` to `plan: starter` for the backend, frontend and database to avoid both.

## Custom domain

Render → the frontend service → Settings → Custom Domain. Nothing else changes.

## Troubleshooting

- **Login fails with `508`:** a proxy loop. Check that `BACKEND_HOST` on the frontend service is the
  *backend's* hostname (not the frontend's, not empty), and that `nginx.conf` sets
  `proxy_set_header Host __BACKEND_HOST__;` rather than `$host`.
- **Login fails with `502`/`504`:** the backend is asleep or down. Open
  `https://<BACKEND_HOST>/api/health` — it should return `{"status":"ok"}` (the bare `/` returning
  `{"detail":"Not Found"}` is normal).
- **Backend won't come up / health check failing:** check the backend logs for the migration step;
  a bad `DATABASE_URL` shows up there first. `app/config.py` normalizes `postgres://` and
  `postgresql://` to `postgresql+psycopg://`.
- **Frontend loads but API calls fail:** confirm `BACKEND_HOST` is set on the frontend service.
- **Logged out immediately after logging in:** almost always `COOKIE_SECURE=false` on a service
  served over HTTPS. The Blueprint sets `true`.
