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
    birth_city: Optional[str] = None
    birth_state_province: Optional[str] = None
    headshot_url: Optional[str] = None
    is_active: Optional[int] = None


@dataclass
class PlayerSeasonStats:
    player_id: int
    season_id: str
    game_type: int
    team_abbrevs: Optional[str] = None
    position_code: Optional[str] = None
    gp: Optional[int] = None
    goals: Optional[int] = None
    assists: Optional[int] = None
    points: Optional[int] = None
    plus_minus: Optional[int] = None
    pim: Optional[int] = None
    pp_goals: Optional[int] = None
    sh_goals: Optional[int] = None
    shots: Optional[int] = None
    shooting_pct: Optional[float] = None
    avg_toi: Optional[str] = None
    wins: Optional[int] = None
    losses: Optional[int] = None
    ot_losses: Optional[int] = None
    save_pct: Optional[float] = None
    gaa: Optional[float] = None
    shutouts: Optional[int] = None


@dataclass
class PlayerCareerStats:
    player_id: int
    rs_gp: Optional[int] = None
    rs_goals: Optional[int] = None
    rs_assists: Optional[int] = None
    rs_points: Optional[int] = None
    rs_plus_minus: Optional[int] = None
    rs_pim: Optional[int] = None
    rs_pp_goals: Optional[int] = None
    rs_sh_goals: Optional[int] = None
    rs_shots: Optional[int] = None
    rs_shooting_pct: Optional[float] = None
    rs_avg_toi: Optional[str] = None
    rs_wins: Optional[int] = None
    rs_losses: Optional[int] = None
    rs_save_pct: Optional[float] = None
    rs_gaa: Optional[float] = None
    rs_shutouts: Optional[int] = None
    po_gp: Optional[int] = None
    po_goals: Optional[int] = None
    po_assists: Optional[int] = None
    po_points: Optional[int] = None
    po_plus_minus: Optional[int] = None
    po_pim: Optional[int] = None
    po_pp_goals: Optional[int] = None
    po_sh_goals: Optional[int] = None
    po_shots: Optional[int] = None
    po_shooting_pct: Optional[float] = None
    po_avg_toi: Optional[str] = None
    po_wins: Optional[int] = None
    po_losses: Optional[int] = None
    po_save_pct: Optional[float] = None
    po_gaa: Optional[float] = None
    po_shutouts: Optional[int] = None


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
