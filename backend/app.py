from flask import Flask, jsonify, request
from flask_cors import CORS
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, REGISTRY
from prometheus_client.core import GaugeMetricFamily
from collections import deque
import requests, random, re, os, logging, time, json, threading
from functools import lru_cache

app = Flask(__name__)
CORS(app)
STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "")

# Prometheus metrics
metrics = PrometheusMetrics(app, path="/metrics", group_by="endpoint")
metrics.info("steam_roulette_info", "Steam Roulette backend", version="1.0.0")

METRICS_TOKEN = os.environ.get("METRICS_TOKEN", "")


def check_metrics_token():
    if not METRICS_TOKEN:
        return jsonify({"error": "Metrics token not configured"}), 503
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {METRICS_TOKEN}":
        return jsonify({"error": "Unauthorized"}), 401
    return None


# Custom Prometheus metrics
spins_total = Counter(
    "steam_roulette_spins_total",
    "Total number of successful game spins",
    ["player", "game"],
)
spin_duration = Histogram(
    "steam_roulette_spin_duration_seconds",
    "Time spent processing a spin request",
)
filter_no_match = Counter(
    "steam_roulette_filter_no_match_total",
    "Spins that returned no result due to filters",
    ["reason"],
)
library_size = Histogram(
    "steam_roulette_library_size",
    "Number of games in the player library",
    buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000],
)

# In-memory ring buffer of the 10 most recent spins
# deque is thread-safe for append/popleft
recent_spins = deque(maxlen=10)
recent_spins_lock = threading.Lock()

class RecentSpinsCollector:
    """Custom Prometheus collector that exposes recent spins as a gauge."""

    def describe(self):
        yield GaugeMetricFamily(
            "steam_roulette_recent_spin",
            "Recent game spins with player and game labels",
        )

    def collect(self):
        g = GaugeMetricFamily(
            "steam_roulette_recent_spin",
            "Recent game spins (position = recency, 1 = most recent)",
            labels=["position", "player", "game", "appid", "ts"],
        )
        with recent_spins_lock:
            spins = list(recent_spins)
        for i, spin in enumerate(spins, start=1):
            g.add_metric(
                [str(i), spin["player"], spin["game"], str(spin["appid"]), spin["ts"]],
                i,
            )
        yield g


REGISTRY.register(RecentSpinsCollector())


# Structured JSON logger
logger = logging.getLogger("steam-roulette")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log(event, **kwargs):
    logger.info(json.dumps({"event": event, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **kwargs}))


CATEGORY_IDS = {
    "singleplayer":      2,
    "multiplayer":       1,
    "co_op":             9,
    "online_co_op":     38,
    "local_multiplayer": 7,
    "local_co_op":      37,
    "pvp":              49,
    "mmo":              20,
}


def resolve_steam_id(profile_url):
    profile_url = profile_url.strip().rstrip("/")
    if re.match(r"^\d{17}$", profile_url):
        return profile_url
    m = re.search(r"steamcommunity\.com/profiles/(\d{17})", profile_url)
    if m:
        return m.group(1)
    m = re.search(r"steamcommunity\.com/id/([^/]+)", profile_url)
    if m:
        r = requests.get(
            "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/",
            params={"key": STEAM_API_KEY, "vanityurl": m.group(1)},
            timeout=10,
        )
        d = r.json().get("response", {})
        if d.get("success") == 1:
            return d["steamid"]
    return None


def get_owned_games(steam_id):
    r = requests.get(
        "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
        params={
            "key": STEAM_API_KEY,
            "steamid": steam_id,
            "include_appinfo": True,
            "include_played_free_games": True,
        },
        timeout=15,
    )
    return r.json().get("response", {}).get("games", [])


def get_player_summary(steam_id):
    r = requests.get(
        "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
        params={"key": STEAM_API_KEY, "steamids": steam_id},
        timeout=10,
    )
    players = r.json().get("response", {}).get("players", [])
    return players[0] if players else {}


@lru_cache(maxsize=512)
def get_app_details(appid):
    try:
        r = requests.get(
            "https://store.steampowered.com/api/appdetails",
            params={"appids": appid, "filters": "basic,genres,categories"},
            timeout=8,
        )
        entry = r.json().get(str(appid), {})
        if entry.get("success"):
            return entry.get("data", {})
    except Exception:
        pass
    return None


def get_achievements(steam_id, appid):
    try:
        r = requests.get(
            "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/",
            params={"key": STEAM_API_KEY, "steamid": steam_id, "appid": appid},
            timeout=8,
        )
        data = r.json().get("playerstats", {})
        if not data.get("success"):
            return None, None
        achievements = data.get("achievements", [])
        if not achievements:
            return None, None
        total = len(achievements)
        unlocked = sum(1 for a in achievements if a.get("achieved") == 1)
        return unlocked, total
    except Exception:
        return None, None


def passes_playtime(game, filters):
    playtime_minutes = game.get("playtime_forever", 0)
    playtime_hours = playtime_minutes / 60.0
    if filters.get("unplayed_only"):
        return playtime_minutes == 0
    pt_min = int(filters.get("playtime_min", 0))
    pt_max = int(filters.get("playtime_max", -1))
    if pt_min > 0 and playtime_hours < pt_min:
        return False
    if pt_max >= 0 and playtime_hours > pt_max:
        return False
    return True


def passes_content(appid, filters):
    modes = filters.get("modes", [])
    genres = filters.get("genres", [])
    if not modes and not genres:
        return True
    details = get_app_details(appid)
    if details is None:
        return True
    if modes:
        cat_ids = {c["id"] for c in details.get("categories", [])}
        if not any(CATEGORY_IDS.get(m) in cat_ids for m in modes):
            return False
    if genres:
        game_genres = {g["description"].lower() for g in details.get("genres", [])}
        if not all(g.lower() in game_genres for g in genres):
            return False
    return True


@app.after_request
def log_request(response):
    if request.path == "/api/health":
        return response
    duration_ms = round((time.time() - request.environ.get("_start_time", time.time())) * 1000)
    log(
        "request",
        method=request.method,
        path=request.path,
        status=response.status_code,
        ip=request.headers.get("X-Forwarded-For", request.remote_addr),
        duration_ms=duration_ms,
    )
    return response


@app.before_request
def mark_start_time():
    request.environ["_start_time"] = time.time()


@app.before_request
def protect_metrics():
    if request.path == "/metrics":
        return check_metrics_token()


@app.route("/api/random-game", methods=["POST"])
def random_game():
    if not STEAM_API_KEY:
        return jsonify({"error": "Steam API key not configured on server."}), 500

    body = request.get_json(silent=True) or {}
    profile_url = body.get("profile_url", "").strip()
    filters = body.get("filters", {})

    if not profile_url:
        return jsonify({"error": "Please provide a Steam profile URL."}), 400

    steam_id = resolve_steam_id(profile_url)
    if not steam_id:
        log("resolve_failed", profile_url=profile_url)
        return jsonify({"error": "Could not resolve Steam ID. Make sure the profile is public."}), 400

    try:
        games = get_owned_games(steam_id)
    except Exception as e:
        log("library_fetch_failed", steam_id=steam_id, error=str(e))
        return jsonify({"error": f"Failed to fetch games: {e}"}), 502

    if not games:
        log("empty_library", steam_id=steam_id)
        return jsonify({"error": "No games found. Library may be private or empty."}), 404

    pool = [g for g in games if passes_playtime(g, filters)]
    if not pool:
        log("playtime_filter_no_match", steam_id=steam_id, filters=filters)
        filter_no_match.labels(reason="playtime").inc()
        return jsonify({"error": "No games match your playtime filter."}), 404

    chosen = None
    has_content_filter = bool(filters.get("modes") or filters.get("genres"))

    if has_content_filter:
        random.shuffle(pool)
        for g in pool[:20]:
            if passes_content(g["appid"], filters):
                chosen = g
                break
        if chosen is None:
            log("content_filter_no_match", steam_id=steam_id, filters=filters)
            filter_no_match.labels(reason="content").inc()
            return jsonify({"error": "No matching game found in 20 tries. Try relaxing your filters."}), 404
    else:
        chosen = random.choice(pool)

    appid = chosen["appid"]
    player = get_player_summary(steam_id)
    details = get_app_details(appid) or {}
    achievements_unlocked, achievements_total = get_achievements(steam_id, appid)

    player_name = player.get("personaname", "Unknown")
    game_name = chosen.get("name", "Unknown")
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    log(
        "spin",
        steam_id=steam_id,
        player=player_name,
        game=game_name,
        appid=appid,
        total_games=len(games),
        filtered_pool=len(pool),
        filters={
            "modes": filters.get("modes", []),
            "genres": filters.get("genres", []),
            "unplayed_only": filters.get("unplayed_only", False),
            "playtime_min": filters.get("playtime_min", 0),
            "playtime_max": filters.get("playtime_max", -1),
        },
    )

    # Prometheus
    spins_total.labels(player=player_name, game=game_name).inc()
    library_size.observe(len(games))
    spin_duration.observe(time.time() - request.environ.get("_start_time", time.time()))

    # Recent spins buffer
    spin_entry = {
        "ts": ts,
        "player": player_name,
        "player_avatar": player.get("avatarfull", ""),
        "player_url": player.get("profileurl", ""),
        "game": game_name,
        "appid": appid,
        "header_image": f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg",
        "store_url": f"https://store.steampowered.com/app/{appid}",
        "genres": [g["description"] for g in details.get("genres", [])],
    }
    with recent_spins_lock:
        recent_spins.appendleft(spin_entry)

    return jsonify({
        "game": {
            "appid": appid,
            "name": game_name,
            "playtime_forever": chosen.get("playtime_forever", 0),
            "header_image": f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg",
            "store_url": f"https://store.steampowered.com/app/{appid}",
            "genres": [g["description"] for g in details.get("genres", [])],
            "categories": [c["description"] for c in details.get("categories", [])],
            "achievements_unlocked": achievements_unlocked,
            "achievements_total": achievements_total,
        },
        "player": {
            "name": player_name,
            "avatar": player.get("avatarfull", ""),
            "profile_url": player.get("profileurl", ""),
        },
        "total_games": len(games),
        "filtered_pool": len(pool),
    })



@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})