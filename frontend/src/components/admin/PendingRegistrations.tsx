import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api, type User, ApiError } from '@/lib/api';
import { Check, X, Clock } from 'lucide-react';

interface PendingRegistrationsProps {
  onAction?: () => void;
}

export function PendingRegistrations({ onAction }: PendingRegistrationsProps) {
  const [users, setUsers] = React.useState<User[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [actionLoading, setActionLoading] = React.useState<string | null>(null);

  const loadPending = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.admin.listPendingUsers();
      setUsers(response.users);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load pending registrations');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadPending();
  }, [loadPending]);

  const handleApprove = async (user: User) => {
    setActionLoading(user.id);
    setActionError(null);
    try {
      await api.admin.approveUser(user.id);
      await loadPending();
      onAction?.();
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
      await loadPending();
      onAction?.();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to reject user';
      setActionError(message);
      console.error('Reject error:', err);
    } finally {
      setActionLoading(null);
    }
  };

  if (isLoading) {
    return (
      <Card className="border-orange-500">
        <CardHeader className="border-b-4 border-orange-500 bg-orange-500 text-white p-4">
          <CardTitle className="flex items-center gap-2 text-white">
            <Clock className="h-5 w-5" />
            Pending Registrations
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="flex items-center justify-center py-8">
            <div className="inline-block w-6 h-6 border-4 border-orange-500 border-t-transparent animate-spin" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-orange-500">
        <CardHeader className="border-b-4 border-orange-500 bg-orange-500 text-white p-4">
          <CardTitle className="flex items-center gap-2 text-white">
            <Clock className="h-5 w-5" />
            Pending Registrations
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="text-center py-4">
            <p className="text-red-600 font-bold">{error}</p>
            <Button onClick={loadPending} variant="secondary" className="mt-4">
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-orange-500">
      <CardHeader className="border-b-4 border-orange-500 bg-orange-500 text-white p-4">
        <CardTitle className="flex items-center gap-2 text-white">
          <Clock className="h-5 w-5" />
          Pending Registrations
          <span className="ml-auto text-sm font-normal">
            {users.length === 0
              ? 'No pending'
              : `${users.length} waiting`}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        {actionError && (
          <div className="mb-4 p-3 border-2 border-red-500 bg-red-50 text-red-600 text-sm font-bold">
            {actionError}
          </div>
        )}
        {users.length === 0 ? (
          <p className="text-center text-gray-500 py-4 font-bold uppercase tracking-wider">
            All caught up!
          </p>
        ) : (
          <div className="space-y-2">
            {users.map((user) => (
              <div
                key={user.id}
                className="flex items-center justify-between p-3 border-2 border-black hover:bg-gray-50"
              >
                <div>
                  <p className="font-bold text-sm">{user.email}</p>
                  <p className="text-xs text-gray-500">
                    Registered {new Date(user.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={() => handleApprove(user)}
                    disabled={actionLoading === user.id}
                  >
                    {actionLoading === user.id ? (
                      <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin" />
                    ) : (
                      <>
                        <Check className="h-4 w-4 mr-1" />
                        Approve
                      </>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleReject(user)}
                    disabled={actionLoading === user.id}
                  >
                    {actionLoading === user.id ? (
                      <div className="w-4 h-4 border-2 border-black border-t-transparent animate-spin" />
                    ) : (
                      <>
                        <X className="h-4 w-4 mr-1" />
                        Reject
                      </>
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
