"""
Backend unit tests — all Steam API calls are mocked.
No real STEAM_API_KEY is needed.
"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import app, passes_playtime, passes_content, get_achievements, resolve_steam_id


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


MOCK_DETAILS = {
    "categories": [{"id": 2, "description": "Single-player"}, {"id": 1, "description": "Multi-player"}],
    "genres": [{"description": "Action"}, {"description": "RPG"}],
}

MOCK_GAMES = [{"appid": 570, "name": "Dota 2", "playtime_forever": 0}]

MOCK_PLAYER = {
    "personaname": "TestUser",
    "avatarfull": "https://example.com/avatar.jpg",
    "profileurl": "https://steamcommunity.com/id/testuser",
}


# ── Health check ──────────────────────────────────────────────────────────────

def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


# ── resolve_steam_id ──────────────────────────────────────────────────────────

def test_resolve_steam_id_raw():
    assert resolve_steam_id("76561198000000000") == "76561198000000000"

def test_resolve_steam_id_profiles_url():
    result = resolve_steam_id("https://steamcommunity.com/profiles/76561198000000000")
    assert result == "76561198000000000"

def test_resolve_steam_id_vanity_url():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"response": {"success": 1, "steamid": "76561198000000001"}}
    with patch("app.requests.get", return_value=mock_resp):
        result = resolve_steam_id("https://steamcommunity.com/id/someuser")
    assert result == "76561198000000001"

def test_resolve_steam_id_vanity_not_found():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"response": {"success": 42}}
    with patch("app.requests.get", return_value=mock_resp):
        result = resolve_steam_id("https://steamcommunity.com/id/doesnotexist")
    assert result is None

def test_resolve_steam_id_unrecognised():
    assert resolve_steam_id("not-a-url") is None


# ── passes_playtime ───────────────────────────────────────────────────────────

def test_playtime_unplayed_passes_zero():
    assert passes_playtime({"playtime_forever": 0}, {"unplayed_only": True}) is True

def test_playtime_unplayed_rejects_played():
    assert passes_playtime({"playtime_forever": 1}, {"unplayed_only": True}) is False

def test_playtime_min_rejects_under():
    # 30 min = 0.5 h, min=1 h → fail
    assert passes_playtime({"playtime_forever": 30}, {"playtime_min": 1, "playtime_max": -1}) is False

def test_playtime_min_passes_over():
    # 90 min = 1.5 h, min=1 h → pass
    assert passes_playtime({"playtime_forever": 90}, {"playtime_min": 1, "playtime_max": -1}) is True

def test_playtime_max_rejects_over():
    # 120 min = 2 h, max=1 h → fail
    assert passes_playtime({"playtime_forever": 120}, {"playtime_min": 0, "playtime_max": 1}) is False

def test_playtime_max_passes_under():
    # 30 min = 0.5 h, max=1 h → pass
    assert passes_playtime({"playtime_forever": 30}, {"playtime_min": 0, "playtime_max": 1}) is True

def test_playtime_within_range():
    # 300 min = 5 h, range 1–10 h → pass
    assert passes_playtime({"playtime_forever": 300}, {"playtime_min": 1, "playtime_max": 10}) is True

def test_playtime_no_filters():
    assert passes_playtime({"playtime_forever": 99999}, {}) is True

def test_playtime_missing_key_defaults_zero():
    assert passes_playtime({}, {"unplayed_only": True}) is True


# ── passes_content ────────────────────────────────────────────────────────────

def test_content_no_filters():
    assert passes_content(570, {}) is True

def test_content_mode_match():
    with patch("app.get_app_details", return_value=MOCK_DETAILS):
        assert passes_content(570, {"modes": ["singleplayer"]}) is True

def test_content_mode_no_match():
    with patch("app.get_app_details", return_value=MOCK_DETAILS):
        assert passes_content(570, {"modes": ["mmo"]}) is False

def test_content_mode_or_logic():
    # mmo won't match but singleplayer will — OR means it should pass
    with patch("app.get_app_details", return_value=MOCK_DETAILS):
        assert passes_content(570, {"modes": ["mmo", "singleplayer"]}) is True

def test_content_genre_match():
    with patch("app.get_app_details", return_value=MOCK_DETAILS):
        assert passes_content(570, {"genres": ["Action", "RPG"]}) is True

def test_content_genre_and_logic_fails():
    # AND: Strategy not in mock → fail
    with patch("app.get_app_details", return_value=MOCK_DETAILS):
        assert passes_content(570, {"genres": ["Action", "Strategy"]}) is False

def test_content_genre_case_insensitive():
    with patch("app.get_app_details", return_value=MOCK_DETAILS):
        assert passes_content(570, {"genres": ["action", "rpg"]}) is True

def test_content_api_failure_includes_game():
    # If store API fails, include the game rather than over-filter
    with patch("app.get_app_details", return_value=None):
        assert passes_content(570, {"modes": ["singleplayer"], "genres": ["RPG"]}) is True


# ── get_achievements ──────────────────────────────────────────────────────────

def test_achievements_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "playerstats": {
            "success": True,
            "achievements": [
                {"achieved": 1},
                {"achieved": 1},
                {"achieved": 0},
            ],
        }
    }
    with patch("app.requests.get", return_value=mock_resp):
        unlocked, total = get_achievements("76561198000000000", 570)
    assert unlocked == 2
    assert total == 3

def test_achievements_no_achievements():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "playerstats": {"success": True, "achievements": []}
    }
    with patch("app.requests.get", return_value=mock_resp):
        unlocked, total = get_achievements("76561198000000000", 570)
    assert unlocked is None
    assert total is None

def test_achievements_api_not_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"playerstats": {"success": False}}
    with patch("app.requests.get", return_value=mock_resp):
        unlocked, total = get_achievements("76561198000000000", 570)
    assert unlocked is None
    assert total is None

def test_achievements_exception_returns_none():
    with patch("app.requests.get", side_effect=Exception("timeout")):
        unlocked, total = get_achievements("76561198000000000", 570)
    assert unlocked is None
    assert total is None


# ── /api/random-game ──────────────────────────────────────────────────────────

def test_random_game_no_api_key(client):
    with patch("app.STEAM_API_KEY", ""):
        res = client.post("/api/random-game", json={"profile_url": "https://steamcommunity.com/id/test"})
    assert res.status_code == 500

def test_random_game_missing_url(client):
    with patch("app.STEAM_API_KEY", "dummy"):
        res = client.post("/api/random-game", json={})
    assert res.status_code == 400

def test_random_game_unresolvable_id(client):
    with patch("app.STEAM_API_KEY", "dummy"), \
         patch("app.resolve_steam_id", return_value=None):
        res = client.post("/api/random-game", json={"profile_url": "https://steamcommunity.com/id/nobody"})
    assert res.status_code == 400

def test_random_game_empty_library(client):
    with patch("app.STEAM_API_KEY", "dummy"), \
         patch("app.resolve_steam_id", return_value="76561198000000000"), \
         patch("app.get_owned_games", return_value=[]):
        res = client.post("/api/random-game", json={"profile_url": "https://steamcommunity.com/id/test"})
    assert res.status_code == 404

def test_random_game_playtime_filter_no_match(client):
    games = [{"appid": 570, "name": "Dota 2", "playtime_forever": 600}]  # 10 h
    with patch("app.STEAM_API_KEY", "dummy"), \
         patch("app.resolve_steam_id", return_value="76561198000000000"), \
         patch("app.get_owned_games", return_value=games):
        res = client.post("/api/random-game", json={
            "profile_url": "https://steamcommunity.com/id/test",
            "filters": {"unplayed_only": True},
        })
    assert res.status_code == 404

def test_random_game_success(client):
    with patch("app.STEAM_API_KEY", "dummy"), \
         patch("app.resolve_steam_id", return_value="76561198000000000"), \
         patch("app.get_owned_games", return_value=MOCK_GAMES), \
         patch("app.get_player_summary", return_value=MOCK_PLAYER), \
         patch("app.get_app_details", return_value=MOCK_DETAILS), \
         patch("app.get_achievements", return_value=(5, 10)):
        res = client.post("/api/random-game", json={"profile_url": "https://steamcommunity.com/id/test"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["game"]["name"] == "Dota 2"
    assert data["game"]["achievements_unlocked"] == 5
    assert data["game"]["achievements_total"] == 10
    assert data["player"]["name"] == "TestUser"
    assert data["total_games"] == 1

def test_random_game_with_mode_filter(client):
    with patch("app.STEAM_API_KEY", "dummy"), \
         patch("app.resolve_steam_id", return_value="76561198000000000"), \
         patch("app.get_owned_games", return_value=MOCK_GAMES), \
         patch("app.get_player_summary", return_value=MOCK_PLAYER), \
         patch("app.get_app_details", return_value=MOCK_DETAILS), \
         patch("app.get_achievements", return_value=(None, None)):
        res = client.post("/api/random-game", json={
            "profile_url": "https://steamcommunity.com/id/test",
            "filters": {"modes": ["singleplayer"]},
        })
    assert res.status_code == 200

def test_random_game_content_filter_no_match(client):
    with patch("app.STEAM_API_KEY", "dummy"), \
         patch("app.resolve_steam_id", return_value="76561198000000000"), \
         patch("app.get_owned_games", return_value=MOCK_GAMES), \
         patch("app.get_app_details", return_value=MOCK_DETAILS):
        res = client.post("/api/random-game", json={
            "profile_url": "https://steamcommunity.com/id/test",
            "filters": {"modes": ["mmo"]},  # mmo not in MOCK_DETAILS
        })
    assert res.status_code == 404