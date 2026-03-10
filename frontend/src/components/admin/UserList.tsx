import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Switch } from '@/components/ui/switch';
import {
  api,
  type App,
  type AuditLog,
  type BannedEmail,
  type BannedIP,
  type User,
  type UserAppAccess,
  type UserSession,
  ApiError,
} from '@/lib/api';
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
  History,
  Ban,
  Monitor,
  RefreshCw,
} from 'lucide-react';

interface UserListProps {
  initialUsers?: User[];
  onRefresh?: () => void;
}

export function UserList({ initialUsers, onRefresh }: UserListProps) {
  const [users, setUsers] = React.useState<User[]>(initialUsers || []);
  const [isLoading, setIsLoading] = React.useState(!initialUsers);
  const [error, setError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
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
  const [activeSessions, setActiveSessions] = React.useState<UserSession[]>([]);
  const [recentAuditLogs, setRecentAuditLogs] = React.useState<AuditLog[]>([]);
  const [activeIPBans, setActiveIPBans] = React.useState<BannedIP[]>([]);
  const [activeEmailBans, setActiveEmailBans] = React.useState<BannedEmail[]>([]);
  const [recentIPs, setRecentIPs] = React.useState<string[]>([]);
  const [lastAuthMethod, setLastAuthMethod] = React.useState<string | null>(null);
  const [lastSeenAt, setLastSeenAt] = React.useState<string | null>(null);
  const [showRecentActivity, setShowRecentActivity] = React.useState(false);
  const [expandedAuditLogId, setExpandedAuditLogId] = React.useState<string | null>(null);

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
      const [investigationRes, appsRes] = await Promise.all([
        api.admin.getUserInvestigation(userId),
        api.admin.listApps(),
      ]);
      setUserDetail(investigationRes.user);
      setAllApps(appsRes.apps);
      setUserApps(investigationRes.app_access);
      setActiveSessions(investigationRes.active_sessions);
      setRecentAuditLogs(investigationRes.recent_audit_logs);
      setActiveIPBans(investigationRes.active_ip_bans);
      setActiveEmailBans(investigationRes.active_email_bans);
      setRecentIPs(investigationRes.recent_ip_addresses);
      setLastAuthMethod(investigationRes.last_auth_method);
      setLastSeenAt(investigationRes.last_seen_at);
      setShowRecentActivity(false);
      setExpandedAuditLogId(null);
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
      setActiveSessions([]);
      setRecentAuditLogs([]);
      setActiveIPBans([]);
      setActiveEmailBans([]);
      setRecentIPs([]);
      setLastAuthMethod(null);
      setLastSeenAt(null);
      setShowRecentActivity(false);
      setExpandedAuditLogId(null);
    } else {
      setExpandedUserId(userId);
      await loadUserDetail(userId);
    }
  };

  const handleToggleAdmin = async (user: User) => {
    setActionLoading(user.id);
    setActionError(null);
    try {
      await api.admin.updateUser(user.id, { is_admin: !user.is_admin });
      await loadUsers();
      if (expandedUserId === user.id) {
        await loadUserDetail(user.id);
      }
      onRefresh?.();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to update user';
      setActionError(message);
      console.error('Toggle admin error:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (user: User) => {
    if (!confirm(`Are you sure you want to delete ${user.email}?`)) return;

    setActionLoading(user.id);
    setActionError(null);
    try {
      await api.admin.deleteUser(user.id);
      if (expandedUserId === user.id) {
        setExpandedUserId(null);
        setUserDetail(null);
      }
      await loadUsers();
      onRefresh?.();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to delete user';
      setActionError(message);
      console.error('Delete error:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleUpdateNotifications = async (field: 'notify_new_registrations' | 'notify_all_registrations', value: boolean) => {
    if (!userDetail) return;
    setIsSavingSettings(true);
    setActionError(null);
    try {
      await api.admin.updateUser(userDetail.id, { [field]: value });
      await loadUserDetail(userDetail.id);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to update notifications';
      setActionError(message);
      console.error('Update notifications error:', err);
    } finally {
      setIsSavingSettings(false);
    }
  };

  const handleGrantAccess = async () => {
    if (!userDetail || !selectedAppToGrant) return;

    setIsGranting(true);
    setActionError(null);
    try {
      await api.admin.grantAccess(selectedAppToGrant, userDetail.email, selectedRole || undefined);
      setSelectedAppToGrant('');
      setSelectedRole('');
      await loadUserDetail(userDetail.id);
      onRefresh?.();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to grant access';
      setActionError(message);
      console.error('Grant access error:', err);
    } finally {
      setIsGranting(false);
    }
  };

  const handleRevokeAccess = async (appSlug: string) => {
    if (!userDetail) return;
    if (!confirm(`Revoke access to ${appSlug}?`)) return;

    setActionLoading(`revoke-${appSlug}`);
    setActionError(null);
    try {
      await api.admin.revokeAccess(appSlug, userDetail.email);
      await loadUserDetail(userDetail.id);
      onRefresh?.();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to revoke access';
      setActionError(message);
      console.error('Revoke access error:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRevokeSession = async (sessionId: string) => {
    if (!userDetail) return;
    if (!confirm('Revoke this session?')) return;

    setActionLoading(`session-${sessionId}`);
    setActionError(null);
    try {
      await api.admin.revokeUserSession(userDetail.id, sessionId);
      await loadUserDetail(userDetail.id);
      onRefresh?.();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to revoke session';
      setActionError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRevokeAllSessions = async () => {
    if (!userDetail) return;
    if (!confirm(`Revoke all active sessions for ${userDetail.email}?`)) return;

    setActionLoading(`sessions-all-${userDetail.id}`);
    setActionError(null);
    try {
      await api.admin.revokeAllUserSessions(userDetail.id);
      await loadUserDetail(userDetail.id);
      onRefresh?.();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to revoke sessions';
      setActionError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleApprove = async (user: User) => {
    setActionLoading(user.id);
    setActionError(null);
    try {
      await api.admin.approveUser(user.id);
      await loadUsers();
      onRefresh?.();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to approve user';
      setActionError(message);
      console.error('Approve error:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (user: User) => {
    if (!confirm(`Are you sure you want to reject ${user.email}? This will also ban their email.`)) return;

    setActionLoading(user.id);
    setActionError(null);
    try {
      await api.admin.rejectUser(user.id);
      await loadUsers();
      onRefresh?.();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to reject user';
      setActionError(message);
      console.error('Reject error:', err);
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

  const formatTimeAgo = (dateStr: string | null) => {
    if (!dateStr) return 'never';
    const date = new Date(dateStr);
    const diffMs = Date.now() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const summarizeAuditLog = (log: AuditLog) => {
    const details = log.details || {};
    const reason = typeof details.reason === 'string' ? details.reason : null;
    const method = typeof details.method === 'string' ? details.method : null;
    const matchedEmail = typeof details.email_matched === 'string' ? details.email_matched : null;

    if (matchedEmail) return matchedEmail;
    if (reason && method) return `${method}: ${reason}`;
    if (reason) return reason;
    if (method) return method;
    return log.actor_email || log.target_id || 'No summary';
  };

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

      {/* Action Error */}
      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

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
                      {user.status === 'pending' && (
                        <>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleApprove(user)}
                            disabled={actionLoading === user.id}
                            title="Approve User"
                            className="text-green-600 hover:text-green-600"
                          >
                            {actionLoading === user.id ? (
                              <div className="w-4 h-4 border-2 border-green-600 border-t-transparent animate-spin" />
                            ) : (
                              <Check className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleReject(user)}
                            disabled={actionLoading === user.id}
                            title="Reject User"
                            className="text-red-600 hover:text-red-600"
                          >
                            {actionLoading === user.id ? (
                              <div className="w-4 h-4 border-2 border-red-600 border-t-transparent animate-spin" />
                            ) : (
                              <X className="h-4 w-4" />
                            )}
                          </Button>
                        </>
                      )}
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
                        title="Delete User"
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
                          <div className="grid gap-4 md:grid-cols-4">
                            <div className="border-2 border-black bg-white p-3">
                              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Last Seen</p>
                              <p className="mt-2 text-sm font-bold">{formatTimeAgo(lastSeenAt)}</p>
                            </div>
                            <div className="border-2 border-black bg-white p-3">
                              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Last Auth</p>
                              <p className="mt-2 text-sm font-bold uppercase">{lastAuthMethod || 'Unknown'}</p>
                            </div>
                            <div className="border-2 border-black bg-white p-3">
                              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Recent IPs</p>
                              <p className="mt-2 text-sm font-bold">{recentIPs[0] || 'None'}</p>
                            </div>
                            <div className="border-2 border-black bg-white p-3">
                              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Active Sessions</p>
                              <p className="mt-2 text-sm font-bold">{activeSessions.length}</p>
                            </div>
                          </div>

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
                                              {access.granted_by && (
                                                <span className="text-xs text-gray-500">
                                                  by {access.granted_by}
                                                </span>
                                              )}
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

                          <div className="grid gap-6 lg:grid-cols-2">
                            <div className="space-y-4">
                              <div className="flex items-center justify-between">
                                <h4 className="font-bold uppercase tracking-wider text-sm flex items-center gap-2">
                                  <Monitor className="h-4 w-4" />
                                  Active Sessions
                                </h4>
                                {activeSessions.length > 0 && (
                                  <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={handleRevokeAllSessions}
                                    disabled={actionLoading === `sessions-all-${userDetail.id}`}
                                  >
                                    {actionLoading === `sessions-all-${userDetail.id}` ? (
                                      <div className="w-4 h-4 border-2 border-black border-t-transparent animate-spin mr-2" />
                                    ) : (
                                      <RefreshCw className="h-4 w-4 mr-2" />
                                    )}
                                    Revoke All
                                  </Button>
                                )}
                              </div>

                              {activeSessions.length === 0 ? (
                                <p className="text-sm text-gray-500 p-4 border-2 border-dashed border-gray-300">
                                  No active sessions.
                                </p>
                              ) : (
                                <div className="border-2 border-black bg-white">
                                  {activeSessions.map((session) => (
                                    <div
                                      key={session.id}
                                      className="flex items-start justify-between gap-4 border-b-2 border-black p-3 last:border-b-0"
                                    >
                                      <div className="min-w-0">
                                        <div className="flex flex-wrap items-center gap-2">
                                          <Badge variant="secondary">{session.auth_method || 'unknown'}</Badge>
                                          <span className="text-xs text-gray-500">{session.ip_address || 'No IP'}</span>
                                        </div>
                                        <p className="mt-2 text-xs text-gray-500 break-all">
                                          {session.user_agent || 'No user agent'}
                                        </p>
                                        <p className="mt-2 text-xs text-gray-500">
                                          Last seen {formatTimeAgo(session.last_seen_at)}. Expires{' '}
                                          {new Date(session.expires_at).toLocaleString()}
                                        </p>
                                      </div>
                                      <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => handleRevokeSession(session.id)}
                                        disabled={actionLoading === `session-${session.id}`}
                                        className="text-red-600 hover:text-red-600"
                                      >
                                        {actionLoading === `session-${session.id}` ? (
                                          <div className="w-4 h-4 border-2 border-red-600 border-t-transparent animate-spin" />
                                        ) : (
                                          <X className="h-4 w-4" />
                                        )}
                                      </Button>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>

                            <div className="space-y-4">
                              <h4 className="font-bold uppercase tracking-wider text-sm flex items-center gap-2">
                                <Ban className="h-4 w-4" />
                                Active Bans
                              </h4>

                              {activeIPBans.length === 0 && activeEmailBans.length === 0 ? (
                                <p className="text-sm text-gray-500 p-4 border-2 border-dashed border-gray-300">
                                  No active bans linked to this user.
                                </p>
                              ) : (
                                <div className="space-y-3">
                                  {activeIPBans.map((ban) => (
                                    <div key={ban.id} className="border-2 border-black bg-white p-3">
                                      <div className="flex items-center gap-2">
                                        <Badge variant="destructive">IP</Badge>
                                        <span className="font-medium text-sm">{ban.ip_address}</span>
                                      </div>
                                      <p className="mt-2 text-xs text-gray-500">
                                        {ban.reason} {ban.details ? `- ${ban.details}` : ''}
                                      </p>
                                    </div>
                                  ))}
                                  {activeEmailBans.map((ban) => (
                                    <div key={ban.id} className="border-2 border-black bg-white p-3">
                                      <div className="flex items-center gap-2">
                                        <Badge variant="destructive">Email</Badge>
                                        <span className="font-medium text-sm">{ban.email}</span>
                                      </div>
                                      <p className="mt-2 text-xs text-gray-500">
                                        {ban.reason} {ban.details ? `- ${ban.details}` : ''}
                                      </p>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>

                          <div className="space-y-4">
                            <div className="flex items-center justify-between">
                              <h4 className="font-bold uppercase tracking-wider text-sm flex items-center gap-2">
                                <History className="h-4 w-4" />
                                Recent Activity
                              </h4>
                              {recentAuditLogs.length > 0 && (
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  onClick={() => setShowRecentActivity((current) => !current)}
                                >
                                  {showRecentActivity ? 'Hide Logs' : 'Show Logs'}
                                </Button>
                              )}
                            </div>

                            {recentAuditLogs.length === 0 ? (
                              <p className="text-sm text-gray-500 p-4 border-2 border-dashed border-gray-300">
                                No recent audit activity for this user.
                              </p>
                            ) : !showRecentActivity ? (
                              <p className="text-sm text-gray-500 p-4 border-2 border-dashed border-gray-300">
                                Recent activity is available but hidden by default. Click `Show Logs` to inspect it.
                              </p>
                            ) : (
                              <div className="border-2 border-black bg-white">
                                {recentAuditLogs.map((log) => (
                                  <div key={log.id} className="border-b-2 border-black p-3 last:border-b-0">
                                    <div className="flex flex-wrap items-center justify-between gap-3">
                                      <div className="min-w-0">
                                        <div className="flex flex-wrap items-center gap-2">
                                          <Badge variant="secondary">{log.event_type}</Badge>
                                          {log.ip_address && (
                                            <span className="text-xs text-gray-500">{log.ip_address}</span>
                                          )}
                                        </div>
                                        <p className="mt-2 text-sm font-medium break-all">
                                          {summarizeAuditLog(log)}
                                        </p>
                                      </div>
                                      <div className="flex items-center gap-2">
                                        <span className="text-xs text-gray-500">
                                          {formatTimeAgo(log.timestamp)}
                                        </span>
                                        {log.details && (
                                          <Button
                                            size="sm"
                                            variant="ghost"
                                            onClick={() =>
                                              setExpandedAuditLogId((current) =>
                                                current === log.id ? null : log.id
                                              )
                                            }
                                          >
                                            {expandedAuditLogId === log.id ? 'Hide Details' : 'Details'}
                                          </Button>
                                        )}
                                      </div>
                                    </div>
                                    {log.details && expandedAuditLogId === log.id && (
                                      <pre className="mt-3 overflow-x-auto whitespace-pre-wrap border-2 border-black bg-gray-50 p-3 text-xs text-gray-600">
                                        {JSON.stringify(log.details, null, 2)}
                                      </pre>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
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
