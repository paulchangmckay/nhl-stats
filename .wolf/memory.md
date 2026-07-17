# Memory

> Chronological action log for this project.
> Backfilled 2026-07-02 from `~/.claude/.wolf/memory.md`, which had been logging this project's
> file-level actions by mistake (the memory-logging hook attributes edits to the Claude Code
> session's primary working directory, not the file's actual project). Entries below are the
> per-file Created/Edited actions for this project extracted from that history; cross-project
> "Session end" summary rows were left in `~/.claude`'s log since they aggregate files from both
> projects and can't be cleanly split.

## Session: 2026-07-02 22:01

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 22:14 | Created .gitignore | — | ~30 |
| 22:14 | Created README.md | — | ~357 |
| 22:14 | Created requirements.txt | — | ~23 |
| 22:15 | Created src/database.py | — | ~1864 |
| 22:15 | Created scripts/setup_db.py | — | ~73 |
| 22:15 | Created src/api_client.py | — | ~270 |
| 22:16 | Created src/models.py | — | ~474 |
| 22:17 | Created etl/load_teams.py | — | ~237 |
| 22:17 | Created etl/load_standings.py | — | ~531 |
| 22:17 | Created etl/load_rosters.py | — | ~506 |
| 22:18 | Created etl/load_schedule.py | — | ~359 |
| 22:18 | Created etl/load_boxscores.py | — | ~721 |
| 22:19 | Created scripts/run_all_etl.py | — | ~188 |
| 22:19 | Created scripts/query_examples.py | — | ~1136 |
| 22:20 | Edited .gitignore | 2→3 lines | ~5 |
| 22:23 | Created .gitignore | — | ~31 |
| 22:23 | Created README.md | — | ~379 |
| 22:26 | Edited src/api_client.py | modified get_boxscore() | ~99 |
| 22:26 | Created etl/load_teams.py | — | ~438 |
| 22:26 | Created etl/load_standings.py | — | ~638 |
| 22:27 | Created etl/load_rosters.py | — | ~479 |
| 22:27 | Created etl/load_schedule.py | — | ~361 |
| 22:28 | Edited etl/load_boxscores.py | 9→9 lines | ~100 |
| 22:29 | Edited etl/load_rosters.py | added 1 import(s) | ~48 |
| 22:29 | Edited etl/load_rosters.py | 5→7 lines | ~79 |
| 22:29 | Edited src/api_client.py | modified _get() | ~177 |
| 22:30 | Created etl/load_boxscores.py | — | ~969 |
| 22:40 | Created app.py | — | ~606 |
| 22:41 | Created templates/index.html | — | ~2238 |
| 22:41 | Edited requirements.txt | 1→2 lines | ~8 |

## Session: 2026-07-02 23:04

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 23:12 | Edited src/database.py | expanded (+80 lines) | ~924 |
| 23:12 | Edited src/database.py | modified run_migrations() | ~152 |
| 23:12 | Edited src/database.py | modified upsert_player() | ~1548 |
| 23:13 | Edited src/models.py | expanded (+67 lines) | ~712 |
| 23:14 | Edited src/api_client.py | modified get_all_teams() | ~228 |
| 23:15 | Edited etl/load_rosters.py | modified _parse_player() | ~241 |
| 23:15 | Created etl/load_season_stats.py | — | ~1388 |
| 23:16 | Created etl/enrich_players.py | — | ~1276 |
| 23:16 | Edited scripts/run_all_etl.py | 11→16 lines | ~140 |

## Session: 2026-07-02 23:47

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 23:54 | Created CONTRIBUTING.md | — | ~104 |
| 23:54 | Edited README.md | 1→3 lines | ~51 |
| 23:54 | Created .github/workflows/ci.yml | — | ~306 |
| 23:59 | Edited src/database.py | expanded (+9 lines) | ~248 |
| 00:00 | Edited src/database.py | modified create_all_tables() | ~260 |
| 00:03 | Edited src/database.py | modified upsert_player_enrichment() | ~258 |
| 01:30 | Edited etl/load_season_stats.py | modified run() | ~337 |
| 01:34 | Edited src/database.py | expanded (+9 lines) | ~248 |
| 01:34 | Edited src/database.py | modified create_all_tables() | ~260 |
| 01:37 | Edited src/database.py | 10→11 lines | ~154 |
| 01:37 | Edited etl/enrich_players.py | modified run() | ~80 |
| 01:39 | Created scripts/sync.py | — | ~350 |

## Session: 2026-07-02 02:09 (~/.claude audit session)

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 02:18 | Created .wolf/cerebrum.md | — | ~2480 |

## Session: 2026-07-03 21:31

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 21:31 | Edited app.py | inline fix | ~17 |
| 21:31 | Edited app.py | modified api_players_stats() | ~1579 |
| 21:32 | Created templates/index.html | — | ~3905 |
| 21:33 | Edited app.py | modified _toi_str() | ~91 |
| 21:34 | Edited app.py | inline fix | ~15 |
| 21:36 | Edited templates/index.html | render() → buildHeader() | ~22 |

## Session: 2026-07-13 00:11 (audit remediation, GitHub issue #7 → PRs #12/#13)

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 00:39 | Edited app.py | debug flag env-gated + B608 nosec query restructure | ~120 |
| 00:39 | Edited src/database.py | narrowed except Exception → sqlite3.OperationalError | ~10 |
| 00:39 | Created tests/conftest.py, test_app_helpers.py, test_database.py, test_enrich_players.py | 19 tests | ~700 |
| 00:39 | Edited requirements.txt | pytest uncommented, then moved to requirements-dev.txt after review | ~30 |
| 00:39 | Created requirements-dev.txt | bandit + pip-audit + pytest | ~20 |
| 00:39 | Created scripts/audit.sh | pip-audit + bandit CI gate | ~60 |
| 00:39 | Edited .github/workflows/ci.yml | added Tests + audit.sh steps | ~30 |
| 00:39 | Created .github/dependabot.yml | pip + github-actions ecosystems | ~40 |
| 00:39 | Edited README.md, CONTRIBUTING.md | documented new test/audit workflow | ~150 |
| 00:50 | Merged PR #12 (squash) | audit remediation bundle (M1/L1/M2/L2) | — |
| 00:52 | Merged PR #13 (squash) | stray cerebrum.md commit from chore/buglog-bug002 | — |
| 00:53 | Deleted origin/Sync-catchup-testing | confirmed with user; would have regressed bug-002 fix | — |

## Session: 2026-07-13 21:52 (sticky column-header bug fix, GitHub issue #20 → PR #22)

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 21:52 | Filed GitHub issue #20 | — | root-cause summary before code touched | ~250 |
| 21:52 | Created worktree .claude/worktrees/fix-20-sticky-headers | branch fix/20-sticky-column-headers | isolated from main | — |
| 21:53 | Edited templates/index.html | .table-wrap bounded scroll pane + thead th top:0 + --toolbar-height rename + resize listener | ~120 |
| 21:58 | Code review (subagent) | templates/index.html | 1 Important finding: missing height floor | — |
| 21:58 | Edited templates/index.html | added max(200px, ...) floor to .table-wrap height | ~15 |
| 21:59 | Pushed branch + opened PR #22 | Closes #20 | — |
