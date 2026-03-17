import { useState, useRef } from "react";
import "./index.css";

interface Game {
  appid: number;
  name: string;
  playtime_forever: number;
  header_image: string;
  store_url: string;
  genres: string[];
  categories: string[];
  is_singleplayer: boolean;
  is_multiplayer: boolean;
  is_co_op: boolean;
}

interface Player {
  name: string;
  avatar: string;
  profile_url: string;
}

interface ApiResponse {
  game: Game;
  player: Player;
  total_games: number;
}

interface Filters {
  mode: "any" | "singleplayer" | "multiplayer" | "co_op";
  genre: string;
}

// In Docker, nginx proxies /api → backend. In dev, Vite proxy does the same.
const API_BASE = "";

const GENRES = [
  "any", "action", "adventure", "rpg", "strategy", "simulation",
  "sports", "racing", "puzzle", "horror", "indie", "casual",
];

const MODE_LABELS: Record<string, string> = {
  any: "Any",
  singleplayer: "Single-player",
  multiplayer: "Multiplayer",
  co_op: "Co-op",
};

function formatPlaytime(minutes: number): string {
  if (minutes === 0) return "Never played";
  if (minutes < 60) return `${minutes}m played`;
  return `${Math.floor(minutes / 60).toLocaleString()}h played`;
}

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export default function App() {
  const [url, setUrl] = useState("");
  const [filters, setFilters] = useState<Filters>({ mode: "any", genre: "any" });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ApiResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rolling, setRolling] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const fetchGame = async (profileUrl: string, activeFilters: Filters) => {
    setLoading(true);
    setError(null);
    setRolling(true);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/random-game`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_url: profileUrl, filters: activeFilters }),
      });

      const data = await res.json();

      if (!res.ok || "error" in data) {
        setError(data.error ?? "Something went wrong.");
        setRolling(false);
        setLoading(false);
        return;
      }

      setTimeout(() => {
        setResult(data as ApiResponse);
        setRolling(false);
        setLoading(false);
      }, 700);
    } catch {
      setError("Could not connect to the server. Is the backend running?");
      setRolling(false);
      setLoading(false);
    }
  };

  const handleSubmit = () => {
    if (!url.trim()) { inputRef.current?.focus(); return; }
    fetchGame(url.trim(), filters);
  };

  const handleReroll = () => {
    if (url.trim()) fetchGame(url.trim(), filters);
  };

  const setMode = (mode: Filters["mode"]) => setFilters(f => ({ ...f, mode }));
  const setGenre = (genre: string) => setFilters(f => ({ ...f, genre }));

  return (
    <div className="app">
      <div className="noise" />

      <header className="header">
        <div className="logo-mark">
          <svg xmlns="http://www.w3.org/2000/svg" width="72" height="77" viewBox="0 0 140 150" aria-label="Dice logo">
            <use href="#dice-logo" />
          </svg>
        </div>
        <h1 className="title">STEAM<span>ROULETTE</span></h1>
        <p className="subtitle">Stop browsing. Start playing.</p>
      </header>

      <main className="main">
        {/* URL input */}
        <div className="input-section">
          <div className="input-wrapper">
            <input
              ref={inputRef}
              type="text"
              className="url-input"
              placeholder="steamcommunity.com/id/yourname"
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSubmit()}
            />
            <button
              className={`spin-btn ${loading ? "loading" : ""}`}
              onClick={handleSubmit}
              disabled={loading}
            >
              {loading ? <span className="spinner" /> : "SPIN"}
            </button>
          </div>
          <p className="hint">Paste your Steam profile URL or vanity name</p>
        </div>

        {/* Filters */}
        <div className="filters-section">
          <div className="filter-group">
            <label className="filter-label">MODE</label>
            <div className="pill-row">
              {(["any", "singleplayer", "multiplayer", "co_op"] as const).map(m => (
                <button
                  key={m}
                  className={`pill ${filters.mode === m ? "active" : ""}`}
                  onClick={() => setMode(m)}
                >
                  {MODE_LABELS[m]}
                </button>
              ))}
            </div>
          </div>

          <div className="filter-group">
            <label className="filter-label">GENRE</label>
            <div className="pill-row">
              {GENRES.map(g => (
                <button
                  key={g}
                  className={`pill ${filters.genre === g ? "active" : ""}`}
                  onClick={() => setGenre(g)}
                >
                  {g === "any" ? "Any" : capitalize(g)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {error && (
          <div className="error-card">
            <span className="error-icon">⚠</span>
            {error}
          </div>
        )}

        {rolling && !error && (
          <div className="rolling-state">
            <div className="roulette-animation">
              {["🎮", "🕹️", "👾", "🎯", "🏆", "⚔️"].map((emoji, i) => (
                <span key={i} style={{ animationDelay: `${i * 0.1}s` }}>{emoji}</span>
              ))}
            </div>
            <p>Raiding your library...</p>
          </div>
        )}

        {result && !rolling && (
          <div className="result-section">
            <div className="player-bar">
              <img src={result.player.avatar} alt={result.player.name} className="player-avatar" />
              <div className="player-info">
                <span className="player-name">{result.player.name}</span>
                <span className="player-games">{result.total_games.toLocaleString()} games in library</span>
              </div>
            </div>

            <div className="game-card">
              <div className="game-image-wrapper">
                <img
                  src={result.game.header_image}
                  alt={result.game.name}
                  className="game-image"
                  onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
                <div className="game-image-overlay" />
              </div>

              <div className="game-info">
                <div className="game-tag">YOUR GAME FOR TODAY</div>
                <h2 className="game-name">{result.game.name}</h2>

                {/* Tags row */}
                <div className="tag-row">
                  {result.game.is_singleplayer && <span className="tag">Single-player</span>}
                  {result.game.is_multiplayer && <span className="tag">Multiplayer</span>}
                  {result.game.is_co_op && <span className="tag">Co-op</span>}
                  {result.game.genres.slice(0, 3).map(g => (
                    <span key={g} className="tag genre-tag">{capitalize(g)}</span>
                  ))}
                </div>

                <div className="game-meta">
                  <span className="playtime">{formatPlaytime(result.game.playtime_forever)}</span>
                </div>

                <div className="game-actions">
                  <a
                    href={result.game.store_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="store-btn"
                  >
                    View on Steam ↗
                  </a>
                  <button className="reroll-btn" onClick={handleReroll}>
                    Reroll ↺
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="footer">
        Not affiliated with Valve or Steam. Requires a public Steam library.
      </footer>
    </div>
  );
}
