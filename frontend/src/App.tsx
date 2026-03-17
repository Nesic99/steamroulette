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
  achievements_unlocked: number | null;
  achievements_total: number | null;
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
  filtered_pool: number;
}

interface Filters {
  modes: string[];
  genres: string[];
  unplayed_only: boolean;
  playtime_min: number;
  playtime_max: number;
}

const API_BASE = "";

const MODE_OPTIONS = [
  { key: "singleplayer",      label: "Single-player", icon: "👤" },
  { key: "multiplayer",       label: "Multiplayer",    icon: "👥" },
  { key: "co_op",             label: "Co-op",          icon: "🤝" },
  { key: "online_co_op",      label: "Online Co-op",   icon: "🌐" },
  { key: "local_multiplayer", label: "Local Multi",    icon: "🛋️" },
  { key: "local_co_op",       label: "Local Co-op",    icon: "🎮" },
  { key: "pvp",               label: "PvP",            icon: "⚔️" },
  { key: "mmo",               label: "MMO",            icon: "🗺️" },
];

const GENRE_OPTIONS = [
  "Action", "Adventure", "Casual", "Early Access", "Free to Play",
  "Indie", "Massively Multiplayer", "RPG", "Racing", "Simulation",
  "Sports", "Strategy",
];

const PLAYTIME_PRESETS = [
  { label: "Any",     min: 0,  max: -1, unplayed: false },
  { label: "Unplayed",min: 0,  max: 0,  unplayed: true  },
  { label: "< 1h",   min: 0,  max: 1,  unplayed: false },
  { label: "1–10h",  min: 1,  max: 10, unplayed: false },
  { label: "10–50h", min: 10, max: 50, unplayed: false },
  { label: "50h+",   min: 50, max: -1, unplayed: false },
];

function formatPlaytime(minutes: number): string {
  if (minutes === 0) return "Never played";
  if (minutes < 60) return `${minutes}m played`;
  return `${Math.floor(minutes / 60).toLocaleString()}h played`;
}

function Toggle({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button className={`toggle ${active ? "active" : ""}`} onClick={onClick}>
      {children}
    </button>
  );
}

export default function App() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ApiResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rolling, setRolling] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    modes: [], genres: [], unplayed_only: false, playtime_min: 0, playtime_max: -1,
  });
  const inputRef = useRef<HTMLInputElement>(null);

  const activeFilterCount =
    filters.modes.length +
    filters.genres.length +
    (filters.unplayed_only ? 1 : 0) +
    (filters.playtime_min > 0 || filters.playtime_max >= 0 ? 1 : 0);

  function toggleMode(key: string) {
    setFilters(f => ({
      ...f,
      modes: f.modes.includes(key) ? f.modes.filter(m => m !== key) : [...f.modes, key],
    }));
  }

  function toggleGenre(g: string) {
    setFilters(f => ({
      ...f,
      genres: f.genres.includes(g) ? f.genres.filter(x => x !== g) : [...f.genres, g],
    }));
  }

  function applyPlaytimePreset(p: typeof PLAYTIME_PRESETS[0]) {
    setFilters(f => ({
      ...f,
      unplayed_only: p.unplayed,
      playtime_min: p.min,
      playtime_max: p.unplayed ? -1 : p.max,
    }));
  }

  const currentPreset = PLAYTIME_PRESETS.find(p => {
    if (p.unplayed) return filters.unplayed_only;
    return !filters.unplayed_only && p.min === filters.playtime_min && p.max === filters.playtime_max;
  });

  const fetchGame = async (profileUrl: string) => {
    setLoading(true);
    setError(null);
    setRolling(true);

    try {
      const res = await fetch(`${API_BASE}/api/random-game`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_url: profileUrl, filters }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        setError(data.error || "Something went wrong.");
        setLoading(false);
        setRolling(false);
      } else {
        setTimeout(() => {
          setResult(data);
          setRolling(false);
          setLoading(false);
        }, 800);
      }
    } catch {
      setError("Could not connect to the server. Is the backend running?");
      setLoading(false);
      setRolling(false);
    }
  };

  const handleSubmit = () => {
    if (!url.trim()) { inputRef.current?.focus(); return; }
    fetchGame(url.trim());
  };

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

        {/* Filters — always visible */}
        <div className="filters-container">
          <div className="filter-group">
            <div className="filter-group-header">
              <span className="filter-label">Play Mode</span>
              <span className="filter-hint">any that apply</span>
            </div>
            <div className="toggle-grid">
              {MODE_OPTIONS.map(m => (
                <Toggle key={m.key} active={filters.modes.includes(m.key)} onClick={() => toggleMode(m.key)}>
                  {m.icon} {m.label}
                </Toggle>
              ))}
            </div>
          </div>

          <div className="filter-group">
            <div className="filter-group-header">
              <span className="filter-label">Genre</span>
              <span className="filter-hint">all must match</span>
            </div>
            <div className="toggle-grid">
              {GENRE_OPTIONS.map(g => (
                <Toggle key={g} active={filters.genres.includes(g)} onClick={() => toggleGenre(g)}>
                  {g}
                </Toggle>
              ))}
            </div>
          </div>

          <div className="filter-group">
            <div className="filter-group-header">
              <span className="filter-label">Playtime</span>
            </div>
            <div className="toggle-grid">
              {PLAYTIME_PRESETS.map(p => (
                <Toggle
                  key={p.label}
                  active={currentPreset?.label === p.label}
                  onClick={() => applyPlaytimePreset(p)}
                >
                  {p.label}
                </Toggle>
              ))}
            </div>
          </div>

          {activeFilterCount > 0 && (
            <button
              className="reset-btn"
              onClick={() => setFilters({ modes: [], genres: [], unplayed_only: false, playtime_min: 0, playtime_max: -1 })}
            >
              ✕ Clear filters
            </button>
          )}
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
            <p>{activeFilterCount > 0 ? "Searching your library…" : "Raiding your library…"}</p>
          </div>
        )}

        {result && !rolling && (
          <div className="result-section">
            <div className="player-bar">
              <img src={result.player.avatar} alt={result.player.name} className="player-avatar" />
              <div className="player-info">
                <span className="player-name">{result.player.name}</span>
                <span className="player-games">
                  {result.filtered_pool !== result.total_games
                    ? `${result.filtered_pool} of ${result.total_games.toLocaleString()} games match`
                    : `${result.total_games.toLocaleString()} games in library`}
                </span>
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
                <div className="game-tag">Your game for today</div>
                <h2 className="game-name">{result.game.name}</h2>

                <div className="game-tags-row">
                  {result.game.genres.map(g => (
                    <span key={g} className="tag tag-genre">{g}</span>
                  ))}
                  {result.game.categories.slice(0, 4).map(c => (
                    <span key={c} className="tag tag-cat">{c}</span>
                  ))}
                </div>

                <div className="game-meta">
                  <span className="playtime">{formatPlaytime(result.game.playtime_forever)}</span>
                  {result.game.achievements_total !== null && (
                    <span className="achievements">
                      🏆 {result.game.achievements_unlocked} / {result.game.achievements_total} achievements
                    </span>
                  )}
                </div>

                <div className="game-actions">
                  <a href={result.game.store_url} target="_blank" rel="noopener noreferrer" className="store-btn">
                    View on Steam ↗
                  </a>
                  <button className="reroll-btn" onClick={() => url.trim() && fetchGame(url.trim())}>
                    Reroll ↺
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="footer">
        Not affiliated with Valve or Steam · Requires a public library
      </footer>
    </div>
  );
}