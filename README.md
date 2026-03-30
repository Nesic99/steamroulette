# <img src="assets/logo.svg" alt="" width="36" height="39" valign="middle" /> Steam Roulette

**Stop browsing. Start playing.**

Pick a random game from a public Steam library, filter by genre, play mode, or playtime, and let the app choose what to play next.

## What It Does

- Accepts a Steam vanity URL, profile URL, or raw Steam64 ID
- Fetches a player's owned games through the Steam Web API
- Filters by play mode, genre, and playtime
- Enriches the selected game with Steam Store metadata and achievement progress
- Persists successful spins and filter failures to Postgres when a database is configured
- Exposes a protected `/metrics` endpoint with Prometheus-formatted stats generated from Postgres

## Stack

- Backend: Flask, Gunicorn, Requests, psycopg2
- Frontend: React, TypeScript, Vite
- Local runtime: Docker Compose
- Deployment: Helm on Kubernetes/k3s
- Database: Postgres 16

## Project Structure

```text
steamroulette/
├── .env.example
├── README.md
├── README-k8s.md
├── docker-compose.yml
├── helm.zip
├── assets/
│   └── logo.svg
├── backend/
│   ├── app.py                 # Flask API and Steam integration
│   ├── db_init.py             # one-time DB schema bootstrap job
│   ├── Dockerfile
│   ├── gunicorn.conf.py
│   ├── requirements.txt
│   ├── sql/
│   │   └── init.sql           # tables, indexes, Prometheus export function
│   └── tests/
│       └── test_app.py
├── frontend/
│   ├── Dockerfile
│   ├── index.html
│   ├── nginx.conf             # serves SPA and proxies /api in containers
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts         # local dev server and /api proxy
│   └── src/
│       ├── App.tsx
│       ├── index.css
│       └── main.tsx
├── helm/
│   └── steam-roulette/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/         # backend, frontend, postgres, ingress, backup jobs
└── systemd/
    ├── steam-roulette-backend.service
    └── steam-roulette-frontend.service
```

## Quick Start With Docker

1. Get a Steam API key at `https://steamcommunity.com/dev/apikey`
2. Copy the example env file:

```bash
cp .env.example .env
```

3. Fill in at least `STEAM_API_KEY` in `.env`
4. Start the full stack:

```bash
docker compose up --build
```

Open `http://localhost:8080`

### Included services

- `frontend` on `:8080`
- `backend` on `:5000`
- `postgres` on `:5432`
- `db-init`, a one-time schema setup job that runs before the backend starts

## Local Development

### Backend

```bash
cd backend
pip install -r requirements.txt
export STEAM_API_KEY="your_key_here"
gunicorn --config gunicorn.conf.py app:app
```

The API runs on `http://localhost:5000`.

Notes:

- `DATABASE_URL` is optional locally. If omitted, the app still works but skips persistence and reports `"db": "unavailable"` on `/api/health`.
- `METRICS_TOKEN` is only needed if you want to use `/metrics`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

During development, Vite proxies `/api` to `http://localhost:5000`.

## Environment Variables

Root `.env` values used by Docker Compose:

| Variable | Required | Purpose |
| --- | --- | --- |
| `STEAM_API_KEY` | Yes | Steam Web API access |
| `METRICS_TOKEN` | Recommended | Bearer token required for `/metrics` |
| `POSTGRES_DB` | Yes for Docker | Local Postgres database name |
| `POSTGRES_USER` | Yes for Docker | Local Postgres username |
| `POSTGRES_PASSWORD` | Yes for Docker | Local Postgres password |
| `DB_INIT_MAX_RETRIES` | No | Retry count for `db-init` |
| `DB_INIT_RETRY_DELAY_SECONDS` | No | Delay between `db-init` retries |

The backend also reads:

- `DATABASE_URL`: enables Postgres persistence and metrics export

## API

### `POST /api/random-game`

Request body:

```json
{
  "profile_url": "https://steamcommunity.com/id/username",
  "filters": {
    "modes": ["singleplayer"],
    "genres": ["RPG"],
    "unplayed_only": false,
    "playtime_min": 0,
    "playtime_max": -1
  }
}
```

Response shape:

```json
{
  "game": {
    "appid": 570,
    "name": "Dota 2",
    "playtime_forever": 1234,
    "header_image": "https://cdn.akamai.steamstatic.com/steam/apps/570/header.jpg",
    "store_url": "https://store.steampowered.com/app/570",
    "genres": ["Action", "Strategy"],
    "categories": ["Multi-player", "Co-op"],
    "achievements_unlocked": 42,
    "achievements_total": 100
  },
  "player": {
    "name": "PlayerName",
    "avatar": "https://...",
    "profile_url": "https://..."
  },
  "total_games": 312,
  "filtered_pool": 87
}
```

### `GET /api/health`

Returns:

```json
{
  "status": "ok",
  "db": "ok"
}
```

If no database is configured or reachable, `db` is reported as `"unavailable"`.

### `GET /metrics`

- Requires `Authorization: Bearer <METRICS_TOKEN>`
- Returns Prometheus text output
- Depends on Postgres being configured and initialized

Metrics currently include:

- total successful spins
- spins in the last hour
- average spin duration
- total filter failures
- filter failures by reason (`playtime`, `content`)

## Filter Behavior

- Play mode uses OR logic: any selected mode may match
- Genre uses AND logic: all selected genres must match
- Playtime is applied before content filtering
- If content filters are active, the backend shuffles the filtered pool and checks up to 20 candidates against Steam Store metadata

## Persistence And Logging

When `DATABASE_URL` is set, the backend stores:

- successful spins in `spins`
- filter misses in `filter_failures`

The API also writes structured JSON logs to stdout for non-health requests.

## Tests

Backend tests are in `backend/tests/test_app.py` and mock all Steam API calls.

Run them with:

```bash
cd backend
pytest
```

## Helm Deployment

The Helm chart lives in `helm/steam-roulette`.

### Defaults

- images are expected from `ghcr.io/nesic99/steam-roulette`
- `backend.createSecret=false`
- `postgres.createSecret=false`
- ingress is disabled by default
- Postgres is enabled by default

### Required Kubernetes secrets

Create the namespace and both secrets before install when using the default external-secret flow:

```bash
kubectl create namespace steam-roulette --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic steam-roulette-secret \
  --from-literal=STEAM_API_KEY=your_key_here \
  --from-literal=METRICS_TOKEN=your_metrics_token \
  -n steam-roulette

kubectl create secret generic steam-roulette-postgres-secret \
  --from-literal=POSTGRES_DB=steamroulette \
  --from-literal=POSTGRES_USER=steamroulette \
  --from-literal=POSTGRES_PASSWORD=strong_password_here \
  --from-literal=DATABASE_URL='postgresql://steamroulette:strong_password_here@steam-roulette-postgres:5432/steamroulette' \
  -n steam-roulette
```

### Install or upgrade

```bash
helm upgrade --install steam-roulette ./helm/steam-roulette \
  --namespace steam-roulette \
  --wait
```

If you want Helm to create the secrets instead, set:

```yaml
backend:
  createSecret: true
postgres:
  createSecret: true
```

### Optional Postgres backups

Set `postgres.backup.enabled=true` to create:

- a backup PVC
- a CronJob that writes gzipped `pg_dump` backups
- automatic pruning based on `postgres.backup.retentionDays`

For more deployment detail, see `README-k8s.md`.

## Useful Commands

```bash
docker compose up --build
docker compose down
docker compose logs -f backend

cd backend && pytest
cd frontend && npm run build

helm lint ./helm/steam-roulette
kubectl get pods -n steam-roulette
kubectl logs -f deployment/steam-roulette-backend -n steam-roulette
```

## Notes

- The Steam library must be public or the app cannot read owned games
- Achievement data depends on the player's privacy settings for that game
- If Steam Store metadata lookup fails for a candidate game, the backend keeps it eligible instead of over-filtering
- This project is not affiliated with Valve or Steam
