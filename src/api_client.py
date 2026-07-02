import time
import requests

BASE_WEB = "https://api-web.nhle.com/v1"
BASE_STATS = "https://api.nhle.com/stats/rest/en"


def _get(url, retries=4):
    """GET with exponential backoff on 429 rate-limit responses."""
    for attempt in range(retries):
        response = requests.get(url, timeout=15)
        if response.status_code == 429:
            wait = 2 ** attempt * 3  # 3, 6, 12, 24 seconds
            print(f"  Rate limited, waiting {wait}s before retry...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()
    response.raise_for_status()


def get_standings():
    """Returns a list of team standing dicts for the current date."""
    data = _get(f"{BASE_WEB}/standings/now")
    return data["standings"]


def get_roster(team_abbrev):
    """Returns dict with keys 'forwards', 'defensemen', 'goalies' for a team."""
    data = _get(f"{BASE_WEB}/roster/{team_abbrev}/current")
    return data


def get_schedule():
    """Returns current week's schedule. Each entry has a 'games' list."""
    data = _get(f"{BASE_WEB}/schedule/now")
    return data.get("gameWeek", [])


def get_boxscore(game_id):
    """Returns boxscore for a completed game including per-player stats."""
    data = _get(f"{BASE_WEB}/gamecenter/{game_id}/boxscore")
    return data


def get_all_teams():
    """Returns all NHL franchise records including IDs and triCodes."""
    data = _get(f"{BASE_STATS}/team")
    return data.get("data", [])


def get_season_stats(season_id, game_type, player_type, limit=100, start=0):
    """Paginated season stats from stats REST API.
    player_type: 'skater' or 'goalie'
    game_type: 2=regular season, 3=playoffs
    Returns {"data": [...], "total": N}
    """
    url = (
        f"{BASE_STATS}/{player_type}/summary"
        f"?limit={limit}&start={start}"
        f"&cayenneExp=seasonId%3D{season_id}%20and%20gameTypeId%3D{game_type}"
    )
    return _get(url)


def get_player_landing(player_id):
    """Full player profile including draft info, bio, and career totals."""
    return _get(f"{BASE_WEB}/player/{player_id}/landing")
