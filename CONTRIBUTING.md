# Contributing

Solo learning project using GitHub Flow:

1. Non-trivial changes get a GitHub issue filed first (see the global github-issue-first
   policy). Reference the issue number in the branch name where applicable, e.g.
   `fix/42-search-suggestion-filter-bug`.
2. Branch off `main`: `feature/…`, `fix/…`, or `chore/…`
3. Commit as you go
4. Push and open a pull request into `main`
5. Wait for the CI check to pass (syntax/import check, pytest suite, and a
   dependency-audit + SAST gate via `scripts/audit.sh` — see
   `.github/workflows/ci.yml`)
6. Merge via "Squash and merge", then delete the branch

`main` is protected — no direct pushes, even for the repo owner.
