import * as React from 'react';
import { api, ApiError, type DeploymentConfig } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, X, Copy, Check, ExternalLink, ArrowRight, ArrowLeft } from 'lucide-react';

interface CreateAppModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

type Step = 1 | 2;

export function CreateAppModal({ onClose, onSuccess }: CreateAppModalProps) {
  const [step, setStep] = React.useState<Step>(1);

  // Form state
  const [slug, setSlug] = React.useState('');
  const [name, setName] = React.useState('');
  const [description, setDescription] = React.useState('');
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Deployment config
  const [config, setConfig] = React.useState<DeploymentConfig | null>(null);
  const [isLoadingConfig, setIsLoadingConfig] = React.useState(true);

  // Copy state
  const [copiedId, setCopiedId] = React.useState<string | null>(null);

  // Nginx config inputs
  const [privateIp, setPrivateIp] = React.useState('127.0.0.1');
  const [appPort, setAppPort] = React.useState('3000');

  React.useEffect(() => {
    async function fetchConfig() {
      try {
        const deployConfig = await api.admin.getDeploymentConfig();
        setConfig(deployConfig);
      } catch {
        // Silently fail - instructions will show placeholder
      } finally {
        setIsLoadingConfig(false);
      }
    }
    fetchConfig();
  }, []);

  // Generate domain from slug and cookie_domain
  const getCookieDomain = () => config?.cookie_domain || '.example.com';
  const getBaseDomain = () => {
    const domain = getCookieDomain();
    return domain.startsWith('.') ? domain.slice(1) : domain;
  };
  const getAppDomain = () => {
    const baseDomain = getBaseDomain();
    return slug ? `${slug}.${baseDomain}` : null;
  };
  const getAppUrl = () => {
    const domain = getAppDomain();
    return domain ? `https://${domain}` : null;
  };

  const getGatekeeperUrl = () => config?.app_url || 'https://auth.example.com';

  const handleSubmit = async () => {
    if (!slug || !name) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await api.admin.createApp({
        slug,
        name,
        description: description || undefined,
        app_url: getAppUrl() || undefined,
      });
      onSuccess();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to create app');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNext = () => {
    if (!slug || !name) return;
    setStep(2);
  };

  const handleBack = () => {
    setStep(1);
  };

  const copyToClipboard = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  // Nginx config template
  const getNginxConfig = () => {
    const domain = getAppDomain() || 'myapp.example.com';
    const gkUrl = getGatekeeperUrl();

    return `server {
    listen 80;
    server_name ${domain};

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${domain};

    # SSL certificates (use certbot or your preferred method)
    ssl_certificate /etc/letsencrypt/live/${domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${domain}/privkey.pem;

    # Auth request to Gatekeeper
    auth_request /gatekeeper-auth;
    auth_request_set $auth_status $upstream_status;

    # Gatekeeper auth endpoint
    location = /gatekeeper-auth {
        internal;
        proxy_pass ${gkUrl}/api/v1/verify?app=${slug || 'myapp'};
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
        proxy_set_header X-Original-URI $request_uri;
        proxy_set_header X-Original-Host $host;
        proxy_set_header Cookie $http_cookie;
    }

    # Redirect to Gatekeeper login on 401
    error_page 401 = @gatekeeper_login;
    location @gatekeeper_login {
        return 302 ${gkUrl}/login?app=${slug || 'myapp'}&redirect=$scheme://$host$request_uri;
    }

    # Your app
    location / {
        proxy_pass http://${privateIp}:${appPort};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}`;
  };

  const installNginxCmd = `# Install Nginx (Ubuntu/Debian)
sudo apt update && sudo apt install -y nginx

# Or on macOS with Homebrew
brew install nginx`;

  const createSiteCmd = () => {
    const domain = getAppDomain() || 'myapp.example.com';
    return `# Create the config file
sudo nano /etc/nginx/sites-available/${domain}

# Paste the Nginx config below, then save and exit (Ctrl+X, Y, Enter)`;
  };

  const enableSiteCmd = () => {
    const domain = getAppDomain() || 'myapp.example.com';
    return `# Create symlink to enable the site
sudo ln -s /etc/nginx/sites-available/${domain} /etc/nginx/sites-enabled/

# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx`;
  };

  const sslCmd = () => {
    const domain = getAppDomain() || 'myapp.example.com';
    return `# Install Certbot if not already installed
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d ${domain}`;
  };

  const CodeBlock = ({
    code,
    id,
    title,
  }: {
    code: string;
    id: string;
    title?: string;
  }) => (
    <div className="relative">
      {title && (
        <div className="text-xs text-muted-foreground mb-1 font-medium">{title}</div>
      )}
      <div className="bg-muted rounded-md p-3 pr-10 font-mono text-sm overflow-x-auto">
        <pre className="whitespace-pre-wrap break-all">{code}</pre>
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="absolute top-1 right-1 h-7 w-7 p-0"
        onClick={() => copyToClipboard(code, id)}
      >
        {copiedId === id ? (
          <Check className="h-3.5 w-3.5 text-green-500" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </Button>
    </div>
  );

  const canProceed = slug.length > 0 && name.length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-background border rounded-lg shadow-lg w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-muted-foreground hover:text-foreground z-10"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Header with step indicator */}
        <div className="p-6 pb-4">
          <h2 className="text-lg font-semibold">Create New App</h2>
          <div className="flex items-center gap-2 mt-3">
            <div
              className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium ${
                step === 1
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-primary/20 text-primary'
              }`}
            >
              1
            </div>
            <span className={`text-sm ${step === 1 ? 'font-medium' : 'text-muted-foreground'}`}>
              App Details
            </span>
            <div className="w-8 h-px bg-border" />
            <div
              className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium ${
                step === 2
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              }`}
            >
              2
            </div>
            <span className={`text-sm ${step === 2 ? 'font-medium' : 'text-muted-foreground'}`}>
              Nginx Setup
            </span>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 pb-6">
          {step === 1 && (
            <div className="space-y-4">
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label htmlFor="slug">Slug</Label>
                <Input
                  id="slug"
                  value={slug}
                  onChange={(e) =>
                    setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))
                  }
                  placeholder="my-app"
                  autoFocus
                />
                <p className="text-xs text-muted-foreground">
                  Lowercase, alphanumeric and hyphens only
                </p>

                {/* URL Preview */}
                {!isLoadingConfig && (
                  <div className="mt-3 p-3 bg-muted/50 rounded-md border">
                    <p className="text-xs text-muted-foreground mb-1">Your app will be available at:</p>
                    <p className="font-mono text-sm">
                      {slug ? (
                        <span className="text-foreground">
                          https://<span className="text-primary font-semibold">{slug}</span>.{getBaseDomain()}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">
                          https://<span className="italic">your-slug</span>.{getBaseDomain()}
                        </span>
                      )}
                    </p>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="name">Display Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My App"
                />
                <p className="text-xs text-muted-foreground">
                  The name shown to users in the dashboard
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description (optional)</Label>
                <Input
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="A brief description of your app"
                />
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6">
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {isLoadingConfig ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : (
                <>
                  {/* Summary card */}
                  <div className="bg-primary/5 rounded-lg p-4 border border-primary/20">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium">{name}</p>
                        <p className="text-sm text-muted-foreground font-mono">{getAppUrl()}</p>
                      </div>
                      <a
                        href="https://gatekeeper-gk.readthedocs.io/en/latest/getting-started/first-app.html"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-primary hover:underline flex items-center gap-1"
                      >
                        Full docs <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  </div>

                  {/* App-specific config inputs */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="private-ip">Private IP / Hostname</Label>
                      <Input
                        id="private-ip"
                        value={privateIp}
                        onChange={(e) => setPrivateIp(e.target.value)}
                        placeholder="127.0.0.1"
                      />
                      <p className="text-xs text-muted-foreground">
                        Where your app runs (localhost or internal IP)
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="app-port">App Port</Label>
                      <Input
                        id="app-port"
                        value={appPort}
                        onChange={(e) => setAppPort(e.target.value)}
                        placeholder="3000"
                      />
                      <p className="text-xs text-muted-foreground">Port your app listens on</p>
                    </div>
                  </div>

                  {/* Step 1: Install Nginx */}
                  <div className="space-y-2">
                    <h4 className="font-medium text-sm">1. Install Nginx</h4>
                    <CodeBlock code={installNginxCmd} id="install" />
                  </div>

                  {/* Step 2: Create config file */}
                  <div className="space-y-2">
                    <h4 className="font-medium text-sm">2. Create Configuration File</h4>
                    <CodeBlock code={createSiteCmd()} id="create-site" />
                  </div>

                  {/* Step 3: Nginx config */}
                  <div className="space-y-2">
                    <h4 className="font-medium text-sm">3. Nginx Configuration</h4>
                    <p className="text-xs text-muted-foreground">
                      Copy this configuration into your site file:
                    </p>
                    <CodeBlock code={getNginxConfig()} id="nginx-config" />
                  </div>

                  {/* Step 4: Enable site */}
                  <div className="space-y-2">
                    <h4 className="font-medium text-sm">4. Enable Site & Reload</h4>
                    <CodeBlock code={enableSiteCmd()} id="enable-site" />
                  </div>

                  {/* Step 5: SSL */}
                  <div className="space-y-2">
                    <h4 className="font-medium text-sm">5. Set Up SSL (Recommended)</h4>
                    <CodeBlock code={sslCmd()} id="ssl" />
                  </div>

                  <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                    <p className="text-sm text-amber-800 dark:text-amber-200">
                      <strong>Note:</strong> Make sure your DNS points{' '}
                      <code className="bg-amber-100 dark:bg-amber-900 px-1 rounded text-xs">
                        {getAppDomain()}
                      </code>{' '}
                      to your server's IP address before setting up SSL.
                    </p>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer with navigation */}
        <div className="border-t p-4 flex justify-between">
          {step === 1 ? (
            <>
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={handleNext} disabled={!canProceed}>
                Next: Nginx Setup
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={handleBack} disabled={isSubmitting}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
              <Button onClick={handleSubmit} disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Create App
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
