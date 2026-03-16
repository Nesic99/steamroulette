# 🎲 Steam Roulette

Pick a random game from any Steam player's library — just paste their profile URL.

## Setup

### 1. Get a Steam API Key
Go to https://steamcommunity.com/dev/apikey and register a key (free, just needs a Steam account).

### 2. Backend (Flask)

```bash
cd backend
pip install -r requirements.txt
export STEAM_API_KEY="your_key_here"   # Windows: set STEAM_API_KEY=your_key_here
python app.py
```

The API will run at **http://localhost:5000**

### 3. Frontend (Vite + React + TypeScript)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

---

## How It Works

1. User pastes a Steam profile URL (e.g. `steamcommunity.com/id/gaben`)
2. Frontend POSTs to `/api/random-game`
3. Backend resolves the vanity URL → Steam64 ID via Steam API
4. Fetches the player's full game library
5. Picks a random game and returns it with metadata

### API Endpoint

**POST** `/api/random-game`
```json
{ "profile_url": "https://steamcommunity.com/id/username" }
```

**Response:**
```json
{
  "game": {
    "appid": 570,
    "name": "Dota 2",
    "playtime_forever": 1234,
    "header_image": "https://...",
    "store_url": "https://store.steampowered.com/app/570"
  },
  "player": {
    "name": "PlayerName",
    "avatar": "https://...",
    "profile_url": "https://..."
  },
  "total_games": 312
}
```

## Notes
- The Steam library must be **public** (Steam Privacy Settings → Game Details → Public)
- Works with vanity URLs (`/id/name`), direct profile URLs (`/profiles/76561...`), and raw Steam64 IDs
