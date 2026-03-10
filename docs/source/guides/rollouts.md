# Rollout Checklist

Use this checklist when rolling Gatekeeper out for a new org or updating an existing auth/app setup.

## 1. Update Gatekeeper

- Pull the latest `main` on the Gatekeeper host.
- Run `uv sync`.
- Run `uv run all-migrations`.
- Rebuild the frontend with `npm -C frontend install && npm -C frontend run build`.
- Restart the Gatekeeper service.

## 2. Confirm Gatekeeper config

- Set `APP_URL` and `FRONTEND_URL` to the public auth hostname.
- Set `PUBLIC_API_DOCS=false` in production.
- Set `TRUSTED_PROXY_IPS` to only the nginx or routing tiers that are allowed to supply forwarded client IP headers.
- Keep `COOKIE_DOMAIN` on the shared parent domain when sibling-subdomain SSO is required.

## 3. Verify the Gatekeeper host

- Confirm `/robots.txt` is served by the auth frontend.
- Confirm `/api/v1/openapi.json` returns `{"detail":"Not found"}` in production.
- If Gatekeeper is behind a local nginx tier, verify its frontend and API proxy still work after deploy.

## 4. Update the public auth nginx

- Add `X-Robots-Tag: noindex, nofollow, noarchive` on the public auth server block.
- Keep forwarding headers explicit:
  - `Host`
  - `X-Real-IP`
  - `X-Forwarded-For`
  - `X-Forwarded-Proto`
- Reload nginx and verify:
  - `curl -I https://auth.example.com`
  - `curl https://auth.example.com/robots.txt`
  - `curl https://auth.example.com/api/v1/openapi.json`

## 5. Update each protected app nginx

- Add `X-Robots-Tag: noindex, nofollow, noarchive`.
- For static or cached apps, add:
  - `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`
  - `Pragma: no-cache`
  - `Expires: 0`
- Ensure the auth subrequest passes:
  - `Host`
  - `X-Real-IP`
  - `X-Forwarded-For`
  - `X-Forwarded-Proto`
  - `Cookie`
- Route `/logout` and `/signout` through Gatekeeper signout, then back to auth signin.

## 6. Verify browser flows

- Logged-out access redirects to Gatekeeper signin.
- Successful sign-in returns to the app.
- Pending approval still behaves correctly for non-approved users.
- Logout clears the session and lands in a clean signed-out state.

## 7. Verify admin warnings

- The superadmin page should stop warning once the auth host sends `X-Robots-Tag` and serves a blocking `robots.txt`.
- The add-user modal should warn on existing users and on internal-domain users.
- The create-app modal should reject reserved auth slugs and duplicate app slugs.

## 8. Request search removal

- Use Google Search Console removals for:
  - the auth hostname
  - any internal app hostname that has already been indexed
- Treat Search Console as acceleration only. The real controls are the auth/app noindex headers and `robots.txt`.
