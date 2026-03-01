import * as React from 'react';
import { AuthProvider, useRequireAuth } from './AuthContext';
import { TopBar } from './TopBar';
import { PasskeyManager } from './auth/PasskeyManager';
import { DeleteAccount } from './auth/DeleteAccount';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Loader2, Check, Pencil, X } from 'lucide-react';
import { api, ApiError } from '@/lib/api';

interface SettingsPageProps {
  appName: string;
}

function SettingsPageContent({ appName }: SettingsPageProps) {
  const { user, loading: authLoading } = useRequireAuth();

  // Profile editing state
  const [isEditingName, setIsEditingName] = React.useState(false);
  const [editName, setEditName] = React.useState('');
  const [isSavingName, setIsSavingName] = React.useState(false);
  const [nameError, setNameError] = React.useState<string | null>(null);
  const [currentUser, setCurrentUser] = React.useState(user);
  const [isSavingNotifications, setIsSavingNotifications] = React.useState(false);

  React.useEffect(() => {
    if (user) {
      setCurrentUser(user);
      setEditName(user.name || '');
    }
  }, [user]);

  const handleSaveName = async () => {
    setIsSavingName(true);
    setNameError(null);
    try {
      const updatedUser = await api.auth.updateProfile({ name: editName || undefined });
      setCurrentUser(updatedUser);
      setIsEditingName(false);
    } catch (err) {
      setNameError(err instanceof ApiError ? err.message : 'Failed to update name');
    } finally {
      setIsSavingName(false);
    }
  };

  const handleCancelEdit = () => {
    setEditName(currentUser?.name || '');
    setIsEditingName(false);
    setNameError(null);
  };

  const handleTogglePendingNotifications = async (enabled: boolean) => {
    setIsSavingNotifications(true);
    try {
      const updatedUser = await api.auth.updateProfile({ notify_new_registrations: enabled });
      setCurrentUser(updatedUser);
    } catch (err) {
      console.error('Failed to update notification preferences:', err);
    } finally {
      setIsSavingNotifications(false);
    }
  };

  const handleToggleAllNotifications = async (enabled: boolean) => {
    setIsSavingNotifications(true);
    try {
      const updatedUser = await api.auth.updateProfile({ notify_all_registrations: enabled });
      setCurrentUser(updatedUser);
    } catch (err) {
      console.error('Failed to update notification preferences:', err);
    } finally {
      setIsSavingNotifications(false);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!currentUser) {
    return null; // Will redirect in useRequireAuth
  }

  return (
    <div className="min-h-screen flex flex-col">
      <TopBar appName={appName} />

      <main className="flex-1 container mx-auto px-4 py-8">
        <div className="max-w-2xl mx-auto space-y-6">
          <div>
            <h1 className="text-2xl font-bold">Settings</h1>
            <p className="text-muted-foreground">Manage your account settings</p>
          </div>

          {/* Profile Section */}
          <Card>
            <CardHeader>
              <CardTitle>Profile</CardTitle>
              <CardDescription>Your account information</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-sm text-muted-foreground">Email</Label>
                <p className="font-medium">{currentUser.email}</p>
                {currentUser.is_admin && (
                  <Badge variant="secondary" className="mt-1">Super Admin</Badge>
                )}
              </div>

              <div>
                <Label className="text-sm text-muted-foreground">Display Name</Label>
                {isEditingName ? (
                  <div className="flex items-center gap-2 mt-1">
                    <Input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      placeholder="Enter your name"
                      className="max-w-xs"
                      disabled={isSavingName}
                    />
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={handleSaveName}
                      disabled={isSavingName}
                    >
                      {isSavingName ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Check className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={handleCancelEdit}
                      disabled={isSavingName}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 mt-1">
                    <p className="font-medium">
                      {currentUser.name || <span className="text-muted-foreground italic">Not set</span>}
                    </p>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => setIsEditingName(true)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                  </div>
                )}
                {nameError && (
                  <p className="text-sm text-destructive mt-1">{nameError}</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Notification Settings Section - Super Admin Only */}
          {currentUser.is_admin && (
            <Card>
              <CardHeader>
                <CardTitle>Notifications</CardTitle>
                <CardDescription>Manage your notification preferences</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-sm font-medium">Pending Registrations</Label>
                    <p className="text-sm text-muted-foreground">
                      Notify me when users from non-approved domains sign up and need approval
                    </p>
                  </div>
                  <Switch
                    checked={currentUser.notify_new_registrations}
                    onCheckedChange={handleTogglePendingNotifications}
                    disabled={isSavingNotifications}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-sm font-medium">All Registrations</Label>
                    <p className="text-sm text-muted-foreground">
                      Notify me when any new user signs up, including auto-approved users
                    </p>
                  </div>
                  <Switch
                    checked={currentUser.notify_all_registrations}
                    onCheckedChange={handleToggleAllNotifications}
                    disabled={isSavingNotifications}
                  />
                </div>
              </CardContent>
            </Card>
          )}

          {/* Passkeys Section */}
          <PasskeyManager />

          {/* Delete Account Section */}
          <DeleteAccount isSeeded={currentUser.is_seeded} />
        </div>
      </main>
    </div>
  );
}

export function SettingsPage(props: SettingsPageProps) {
  return (
    <AuthProvider>
      <SettingsPageContent {...props} />
    </AuthProvider>
  );
}
