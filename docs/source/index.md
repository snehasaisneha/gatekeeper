# Gatekeeper

Gatekeeper is a lightweight authentication gateway for protecting your internal tools. It sits in front of your apps and handles login, so you don't have to build auth into every service.

## Why Gatekeeper?

- **Simple**: One binary, one database file, deploy in 15 minutes
- **Multiple auth methods**: Google SSO, email codes, or passkeys—no passwords to manage
- **Self-hosted**: Your data stays on your servers, no vendor lock-in
- **Multi-app SSO**: One login works across all your internal tools

## How it works

Gatekeeper runs alongside nginx. When someone visits a protected app, nginx asks Gatekeeper "is this person allowed in?" If yes, they get through. If not, they're sent to sign in.

```
User → nginx → Gatekeeper: "Is this user authenticated?"
                    ↓
              Yes: Let them through
              No:  Redirect to sign-in page
```

Once signed in, users can access any app they've been granted access to without signing in again.

## Quick start

```bash
# Install
git clone https://github.com/snehasaisneha/gatekeeper
cd gatekeeper
uv sync

# Configure (copy and edit .env.example)
cp .env.example .env

# Set up database and create admin
uv run all-migrations
uv run gk users add --email you@example.com --admin --seeded

# Run
uv run gk ops serve
```

Then open `http://localhost:8000` and sign in with your email.

## What's next?

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} Getting Started
:link: getting-started/index
:link-type: doc

Install Gatekeeper, configure it, and protect your first app.
:::

:::{grid-item-card} Guides
:link: guides/index
:link-type: doc

Step-by-step instructions for common tasks like adding users and apps.
:::

:::{grid-item-card} Reference
:link: reference/index
:link-type: doc

CLI commands, environment variables, and configuration details.
:::

::::

```{toctree}
:hidden:
:maxdepth: 2

getting-started/index
guides/index
reference/index
```
