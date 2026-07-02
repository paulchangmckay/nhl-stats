import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "nhl_stats.db")

CREATE_TEAMS = """
CREATE TABLE IF NOT EXISTS teams (
    team_id     INTEGER PRIMARY KEY,
    abbrev      TEXT    NOT NULL,
    common_name TEXT    NOT NULL,
    place_name  TEXT    NOT NULL,
    conference  TEXT,
    division    TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);
"""

CREATE_SEASONS = """
CREATE TABLE IF NOT EXISTS seasons (
    season_id  TEXT    PRIMARY KEY,
    start_year INTEGER NOT NULL,
    end_year   INTEGER NOT NULL,
    created_at TEXT    DEFAULT (datetime('now'))
);
"""

CREATE_PLAYERS = """
CREATE TABLE IF NOT EXISTS players (
    player_id       INTEGER PRIMARY KEY,
    first_name      TEXT    NOT NULL,
    last_name       TEXT    NOT NULL,
    position_code   TEXT,
    sweater_number  INTEGER,
    shoots_catches  TEXT,
    height_inches   INTEGER,
    weight_pounds   INTEGER,
    birth_date      TEXT,
    birth_country   TEXT,
    current_team_id INTEGER REFERENCES teams(team_id),
    updated_at      TEXT    DEFAULT (datetime('now'))
);
"""

CREATE_GAMES = """
CREATE TABLE IF NOT EXISTS games (
    game_id          INTEGER PRIMARY KEY,
    season_id        TEXT    REFERENCES seasons(season_id),
    game_type        INTEGER,
    game_date        TEXT    NOT NULL,
    venue            TEXT,
    home_team_id     INTEGER REFERENCES teams(team_id),
    away_team_id     INTEGER REFERENCES teams(team_id),
    home_score       INTEGER,
    away_score       INTEGER,
    last_period_type TEXT,
    game_state       TEXT,
    created_at       TEXT    DEFAULT (datetime('now'))
);
"""

CREATE_PLAYER_GAME_STATS = """
CREATE TABLE IF NOT EXISTS player_game_stats (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       INTEGER NOT NULL REFERENCES games(game_id),
    player_id     INTEGER NOT NULL REFERENCES players(player_id),
    team_id       INTEGER REFERENCES teams(team_id),
    goals         INTEGER DEFAULT 0,
    assists       INTEGER DEFAULT 0,
    points        INTEGER DEFAULT 0,
    plus_minus    INTEGER DEFAULT 0,
    pim           INTEGER DEFAULT 0,
    hits          INTEGER DEFAULT 0,
    shots_on_goal INTEGER DEFAULT 0,
    blocked_shots INTEGER DEFAULT 0,
    toi           TEXT,
    created_at    TEXT    DEFAULT (datetime('now')),
    UNIQUE (game_id, player_id)
);
"""

CREATE_STANDINGS = """
CREATE TABLE IF NOT EXISTS standings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date   TEXT    NOT NULL,
    season_id       TEXT    REFERENCES seasons(season_id),
    team_id         INTEGER REFERENCES teams(team_id),
    games_played    INTEGER,
    wins            INTEGER,
    losses          INTEGER,
    ot_losses       INTEGER,
    points          INTEGER,
    regulation_wins INTEGER,
    goal_for        INTEGER,
    goal_against    INTEGER,
    point_pct       REAL,
    streak_code     TEXT,
    streak_count    INTEGER,
    created_at      TEXT    DEFAULT (datetime('now')),
    UNIQUE (snapshot_date, team_id)
);
"""


def get_connection(db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_all_tables(conn):
    for sql in [CREATE_TEAMS, CREATE_SEASONS, CREATE_PLAYERS,
                CREATE_GAMES, CREATE_PLAYER_GAME_STATS, CREATE_STANDINGS]:
        conn.execute(sql)
    conn.commit()
    print("All tables created.")


def upsert_team(conn, t):
    conn.execute(
        "INSERT OR REPLACE INTO teams (team_id, abbrev, common_name, place_name, conference, division) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (t["team_id"], t["abbrev"], t["common_name"], t["place_name"], t["conference"], t["division"]),
    )


def upsert_season(conn, s):
    conn.execute(
        "INSERT OR IGNORE INTO seasons (season_id, start_year, end_year) VALUES (?, ?, ?)",
        (s["season_id"], s["start_year"], s["end_year"]),
    )


def upsert_player(conn, p):
    conn.execute(
        "INSERT OR REPLACE INTO players "
        "(player_id, first_name, last_name, position_code, sweater_number, "
        "shoots_catches, height_inches, weight_pounds, birth_date, birth_country, current_team_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (p["player_id"], p["first_name"], p["last_name"], p["position_code"],
         p["sweater_number"], p["shoots_catches"], p["height_inches"],
         p["weight_pounds"], p["birth_date"], p["birth_country"], p["current_team_id"]),
    )


def insert_game(conn, g):
    conn.execute(
        "INSERT OR IGNORE INTO games "
        "(game_id, season_id, game_type, game_date, venue, home_team_id, away_team_id, "
        "home_score, away_score, last_period_type, game_state) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (g["game_id"], g["season_id"], g["game_type"], g["game_date"], g["venue"],
         g["home_team_id"], g["away_team_id"], g.get("home_score"), g.get("away_score"),
         g.get("last_period_type"), g["game_state"]),
    )


def update_game_score(conn, game_id, home_score, away_score, last_period_type, game_state):
    conn.execute(
        "UPDATE games SET home_score=?, away_score=?, last_period_type=?, game_state=? WHERE game_id=?",
        (home_score, away_score, last_period_type, game_state, game_id),
    )


def insert_player_game_stats(conn, s):
    conn.execute(
        "INSERT OR IGNORE INTO player_game_stats "
        "(game_id, player_id, team_id, goals, assists, points, plus_minus, "
        "pim, hits, shots_on_goal, blocked_shots, toi) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (s["game_id"], s["player_id"], s["team_id"], s["goals"], s["assists"],
         s["points"], s["plus_minus"], s["pim"], s["hits"],
         s["shots_on_goal"], s["blocked_shots"], s["toi"]),
    )


def insert_standings_snapshot(conn, s):
    conn.execute(
        "INSERT OR IGNORE INTO standings "
        "(snapshot_date, season_id, team_id, games_played, wins, losses, ot_losses, "
        "points, regulation_wins, goal_for, goal_against, point_pct, streak_code, streak_count) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (s["snapshot_date"], s["season_id"], s["team_id"], s["games_played"],
         s["wins"], s["losses"], s["ot_losses"], s["points"], s["regulation_wins"],
         s["goal_for"], s["goal_against"], s["point_pct"], s["streak_code"], s["streak_count"]),
    )
