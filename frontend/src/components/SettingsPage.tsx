import * as React from 'react';
import { AuthProvider, useRequireAuth } from './AuthContext';
import { TopBar } from './TopBar';
import { PasskeyManager } from './auth/PasskeyManager';
import { DeleteAccount } from './auth/DeleteAccount';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Check, Pencil, X, User, Bell } from 'lucide-react';
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
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-4 border-black border-t-transparent animate-spin" />
          <p className="mt-4 text-sm font-bold uppercase tracking-wider">Loading...</p>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return null;
  }

  return (
    <div className="min-h-screen bg-white flex flex-col">
      <TopBar appName={appName} />

      <main className="flex-1 container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          {/* Page Header */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold uppercase tracking-wider">Settings</h1>
            <p className="text-sm text-gray-500 mt-1">Manage your account settings</p>
          </div>

          {/* Two-Column Layout */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Left Column */}
            <div className="space-y-6">
              {/* Profile Section */}
              <Card>
                <CardHeader className="border-b-4 border-black bg-black text-white p-4">
                  <CardTitle className="flex items-center gap-2 text-white">
                    <User className="h-5 w-5" />
                    Profile
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 space-y-4">
                  {/* Email */}
                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">
                      Email
                    </label>
                    <p className="font-medium mt-1">{currentUser.email}</p>
                    <div className="flex gap-2 mt-2">
                      {currentUser.is_internal && (
                        <Badge variant="default">Internal</Badge>
                      )}
                      {currentUser.is_admin && (
                        <Badge variant="solid">Super Admin</Badge>
                      )}
                    </div>
                  </div>

                  {/* Display Name */}
                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">
                      Display Name
                    </label>
                    {isEditingName ? (
                      <div className="flex items-center gap-2 mt-1">
                        <Input
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          placeholder="Enter your name"
                          className="flex-1"
                          slim
                          disabled={isSavingName}
                        />
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={handleSaveName}
                          disabled={isSavingName}
                        >
                          {isSavingName ? (
                            <div className="w-4 h-4 border-2 border-black border-t-transparent animate-spin" />
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
                          {currentUser.name || (
                            <span className="text-gray-400 italic">Not set</span>
                          )}
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
                      <p className="text-sm text-red-600 mt-1">{nameError}</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Notifications Section - Admin Only */}
              {currentUser.is_admin && (
                <Card>
                  <CardHeader className="border-b-4 border-black bg-black text-white p-4">
                    <CardTitle className="flex items-center gap-2 text-white">
                      <Bell className="h-5 w-5" />
                      Notifications
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 space-y-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-bold uppercase tracking-wider">
                          Pending Registrations
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          Notify when users need approval
                        </p>
                      </div>
                      <Switch
                        checked={currentUser.notify_new_registrations}
                        onCheckedChange={handleTogglePendingNotifications}
                        disabled={isSavingNotifications}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-bold uppercase tracking-wider">
                          All Registrations
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          Notify on any new sign-up
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
            </div>

            {/* Right Column */}
            <div className="space-y-6">
              {/* Passkeys Section */}
              <PasskeyManager />

              {/* Delete Account Section */}
              <DeleteAccount isSeeded={currentUser.is_seeded} />
            </div>
          </div>
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
