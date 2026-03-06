import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { api, type App, type AppDetail, ApiError } from '@/lib/api';
import {
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
  Settings,
  Pencil,
} from 'lucide-react';
import { CreateAppModal } from './CreateAppModal';

interface AppManagementProps {
  onRefresh?: () => void;
}

export function AppManagement({ onRefresh }: AppManagementProps) {
  const [apps, setApps] = React.useState<App[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Create app modal
  const [showCreateModal, setShowCreateModal] = React.useState(false);

  // Expanded app details
  const [expandedApp, setExpandedApp] = React.useState<string | null>(null);
  const [appDetail, setAppDetail] = React.useState<AppDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = React.useState(false);

  // Edit app form
  const [editName, setEditName] = React.useState('');
  const [editDescription, setEditDescription] = React.useState('');
  const [editAppUrl, setEditAppUrl] = React.useState('');
  const [editRoles, setEditRoles] = React.useState('admin,user');
  const [isSavingApp, setIsSavingApp] = React.useState(false);
  const [hasAppChanges, setHasAppChanges] = React.useState(false);

  // Grant access form
  const [grantEmail, setGrantEmail] = React.useState('');
  const [grantRole, setGrantRole] = React.useState('');
  const [isGranting, setIsGranting] = React.useState(false);

  // Action loading states
  const [actionLoading, setActionLoading] = React.useState<string | null>(null);

  // Edit user role
  const [editingUserRole, setEditingUserRole] = React.useState<string | null>(null);
  const [editUserRoleValue, setEditUserRoleValue] = React.useState<string>('');

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
      const detail = await api.admin.getApp(slug);
      setAppDetail(detail);
      // Populate edit fields
      setEditName(detail.name);
      setEditDescription(detail.description || '');
      setEditAppUrl(detail.app_url || '');
      setEditRoles(detail.roles || 'admin,user');
      setHasAppChanges(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleSaveAppChanges = async () => {
    if (!expandedApp || !appDetail) return;
    setIsSavingApp(true);
    setError(null);

    try {
      const updated = await api.admin.updateApp(expandedApp, {
        name: editName !== appDetail.name ? editName : undefined,
        description: editDescription !== (appDetail.description || '') ? editDescription : undefined,
        app_url: editAppUrl !== (appDetail.app_url || '') ? editAppUrl : undefined,
        roles: editRoles !== appDetail.roles ? editRoles : undefined,
      });
      // Update local state
      setAppDetail({ ...appDetail, ...updated });
      setHasAppChanges(false);
      await loadApps(); // Refresh app list
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setIsSavingApp(false);
    }
  };

  // Track changes to edit fields
  React.useEffect(() => {
    if (!appDetail) return;
    const changed =
      editName !== appDetail.name ||
      editDescription !== (appDetail.description || '') ||
      editAppUrl !== (appDetail.app_url || '') ||
      editRoles !== appDetail.roles;
    setHasAppChanges(changed);
  }, [editName, editDescription, editAppUrl, editRoles, appDetail]);

  const handleToggleExpand = async (slug: string) => {
    if (expandedApp === slug) {
      setExpandedApp(null);
      setAppDetail(null);
    } else {
      setExpandedApp(slug);
      await loadAppDetail(slug);
    }
  };

  const handleCreateSuccess = async () => {
    setShowCreateModal(false);
    await loadApps();
    onRefresh?.();
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

  const handleSaveUserRole = async (email: string) => {
    if (!expandedApp) return;

    setActionLoading(`role-${email}`);
    try {
      await api.admin.grantAccess(expandedApp, email, editUserRoleValue || undefined);
      setEditingUserRole(null);
      setEditUserRoleValue('');
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

  const startEditingRole = (email: string, currentRole: string | null) => {
    setEditingUserRole(email);
    setEditUserRoleValue(currentRole || '');
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="inline-block w-6 h-6 border-4 border-black border-t-transparent animate-spin" />
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
          <span className="font-bold uppercase tracking-wider">Apps ({apps.length})</span>
        </div>
        <Button size="sm" onClick={() => setShowCreateModal(true)}>
          <Plus className="h-4 w-4 mr-1" />
          Add App
        </Button>
      </div>

      {showCreateModal && (
        <CreateAppModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleCreateSuccess}
        />
      )}

      {apps.length === 0 ? (
        <div className="text-center py-8 text-gray-500 border-4 border-dashed border-gray-300">
          <p className="font-bold uppercase tracking-wider">No apps configured</p>
          <p className="text-sm mt-1">Create one to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {apps.map((app) => (
            <div key={app.slug} className="border-4 border-black">
              <div
                className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
                onClick={() => handleToggleExpand(app.slug)}
              >
                <div className="flex items-center gap-3">
                  <AppWindow className="h-5 w-5 text-gray-500" />
                  <div>
                    <p className="font-bold">{app.name}</p>
                    <p className="text-sm text-gray-500 font-mono">{app.slug}</p>
                    {app.description && (
                      <p className="text-sm text-gray-500 line-clamp-1">{app.description}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteApp(app.slug);
                    }}
                    disabled={actionLoading === `delete-${app.slug}`}
                    className="text-red-600 hover:text-red-600"
                  >
                    {actionLoading === `delete-${app.slug}` ? (
                      <div className="w-4 h-4 border-2 border-red-600 border-t-transparent animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                  {expandedApp === app.slug ? (
                    <ChevronUp className="h-5 w-5 text-gray-500" />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-gray-500" />
                  )}
                </div>
              </div>

              {expandedApp === app.slug && (
                <div className="border-t-4 border-black p-4 bg-gray-50">
                  {isLoadingDetail ? (
                    <div className="flex items-center justify-center py-4">
                      <div className="inline-block w-6 h-6 border-4 border-black border-t-transparent animate-spin" />
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {/* App Settings */}
                      <div className="space-y-4">
                        <h4 className="font-bold text-sm uppercase tracking-wider flex items-center gap-2">
                          <Settings className="h-4 w-4" />
                          App Settings
                        </h4>
                        <div className="grid gap-4 sm:grid-cols-2">
                          <div className="space-y-2">
                            <label className="text-xs font-bold uppercase tracking-wider">
                              Display Name
                            </label>
                            <Input
                              value={editName}
                              onChange={(e) => setEditName(e.target.value)}
                              placeholder="App name"
                              slim
                            />
                          </div>
                          <div className="space-y-2">
                            <label className="text-xs font-bold uppercase tracking-wider">
                              App URL
                            </label>
                            <Input
                              type="url"
                              value={editAppUrl}
                              onChange={(e) => setEditAppUrl(e.target.value)}
                              placeholder="https://myapp.example.com"
                              slim
                            />
                          </div>
                        </div>
                        <div className="grid gap-4 sm:grid-cols-2">
                          <div className="space-y-2">
                            <label className="text-xs font-bold uppercase tracking-wider">
                              Description
                            </label>
                            <Input
                              value={editDescription}
                              onChange={(e) => setEditDescription(e.target.value)}
                              placeholder="A brief description of your app"
                              slim
                            />
                          </div>
                          <div className="space-y-2">
                            <label className="text-xs font-bold uppercase tracking-wider">
                              Roles
                            </label>
                            <Input
                              value={editRoles}
                              onChange={(e) => setEditRoles(e.target.value)}
                              placeholder="admin,user"
                              slim
                            />
                            <p className="text-xs text-gray-500">Comma-separated list of roles</p>
                          </div>
                        </div>
                        {hasAppChanges && (
                          <div className="flex justify-end">
                            <Button
                              size="sm"
                              onClick={handleSaveAppChanges}
                              disabled={isSavingApp}
                            >
                              {isSavingApp && (
                                <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin mr-2" />
                              )}
                              Save Changes
                            </Button>
                          </div>
                        )}
                      </div>

                      {/* Users with Access */}
                      <div>
                        <h4 className="font-bold text-sm uppercase tracking-wider mb-1 flex items-center gap-2">
                          <Users className="h-4 w-4" />
                          Users with Access ({appDetail?.users.length || 0})
                        </h4>
                        <p className="text-xs text-gray-500 mb-3">
                          External users with explicit access grants. Internal users automatically have access.
                        </p>
                        {!appDetail?.users.length ? (
                          <p className="text-sm text-gray-500 text-center p-4 border-2 border-dashed border-gray-300">
                            No external users have explicit access grants.
                          </p>
                        ) : (
                          <div className="border-2 border-black">
                            <table className="w-full text-sm">
                              <thead className="bg-black text-white">
                                <tr>
                                  <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">Email</th>
                                  <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">Role</th>
                                  <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">Granted</th>
                                  <th className="p-3 text-right text-xs font-bold uppercase tracking-wider">Actions</th>
                                </tr>
                              </thead>
                              <tbody>
                                {appDetail.users.map((user) => (
                                  <tr key={user.email} className="border-t-2 border-black">
                                    <td className="p-3">{user.email}</td>
                                    <td className="p-3">
                                      {editingUserRole === user.email ? (
                                        <div className="flex items-center gap-2">
                                          <select
                                            value={editUserRoleValue}
                                            onChange={(e) => setEditUserRoleValue(e.target.value)}
                                            className="h-8 w-28 border-2 border-black px-2 text-sm"
                                          >
                                            <option value="">No role</option>
                                            {(appDetail?.roles || 'admin,user').split(',').map((role) => (
                                              <option key={role.trim()} value={role.trim()}>
                                                {role.trim()}
                                              </option>
                                            ))}
                                          </select>
                                          <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => handleSaveUserRole(user.email)}
                                            disabled={actionLoading === `role-${user.email}`}
                                          >
                                            {actionLoading === `role-${user.email}` ? (
                                              <div className="w-4 h-4 border-2 border-black border-t-transparent animate-spin" />
                                            ) : (
                                              <Check className="h-4 w-4" />
                                            )}
                                          </Button>
                                          <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => setEditingUserRole(null)}
                                          >
                                            <X className="h-4 w-4" />
                                          </Button>
                                        </div>
                                      ) : (
                                        <div className="flex items-center gap-2">
                                          {user.role ? (
                                            <Badge variant="secondary">{user.role}</Badge>
                                          ) : (
                                            <span className="text-gray-400">—</span>
                                          )}
                                          <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => startEditingRole(user.email, user.role)}
                                            className="h-6 w-6"
                                          >
                                            <Pencil className="h-3 w-3" />
                                          </Button>
                                        </div>
                                      )}
                                    </td>
                                    <td className="p-3 text-gray-500">
                                      {new Date(user.granted_at).toLocaleDateString()}
                                    </td>
                                    <td className="p-3 text-right">
                                      <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => handleRevokeAccess(user.email)}
                                        disabled={actionLoading === `revoke-${user.email}`}
                                        className="text-red-600 hover:text-red-600"
                                      >
                                        {actionLoading === `revoke-${user.email}` ? (
                                          <div className="w-4 h-4 border-2 border-red-600 border-t-transparent animate-spin" />
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

                      {/* Grant Access Form */}
                      <div>
                        <h4 className="font-bold text-sm uppercase tracking-wider mb-2 flex items-center gap-2">
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
                            slim
                          />
                          <select
                            value={grantRole}
                            onChange={(e) => setGrantRole(e.target.value)}
                            className="h-10 w-32 border-2 border-black px-3 text-sm"
                          >
                            <option value="">No role</option>
                            {(appDetail?.roles || 'admin,user').split(',').map((role) => (
                              <option key={role.trim()} value={role.trim()}>
                                {role.trim()}
                              </option>
                            ))}
                          </select>
                          <Button type="submit" disabled={isGranting} size="sm">
                            {isGranting ? (
                              <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin" />
                            ) : (
                              'Grant'
                            )}
                          </Button>
                        </form>
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
