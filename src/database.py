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

CREATE_PLAYER_SEASON_STATS = """
CREATE TABLE IF NOT EXISTS player_season_stats (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id     INTEGER NOT NULL REFERENCES players(player_id),
    season_id     TEXT    NOT NULL,
    game_type     INTEGER NOT NULL,
    team_abbrevs  TEXT,
    position_code TEXT,
    gp            INTEGER,
    goals         INTEGER,
    assists       INTEGER,
    points        INTEGER,
    plus_minus    INTEGER,
    pim           INTEGER,
    pp_goals      INTEGER,
    sh_goals      INTEGER,
    shots         INTEGER,
    shooting_pct  REAL,
    avg_toi       TEXT,
    wins          INTEGER,
    losses        INTEGER,
    ot_losses     INTEGER,
    save_pct      REAL,
    gaa           REAL,
    shutouts      INTEGER,
    UNIQUE (player_id, season_id, game_type)
);
"""

CREATE_PLAYER_CAREER_STATS = """
CREATE TABLE IF NOT EXISTS player_career_stats (
    player_id       INTEGER PRIMARY KEY REFERENCES players(player_id),
    rs_gp           INTEGER,
    rs_goals        INTEGER,
    rs_assists      INTEGER,
    rs_points       INTEGER,
    rs_plus_minus   INTEGER,
    rs_pim          INTEGER,
    rs_pp_goals     INTEGER,
    rs_sh_goals     INTEGER,
    rs_shots        INTEGER,
    rs_shooting_pct REAL,
    rs_avg_toi      TEXT,
    rs_wins         INTEGER,
    rs_losses       INTEGER,
    rs_save_pct     REAL,
    rs_gaa          REAL,
    rs_shutouts     INTEGER,
    po_gp           INTEGER,
    po_goals        INTEGER,
    po_assists      INTEGER,
    po_points       INTEGER,
    po_plus_minus   INTEGER,
    po_pim          INTEGER,
    po_pp_goals     INTEGER,
    po_sh_goals     INTEGER,
    po_shots        INTEGER,
    po_shooting_pct REAL,
    po_avg_toi      TEXT,
    po_wins         INTEGER,
    po_losses       INTEGER,
    po_save_pct     REAL,
    po_gaa          REAL,
    po_shutouts     INTEGER,
    last_updated    TEXT DEFAULT (datetime('now'))
);
"""

CREATE_GAME_EVENTS = """
CREATE TABLE IF NOT EXISTS game_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id             INTEGER NOT NULL REFERENCES games(game_id),
    event_id            INTEGER NOT NULL,
    period              INTEGER NOT NULL,
    time_in_period      TEXT,
    situation_code      TEXT,
    event_type          TEXT NOT NULL,
    zone_code           TEXT,
    x_coord             INTEGER,
    y_coord             INTEGER,
    shot_type           TEXT,
    event_owner_team_id INTEGER REFERENCES teams(team_id),
    shooting_player_id  INTEGER REFERENCES players(player_id),
    blocking_player_id  INTEGER REFERENCES players(player_id),
    goalie_in_net_id    INTEGER REFERENCES players(player_id),
    assist1_player_id   INTEGER REFERENCES players(player_id),
    assist2_player_id   INTEGER REFERENCES players(player_id),
    details_json        TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE (game_id, event_id)
);
"""

CREATE_GAME_EVENTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_game_events_team_type ON game_events(event_owner_team_id, event_type)",
    "CREATE INDEX IF NOT EXISTS idx_game_events_shooter ON game_events(shooting_player_id)",
]

CREATE_PLAYER_SHIFTS = """
CREATE TABLE IF NOT EXISTS player_shifts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id    INTEGER NOT NULL REFERENCES games(game_id),
    shift_id   INTEGER NOT NULL,
    player_id  INTEGER NOT NULL REFERENCES players(player_id),
    team_id    INTEGER REFERENCES teams(team_id),
    period     INTEGER NOT NULL,
    start_time TEXT,
    end_time   TEXT,
    duration   TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (game_id, shift_id)
);
"""

CREATE_PLAYER_SHIFTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_player_shifts_player_game ON player_shifts(player_id, game_id)",
]

CREATE_SYNC_LOG = """
CREATE TABLE IF NOT EXISTS sync_log (
    key          TEXT PRIMARY KEY,
    synced_at    TEXT NOT NULL DEFAULT (datetime('now')),
    record_count INTEGER
);
"""

_PLAYER_MIGRATIONS = [
    "ALTER TABLE players ADD COLUMN birth_city           TEXT",
    "ALTER TABLE players ADD COLUMN birth_state_province TEXT",
    "ALTER TABLE players ADD COLUMN headshot_url         TEXT",
    "ALTER TABLE players ADD COLUMN draft_year           INTEGER",
    "ALTER TABLE players ADD COLUMN draft_round          INTEGER",
    "ALTER TABLE players ADD COLUMN draft_pick           INTEGER",
    "ALTER TABLE players ADD COLUMN draft_overall        INTEGER",
    "ALTER TABLE players ADD COLUMN draft_team_abbrev    TEXT",
    "ALTER TABLE players ADD COLUMN is_active            INTEGER",
    "ALTER TABLE players ADD COLUMN enriched_at          TEXT",
]

_GAME_EVENTS_MIGRATIONS = [
    "ALTER TABLE game_events ADD COLUMN home_team_defending_side TEXT",
]


def get_connection(db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_migrations(conn):
    for sql in _PLAYER_MIGRATIONS + _GAME_EVENTS_MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()


def create_all_tables(conn):
    for sql in [CREATE_TEAMS, CREATE_SEASONS, CREATE_PLAYERS,
                CREATE_GAMES, CREATE_PLAYER_GAME_STATS, CREATE_STANDINGS,
                CREATE_PLAYER_SEASON_STATS, CREATE_PLAYER_CAREER_STATS,
                CREATE_GAME_EVENTS, CREATE_PLAYER_SHIFTS, CREATE_SYNC_LOG]:
        conn.execute(sql)
    for sql in CREATE_GAME_EVENTS_INDEXES + CREATE_PLAYER_SHIFTS_INDEXES:
        conn.execute(sql)
    run_migrations(conn)
    conn.commit()
    print("All tables created.")


def get_sync_record(conn, key):
    """Return the synced_at timestamp for a key, or None if not found."""
    row = conn.execute("SELECT synced_at FROM sync_log WHERE key = ?", (key,)).fetchone()
    return row["synced_at"] if row else None


def set_sync_record(conn, key, record_count=None):
    """Mark a sync key as complete with the current timestamp."""
    conn.execute(
        "INSERT OR REPLACE INTO sync_log (key, synced_at, record_count) VALUES (?, datetime('now'), ?)",
        (key, record_count),
    )
    conn.commit()


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
    """Upsert roster-sourced player data. Never overwrites draft_* or is_active."""
    conn.execute("""
        INSERT INTO players (
            player_id, first_name, last_name, position_code, sweater_number,
            shoots_catches, height_inches, weight_pounds, birth_date, birth_country,
            current_team_id, birth_city, birth_state_province, headshot_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET
            first_name           = excluded.first_name,
            last_name            = excluded.last_name,
            position_code        = excluded.position_code,
            sweater_number       = excluded.sweater_number,
            shoots_catches       = excluded.shoots_catches,
            height_inches        = excluded.height_inches,
            weight_pounds        = excluded.weight_pounds,
            birth_date           = excluded.birth_date,
            birth_country        = excluded.birth_country,
            current_team_id      = excluded.current_team_id,
            birth_city           = excluded.birth_city,
            birth_state_province = excluded.birth_state_province,
            headshot_url         = excluded.headshot_url,
            updated_at           = datetime('now')
    """, (
        p["player_id"], p["first_name"], p["last_name"], p.get("position_code"),
        p.get("sweater_number"), p.get("shoots_catches"), p.get("height_inches"),
        p.get("weight_pounds"), p.get("birth_date"), p.get("birth_country"),
        p.get("current_team_id"), p.get("birth_city"), p.get("birth_state_province"),
        p.get("headshot_url"),
    ))


def upsert_player_stub(conn, p):
    """INSERT OR IGNORE — creates a minimal record for historical players not on any roster."""
    conn.execute(
        "INSERT OR IGNORE INTO players "
        "(player_id, first_name, last_name, position_code, shoots_catches) "
        "VALUES (?, ?, ?, ?, ?)",
        (p["player_id"], p["first_name"], p["last_name"],
         p.get("position_code"), p.get("shoots_catches")),
    )


def upsert_player_enrichment(conn, p):
    """UPDATE players with bio/draft data from the landing API."""
    conn.execute("""
        UPDATE players SET
            draft_year           = ?,
            draft_round          = ?,
            draft_pick           = ?,
            draft_overall        = ?,
            draft_team_abbrev    = ?,
            is_active            = ?,
            position_code        = COALESCE(position_code, ?),
            birth_city           = COALESCE(birth_city, ?),
            birth_state_province = COALESCE(birth_state_province, ?),
            headshot_url         = COALESCE(headshot_url, ?),
            height_inches        = COALESCE(height_inches, ?),
            weight_pounds        = COALESCE(weight_pounds, ?),
            birth_date           = COALESCE(birth_date, ?),
            birth_country        = COALESCE(birth_country, ?),
            enriched_at          = datetime('now')
        WHERE player_id = ?
    """, (
        p.get("draft_year"), p.get("draft_round"), p.get("draft_pick"),
        p.get("draft_overall"), p.get("draft_team_abbrev"), p.get("is_active"),
        p.get("position_code"),
        p.get("birth_city"), p.get("birth_state_province"), p.get("headshot_url"),
        p.get("height_inches"), p.get("weight_pounds"), p.get("birth_date"),
        p.get("birth_country"),
        p["player_id"],
    ))


def upsert_season_stats(conn, s):
    conn.execute("""
        INSERT OR REPLACE INTO player_season_stats (
            player_id, season_id, game_type, team_abbrevs, position_code,
            gp, goals, assists, points, plus_minus, pim, pp_goals, sh_goals,
            shots, shooting_pct, avg_toi,
            wins, losses, ot_losses, save_pct, gaa, shutouts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        s["player_id"], s["season_id"], s["game_type"], s.get("team_abbrevs"),
        s.get("position_code"), s.get("gp"), s.get("goals"), s.get("assists"),
        s.get("points"), s.get("plus_minus"), s.get("pim"), s.get("pp_goals"),
        s.get("sh_goals"), s.get("shots"), s.get("shooting_pct"), s.get("avg_toi"),
        s.get("wins"), s.get("losses"), s.get("ot_losses"), s.get("save_pct"),
        s.get("gaa"), s.get("shutouts"),
    ))


def upsert_career_stats(conn, c):
    conn.execute("""
        INSERT OR REPLACE INTO player_career_stats (
            player_id,
            rs_gp, rs_goals, rs_assists, rs_points, rs_plus_minus, rs_pim,
            rs_pp_goals, rs_sh_goals, rs_shots, rs_shooting_pct, rs_avg_toi,
            rs_wins, rs_losses, rs_save_pct, rs_gaa, rs_shutouts,
            po_gp, po_goals, po_assists, po_points, po_plus_minus, po_pim,
            po_pp_goals, po_sh_goals, po_shots, po_shooting_pct, po_avg_toi,
            po_wins, po_losses, po_save_pct, po_gaa, po_shutouts,
            last_updated
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now')
        )
    """, (
        c["player_id"],
        c.get("rs_gp"), c.get("rs_goals"), c.get("rs_assists"), c.get("rs_points"),
        c.get("rs_plus_minus"), c.get("rs_pim"), c.get("rs_pp_goals"), c.get("rs_sh_goals"),
        c.get("rs_shots"), c.get("rs_shooting_pct"), c.get("rs_avg_toi"),
        c.get("rs_wins"), c.get("rs_losses"), c.get("rs_save_pct"), c.get("rs_gaa"),
        c.get("rs_shutouts"),
        c.get("po_gp"), c.get("po_goals"), c.get("po_assists"), c.get("po_points"),
        c.get("po_plus_minus"), c.get("po_pim"), c.get("po_pp_goals"), c.get("po_sh_goals"),
        c.get("po_shots"), c.get("po_shooting_pct"), c.get("po_avg_toi"),
        c.get("po_wins"), c.get("po_losses"), c.get("po_save_pct"), c.get("po_gaa"),
        c.get("po_shutouts"),
    ))


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


def insert_game_event(conn, e):
    # ON CONFLICT DO UPDATE (not INSERT OR IGNORE) is deliberate here: the
    # one-time home_team_defending_side gap-fill (backfill_defending_side.py)
    # re-inserts already-loaded events solely to populate that one column,
    # and needs the update to actually take effect on a second call for the
    # same (game_id, event_id).
    conn.execute(
        "INSERT INTO game_events "
        "(game_id, event_id, period, time_in_period, situation_code, event_type, "
        "zone_code, x_coord, y_coord, shot_type, event_owner_team_id, "
        "shooting_player_id, blocking_player_id, goalie_in_net_id, "
        "assist1_player_id, assist2_player_id, details_json, home_team_defending_side) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(game_id, event_id) DO UPDATE SET "
        "period=excluded.period, time_in_period=excluded.time_in_period, "
        "situation_code=excluded.situation_code, event_type=excluded.event_type, "
        "zone_code=excluded.zone_code, x_coord=excluded.x_coord, y_coord=excluded.y_coord, "
        "shot_type=excluded.shot_type, event_owner_team_id=excluded.event_owner_team_id, "
        "shooting_player_id=excluded.shooting_player_id, "
        "blocking_player_id=excluded.blocking_player_id, "
        "goalie_in_net_id=excluded.goalie_in_net_id, "
        "assist1_player_id=excluded.assist1_player_id, "
        "assist2_player_id=excluded.assist2_player_id, "
        "details_json=excluded.details_json, "
        "home_team_defending_side=excluded.home_team_defending_side",
        (e["game_id"], e["event_id"], e["period"], e["time_in_period"],
         e["situation_code"], e["event_type"], e["zone_code"], e["x_coord"],
         e["y_coord"], e["shot_type"], e["event_owner_team_id"],
         e["shooting_player_id"], e["blocking_player_id"], e["goalie_in_net_id"],
         e["assist1_player_id"], e["assist2_player_id"], e["details_json"],
         e.get("home_team_defending_side")),
    )


def insert_player_shift(conn, s):
    conn.execute(
        "INSERT OR IGNORE INTO player_shifts "
        "(game_id, shift_id, player_id, team_id, period, start_time, end_time, duration) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (s["game_id"], s["shift_id"], s["player_id"], s["team_id"], s["period"],
         s["start_time"], s["end_time"], s["duration"]),
    )


def ensure_player_stub(conn, player_id, first_name="Unknown", last_name=""):
    """Inserts a minimal placeholder player row if player_id isn't already
    present, so FK-constrained inserts (game_events, player_shifts) referencing
    a not-yet-seen player don't fail. enrich_players.py's landing-API pass
    (gated on position_code IS NULL) picks up any such stub and fills in the
    real name/bio on its next run."""
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first_name, last_name),
    )


def ensure_team_stub(conn, team_id, abbrev="UNK", common_name="Unknown", place_name="Unknown"):
    """Inserts a minimal placeholder team row if team_id isn't already
    present, so FK-constrained inserts referencing a relocated/historical
    team (e.g. Arizona Coyotes, team_id 53, absent from load_teams' active-
    roster seed) don't fail. A later load_teams run does not overwrite this
    stub (upsert_team uses INSERT OR REPLACE keyed only on team_id, so if
    load_teams ever adds this ID with real data it will correctly replace
    the stub — but until then the placeholder satisfies the FK).

    wolf-debt: rows joining through an unresolved stub render as
    abbrev='UNK'/common_name='Unknown' with no warning, including for an
    active team that load_teams unexpectedly fails to seed (not just
    relocated/historical ones) -- upgrade trigger: when a reporting/metrics
    layer starts querying teams by name, seed real historical team data
    (e.g. via a static relocation table) or add a `WHERE abbrev='UNK'`
    reconciliation check to surface any stub that's still unresolved."""
    conn.execute(
        "INSERT OR IGNORE INTO teams (team_id, abbrev, common_name, place_name) VALUES (?, ?, ?, ?)",
        (team_id, abbrev, common_name, place_name),
    )
