## Frontend Design System

**IMPORTANT**: Before implementing ANY frontend feature, read `skills/gatekeeper-design-system/SKILL.md` for UI patterns and component usage.

Gatekeeper uses a **brutalist design aesthetic**:
- No border-radius on interactive elements (buttons, inputs, cards, badges)
- Thick borders (4px on primary elements, 2px on secondary)
- Uppercase headings with `tracking-wider`
- High contrast black/white with configurable accent color
- Border-based loading spinners (not Loader2 icon)

Key files:
- CSS System: `frontend/src/styles/globals.css`
- Components: `frontend/src/components/ui/`

---

- Delete unused or obsolete files when your changes make them irrelevant (refactors, feature removals, etc.), and revert files only when the change is yours or explicitly requested. If a git operation leaves you unsure about other agents' in-flight work, stop and coordinate instead of deleting.
- **Before attempting to delete a file to resolve a local type/lint failure, stop and ask the user.** Other agents are often editing adjacent files; deleting their work to silence an error is never acceptable without explicit approval.
- NEVER edit `.env` or any environment variable files—only the user may change them.
- Coordinate with other agents before removing their in-progress edits—don't revert or delete work you didn't author unless everyone agrees.
- Moving/renaming and restoring files is allowed.
- ABSOLUTELY NEVER run destructive git operations (e.g., `git reset --hard`, `rm`, `git checkout`/`git restore` to an older commit) unless the user gives an explicit, written instruction in this conversation. Treat these commands as catastrophic; if you are even slightly unsure, stop and ask before touching them. _(When working within Cursor or Codex Web, these git limitations do not apply; use the tooling's capabilities as needed.)_
- Never use `git restore` (or similar commands) to revert files you didn't author—coordinate with other agents instead so their in-progress work stays intact.
- Always double-check git status before any commit.
- Keep commits atomic: commit only the files you touched and list each path explicitly. For tracked files run `git commit -m "<scoped message>" -- path/to/file1 path/to/file2`. For brand-new files, use the one-liner `git restore --staged :/ && git add "path/to/file1" "path/to/file2" && git commit -m "<scoped message>" -- path/to/file1 path/to/file2`.
- Prefer conventional commit messages for all commits: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`. Keep messages scoped and specific to the atomic change being committed.
- Quote any git paths containing brackets or parentheses (e.g., `src/app/[candidate]/**`) when staging or committing so the shell does not treat them as globs or subshells.
- When running `git rebase`, avoid opening editors—export `GIT_EDITOR=:` and `GIT_SEQUENCE_EDITOR=:` (or pass `--no-edit`) so the default messages are used automatically.
- Never amend commits unless you have explicit written approval in the task thread.
- Never disable GPG signing (e.g., `commit.gpgsign=false`). If a commit fails due to signing issues, let it fail.

## Before Pushing

- **Always run `./scripts/ci-check.sh` before pushing.** This mirrors all CI checks locally: lint, tests, CLI smoke tests, frontend build, and docs build.
- If dependency manifests change, sync the lockfile before running `./scripts/ci-check.sh` so the committed manifest and resolved dependency graph stay aligned.
- The CLI entry point is `gk` with subcommands: `users`, `apps`, `ops`. There is no `db`, `user`, or `app` singular command.
- Environment variables have NO prefix (e.g., `SECRET_KEY`, not `GATEKEEPER_SECRET_KEY`). Check `.env.example` for correct names.

## Deployment Model

- Gatekeeper is deployed on a private host. A separate public routing host runs nginx and is the canonical public control point for TLS, proxy headers, auth redirects, and crawler controls.
- Prefer private-IP upstreams for internal proxy hops. Do not route internal auth validation through public hostnames when a private Gatekeeper address is available.
- In production, keep `PUBLIC_API_DOCS=false` unless public API docs are an intentional requirement.
- Trust forwarded client IP headers only from explicitly configured proxy IPs via `TRUSTED_PROXY_IPS`.

## Nginx Conventions

- Treat auth-host deindexing as a routing-layer concern. Public auth domains should emit `X-Robots-Tag: noindex, nofollow, noarchive`.
- Protected internal apps should emit both crawler controls and cache-busting headers:
  - `X-Robots-Tag: noindex, nofollow, noarchive`
  - `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`
  - `Pragma: no-cache`
  - `Expires: 0`
- Protected-app logout routes should redirect through the auth host signin flow rather than directly back to the app. This avoids stale protected pages after logout while preserving a clean re-login path.
- When changing nginx guidance, update the generated wizard output, deployment templates, and docs in the same change.

## Config And Source Of Truth

- The database is the runtime source of truth for approved domains, users, apps, and bans. Environment variables may seed defaults, but UI and docs should reflect DB-backed behavior.
- When adding or changing security-sensitive configuration, update `.env.example`, deployment docs, and relevant templates in the same commit series.

## Operational Hygiene

- This repo is operated with stepwise, org-by-org production rollouts across separate auth and app domains. Preserve rollout clarity in docs and generated nginx snippets.
- Do not leave temporary rollout helper files, ad hoc nginx snippets, or planning artifacts in the repo after the final commit unless they are intentional documentation.
