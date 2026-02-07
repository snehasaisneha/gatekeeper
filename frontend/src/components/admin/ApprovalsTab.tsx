import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { api, type AccessRequest, type App, ApiError } from '@/lib/api';
import { Loader2, Check, X, MessageSquare } from 'lucide-react';

interface ApprovalsTabProps {
  onRefresh?: () => void;
}

export function ApprovalsTab({ onRefresh }: ApprovalsTabProps) {
  const [requests, setRequests] = React.useState<AccessRequest[]>([]);
  const [apps, setApps] = React.useState<Map<string, App>>(new Map());
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [actionLoading, setActionLoading] = React.useState<string | null>(null);
  const [selectedRoles, setSelectedRoles] = React.useState<Record<string, string>>({});

  const loadRequests = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [requestsRes, appsRes] = await Promise.all([
        api.admin.listAllAccessRequests(),
        api.admin.listApps(),
      ]);
      setRequests(requestsRes);

      // Create a map of app slug to app for quick lookup
      const appMap = new Map<string, App>();
      appsRes.apps.forEach(app => appMap.set(app.slug, app));
      setApps(appMap);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load access requests');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  const handleApprove = async (request: AccessRequest) => {
    setActionLoading(request.id);
    try {
      const role = selectedRoles[request.id] || undefined;
      await api.admin.approveAccessRequest(request.app_slug, request.id, role);
      await loadRequests();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (request: AccessRequest) => {
    if (!confirm(`Are you sure you want to reject ${request.user_email}'s request for ${request.app_name}?`)) return;

    setActionLoading(request.id);
    try {
      await api.admin.rejectAccessRequest(request.app_slug, request.id);
      await loadRequests();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const getRolesForApp = (appSlug: string): string[] => {
    const app = apps.get(appSlug);
    if (!app || !app.roles) return [];
    return app.roles.split(',').map(r => r.trim()).filter(Boolean);
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Access Requests</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Access Requests</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-4">
            <p className="text-destructive">{error}</p>
            <Button onClick={loadRequests} variant="outline" className="mt-4">
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Access Requests</CardTitle>
        <CardDescription>
          {requests.length === 0
            ? 'No pending access requests'
            : `${requests.length} request${requests.length === 1 ? '' : 's'} waiting for review`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {requests.length === 0 ? (
          <p className="text-center text-muted-foreground py-8">No pending access requests</p>
        ) : (
          <div className="space-y-3">
            {requests.map((request) => {
              const roles = getRolesForApp(request.app_slug);
              return (
                <div
                  key={request.id}
                  className="flex flex-col p-4 rounded-lg border gap-4"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-medium truncate">{request.user_name || request.user_email}</p>
                        <Badge variant="outline">{request.app_name}</Badge>
                      </div>
                      {request.user_name && (
                        <p className="text-sm text-muted-foreground truncate">{request.user_email}</p>
                      )}
                      <p className="text-sm text-muted-foreground">
                        Requested {new Date(request.created_at).toLocaleDateString()}
                      </p>
                      {request.message && (
                        <div className="mt-2 flex items-start gap-2 text-sm text-muted-foreground">
                          <MessageSquare className="h-4 w-4 mt-0.5 flex-shrink-0" />
                          <p className="italic">"{request.message}"</p>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                    {roles.length > 0 && (
                      <div className="flex items-center gap-2">
                        <label className="text-sm text-muted-foreground whitespace-nowrap">Role:</label>
                        <select
                          className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
                          value={selectedRoles[request.id] || ''}
                          onChange={(e) => setSelectedRoles(prev => ({ ...prev, [request.id]: e.target.value }))}
                        >
                          <option value="">No role</option>
                          {roles.map(role => (
                            <option key={role} value={role}>{role}</option>
                          ))}
                        </select>
                      </div>
                    )}
                    <div className="flex items-center gap-2 sm:ml-auto">
                      <Button
                        size="sm"
                        onClick={() => handleApprove(request)}
                        disabled={actionLoading === request.id}
                      >
                        {actionLoading === request.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <>
                            <Check className="h-4 w-4 mr-1" />
                            Approve
                          </>
                        )}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleReject(request)}
                        disabled={actionLoading === request.id}
                      >
                        {actionLoading === request.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <>
                            <X className="h-4 w-4 mr-1" />
                            Reject
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
