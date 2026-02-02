import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { UserList } from './UserList';
import { PendingRegistrations } from './PendingRegistrations';
import { AppManagement } from './AppManagement';
import { api, ApiError } from '@/lib/api';
import { Loader2, UserPlus, AppWindow, Users } from 'lucide-react';

type TabType = 'users' | 'apps';

export function AdminDashboard() {
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [activeTab, setActiveTab] = React.useState<TabType>('users');
  const [showAddUser, setShowAddUser] = React.useState(false);
  const [newEmail, setNewEmail] = React.useState('');
  const [isAdminUser, setIsAdminUser] = React.useState(false);
  const [isAddingUser, setIsAddingUser] = React.useState(false);
  const [addError, setAddError] = React.useState<string | null>(null);
  const [addSuccess, setAddSuccess] = React.useState<string | null>(null);

  const handleRefresh = () => {
    setRefreshKey((k) => k + 1);
  };

  const handleAddUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsAddingUser(true);
    setAddError(null);
    setAddSuccess(null);

    try {
      const user = await api.admin.createUser(newEmail, isAdminUser, true);
      setAddSuccess(`User ${user.email} created successfully`);
      setNewEmail('');
      setIsAdminUser(false);
      setShowAddUser(false);
      handleRefresh();
    } catch (err) {
      if (err instanceof ApiError) {
        setAddError(err.message);
      } else {
        setAddError('Failed to create user');
      }
    } finally {
      setIsAddingUser(false);
    }
  };

  return (
    <div className="space-y-6" key={refreshKey}>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Admin Dashboard</h1>
          <p className="text-muted-foreground">Manage users and apps</p>
        </div>
        {activeTab === 'users' && (
          <Button onClick={() => setShowAddUser(!showAddUser)}>
            <UserPlus className="h-4 w-4 mr-2" />
            Add User
          </Button>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 border-b">
        <button
          onClick={() => setActiveTab('users')}
          className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
            activeTab === 'users'
              ? 'border-primary text-primary font-medium'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Users className="h-4 w-4" />
          Users
        </button>
        <button
          onClick={() => setActiveTab('apps')}
          className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
            activeTab === 'apps'
              ? 'border-primary text-primary font-medium'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <AppWindow className="h-4 w-4" />
          Apps
        </button>
      </div>

      {activeTab === 'users' && (
        <>
          {showAddUser && (
            <Card>
              <CardHeader>
                <CardTitle>Add New User</CardTitle>
                <CardDescription>Create a new user account directly</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleAddUser} className="space-y-4">
                  {addError && (
                    <Alert variant="destructive">
                      <AlertDescription>{addError}</AlertDescription>
                    </Alert>
                  )}
                  {addSuccess && (
                    <Alert variant="success">
                      <AlertDescription>{addSuccess}</AlertDescription>
                    </Alert>
                  )}
                  <div className="space-y-2">
                    <Label htmlFor="new-email">Email</Label>
                    <Input
                      id="new-email"
                      type="email"
                      value={newEmail}
                      onChange={(e) => setNewEmail(e.target.value)}
                      placeholder="user@example.com"
                      required
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is-admin"
                      checked={isAdminUser}
                      onChange={(e) => setIsAdminUser(e.target.checked)}
                      className="h-4 w-4"
                    />
                    <Label htmlFor="is-admin">Make admin</Label>
                  </div>
                  <div className="flex gap-2">
                    <Button type="submit" disabled={isAddingUser}>
                      {isAddingUser && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                      Create User
                    </Button>
                    <Button type="button" variant="outline" onClick={() => setShowAddUser(false)}>
                      Cancel
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          <PendingRegistrations onAction={handleRefresh} />

          <Card>
            <CardHeader>
              <CardTitle>All Users</CardTitle>
              <CardDescription>Manage all registered users</CardDescription>
            </CardHeader>
            <CardContent>
              <UserList onRefresh={handleRefresh} />
            </CardContent>
          </Card>
        </>
      )}

      {activeTab === 'apps' && (
        <Card>
          <CardHeader>
            <CardTitle>App Management</CardTitle>
            <CardDescription>Manage apps and access permissions</CardDescription>
          </CardHeader>
          <CardContent>
            <AppManagement onRefresh={handleRefresh} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
