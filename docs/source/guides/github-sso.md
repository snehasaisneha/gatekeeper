# GitHub SSO

Enable "Sign in with GitHub" for your Gatekeeper instance.

## Overview

GitHub SSO allows users to sign in using their GitHub account. Gatekeeper checks **all verified emails** linked to the GitHub account, so users don't need to set their work email as their primary GitHub email.

## Setup

### 1. Create a GitHub OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click **OAuth Apps** → **New OAuth App**
3. Fill in the details:

| Field | Value |
|-------|-------|
| Application name | Your app name (e.g., "Gatekeeper") |
| Homepage URL | `https://auth.yourdomain.com` |
| Authorization callback URL | `https://auth.yourdomain.com/api/v1/auth/github/callback` |

4. Click **Register application**
5. Copy the **Client ID**
6. Click **Generate a new client secret** and copy it

### 2. Configure Gatekeeper

Add to your `.env`:

```bash
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
```

Restart Gatekeeper. The GitHub sign-in button will appear automatically.

## How it works

1. User clicks "Sign in with GitHub"
2. GitHub asks user to authorize Gatekeeper
3. Gatekeeper receives all verified emails from the user's GitHub account
4. If any email matches an approved domain → user is auto-approved
5. If no match → user sees an error asking them to link their org email or use email/passkey

## Multiple emails

GitHub users often have multiple emails linked:
- Personal email (primary)
- Work email (secondary)
- Old university email

Gatekeeper checks **all verified emails**, not just the primary. If a user has `work@company.com` linked to their GitHub (even as secondary), and `company.com` is an approved domain, they'll be auto-approved.

## Troubleshooting

**"No approved email found" error**

The user's GitHub account doesn't have any email from an approved domain. They should:
1. Add their work email to GitHub: Settings → Emails → Add email
2. Verify the email
3. Try signing in again

Or use email OTP / passkey instead.

**OAuth errors**

- Verify the callback URL matches exactly: `https://your-domain/api/v1/auth/github/callback`
- Check that client ID and secret are correct
- Ensure the OAuth app is not suspended
