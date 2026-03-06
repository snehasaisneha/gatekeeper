import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Switch } from '@/components/ui/switch';
import { api, type User, type App, ApiError } from '@/lib/api';
import {
  Trash2,
  Shield,
  ShieldOff,
  ChevronDown,
  ChevronUp,
  Search,
  AppWindow,
  Bell,
  Check,
  X,
  Plus,
} from 'lucide-react';

interface UserListProps {
  initialUsers?: User[];
  onRefresh?: () => void;
}

interface UserAppAccess {
  app_slug: string;
  app_name: string;
  role: string | null;
  granted_at: string;
}

export function UserList({ initialUsers, onRefresh }: UserListProps) {
  const [users, setUsers] = React.useState<User[]>(initialUsers || []);
  const [isLoading, setIsLoading] = React.useState(!initialUsers);
  const [error, setError] = React.useState<string | null>(null);
  const [actionLoading, setActionLoading] = React.useState<string | null>(null);

  // Search and filter
  const [searchQuery, setSearchQuery] = React.useState('');

  // Expanded user details
  const [expandedUserId, setExpandedUserId] = React.useState<string | null>(null);
  const [userApps, setUserApps] = React.useState<UserAppAccess[]>([]);
  const [allApps, setAllApps] = React.useState<App[]>([]);
  const [isLoadingDetail, setIsLoadingDetail] = React.useState(false);
  const [userDetail, setUserDetail] = React.useState<User | null>(null);
  const [isSavingSettings, setIsSavingSettings] = React.useState(false);

  // Grant access state
  const [selectedAppToGrant, setSelectedAppToGrant] = React.useState('');
  const [selectedRole, setSelectedRole] = React.useState('');
  const [isGranting, setIsGranting] = React.useState(false);

  const loadUsers = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.admin.listUsers(1, 100);
      setUsers(response.users);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load users');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (!initialUsers) {
      loadUsers();
    }
  }, [initialUsers, loadUsers]);

  const loadUserDetail = async (userId: string) => {
    setIsLoadingDetail(true);
    try {
      const [userRes, appsRes] = await Promise.all([
        api.admin.getUser(userId),
        api.admin.listApps(),
      ]);
      setUserDetail(userRes);
      setAllApps(appsRes.apps);

      // Load user's app access
      const accessList: UserAppAccess[] = [];
      for (const app of appsRes.apps) {
        try {
          const detail = await api.admin.getApp(app.slug);
          const userAccess = detail.users.find((u) => u.email === userRes.email);
          if (userAccess) {
            accessList.push({
              app_slug: app.slug,
              app_name: app.name,
              role: userAccess.role,
              granted_at: userAccess.granted_at,
            });
          }
        } catch {
          // Skip apps that fail to load
        }
      }
      setUserApps(accessList);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleToggleExpand = async (userId: string) => {
    if (expandedUserId === userId) {
      setExpandedUserId(null);
      setUserDetail(null);
      setUserApps([]);
    } else {
      setExpandedUserId(userId);
      await loadUserDetail(userId);
    }
  };

  const handleToggleAdmin = async (user: User) => {
    setActionLoading(user.id);
    try {
      await api.admin.updateUser(user.id, { is_admin: !user.is_admin });
      await loadUsers();
      if (expandedUserId === user.id) {
        await loadUserDetail(user.id);
      }
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (user: User) => {
    if (!confirm(`Are you sure you want to delete ${user.email}?`)) return;

    setActionLoading(user.id);
    try {
      await api.admin.deleteUser(user.id);
      if (expandedUserId === user.id) {
        setExpandedUserId(null);
        setUserDetail(null);
      }
      await loadUsers();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleUpdateNotifications = async (field: 'notify_new_registrations' | 'notify_all_registrations', value: boolean) => {
    if (!userDetail) return;
    setIsSavingSettings(true);
    try {
      await api.admin.updateUser(userDetail.id, { [field]: value });
      await loadUserDetail(userDetail.id);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setIsSavingSettings(false);
    }
  };

  const handleGrantAccess = async () => {
    if (!userDetail || !selectedAppToGrant) return;

    setIsGranting(true);
    try {
      await api.admin.grantAccess(selectedAppToGrant, userDetail.email, selectedRole || undefined);
      setSelectedAppToGrant('');
      setSelectedRole('');
      await loadUserDetail(userDetail.id);
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setIsGranting(false);
    }
  };

  const handleRevokeAccess = async (appSlug: string) => {
    if (!userDetail) return;
    if (!confirm(`Revoke access to ${appSlug}?`)) return;

    setActionLoading(`revoke-${appSlug}`);
    try {
      await api.admin.revokeAccess(appSlug, userDetail.email);
      await loadUserDetail(userDetail.id);
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved':
        return <Badge variant="success">Approved</Badge>;
      case 'pending':
        return <Badge variant="warning">Pending</Badge>;
      case 'rejected':
        return <Badge variant="destructive">Rejected</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  // Filter users by search query
  const filteredUsers = React.useMemo(() => {
    if (!searchQuery.trim()) return users;
    const query = searchQuery.toLowerCase();
    return users.filter(
      (user) =>
        user.email.toLowerCase().includes(query) ||
        (user.name && user.name.toLowerCase().includes(query))
    );
  }, [users, searchQuery]);

  // Get apps not yet granted to user
  const availableAppsToGrant = React.useMemo(() => {
    const grantedSlugs = new Set(userApps.map((a) => a.app_slug));
    return allApps.filter((app) => !grantedSlugs.has(app.slug));
  }, [allApps, userApps]);

  // Get roles for selected app
  const selectedAppRoles = React.useMemo(() => {
    if (!selectedAppToGrant) return [];
    const app = allApps.find((a) => a.slug === selectedAppToGrant);
    if (!app) return [];
    // We need to fetch app details for roles, for now use default
    return ['admin', 'user'];
  }, [selectedAppToGrant, allApps]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="inline-block w-6 h-6 border-4 border-black border-t-transparent animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button onClick={loadUsers} variant="secondary" className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  if (users.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 border-4 border-dashed border-gray-300">
        <p className="font-bold uppercase tracking-wider">No users found</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search by email or name..."
          className="pl-10"
          slim
        />
      </div>

      {/* Users Table */}
      <div className="border-4 border-black">
        <table className="w-full">
          <thead className="bg-black text-white">
            <tr>
              <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">Email</th>
              <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">Type</th>
              <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">Status</th>
              <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">Role</th>
              <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">Created</th>
              <th className="p-3 text-right text-xs font-bold uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map((user) => (
              <React.Fragment key={user.id}>
                <tr
                  className="border-t-2 border-black hover:bg-gray-50 cursor-pointer"
                  onClick={() => handleToggleExpand(user.id)}
                >
                  <td className="p-3 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{user.email}</span>
                      {expandedUserId === user.id ? (
                        <ChevronUp className="h-4 w-4 text-gray-400" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-gray-400" />
                      )}
                    </div>
                    {user.name && (
                      <p className="text-xs text-gray-500 mt-0.5">{user.name}</p>
                    )}
                  </td>
                  <td className="p-3 text-sm">
                    {user.is_internal ? (
                      <Badge variant="default">Internal</Badge>
                    ) : (
                      <Badge variant="secondary">External</Badge>
                    )}
                  </td>
                  <td className="p-3 text-sm">{getStatusBadge(user.status)}</td>
                  <td className="p-3 text-sm">
                    {user.is_admin ? (
                      <Badge variant="solid">Super Admin</Badge>
                    ) : (
                      <Badge variant="secondary">User</Badge>
                    )}
                  </td>
                  <td className="p-3 text-sm text-gray-500">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td className="p-3 text-sm text-right">
                    <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleToggleAdmin(user)}
                        disabled={actionLoading === user.id}
                        title={user.is_admin ? 'Remove Super Admin' : 'Make Super Admin'}
                      >
                        {actionLoading === user.id ? (
                          <div className="w-4 h-4 border-2 border-black border-t-transparent animate-spin" />
                        ) : user.is_admin ? (
                          <ShieldOff className="h-4 w-4" />
                        ) : (
                          <Shield className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(user)}
                        disabled={actionLoading === user.id}
                        className="text-red-600 hover:text-red-600"
                      >
                        {actionLoading === user.id ? (
                          <div className="w-4 h-4 border-2 border-red-600 border-t-transparent animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </td>
                </tr>

                {/* Expanded User Detail Panel */}
                {expandedUserId === user.id && (
                  <tr>
                    <td colSpan={6} className="border-t-2 border-black bg-gray-50 p-0">
                      {isLoadingDetail ? (
                        <div className="flex items-center justify-center py-8">
                          <div className="inline-block w-6 h-6 border-4 border-black border-t-transparent animate-spin" />
                        </div>
                      ) : userDetail ? (
                        <div className="p-4 space-y-6">
                          <div className="grid md:grid-cols-2 gap-6">
                            {/* Left Column - User Settings */}
                            <div className="space-y-4">
                              <h4 className="font-bold uppercase tracking-wider text-sm flex items-center gap-2">
                                <Bell className="h-4 w-4" />
                                User Settings
                              </h4>

                              {userDetail.is_admin && (
                                <div className="space-y-4 p-4 border-2 border-black">
                                  <div className="flex items-center justify-between">
                                    <div>
                                      <p className="text-sm font-bold uppercase tracking-wider">
                                        Pending Notifications
                                      </p>
                                      <p className="text-xs text-gray-500">
                                        Notify on new registrations needing approval
                                      </p>
                                    </div>
                                    <Switch
                                      checked={userDetail.notify_new_registrations}
                                      onCheckedChange={(v) => handleUpdateNotifications('notify_new_registrations', v)}
                                      disabled={isSavingSettings}
                                    />
                                  </div>
                                  <div className="flex items-center justify-between">
                                    <div>
                                      <p className="text-sm font-bold uppercase tracking-wider">
                                        All Notifications
                                      </p>
                                      <p className="text-xs text-gray-500">
                                        Notify on all new sign-ups
                                      </p>
                                    </div>
                                    <Switch
                                      checked={userDetail.notify_all_registrations}
                                      onCheckedChange={(v) => handleUpdateNotifications('notify_all_registrations', v)}
                                      disabled={isSavingSettings}
                                    />
                                  </div>
                                </div>
                              )}

                              {!userDetail.is_admin && (
                                <p className="text-sm text-gray-500 italic p-4 border-2 border-dashed border-gray-300">
                                  Notification settings are only available for admin users.
                                </p>
                              )}
                            </div>

                            {/* Right Column - App Access */}
                            <div className="space-y-4">
                              <h4 className="font-bold uppercase tracking-wider text-sm flex items-center gap-2">
                                <AppWindow className="h-4 w-4" />
                                App Access
                              </h4>

                              {userDetail.is_internal || userDetail.is_admin ? (
                                <p className="text-sm text-gray-500 italic p-4 border-2 border-dashed border-gray-300">
                                  {userDetail.is_admin
                                    ? 'Super admins have access to all apps.'
                                    : 'Internal users have access to all apps.'}
                                </p>
                              ) : (
                                <>
                                  {/* Current App Access */}
                                  {userApps.length === 0 ? (
                                    <p className="text-sm text-gray-500 p-4 border-2 border-dashed border-gray-300">
                                      No explicit app access grants.
                                    </p>
                                  ) : (
                                    <div className="border-2 border-black">
                                      {userApps.map((access) => (
                                        <div
                                          key={access.app_slug}
                                          className="flex items-center justify-between p-3 border-b-2 border-black last:border-b-0"
                                        >
                                          <div>
                                            <p className="font-medium text-sm">{access.app_name}</p>
                                            <div className="flex items-center gap-2 mt-1">
                                              {access.role && (
                                                <Badge variant="secondary">{access.role}</Badge>
                                              )}
                                              <span className="text-xs text-gray-500">
                                                Granted {new Date(access.granted_at).toLocaleDateString()}
                                              </span>
                                            </div>
                                          </div>
                                          <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => handleRevokeAccess(access.app_slug)}
                                            disabled={actionLoading === `revoke-${access.app_slug}`}
                                            className="text-red-600 hover:text-red-600"
                                          >
                                            {actionLoading === `revoke-${access.app_slug}` ? (
                                              <div className="w-4 h-4 border-2 border-red-600 border-t-transparent animate-spin" />
                                            ) : (
                                              <X className="h-4 w-4" />
                                            )}
                                          </Button>
                                        </div>
                                      ))}
                                    </div>
                                  )}

                                  {/* Grant Access Form */}
                                  {availableAppsToGrant.length > 0 && (
                                    <div className="flex gap-2 items-end">
                                      <div className="flex-1">
                                        <label className="text-xs font-bold uppercase tracking-wider">
                                          Grant Access
                                        </label>
                                        <select
                                          value={selectedAppToGrant}
                                          onChange={(e) => setSelectedAppToGrant(e.target.value)}
                                          className="w-full h-10 border-2 border-black px-3 text-sm mt-1"
                                        >
                                          <option value="">Select app...</option>
                                          {availableAppsToGrant.map((app) => (
                                            <option key={app.slug} value={app.slug}>
                                              {app.name}
                                            </option>
                                          ))}
                                        </select>
                                      </div>
                                      <div className="w-24">
                                        <label className="text-xs font-bold uppercase tracking-wider">
                                          Role
                                        </label>
                                        <select
                                          value={selectedRole}
                                          onChange={(e) => setSelectedRole(e.target.value)}
                                          className="w-full h-10 border-2 border-black px-2 text-sm mt-1"
                                          disabled={!selectedAppToGrant}
                                        >
                                          <option value="">None</option>
                                          {selectedAppRoles.map((role) => (
                                            <option key={role} value={role}>
                                              {role}
                                            </option>
                                          ))}
                                        </select>
                                      </div>
                                      <Button
                                        size="sm"
                                        onClick={handleGrantAccess}
                                        disabled={!selectedAppToGrant || isGranting}
                                      >
                                        {isGranting ? (
                                          <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin" />
                                        ) : (
                                          <Plus className="h-4 w-4" />
                                        )}
                                      </Button>
                                    </div>
                                  )}
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {filteredUsers.length === 0 && searchQuery && (
        <p className="text-center text-gray-500 py-4">
          No users match "{searchQuery}"
        </p>
      )}
    </div>
  );
}
