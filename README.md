<img src="assets/logo.svg" alt="Steam Roulette" width="80" height="86" />

# Steam Roulette

**Stop browsing. Start playing.**

Pick a random game from any Steam player's library — filter by genre, play mode, and playtime, then spin.

</div>

---

## Stack

- **Backend** — Python, Flask, Steam Web API
- **Frontend** — React, TypeScript, Vite
- **Serving** — nginx (production), Vite dev server (development)
- **Containerisation** — Docker, Docker Compose

## Project Structure

```
steam-roulette/
├── .env.example
├── .gitignore
├── docker-compose.yml
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

## How It Works

1. User pastes a Steam profile URL (e.g. `steamcommunity.com/id/gaben`)
2. Optional filters are selected — play mode, genre, playtime range
3. Frontend POSTs to `/api/random-game` with the URL and active filters
4. Backend resolves the vanity URL → Steam64 ID
5. Fetches the player's full game library
6. Applies playtime filters locally, then checks up to 20 random candidates against the Steam Store API for genre/category metadata
7. Returns a matching game with full metadata — genres, categories, header image, store link

### Filters

| Filter | Logic | Options |
|---|---|---|
| Play mode | OR — any selected mode must match | Single-player, Multiplayer, Co-op, Local Multi, Local Co-op, PvP, MMO |
| Genre | AND — all selected genres must match | Action, Adventure, Casual, Indie, RPG, Racing, Simulation, Sports, Strategy, and more |
| Playtime | Preset ranges | Any, Unplayed, <1h, 1–10h, 10–50h, 50h+ |

Genre/category metadata is fetched from the Steam Store API and cached in memory, so repeated spins on the same library get faster over time.

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
    "categories": ["Multi-player", "Co-op"]
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

## Notes

- The Steam library must be **public**: Steam → Settings → Privacy → Game Details → Public
- Accepts vanity URLs (`/id/name`), profile URLs (`/profiles/76561...`), and raw Steam64 IDs
- With genre/mode filters active, each spin may take 1–3 seconds longer on the first roll (Steam Store API calls). Subsequent spins on already-checked games are instant thanks to in-memory caching
- Not affiliated with Valve or Steam