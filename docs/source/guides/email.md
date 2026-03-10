# Email setup

Gatekeeper sends emails for login codes and notifications. This guide covers setting up AWS SES and SMTP.

## Choosing a provider

Gatekeeper supports two email providers:

| Provider | Best for | Setup complexity |
|----------|----------|------------------|
| AWS SES | Production, high volume | Medium (requires AWS account, domain verification) |
| SMTP | Development, small teams | Low (works with Gmail, any SMTP server) |

## AWS SES setup

### 1. Create SES credentials

In the AWS Console:

1. Go to **SES** → **SMTP Settings**
2. Click **Create SMTP Credentials**
3. Save the access key ID and secret

Or use IAM credentials with SES permissions.

### 2. Verify your domain

SES requires domain verification to send emails:

1. Go to **SES** → **Verified Identities**
2. Click **Create Identity** → **Domain**
3. Add the DNS records SES provides
4. Wait for verification (usually a few minutes)

### 3. Request production access

New SES accounts are in sandbox mode (can only send to verified emails). To send to anyone:

1. Go to **SES** → **Account Dashboard**
2. Click **Request Production Access**
3. Fill out the form explaining your use case

### 4. Configure Gatekeeper

```bash
EMAIL_PROVIDER=ses
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
SES_FROM_EMAIL=noreply@yourdomain.com
```

The `SES_FROM_EMAIL` address must be from your verified domain.

## SMTP setup

### Gmail

1. Enable 2-factor authentication on your Google account
2. Generate an [App Password](https://support.google.com/accounts/answer/185833)
3. Configure Gatekeeper:

```bash
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=you@gmail.com
```

### Other SMTP servers

```bash
EMAIL_PROVIDER=smtp
SMTP_HOST=mail.example.com
SMTP_PORT=587
SMTP_USER=user
SMTP_PASSWORD=password
SMTP_FROM_EMAIL=noreply@example.com
```

Common ports:
- **587** — TLS (recommended)
- **465** — SSL
- **25** — Unencrypted (not recommended)

## Testing email

Verify your email configuration works:

```bash
uv run gk ops test-email --to you@example.com
```

This sends a test email. Check your inbox (and spam folder).

## Troubleshooting

### Emails going to spam

- Use a verified domain (not a free email provider)
- Set up SPF, DKIM, and DMARC records
- Avoid spammy subject lines

### Connection refused

- Check firewall rules allow outbound SMTP
- Verify the host and port are correct
- Some cloud providers block port 25

### Authentication failed

- Double-check username and password
- For Gmail, ensure you're using an App Password
- For SES, verify IAM permissions include `ses:SendEmail`

### Rate limiting

SES and some SMTP providers have sending limits:

- SES sandbox: 200 emails/day
- SES production: Starts at 50,000/day
- Gmail: 500 emails/day

For production, request higher SES limits or use a dedicated email service.
