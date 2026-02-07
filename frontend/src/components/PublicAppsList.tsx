import * as React from 'react';
import { api, ApiError } from '@/lib/api';
import type { AppPublic, UserAppAccess } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, AppWindow, ExternalLink } from 'lucide-react';

interface PublicAppsListProps {
  userApps: UserAppAccess[];
}

export function PublicAppsList({ userApps }: PublicAppsListProps) {
  const [publicApps, setPublicApps] = React.useState<AppPublic[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const userAppSlugs = React.useMemo(
    () => new Set(userApps.map((a) => a.app_slug)),
    [userApps]
  );

  React.useEffect(() => {
    async function fetchPublicApps() {
      try {
        const apps = await api.auth.publicApps();
        setPublicApps(apps);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError('Failed to load public apps');
        }
      } finally {
        setIsLoading(false);
      }
    }

    fetchPublicApps();
  }, []);

  // Filter out apps the user already has explicit access to (shown in "Your Apps")
  const availableApps = publicApps.filter((app) => !userAppSlugs.has(app.slug));

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (availableApps.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground border rounded-lg bg-muted/30">
        <p>No additional public apps available.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border divide-y">
      {availableApps.map((app) => (
        <div
          key={app.slug}
          className="flex items-center justify-between p-4 gap-4"
        >
          <div className="flex items-start gap-3 min-w-0">
            <AppWindow className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="font-medium">{app.name}</p>
              {app.description && (
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {app.description}
                </p>
              )}
            </div>
          </div>

          <div className="flex-shrink-0">
            {app.app_url ? (
              <Button asChild size="sm">
                <a href={app.app_url} target="_blank" rel="noopener noreferrer">
                  Open
                  <ExternalLink className="h-4 w-4 ml-1" />
                </a>
              </Button>
            ) : (
              <Button variant="outline" size="sm" disabled>
                No URL
              </Button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
