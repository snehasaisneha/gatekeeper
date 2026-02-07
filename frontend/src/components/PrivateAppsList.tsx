import * as React from 'react';
import { api, ApiError } from '@/lib/api';
import type { AppPublic } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Lock, Send, CheckCircle } from 'lucide-react';

export function PrivateAppsList() {
  const [apps, setApps] = React.useState<AppPublic[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [submittingSlug, setSubmittingSlug] = React.useState<string | null>(null);
  const [requestedSlugs, setRequestedSlugs] = React.useState<Set<string>>(new Set());

  React.useEffect(() => {
    async function fetchPrivateApps() {
      try {
        const privateApps = await api.auth.privateApps();
        setApps(privateApps);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError('Failed to load apps');
        }
      } finally {
        setIsLoading(false);
      }
    }

    fetchPrivateApps();
  }, []);

  async function handleRequestAccess(slug: string) {
    setSubmittingSlug(slug);
    setError(null);
    try {
      await api.auth.requestAppAccess(slug);
      setRequestedSlugs((prev) => new Set([...prev, slug]));
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to submit request');
      }
    } finally {
      setSubmittingSlug(null);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (apps.length === 0 && !error) {
    return (
      <div className="text-center py-8 text-muted-foreground border rounded-lg bg-muted/30">
        <p>No private apps available to request access.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {apps.length > 0 && (
        <div className="rounded-lg border divide-y">
          {apps.map((app) => (
            <div
              key={app.slug}
              className="flex items-center justify-between p-4 gap-4"
            >
              <div className="flex items-start gap-3 min-w-0">
                <Lock className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
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
                {requestedSlugs.has(app.slug) ? (
                  <Button variant="outline" size="sm" disabled>
                    <CheckCircle className="h-4 w-4 mr-1" />
                    Requested
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleRequestAccess(app.slug)}
                    disabled={submittingSlug === app.slug}
                  >
                    {submittingSlug === app.slug ? (
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4 mr-1" />
                    )}
                    Request Access
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
