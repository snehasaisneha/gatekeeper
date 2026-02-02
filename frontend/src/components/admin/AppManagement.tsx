import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { api, type App, type AppDetail, type AccessRequest, ApiError } from '@/lib/api';
import {
  Loader2,
  Plus,
  Trash2,
  Users,
  ChevronDown,
  ChevronUp,
  UserPlus,
  UserMinus,
  Check,
  X,
  AppWindow,
} from 'lucide-react';

interface AppManagementProps {
  onRefresh?: () => void;
}

export function AppManagement({ onRefresh }: AppManagementProps) {
  const [apps, setApps] = React.useState<App[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Create app form
  const [showCreateForm, setShowCreateForm] = React.useState(false);
  const [newSlug, setNewSlug] = React.useState('');
  const [newName, setNewName] = React.useState('');
  const [isCreating, setIsCreating] = React.useState(false);
  const [createError, setCreateError] = React.useState<string | null>(null);

  // Expanded app details
  const [expandedApp, setExpandedApp] = React.useState<string | null>(null);
  const [appDetail, setAppDetail] = React.useState<AppDetail | null>(null);
  const [accessRequests, setAccessRequests] = React.useState<AccessRequest[]>([]);
  const [isLoadingDetail, setIsLoadingDetail] = React.useState(false);

  // Grant access form
  const [grantEmail, setGrantEmail] = React.useState('');
  const [grantRole, setGrantRole] = React.useState('');
  const [isGranting, setIsGranting] = React.useState(false);

  // Action loading states
  const [actionLoading, setActionLoading] = React.useState<string | null>(null);

  const loadApps = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.admin.listApps();
      setApps(response.apps);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load apps');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadApps();
  }, [loadApps]);

  const loadAppDetail = async (slug: string) => {
    setIsLoadingDetail(true);
    try {
      const [detail, requests] = await Promise.all([
        api.admin.getApp(slug),
        api.admin.listAccessRequests(slug, 'pending'),
      ]);
      setAppDetail(detail);
      setAccessRequests(requests);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleToggleExpand = async (slug: string) => {
    if (expandedApp === slug) {
      setExpandedApp(null);
      setAppDetail(null);
      setAccessRequests([]);
    } else {
      setExpandedApp(slug);
      await loadAppDetail(slug);
    }
  };

  const handleCreateApp = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    setCreateError(null);

    try {
      await api.admin.createApp(newSlug, newName);
      setNewSlug('');
      setNewName('');
      setShowCreateForm(false);
      await loadApps();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setCreateError(err.message);
      } else {
        setCreateError('Failed to create app');
      }
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteApp = async (slug: string) => {
    if (!confirm(`Are you sure you want to delete the app "${slug}"? This will remove all access grants.`)) return;

    setActionLoading(`delete-${slug}`);
    try {
      await api.admin.deleteApp(slug);
      if (expandedApp === slug) {
        setExpandedApp(null);
        setAppDetail(null);
      }
      await loadApps();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleGrantAccess = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!expandedApp) return;

    setIsGranting(true);
    try {
      await api.admin.grantAccess(expandedApp, grantEmail, grantRole || undefined);
      setGrantEmail('');
      setGrantRole('');
      await loadAppDetail(expandedApp);
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setIsGranting(false);
    }
  };

  const handleRevokeAccess = async (email: string) => {
    if (!expandedApp) return;
    if (!confirm(`Revoke access for ${email}?`)) return;

    setActionLoading(`revoke-${email}`);
    try {
      await api.admin.revokeAccess(expandedApp, email);
      await loadAppDetail(expandedApp);
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleApproveRequest = async (requestId: string) => {
    if (!expandedApp) return;

    setActionLoading(`approve-${requestId}`);
    try {
      await api.admin.approveAccessRequest(expandedApp, requestId);
      await loadAppDetail(expandedApp);
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectRequest = async (requestId: string) => {
    if (!expandedApp) return;

    setActionLoading(`reject-${requestId}`);
    try {
      await api.admin.rejectAccessRequest(expandedApp, requestId);
      await loadAppDetail(expandedApp);
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setActionLoading(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin" />
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

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AppWindow className="h-5 w-5" />
          <span className="font-medium">Apps ({apps.length})</span>
        </div>
        <Button size="sm" onClick={() => setShowCreateForm(!showCreateForm)}>
          <Plus className="h-4 w-4 mr-1" />
          Add App
        </Button>
      </div>

      {showCreateForm && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Create New App</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateApp} className="space-y-4">
              {createError && (
                <Alert variant="destructive">
                  <AlertDescription>{createError}</AlertDescription>
                </Alert>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="app-slug">Slug</Label>
                  <Input
                    id="app-slug"
                    value={newSlug}
                    onChange={(e) => setNewSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                    placeholder="my-app"
                    required
                  />
                  <p className="text-xs text-muted-foreground">Lowercase, alphanumeric and hyphens only</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="app-name">Display Name</Label>
                  <Input
                    id="app-name"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="My App"
                    required
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={isCreating}>
                  {isCreating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                  Create App
                </Button>
                <Button type="button" variant="outline" onClick={() => setShowCreateForm(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {apps.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          No apps configured. Create one to get started.
        </div>
      ) : (
        <div className="space-y-2">
          {apps.map((app) => (
            <div key={app.slug} className="border rounded-lg">
              <div
                className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted/50"
                onClick={() => handleToggleExpand(app.slug)}
              >
                <div className="flex items-center gap-3">
                  <AppWindow className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="font-medium">{app.name}</p>
                    <p className="text-sm text-muted-foreground">{app.slug}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteApp(app.slug);
                    }}
                    disabled={actionLoading === `delete-${app.slug}`}
                    className="text-destructive hover:text-destructive"
                  >
                    {actionLoading === `delete-${app.slug}` ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                  {expandedApp === app.slug ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
              </div>

              {expandedApp === app.slug && (
                <div className="border-t p-4 bg-muted/30">
                  {isLoadingDetail ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="h-6 w-6 animate-spin" />
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* Pending Access Requests */}
                      {accessRequests.length > 0 && (
                        <div>
                          <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
                            <Badge variant="warning">{accessRequests.length}</Badge>
                            Pending Access Requests
                          </h4>
                          <div className="space-y-2">
                            {accessRequests.map((request) => (
                              <div
                                key={request.id}
                                className="flex items-center justify-between p-2 bg-background rounded border"
                              >
                                <div>
                                  <p className="font-medium">{request.user_email}</p>
                                  {request.message && (
                                    <p className="text-sm text-muted-foreground">"{request.message}"</p>
                                  )}
                                </div>
                                <div className="flex gap-1">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => handleApproveRequest(request.id)}
                                    disabled={actionLoading === `approve-${request.id}`}
                                    className="text-green-600 hover:text-green-600"
                                  >
                                    {actionLoading === `approve-${request.id}` ? (
                                      <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                      <Check className="h-4 w-4" />
                                    )}
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => handleRejectRequest(request.id)}
                                    disabled={actionLoading === `reject-${request.id}`}
                                    className="text-destructive hover:text-destructive"
                                  >
                                    {actionLoading === `reject-${request.id}` ? (
                                      <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                      <X className="h-4 w-4" />
                                    )}
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Grant Access Form */}
                      <div>
                        <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
                          <UserPlus className="h-4 w-4" />
                          Grant Access
                        </h4>
                        <form onSubmit={handleGrantAccess} className="flex gap-2">
                          <Input
                            value={grantEmail}
                            onChange={(e) => setGrantEmail(e.target.value)}
                            placeholder="user@example.com"
                            type="email"
                            required
                            className="flex-1"
                          />
                          <Input
                            value={grantRole}
                            onChange={(e) => setGrantRole(e.target.value)}
                            placeholder="Role (optional)"
                            className="w-32"
                          />
                          <Button type="submit" disabled={isGranting}>
                            {isGranting ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Grant'}
                          </Button>
                        </form>
                      </div>

                      {/* Users with Access */}
                      <div>
                        <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
                          <Users className="h-4 w-4" />
                          Users with Access ({appDetail?.users.length || 0})
                        </h4>
                        {!appDetail?.users.length ? (
                          <p className="text-sm text-muted-foreground">No users have access yet.</p>
                        ) : (
                          <div className="rounded-md border">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b bg-muted/50">
                                  <th className="h-10 px-3 text-left font-medium">Email</th>
                                  <th className="h-10 px-3 text-left font-medium">Role</th>
                                  <th className="h-10 px-3 text-left font-medium">Granted</th>
                                  <th className="h-10 px-3 text-right font-medium">Actions</th>
                                </tr>
                              </thead>
                              <tbody>
                                {appDetail.users.map((user) => (
                                  <tr key={user.email} className="border-b last:border-0">
                                    <td className="p-3">{user.email}</td>
                                    <td className="p-3">
                                      {user.role ? (
                                        <Badge variant="outline">{user.role}</Badge>
                                      ) : (
                                        <span className="text-muted-foreground">—</span>
                                      )}
                                    </td>
                                    <td className="p-3 text-muted-foreground">
                                      {new Date(user.granted_at).toLocaleDateString()}
                                    </td>
                                    <td className="p-3 text-right">
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleRevokeAccess(user.email)}
                                        disabled={actionLoading === `revoke-${user.email}`}
                                        className="text-destructive hover:text-destructive"
                                      >
                                        {actionLoading === `revoke-${user.email}` ? (
                                          <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : (
                                          <UserMinus className="h-4 w-4" />
                                        )}
                                      </Button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
