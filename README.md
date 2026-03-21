# <img src="assets/logo.svg" alt="" width="36" height="39" valign="middle" /> Steam Roulette

**Stop browsing. Start playing.**

Pick a random game from any Steam player's library — filter by genre, play mode, and playtime, then spin.

</div>

---

## Stack

- **Backend** — Python, Flask, Gunicorn, Steam Web API
- **Frontend** — React, TypeScript, Vite
- **Serving** — nginx (container static files), Gunicorn (WSGI), external nginx (reverse proxy)
- **Containerisation** — Docker, Docker Compose
- **Orchestration** — Kubernetes (k3s), Helm
- **CI/CD** — GitHub Actions (lint + test + build) -> GHCR

## Project Structure

```
steam-roulette/
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
├── nginx.conf                          # external reverse proxy config
├── .github/
│   └── workflows/
│       └── deploy.yml                  # CI/CD pipeline
├── systemd/
│   ├── steam-roulette-backend.service  # port-forward systemd service
│   └── steam-roulette-frontend.service
├── helm/
│   └── steam-roulette/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── _helpers.tpl
│           ├── secret.yaml
│           ├── backend-deployment.yaml
│           ├── backend-service.yaml
│           ├── frontend-deployment.yaml
│           ├── frontend-service.yaml
│           └── ingress.yaml
├── backend/
│   ├── .dockerignore
│   ├── Dockerfile
│   ├── app.py
│   ├── gunicorn.conf.py
│   ├── requirements.txt
│   └── tests/
│       └── test_app.py
└── frontend/
    ├── .dockerignore
    ├── Dockerfile
    ├── index.html
    ├── nginx.conf                      # container nginx (static files + SPA fallback)
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx
        ├── index.css
        └── main.tsx
```

---

## Quick Start (Docker)

**1. Get a Steam API key** — register for free at https://steamcommunity.com/dev/apikey

**2. Create your `.env` file:**
```bash
cp .env.example .env
# then edit .env and paste your key
```

**3. Build and run:**
```bash
docker compose up --build
```

Open **http://localhost:8080**

---

## Manual Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
export STEAM_API_KEY="your_key_here"
gunicorn --config gunicorn.conf.py app:app
```

Runs at **http://localhost:5000**

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** — Vite proxies `/api` requests to the backend automatically.

---

## Production — k3s + Helm

### Prerequisites

- k3s cluster up and reachable
- `kubectl` and `helm` v3 installed locally
- External nginx proxy with access to the k3s node IP
- GitHub repo with Actions enabled (images pushed to GHCR)

### 1. GitHub Actions secrets

The pipeline only needs one secret for GHCR. Go to **Settings -> Secrets and variables -> Actions**:

| Secret | Value |
|---|---|
| `GITHUB_TOKEN` | Provided automatically by GitHub — no action needed |

Your `STEAM_API_KEY` is managed as a Kubernetes secret directly on the cluster — never stored in GitHub or the repo.

### 2. Update `values.yaml`

```yaml
image:
  repository: yourname/steam-roulette
```

NodePorts default to `30082` (frontend) and `30503` (backend). Change if those conflict with existing deployments.

### 3. Create the Steam API key secret

```bash
kubectl create secret generic steam-roulette-secret \
  --from-literal=STEAM_API_KEY=your_key_here \
  --namespace steam-roulette \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 4. Deploy with Helm

```bash
kubectl create namespace steam-roulette --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install steam-roulette ./helm/steam-roulette \
  --namespace steam-roulette \
  --set backend.image.tag=sha-abc1234 \
  --set frontend.image.tag=sha-abc1234 \
  --wait
```

The SHA tag is shown in the GitHub Actions job summary after a successful build.

### 5. Configure external nginx

Edit `nginx.conf` — replace the two placeholders and install:

```bash
sudo cp nginx.conf /etc/nginx/sites-available/steam-roulette
sudo ln -s /etc/nginx/sites-available/steam-roulette /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Run `certbot --nginx -d yourdomain.com` to provision TLS.

### 6. Port-forward systemd services (optional)

If your nginx and k3s run on different machines:

```bash
sudo cp systemd/steam-roulette-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now steam-roulette-frontend steam-roulette-backend
```

---

## CI/CD Pipeline

Every push and pull request to `main` runs `.github/workflows/deploy.yml` with four jobs:

**1. Lint & Test — Backend**
- `flake8` on `app.py` and `tests/`
- `pytest` with coverage — minimum 60% enforced

**2. Lint — Frontend (TypeScript)**
- `npm ci` then `tsc --noEmit`

**3. Lint — Helm Chart**
- `helm lint` + `helm template --debug` dry-run

**4. Build & Push Images** *(push to `main` only)*
- Builds both images via Buildx with layer caching
- Pushes to GHCR tagged as `sha-<commit>` and `latest`
- Writes a summary to the Actions UI

Pull requests run all lint jobs but do not push images.

---

## How It Works

1. User pastes a Steam profile URL (e.g. `steamcommunity.com/id/gaben`)
2. Optional filters are selected — play mode, genre, playtime range
3. Frontend POSTs to `/api/random-game` with the URL and active filters
4. Backend resolves the vanity URL to a Steam64 ID
5. Fetches the player's full game library
6. Applies playtime filters locally (no API call needed)
7. Checks up to 20 random candidates against the Steam Store API for genre/category metadata
8. Fetches achievement stats for the chosen game
9. Returns the game with full metadata and logs the spin to stdout

### Filters

| Filter | Logic | Options |
|---|---|---|
| Play mode | OR — any selected mode must match | Single-player, Multiplayer, Co-op, Online Co-op, Local Multi, Local Co-op, PvP, MMO |
| Genre | AND — all selected genres must match | Action, Adventure, Casual, Early Access, Free to Play, Indie, Massively Multiplayer, RPG, Racing, Simulation, Sports, Strategy |
| Playtime | Preset ranges | Any, Unplayed, <1h, 1-10h, 10-50h, 50h+ |

### API Endpoint

**POST** `/api/random-game`

Request:
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

Response:
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

### Logging

All API calls are logged as structured JSON to stdout. Health checks are excluded. View live:

```bash
# All logs
kubectl logs -f deployment/steam-roulette-backend -n steam-roulette

# Spins only
kubectl logs deployment/steam-roulette-backend -n steam-roulette | grep '"event": "spin"'

# Pretty-printed
kubectl logs -f deployment/steam-roulette-backend -n steam-roulette | grep -v Werkzeug | jq .
```

---

## Useful Commands

```bash
# Check pod status
kubectl get pods -n steam-roulette

# Restart both deployments
kubectl rollout restart deployment/steam-roulette-frontend deployment/steam-roulette-backend -n steam-roulette

# Tail backend logs
kubectl logs -f deployment/steam-roulette-backend -n steam-roulette

# Rotate Steam API key
kubectl create secret generic steam-roulette-secret \
  --from-literal=STEAM_API_KEY=new_key_here \
  --namespace steam-roulette \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deployment/steam-roulette-backend -n steam-roulette

# Lint the Helm chart
helm lint ./helm/steam-roulette

# Uninstall
helm uninstall steam-roulette -n steam-roulette
```

---

## Notes

- The Steam library must be **public**: Steam -> Settings -> Privacy -> Game Details -> Public
- Accepts vanity URLs (`/id/name`), profile URLs (`/profiles/76561...`), and raw Steam64 IDs
- Achievement data respects the player's privacy settings — if game details are private the badge won't appear
- Not affiliated with Valve or Steam
