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

## Session: 2026-07-25 (player profile overlay, GitHub issue #73)

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| — | Fixed stale desktop launcher | — | killed stale server process, rebuilt frontend (missing recharts dep) | — |
| — | Ran etl/compute_advanced_stats.py | data/nhl_stats.db | populated previously-empty player_season_advanced_stats (62,143 rows) + player_advanced_percentiles (12,826 rows); logged bug-016 | — |
| — | Logged bug-017 | — | cosmetic Vite base-path font 404, left unfixed (out of scope) | — |
| — | Brainstorm + grill + plan | docs/superpowers/specs/2026-07-25-player-profile-overlay-design.md, docs/superpowers/plans/2026-07-25-player-profile-overlay.md | design spec + 7-task TDD plan, approved | — |
| — | Filed GitHub issue #73 | — | tracks the plan | — |
| — | Created worktree .claude/worktrees/73-player-profile-overlay | branch feature/73-player-profile-overlay | isolated from main | — |
| — | Edited app.py | _fetch_players() now selects headshot_url/birth_city/birth_state_province/draft_* | ~80 |
| — | Edited frontend/src/lib/types.ts, mock-data.ts | Player type + mocks gain photo/bio/draft fields | ~50 |
| — | Created frontend/src/lib/teamBranding.ts | 32-team color map + NHL CDN logoUrl() (dark variant) | ~80 |
| — | Edited frontend/src/components/PlayerTable.tsx | whole-row click/keyboard trigger replaces CF%-cell-only trigger | ~90 |
| — | Renamed PlayerAdvancedPanel.tsx → PlayerProfilePanel.tsx | added photo/team-accent header, bio row, goalie/skater box score, progressive loading | ~280 |
| — | Edited frontend/src/App.tsx | merges Player bio row + PlayerStats row by player_id for the panel | ~40 |
| — | Manual verification (Playwright) | McDavid (photo+accent+advanced), Tanev (Undrafted), Markstrom (goalie box score, no advanced section) | all passed |

## Session: 2026-07-26/27 (launcher auto-sync, GitHub issue #76)

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| — | Investigated stale desktop app | — | local main had diverged from origin/main (never pulled PR #74/#75); confirmed via grep that app.py/App.tsx had zero trace of the profile-overlay feature | — |
| — | Brainstorm + grill + plan | docs/superpowers/specs/2026-07-26-launcher-auto-sync-design.md, docs/superpowers/plans/2026-07-26-launcher-auto-sync.md | design spec + 2-task plan, approved | — |
| — | Filed GitHub issue #76 | — | tracks the plan | — |
| — | Created worktree .claude/worktrees/76-launcher-auto-sync | branch feature/76-launcher-auto-sync, rebased onto local main to reconcile the divergence | isolated from main | — |
| — | Task 1: rewrote scripts/launch_app.sh | git auto-sync (fetch/rebase/stash/conflict-alert) + conditional frontend rebuild/restart | task review: Approved, one Important plan-mandated fix (kill -0 instead of is_up) applied with user sign-off | — |
| — | Found + fixed bug-018 | scripts/launch_app.sh | alert()'s osascript stdout was leaking into a captured shell variable, corrupting AFTER_SHA on any alert | — |
| — | Found + fixed bug-019 | scripts/launch_app.sh | `lsof \| head -n 1` under set -euo pipefail aborted the whole script when no server was listening (the common cold-start case) | — |
| — | Task 2: manual scenario verification | disposable throwaway clones, origin redirected to the worktree | 5/5 scenarios passed (fast-forward, rebase, dirty-tree, offline, conflict) | — |
| — | Final whole-branch review (Opus) | scripts/launch_app.sh + docs | Ready to merge: Yes, no Critical/Important issues; reconciled doc drift (kill -0 vs is_up) before merge | — |
| — | Pushed branch + opened PR #77, merged | — | Closes #76 | — |
| — | Resolved 3 Dependabot alerts | frontend/package-lock.json | brace-expansion, fast-uri, @hono/node-server — all transitive deps of `shadcn` CLI, not runtime code; `npm audit fix` (no --force) resolved all 3 | — |
| — | Filed + merged PR #78 | — | lockfile-only, no package.json edits, CI green | — |
| — | Discovered recurring rebase conflict | — | local main's OWN old doc commits (content-identical to already-squash-merged PRs, different SHAs) will conflict on every future auto-sync rebase; `git merge` tolerates this, `git rebase` does not | — |
| — | User ran `git reset --hard origin/main` | — | permanently ends the recurring conflict; confirmed zero divergence afterward | — |
| — | Learned (the hard way): local-only commits to main get discarded by reset | .wolf/cerebrum.md, .wolf/memory.md | first attempt at merge-conflict-resolution for these files was committed directly to local main (violating this project's own documented convention) and was wiped out by the reset since it was never pushed; redone via a proper worktree + PR (this session-reflect commit) | — |
