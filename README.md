# <img src="assets/logo.svg" alt="" width="36" height="39" valign="middle" /> Steam Roulette

**Stop browsing. Start playing.**

Pick a random game from any Steam player's library — filter by genre, play mode, and playtime, then spin.

</div>

---

## Stack

- **Backend** — Python, Flask, Steam Web API
- **Frontend** — React, TypeScript, Vite
- **Serving** — nginx (production), Vite dev server (development)
- **Containerisation** — Docker, Docker Compose
- **Orchestration** — Kubernetes (k3s), Helm
- **CI/CD** — GitHub Actions → GHCR → k3s

## Project Structure

```
steam-roulette/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── .github/
│   └── workflows/
│       └── deploy.yml        # CI/CD pipeline
├── helm/
│   └── steam-roulette/       # Helm chart
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── _helpers.tpl
│           ├── namespace.yaml
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
│   └── requirements.txt
└── frontend/
    ├── .dockerignore
    ├── Dockerfile
    ├── index.html
    ├── nginx.conf
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

The easiest way to run the full stack locally.

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
export STEAM_API_KEY="your_key_here"   # Windows: set STEAM_API_KEY=your_key_here
python app.py
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
- GitHub repo with Actions enabled (images are pushed to GHCR — no separate registry needed)

### 1. Add GitHub Actions secrets

Go to **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `KUBECONFIG` | Full contents of your k3s config file (`/etc/rancher/k3s/k3s.yaml` on the node — replace `127.0.0.1` with the node's actual IP) |
| `STEAM_API_KEY` | Your Steam Web API key |

The pipeline creates and updates the in-cluster Kubernetes secret automatically — the key never touches your repository.

### 2. Update `values.yaml`

Two fields must be set before the first deploy:

```yaml
image:
  repository: yourname/steam-roulette   # your GitHub username or org

ingress:
  host: steam-roulette.yourdomain.com   # your domain or local hostname
```

k3s ships with **Traefik** as the default ingress controller, which `values.yaml` targets out of the box. If you're using `ingress-nginx`, change `ingress.className` to `nginx`.

### 3. First manual deploy

```bash
# Create namespace
kubectl create namespace steam-roulette

# Create the secret
kubectl create secret generic steam-roulette-secret \
  --from-literal=STEAM_API_KEY=your_key_here \
  --namespace steam-roulette

# Install the chart
helm upgrade --install steam-roulette ./helm/steam-roulette \
  --namespace steam-roulette \
  --set image.repository=yourname/steam-roulette \
  --wait
```

### TLS with cert-manager (optional)

If cert-manager is installed on the cluster:

```yaml
# values.yaml
ingress:
  tls:
    enabled: true
    secretName: steam-roulette-tls
```

The ingress template will automatically add the `cert-manager.io/cluster-issuer: letsencrypt-prod` annotation.

---

## CI/CD Pipeline

Every push to `main` runs `.github/workflows/deploy.yml`:

1. **Build** — builds `backend` and `frontend` Docker images, pushes to GHCR tagged as `sha-<commit>` and `latest`
2. **Secret** — creates/updates `steam-roulette-secret` in the cluster from the `STEAM_API_KEY` GitHub secret
3. **Deploy** — runs `helm upgrade --install` with the exact SHA image tags, waits for both rollouts to complete

Pull requests only run the build step — no images are pushed and nothing is deployed.

---

## How It Works

1. User pastes a Steam profile URL (e.g. `steamcommunity.com/id/gaben`)
2. Optional filters are selected — play mode, genre, playtime range
3. Frontend POSTs to `/api/random-game` with the URL and active filters
4. Backend resolves the vanity URL → Steam64 ID
5. Fetches the player's full game library
6. Applies playtime filters locally (no API call needed), then checks up to 20 random candidates against the Steam Store API for genre/category metadata
7. Fetches achievement stats for the chosen game
8. Returns the game with full metadata — genres, categories, achievements, header image, store link

### Filters

| Filter | Logic | Options |
|---|---|---|
| Play mode | OR — any selected mode must match | Single-player, Multiplayer, Co-op, Online Co-op, Local Multi, Local Co-op, PvP, MMO |
| Genre | AND — all selected genres must match | Action, Adventure, Casual, Early Access, Free to Play, Indie, Massively Multiplayer, RPG, Racing, Simulation, Sports, Strategy |
| Playtime | Preset ranges | Any, Unplayed, <1h, 1–10h, 10–50h, 50h+ |

Genre/category metadata is fetched from the Steam Store API and cached in memory — repeated spins on an already-checked game are instant.

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

---

## Useful Commands

```bash
# Check pod status
kubectl get pods -n steam-roulette

# Tail backend logs
kubectl logs -f deployment/steam-roulette-backend -n steam-roulette

# Tail frontend logs
kubectl logs -f deployment/steam-roulette-frontend -n steam-roulette

# Lint the Helm chart
helm lint ./helm/steam-roulette

# Uninstall
helm uninstall steam-roulette -n steam-roulette
```

---

## Notes

- The Steam library must be **public**: Steam → Settings → Privacy → Game Details → Public
- Accepts vanity URLs (`/id/name`), profile URLs (`/profiles/76561...`), and raw Steam64 IDs
- Achievement data respects the player's privacy settings — if game details are private the achievement badge simply won't appear
- Not affiliated with Valve or Steam