# Deploying TaskFlow

`render.yaml` in the repo root is a [Render](https://render.com) Blueprint that deploys the whole
app: two Docker web services (backend, frontend) plus a managed Postgres database, wired together
automatically. This isn't the only way to run it — anywhere that runs `docker compose up` (a VM,
Fly.io, Railway, ECS) works too, using the existing `docker-compose.yml` unmodified — but Render's
Blueprint needs zero manual configuration, which makes it the fastest path to a live URL.

## Why this shape

The frontend (nginx) is the *only* publicly reachable service. It reaches the backend over
Render's private network — the same relationship `docker-compose.yml` sets up locally with the
`backend:8000` hostname, just resolved to Render's internal address at deploy time instead. The
browser therefore only ever talks to one origin, so the refresh-cookie auth design (`SameSite=
Strict`, same-origin fetches) needed **no changes** to deploy — the deployed topology is the same
one already tested locally and in the demo video, just with real hostnames.

## Deploy

1. Push this repo to GitHub (keep the commit history — it's part of the submission).
2. On [render.com](https://render.com): **New → Blueprint**, connect the repo. Render reads
   `render.yaml` and shows the three resources it's about to create.
3. Click **Apply**. `JWT_SECRET` is generated automatically; the backend gets its database URL
   and the frontend gets the backend's internal address automatically too — nothing to type in.
4. First boot takes a little longer than later ones: the backend runs its migrations and, since
   `SEED_ON_START=true`, seeds the three demo accounts (see the main README) before it starts
   accepting requests.
5. Open the frontend service's `.onrender.com` URL. That's the whole app.

## Free vs. always-on

`render.yaml` defaults every resource to `plan: free`, so a first deploy costs nothing. Two
things to know if you leave it there:

- **Cold starts:** a free web service sleeps after 15 minutes idle and takes ~30-60s to wake on
  the next request — noticeable if a reviewer opens the link after it's been quiet.
- **The free Postgres database expires 30 days after creation** and gets deleted unless you
  upgrade it before then.

To avoid both, change `plan: free` to `plan: starter` for `taskflow-backend`, `taskflow-frontend`,
and `taskflow-db` in `render.yaml` (roughly $20/month total, all three combined) before applying
the Blueprint, or switch a service's plan later from its Settings page on Render.

## Custom domain

Render → the frontend service → Settings → Custom Domain. Nothing else changes — the frontend is
still the only origin the browser sees, so the cookie/auth setup keeps working as-is.

## Troubleshooting

- **Backend won't come up / health check failing:** check the backend service's logs for the
  migration step — a bad `DATABASE_URL` (wrong scheme, wrong credentials) shows up there first.
  `app/config.py` already normalizes a bare `postgres://` or `postgresql://` URL to
  `postgresql+psycopg://`, so Render's own connection string works unmodified.
- **Frontend loads but API calls fail:** confirm `BACKEND_HOST` is set on the frontend service
  (Blueprint sets this automatically; it only goes missing if the service was created by hand
  instead of via `render.yaml`).
- **Logged out immediately after logging in:** almost always `COOKIE_SECURE=false` on a service
  actually served over HTTPS. The Blueprint sets `true` for you; only relevant if you changed it.
