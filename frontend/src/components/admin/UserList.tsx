import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { api, type User, ApiError } from '@/lib/api';
import { Loader2, Trash2, Shield, ShieldOff } from 'lucide-react';

interface UserListProps {
  initialUsers?: User[];
  onRefresh?: () => void;
}

export function UserList({ initialUsers, onRefresh }: UserListProps) {
  const [users, setUsers] = React.useState<User[]>(initialUsers || []);
  const [isLoading, setIsLoading] = React.useState(!initialUsers);
  const [error, setError] = React.useState<string | null>(null);
  const [actionLoading, setActionLoading] = React.useState<string | null>(null);

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

  const handleToggleAdmin = async (user: User) => {
    setActionLoading(user.id);
    try {
      await api.admin.updateUser(user.id, { is_admin: !user.is_admin });
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

  const handleDelete = async (user: User) => {
    if (!confirm(`Are you sure you want to delete ${user.email}?`)) return;

    setActionLoading(user.id);
    try {
      await api.admin.deleteUser(user.id);
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-destructive">{error}</p>
        <Button onClick={loadUsers} variant="outline" className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  if (users.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No users found
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="h-12 px-4 text-left align-middle font-medium">Email</th>
              <th className="h-12 px-4 text-left align-middle font-medium">Type</th>
              <th className="h-12 px-4 text-left align-middle font-medium">Status</th>
              <th className="h-12 px-4 text-left align-middle font-medium">Role</th>
              <th className="h-12 px-4 text-left align-middle font-medium">Created</th>
              <th className="h-12 px-4 text-right align-middle font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-b">
                <td className="p-4 align-middle">{user.email}</td>
                <td className="p-4 align-middle">
                  {user.is_internal ? (
                    <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">Internal</Badge>
                  ) : (
                    <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">External</Badge>
                  )}
                </td>
                <td className="p-4 align-middle">{getStatusBadge(user.status)}</td>
                <td className="p-4 align-middle">
                  {user.is_admin ? (
                    <Badge>Super Admin</Badge>
                  ) : (
                    <Badge variant="secondary">User</Badge>
                  )}
                </td>
                <td className="p-4 align-middle text-muted-foreground">
                  {new Date(user.created_at).toLocaleDateString()}
                </td>
                <td className="p-4 align-middle text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleToggleAdmin(user)}
                      disabled={actionLoading === user.id}
                      title={user.is_admin ? 'Remove Super Admin' : 'Make Super Admin'}
                    >
                      {actionLoading === user.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : user.is_admin ? (
                        <ShieldOff className="h-4 w-4" />
                      ) : (
                        <Shield className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(user)}
                      disabled={actionLoading === user.id}
                      className="text-destructive hover:text-destructive"
                    >
                      {actionLoading === user.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
