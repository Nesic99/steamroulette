from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import random
import re
import os
from functools import lru_cache

app = Flask(__name__)
CORS(app)

STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "")


def resolve_steam_id(profile_url: str) -> str | None:
    profile_url = profile_url.strip().rstrip("/")
    if re.match(r"^\d{17}$", profile_url):
        return profile_url
    profiles_match = re.search(r"steamcommunity\.com/profiles/(\d{17})", profile_url)
    if profiles_match:
        return profiles_match.group(1)
    id_match = re.search(r"steamcommunity\.com/id/([^/]+)", profile_url)
    if id_match:
        vanity = id_match.group(1)
        resp = requests.get(
            "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/",
            params={"key": STEAM_API_KEY, "vanityurl": vanity},
            timeout=10,
        )
        data = resp.json()
        if data.get("response", {}).get("success") == 1:
            return data["response"]["steamid"]
    return None


def get_owned_games(steam_id: str) -> list:
    resp = requests.get(
        "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
        params={
            "key": STEAM_API_KEY,
            "steamid": steam_id,
            "include_appinfo": True,
            "include_played_free_games": True,
        },
        timeout=15,
    )
    return resp.json().get("response", {}).get("games", [])


def get_player_summary(steam_id: str) -> dict:
    resp = requests.get(
        "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
        params={"key": STEAM_API_KEY, "steamids": steam_id},
        timeout=10,
    )
    players = resp.json().get("response", {}).get("players", [])
    return players[0] if players else {}


@lru_cache(maxsize=512)
def get_store_details(appid: int) -> dict:
    """Fetch genre/category metadata from the Steam store API. Cached per appid."""
    try:
        resp = requests.get(
            "https://store.steampowered.com/api/appdetails",
            params={"appids": appid, "filters": "categories,genres"},
            timeout=8,
        )
        data = resp.json().get(str(appid), {})
        if not data.get("success"):
            return {}
        details = data.get("data", {})
        raw_categories = details.get("categories", [])
        category_ids = {int(c.get("id", -1)) for c in raw_categories}
        genres = [g["description"].lower() for g in details.get("genres", [])]
        categories = [c["description"].lower() for c in raw_categories]

        return {
            "genres": genres,
            "categories": categories,
            "is_singleplayer": 2 in category_ids,
            "is_multiplayer": bool(category_ids & {1, 36}),
            "is_co_op": bool(category_ids & {9, 37, 38}),
        }
    except Exception:
        return {}


def matches_filters(store_data: dict, filters: dict) -> bool:
    if not store_data:
        return False

    mode = filters.get("mode", "any")
    if mode == "singleplayer" and not store_data.get("is_singleplayer"):
        return False
    if mode == "multiplayer" and not store_data.get("is_multiplayer"):
        return False
    if mode == "co_op" and not store_data.get("is_co_op"):
        return False

    genre_filter = filters.get("genre", "").strip().lower()
    if genre_filter and genre_filter != "any":
        wanted = {g.strip() for g in genre_filter.split(",") if g.strip()}
        game_genres = set(store_data.get("genres", []))
        if not wanted.intersection(game_genres):
            return False

    return True


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
        return jsonify({"error": "Could not resolve Steam ID from that URL. Make sure the profile is public."}), 400

    try:
        games = get_owned_games(steam_id)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch games: {str(e)}"}), 502

    if not games:
        return jsonify({"error": "No games found. The library may be private or empty."}), 404

    has_filters = bool(
        (filters.get("mode") and filters.get("mode") != "any") or
        (filters.get("genre") and filters.get("genre") != "any")
    )

    game = None
    store_data = {}

    if not has_filters:
        game = random.choice(games)
        store_data = get_store_details(game["appid"])
    else:
        candidates = random.sample(games, min(len(games), 40))
        for candidate in candidates:
            sd = get_store_details(candidate["appid"])
            if matches_filters(sd, filters):
                game = candidate
                store_data = sd
                break

        if game is None:
            return jsonify({
                "error": "No games matched your filters. Try relaxing them."
            }), 404

    appid = game["appid"]
    player = get_player_summary(steam_id)

    return jsonify({
        "game": {
            "appid": appid,
            "name": game.get("name", "Unknown Game"),
            "playtime_forever": game.get("playtime_forever", 0),
            "header_image": f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg",
            "store_url": f"https://store.steampowered.com/app/{appid}",
            "genres": store_data.get("genres", []),
            "categories": store_data.get("categories", []),
            "is_singleplayer": store_data.get("is_singleplayer", False),
            "is_multiplayer": store_data.get("is_multiplayer", False),
            "is_co_op": store_data.get("is_co_op", False),
        },
        "player": {
            "name": player.get("personaname", "Unknown"),
            "avatar": player.get("avatarfull", ""),
            "profile_url": player.get("profileurl", ""),
        },
        "total_games": len(games),
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
