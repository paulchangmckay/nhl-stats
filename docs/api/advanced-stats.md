# Advanced Stats API Reference

Documents `GET /api/players/<player_id>/advanced` and `GET /api/teams/<team_abbrev>/advanced`.

## `GET /api/players/<player_id>/advanced?season=<season_id>`

Returns `{ player_id, season_id, strength_states, trend, pdo }`.

`strength_states` is keyed by `5v5` / `5v4` / `4v5`. Every state has:

| Field | Type | Meaning |
|---|---|---|
| `cf`, `ca` | int | On-ice Corsi For/Against (all on-ice skaters credited) |
| `cf_pct` | float\|null | `cf / (cf+ca) * 100`, 1 decimal |
| `ff`, `fa`, `ff_pct` | — | Fenwick equivalents (excludes blocked shots) |
| `hdcf`, `hdca`, `hdcf_pct` | — | High-danger Corsi equivalents |
| `primary_points` | int | Goals + primary assists (on-ice independent) |
| `cf_pctile`, `ff_pctile`, `hdcf_pctile`, `primary_points_pctile` | float\|null | Percentile rank within position group, 10-GP floor, `5v5`/`5v4`/`4v5` only |

**`5v5` only**, additionally:

| Field | Type | Meaning |
|---|---|---|
| `shots_per60` | float\|null | Individual shot attempts (on goal+missed+blocked+goal) / 5v5 TOI hours, 2 decimals |
| `chances_per60` | float\|null | Individual high-danger shot attempts / TOI hours |
| `rebounds_created_per60` | float\|null | **Heuristic**: shot attempts followed within 3s by a same-team shot attempt, credited to the original shooter / TOI hours. Not possession-confirmed. |
| `deflections_per60` | float\|null | Individual shot attempts with `shot_type IN ('deflected','tip-in')` / TOI hours |
| `points_per60` | float\|null | Goals + all assists / TOI hours |
| `primary_points_per60` | float\|null | `primary_points` / TOI hours |
| `shots_per60_z`, `chances_per60_z`, `rebounds_created_per60_z`, `deflections_per60_z`, `points_per60_z`, `primary_points_per60_z` | float\|null | Z-score vs. position-group population (regular season, 10-GP floor, 20-player minimum population). `null` if the player or the league sample doesn't clear the floor. |

## `GET /api/teams/<team_abbrev>/advanced?season=<season_id>`

Returns `{ team_abbrev, season_id, strength_states }`.

`strength_states` is keyed by `5v5` / `5v4` / `4v5`. Every state has:

| Field | Type | Meaning |
|---|---|---|
| `cf`, `ca` | int | Team Corsi For/Against |
| `cf_pct` | float\|null | `cf / (cf+ca) * 100`, 1 decimal |
| `ff`, `fa`, `ff_pct` | — | Fenwick equivalents (excludes blocked shots) |
| `gf`, `ga` | int | Goals For/Against |
| `pdo` | float\|null | (Goal For % + Save %) * 1000, 1 decimal; `null` if shots data unavailable |

## `GET /api/players/stats?seasons=<season_id>`

Adds `shots_per60_5v5` (float\|null) alongside the existing `cf_pct_5v5` teaser field — same "season-specific query only, `null` for the all-seasons/career view" caveat, since no career-level advanced-stats aggregation is populated yet.

## Not available (Phase 2 — blocked on a data source beyond the free NHL API)

- **Passing**: Point Shot Setups/60, Passes from Center Lane/60, High Danger Assists/60, Deflection Assists/60, One-timer Assists/60 — no pass event/coordinate data in the NHL public feed.
- **Zone Entries**: Zone Entries/60, Controlled Entry%, Controlled Entries/60, Entries w/ Passing Play/60, Entries w/ Chances/60, Entry w/ Pass%, Controlled Entry w/ Chance% — entry style (carried/passed/dumped) isn't derivable from discrete zone-coded events.
- **DZ Retrievals & Exits**: all 12 stats — same possession-tracking gap.
- **Forechecking**: Pressures/60, Recovered Dump-ins/60 — needs proximity/pressure data (NHL Edge tracking or manual charting).
- **Rush Offense/60, Cycle & Forecheck Offense/60, One-timers/60, Shots off HD Passes/60** — deferred alongside the above (possession/passing gap).
