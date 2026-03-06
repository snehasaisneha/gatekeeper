import * as React from 'react';
import { api, ApiError, type DeploymentConfig } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { X, Copy, Check, ExternalLink, ArrowRight, ArrowLeft, AppWindow } from 'lucide-react';

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

  // Nginx config template - matches real production implementation
  const getNginxConfig = () => {
    const domain = getAppDomain() || 'myapp.example.com';
    const gkUrl = getGatekeeperUrl();
    // Extract just the host from gkUrl for redirects
    const gkHost = gkUrl.replace(/^https?:\/\//, '').replace(/\/.*$/, '');

    return `server {
    listen 80;
    server_name ${domain};

    # Gatekeeper auth validation endpoint
    location = /_gk/validate {
        internal;
        proxy_pass ${gkUrl}/api/v1/auth/validate;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
        proxy_set_header X-Original-URI $request_uri;
        proxy_set_header X-GK-App ${slug || 'myapp'};
        proxy_set_header Cookie $http_cookie;
    }

    # Logout: redirect to Gatekeeper signout with return URL
    location = /logout {
        return 302 https://${gkHost}/signout?redirect=https://$host/;
    }
    location = /signout {
        return 302 https://${gkHost}/signout?redirect=https://$host/;
    }

    # All requests: validate auth, then proxy to your app
    location / {
        auth_request /_gk/validate;
        auth_request_set $auth_user $upstream_http_x_auth_user;

        proxy_pass http://${privateIp}:${appPort};
        proxy_set_header Host $host;
        proxy_set_header X-Auth-User $auth_user;
        proxy_set_header X-Forwarded-Proto $scheme;

        error_page 401 = @login;
        error_page 403 = @denied;
    }

    # Redirect to login on 401 (not authenticated)
    location @login {
        return 302 https://${gkHost}/signin?redirect=$scheme://$host$request_uri;
    }

    # Redirect to request access on 403 (no permission)
    location @denied {
        return 302 https://${gkHost}/request-access?app=${slug || 'myapp'};
    }
}

}`;
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
        <div className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">{title}</div>
      )}
      <div className="bg-gray-100 border-2 border-black p-3 pr-10 font-mono text-sm overflow-x-auto">
        <pre className="whitespace-pre-wrap break-all">{code}</pre>
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-1 right-1 h-7 w-7"
        onClick={() => copyToClipboard(code, id)}
      >
        {copiedId === id ? (
          <Check className="h-3.5 w-3.5 text-green-600" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </Button>
    </div>
  );

  const canProceed = slug.length > 0 && name.length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      <div className="relative bg-white border-4 border-black w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="bg-black text-white p-4 flex justify-between items-center">
          <h2 className="font-bold uppercase tracking-wider flex items-center gap-2">
            <AppWindow className="h-5 w-5" />
            Create New App
          </h2>
          <button
            onClick={onClose}
            className="text-white hover:text-gray-300"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Step Indicator */}
        <div className="p-4 border-b-4 border-black flex items-center gap-2">
          <div
            className={`flex items-center justify-center w-6 h-6 text-xs font-bold ${
              step === 1
                ? 'bg-black text-white'
                : 'bg-gray-200 text-black'
            }`}
          >
            1
          </div>
          <span className={`text-sm font-bold uppercase tracking-wider ${step === 1 ? '' : 'text-gray-500'}`}>
            App Details
          </span>
          <div className="w-8 h-0.5 bg-black" />
          <div
            className={`flex items-center justify-center w-6 h-6 text-xs font-bold ${
              step === 2
                ? 'bg-black text-white'
                : 'bg-gray-200 text-gray-500'
            }`}
          >
            2
          </div>
          <span className={`text-sm font-bold uppercase tracking-wider ${step === 2 ? '' : 'text-gray-500'}`}>
            Nginx Setup
          </span>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {step === 1 && (
            <div className="space-y-4">
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider">Slug</label>
                <Input
                  value={slug}
                  onChange={(e) =>
                    setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))
                  }
                  placeholder="my-app"
                  autoFocus
                  slim
                />
                <p className="text-xs text-gray-500">
                  Lowercase, alphanumeric and hyphens only
                </p>

                {/* URL Preview */}
                {!isLoadingConfig && (
                  <div className="mt-3 p-3 bg-gray-100 border-2 border-black">
                    <p className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">
                      Your app will be available at:
                    </p>
                    <p className="font-mono text-sm">
                      {slug ? (
                        <span>
                          https://<span className="font-bold">{slug}</span>.{getBaseDomain()}
                        </span>
                      ) : (
                        <span className="text-gray-400">
                          https://<span className="italic">your-slug</span>.{getBaseDomain()}
                        </span>
                      )}
                    </p>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider">Display Name</label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My App"
                  slim
                />
                <p className="text-xs text-gray-500">
                  The name shown to users in the dashboard
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider">Description (optional)</label>
                <Input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="A brief description of your app"
                  slim
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
                  <div className="inline-block w-6 h-6 border-4 border-black border-t-transparent animate-spin" />
                </div>
              ) : (
                <>
                  {/* Summary card */}
                  <div className="bg-gray-100 border-2 border-black p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-bold">{name}</p>
                        <p className="text-sm text-gray-500 font-mono">{getAppUrl()}</p>
                      </div>
                      <a
                        href="https://gatekeeper-gk.readthedocs.io/en/latest/getting-started/first-app.html"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-bold uppercase tracking-wider hover:underline flex items-center gap-1"
                      >
                        Full docs <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  </div>

                  {/* DNS instruction */}
                  <div className="bg-orange-100 border-2 border-orange-500 p-3">
                    <p className="text-sm">
                      <strong>First:</strong> Point{' '}
                      <code className="bg-orange-200 px-1 font-mono text-xs">
                        {getAppDomain()}
                      </code>{' '}
                      to your server's IP address in DNS.
                    </p>
                  </div>

                  {/* App-specific config inputs */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-wider">
                        Private IP / Hostname
                      </label>
                      <Input
                        value={privateIp}
                        onChange={(e) => setPrivateIp(e.target.value)}
                        placeholder="127.0.0.1"
                        slim
                      />
                      <p className="text-xs text-gray-500">
                        Internal IP where your app runs
                      </p>
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-wider">
                        App Port
                      </label>
                      <Input
                        value={appPort}
                        onChange={(e) => setAppPort(e.target.value)}
                        placeholder="3000"
                        slim
                      />
                      <p className="text-xs text-gray-500">Port your app listens on</p>
                    </div>
                  </div>

                  <div className="bg-blue-100 border-2 border-blue-500 p-3">
                    <p className="text-sm">
                      <strong>Serving static files?</strong> Run a simple server in your docs folder:
                    </p>
                    <div className="mt-2 space-y-1">
                      <CodeBlock code="python -m http.server 8000" id="static-python" />
                      <p className="text-xs text-blue-600 text-center">or</p>
                      <CodeBlock code="npx serve -p 8000" id="static-npx" />
                    </div>
                  </div>

                  {/* Step 1: Install Nginx */}
                  <div className="space-y-3">
                    <h3 className="font-bold uppercase tracking-wider">1. Install Nginx</h3>
                    <p className="text-sm text-gray-500">Update packages and install nginx:</p>
                    <CodeBlock code="sudo apt update && sudo apt install -y nginx" id="install" />
                  </div>

                  {/* Step 2: Create config file */}
                  <div className="space-y-3">
                    <h3 className="font-bold uppercase tracking-wider">2. Create Configuration File</h3>
                    <p className="text-sm text-gray-500">Open the nginx config file:</p>
                    <CodeBlock code={`sudo nano /etc/nginx/sites-available/${getAppDomain()}`} id="create-site" />
                  </div>

                  {/* Step 3: Nginx config */}
                  <div className="space-y-3">
                    <h3 className="font-bold uppercase tracking-wider">3. Nginx Configuration</h3>
                    <p className="text-sm text-gray-500">
                      Paste this configuration, then save with Ctrl+X, Y, Enter:
                    </p>
                    <CodeBlock code={getNginxConfig()} id="nginx-config" />
                  </div>

                  {/* Step 4: Enable site */}
                  <div className="space-y-3">
                    <h3 className="font-bold uppercase tracking-wider">4. Enable Site</h3>

                    <p className="text-sm text-gray-500">Create symlink to enable the site:</p>
                    <CodeBlock code={`sudo ln -s /etc/nginx/sites-available/${getAppDomain()} /etc/nginx/sites-enabled/`} id="symlink" />

                    <p className="text-sm text-gray-500">Test nginx configuration:</p>
                    <CodeBlock code="sudo nginx -t" id="nginx-test" />

                    <p className="text-sm text-gray-500">Reload nginx:</p>
                    <CodeBlock code="sudo systemctl reload nginx" id="nginx-reload" />
                  </div>

                  {/* Step 5: SSL */}
                  <div className="space-y-3">
                    <h3 className="font-bold uppercase tracking-wider">5. Set Up SSL</h3>

                    <p className="text-sm text-gray-500">Install certbot:</p>
                    <CodeBlock code="sudo apt install -y certbot" id="certbot-install" />

                    <p className="text-sm text-gray-500">Get SSL certificate:</p>
                    <CodeBlock code={`sudo certbot --nginx -d ${getAppDomain()}`} id="certbot-run" />
                  </div>

                  {/* Logout note */}
                  <div className="bg-gray-100 border-2 border-black p-3">
                    <p className="text-sm text-gray-600">
                      <strong className="text-black">Logout:</strong> Link to{' '}
                      <code className="bg-gray-200 px-1 font-mono text-xs">/logout</code>,{' '}
                      <code className="bg-gray-200 px-1 font-mono text-xs">/signout</code>, or{' '}
                      <code className="bg-gray-200 px-1 font-mono text-xs">/_gk/logout</code>{' '}
                      to sign users out via Gatekeeper.
                    </p>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t-4 border-black p-4 flex justify-between">
          {step === 1 ? (
            <>
              <Button variant="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={handleNext} disabled={!canProceed}>
                Next: Nginx Setup
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </>
          ) : (
            <>
              <Button variant="secondary" onClick={handleBack} disabled={isSubmitting}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
              <Button onClick={handleSubmit} disabled={isSubmitting}>
                {isSubmitting && (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin mr-2" />
                )}
                Create App
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
