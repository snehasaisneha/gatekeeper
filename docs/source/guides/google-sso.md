# Google SSO Setup

Enable "Sign in with Google" for your Gatekeeper deployment. Users can authenticate with their Google account instead of email OTP codes.

## Prerequisites

- A Google Cloud Platform account
- A verified domain (for production)

## Step 1: Create OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Select or create a project
3. Click **Create Credentials** → **OAuth client ID**
4. Select **Web application** as the application type
5. Give it a name (e.g., "Gatekeeper Auth")

## Step 2: Configure OAuth settings

### Authorized JavaScript origins

Add your Gatekeeper frontend URL:

```
https://auth.yourdomain.com
```

### Authorized redirect URIs

Add the OAuth callback endpoint:

```
https://auth.yourdomain.com/api/v1/auth/google/callback
```

:::{important}
The redirect URI must point to your **backend API**, not your frontend. It always ends with `/api/v1/auth/google/callback`.
:::

## Step 3: Configure OAuth consent screen

Before users can sign in, you need to configure the OAuth consent screen:

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** (or **Internal** for Google Workspace)
3. Fill in required fields:
   - App name: Your app name
   - User support email: Your email
   - Developer contact: Your email
4. Add scopes: `email`, `profile`, `openid`
5. Add test users if in testing mode

## Step 4: Add environment variables

After creating the OAuth client, copy the Client ID and Client Secret to your `.env` file:

```bash
GOOGLE_CLIENT_ID=123456789-abcdef.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret
```

:::{warning}
Keep your client secret secure. Never commit it to version control.
:::

## Step 5: Verify setup

1. Restart Gatekeeper to load the new configuration
2. Visit your sign-in page
3. The "Continue with Google" button should now appear
4. Click it to test the flow

## How it works

1. User clicks "Continue with Google"
2. User is redirected to Google's OAuth page
3. After authentication, Google redirects back with an authorization code
4. Gatekeeper exchanges the code for user info (email, name)
5. Based on the email domain:
   - **Approved domain**: User is auto-approved and signed in
   - **Other domain**: User account is created as pending, awaiting admin approval

## Troubleshooting

### "Google OAuth is not configured" error

Make sure both `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set and Gatekeeper was restarted.

### Redirect URI mismatch

The redirect URI in Google Console must exactly match:
```
https://your-app-url/api/v1/auth/google/callback
```

Where `your-app-url` matches your `APP_URL` environment variable.

### "Access blocked: This app's request is invalid"

Check that:
- The OAuth consent screen is configured
- Your redirect URI is added to the authorized redirect URIs
- You're using the correct client ID and secret

### Users from approved domains still pending

Make sure the domain is added to the approved domains list:

```bash
gk domains add --domain yourdomain.com
```

Or via the admin UI: **Settings** → **Domains** → **Add Domain**
