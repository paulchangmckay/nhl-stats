-- NHL Stats Database Schema
-- PostgreSQL Version

-- ============================================
-- CORE ENTITIES
-- ============================================

-- Teams table
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    abbreviation VARCHAR(5) NOT NULL,
    city VARCHAR(100),
    conference VARCHAR(50),
    division VARCHAR(50),
    founded_year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_teams_abbreviation ON teams(abbreviation);
CREATE INDEX idx_teams_division ON teams(division);

-- Players table
CREATE TABLE players (
    player_id INTEGER PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    position VARCHAR(10), -- C, LW, RW, D, G
    shoots VARCHAR(1), -- L or R
    birth_date DATE,
    birth_city VARCHAR(100),
    birth_country VARCHAR(100),
    height_inches INTEGER,
    weight_pounds INTEGER,
    current_team_id INTEGER REFERENCES teams(team_id),
    jersey_number INTEGER,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_players_team ON players(current_team_id);
CREATE INDEX idx_players_position ON players(position);
CREATE INDEX idx_players_name ON players(last_name, first_name);

-- ============================================
-- GAMES & EVENTS
-- ============================================

-- Games table
CREATE TABLE games (
    game_id BIGINT PRIMARY KEY,
    season VARCHAR(10) NOT NULL, -- e.g., "20232024"
    game_type VARCHAR(5), -- R (regular), P (playoffs), PR (preseason)
    game_date DATE NOT NULL,
    game_time TIME,
    home_team_id INTEGER REFERENCES teams(team_id),
    away_team_id INTEGER REFERENCES teams(team_id),
    home_score INTEGER,
    away_score INTEGER,
    game_state VARCHAR(20), -- scheduled, live, final, postponed
    venue VARCHAR(200),
    attendance INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_games_season ON games(season);
CREATE INDEX idx_games_date ON games(game_date);
CREATE INDEX idx_games_home_team ON games(home_team_id);
CREATE INDEX idx_games_away_team ON games(away_team_id);
CREATE INDEX idx_games_state ON games(game_state);

-- ============================================
-- STATISTICS
-- ============================================

-- Game-level team statistics
CREATE TABLE game_team_stats (
    id SERIAL PRIMARY KEY,
    game_id BIGINT REFERENCES games(game_id),
    team_id INTEGER REFERENCES teams(team_id),
    is_home BOOLEAN,
    goals INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,
    pim INTEGER DEFAULT 0, -- Penalty minutes
    power_play_opportunities INTEGER DEFAULT 0,
    power_play_goals INTEGER DEFAULT 0,
    face_off_win_percentage DECIMAL(5,2),
    blocked_shots INTEGER DEFAULT 0,
    takeaways INTEGER DEFAULT 0,
    giveaways INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, team_id)
);

CREATE INDEX idx_game_team_stats_game ON game_team_stats(game_id);
CREATE INDEX idx_game_team_stats_team ON game_team_stats(team_id);

-- Game-level player statistics
CREATE TABLE game_player_stats (
    id SERIAL PRIMARY KEY,
    game_id BIGINT REFERENCES games(game_id),
    player_id INTEGER REFERENCES players(player_id),
    team_id INTEGER REFERENCES teams(team_id),
    time_on_ice INTEGER, -- seconds
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    hits INTEGER DEFAULT 0,
    blocked_shots INTEGER DEFAULT 0,
    plus_minus INTEGER DEFAULT 0,
    penalty_minutes INTEGER DEFAULT 0,
    power_play_goals INTEGER DEFAULT 0,
    power_play_assists INTEGER DEFAULT 0,
    short_handed_goals INTEGER DEFAULT 0,
    short_handed_assists INTEGER DEFAULT 0,
    face_off_wins INTEGER DEFAULT 0,
    face_off_taken INTEGER DEFAULT 0,
    takeaways INTEGER DEFAULT 0,
    giveaways INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, player_id)
);

CREATE INDEX idx_game_player_stats_game ON game_player_stats(game_id);
CREATE INDEX idx_game_player_stats_player ON game_player_stats(player_id);
CREATE INDEX idx_game_player_stats_team ON game_player_stats(team_id);

-- Goalie-specific game statistics
CREATE TABLE game_goalie_stats (
    id SERIAL PRIMARY KEY,
    game_id BIGINT REFERENCES games(game_id),
    player_id INTEGER REFERENCES players(player_id),
    team_id INTEGER REFERENCES teams(team_id),
    time_on_ice INTEGER, -- seconds
    shots_against INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    save_percentage DECIMAL(5,3),
    shutout BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, player_id)
);

CREATE INDEX idx_game_goalie_stats_game ON game_goalie_stats(game_id);
CREATE INDEX idx_game_goalie_stats_player ON game_goalie_stats(player_id);

-- ============================================
-- SEASON AGGREGATES (for performance)
-- ============================================

-- Season-level player statistics (aggregated)
CREATE TABLE season_player_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id),
    season VARCHAR(10) NOT NULL,
    games_played INTEGER DEFAULT 0,
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    plus_minus INTEGER DEFAULT 0,
    penalty_minutes INTEGER DEFAULT 0,
    shots INTEGER DEFAULT 0,
    shooting_percentage DECIMAL(5,2),
    time_on_ice_per_game INTEGER, -- seconds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season)
);

CREATE INDEX idx_season_player_stats_season ON season_player_stats(season);
CREATE INDEX idx_season_player_stats_player ON season_player_stats(player_id);

-- ============================================
-- NOTES & CUSTOMIZATION
-- ============================================

/*
CUSTOMIZATION AREAS:
1. Add more advanced stats (Corsi, Fenwick, xG) as separate columns or table
2. Add player_team_history table if tracking trades/signings
3. Add playoff-specific aggregations
4. Add injury tracking table
5. Add contract/salary information (if needed)

PERFORMANCE CONSIDERATIONS:
- Indexes added for common query patterns
- Consider partitioning games table by season for large datasets
- Season aggregate tables reduce query load for common analytics
- Add materialized views for complex, frequently-run queries

DATA SOURCES:
- Most fields map directly to NHL API responses
- Adjust field names/types based on your chosen data source
*/
