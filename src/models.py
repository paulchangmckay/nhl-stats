from dataclasses import dataclass
from typing import Optional


@dataclass
class Team:
    team_id: int
    abbrev: str
    common_name: str
    place_name: str
    conference: Optional[str]
    division: Optional[str]


@dataclass
class Season:
    season_id: str   # NHL format: '20252026'
    start_year: int
    end_year: int


@dataclass
class Player:
    player_id: int
    first_name: str
    last_name: str
    position_code: Optional[str]
    sweater_number: Optional[int]
    shoots_catches: Optional[str]
    height_inches: Optional[int]
    weight_pounds: Optional[int]
    birth_date: Optional[str]
    birth_country: Optional[str]
    current_team_id: Optional[int]


@dataclass
class Game:
    game_id: int
    season_id: Optional[str]
    game_type: Optional[int]
    game_date: str
    venue: Optional[str]
    home_team_id: Optional[int]
    away_team_id: Optional[int]
    home_score: Optional[int]
    away_score: Optional[int]
    last_period_type: Optional[str]
    game_state: Optional[str]


@dataclass
class PlayerGameStats:
    game_id: int
    player_id: int
    team_id: Optional[int]
    goals: int = 0
    assists: int = 0
    points: int = 0
    plus_minus: int = 0
    pim: int = 0
    hits: int = 0
    shots_on_goal: int = 0
    blocked_shots: int = 0
    toi: Optional[str] = None


@dataclass
class StandingsSnapshot:
    snapshot_date: str
    season_id: Optional[str]
    team_id: int
    games_played: int
    wins: int
    losses: int
    ot_losses: int
    points: int
    regulation_wins: int
    goal_for: int
    goal_against: int
    point_pct: float
    streak_code: Optional[str]
    streak_count: Optional[int]
