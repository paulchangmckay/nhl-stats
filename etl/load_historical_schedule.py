import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from src.models import Game

SEASONS = ["20202021", "20212022", "20222023", "20232024", "20242025", "20252026"]
GAME_TYPES = [2, 3]  # regular season, playoffs

_GAME_STATE_MAP = {
    7: "OFF",
}


def _map_game_state(game_state_id):
    """Maps the numeric gameStateId from the season-game-list endpoint to the
    string gameState vocabulary used everywhere else in this codebase
    (game_state = 'OFF' gating). Falls back to the raw numeric value as a
    string for anything unmapped, so the row isn't lost -- it just won't
    match 'OFF'-gated queries until the mapping is extended."""
    return _GAME_STATE_MAP.get(game_state_id, str(game_state_id))


def _extract_game(g):
    return Game(
        game_id=g["id"],
        season_id=str(g.get("season", "")),
        game_type=g.get("gameType"),
        game_date=g.get("gameDate", ""),
        venue=None,
        home_team_id=g.get("homeTeamId"),
        away_team_id=g.get("visitingTeamId"),
        home_score=g.get("homeScore"),
        away_score=g.get("visitingScore"),
        last_period_type=None,
        game_state=_map_game_state(g.get("gameStateId")),
    )


def run(conn):
    print("Loading historical schedule (season game backfill)...")
    total = 0

    for season_id in SEASONS:
        database.upsert_season(conn, {
            "season_id": season_id,
            "start_year": int(season_id[:4]),
            "end_year": int(season_id[4:]),
        })

        for game_type in GAME_TYPES:
            try:
                games = api_client.get_season_games(season_id, game_type)
            except Exception as e:
                print(f"  Warning: could not fetch game list for season {season_id} "
                      f"type {game_type}: {e}")
                continue

            for g in games:
                if g.get("gameStateId") not in _GAME_STATE_MAP:
                    print(f"  Warning: game {g.get('id')} has unmapped "
                          f"gameStateId {g.get('gameStateId')!r}")
                try:
                    game = _extract_game(g)
                    if game.home_team_id is not None:
                        database.ensure_team_stub(conn, game.home_team_id)
                    if game.away_team_id is not None:
                        database.ensure_team_stub(conn, game.away_team_id)
                    database.insert_game(conn, game.__dict__)
                except Exception as e:
                    print(f"  Warning: could not insert game {g.get('id')}: {e}")
                    continue
                total += 1

            conn.commit()

    print(f"  {total} historical games loaded/verified.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
