import * as React from 'react';
import { api, ApiError } from '@/lib/api';
import type { User, UserAppAccess } from '@/lib/api';
import { PasskeyManager } from './PasskeyManager';
import { DeleteAccount } from './DeleteAccount';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, LogOut, ArrowLeft, Check, Pencil, X, AppWindow } from 'lucide-react';

interface AccountPageProps {
  appName: string;
}

export function AccountPage({ appName }: AccountPageProps) {
  const [user, setUser] = React.useState<User | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isSigningOut, setIsSigningOut] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Profile editing state
  const [isEditingName, setIsEditingName] = React.useState(false);
  const [editName, setEditName] = React.useState('');
  const [isSavingName, setIsSavingName] = React.useState(false);
  const [nameError, setNameError] = React.useState<string | null>(null);

  // Apps state
  const [apps, setApps] = React.useState<UserAppAccess[]>([]);
  const [isLoadingApps, setIsLoadingApps] = React.useState(true);

  React.useEffect(() => {
    async function fetchUser() {
      try {
        const userData = await api.auth.me();
        setUser(userData);
        setEditName(userData.name || '');
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          window.location.href = '/signin?redirect=/account';
          return;
        }
        setError('Failed to load user data');
      } finally {
        setIsLoading(false);
      }
    }
    fetchUser();
  }, []);

  React.useEffect(() => {
    async function fetchApps() {
      try {
        const userApps = await api.auth.myApps();
        setApps(userApps);
      } catch {
        // Silently fail - apps section just won't show
      } finally {
        setIsLoadingApps(false);
      }
    }
    fetchApps();
  }, []);

  const handleSaveName = async () => {
    setIsSavingName(true);
    setNameError(null);
    try {
      const updatedUser = await api.auth.updateProfile({ name: editName || undefined });
      setUser(updatedUser);
      setIsEditingName(false);
    } catch (err) {
      setNameError(err instanceof ApiError ? err.message : 'Failed to update name');
    } finally {
      setIsSavingName(false);
    }
  };

  const handleCancelEdit = () => {
    setEditName(user?.name || '');
    setIsEditingName(false);
    setNameError(null);
  };

  const handleSignOut = async () => {
    setIsSigningOut(true);
    try {
      await api.auth.signout();
      window.location.href = '/signin';
    } catch {
      setIsSigningOut(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="flex items-center justify-center min-h-screen p-4">
        <Alert variant="destructive" className="max-w-md">
          <AlertDescription>{error || 'Please sign in to continue'}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">{appName}</h1>
            <p className="text-muted-foreground">Account Settings</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" asChild>
              <a href="/">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </a>
            </Button>
            <Button variant="outline" onClick={handleSignOut} disabled={isSigningOut}>
              {isSigningOut ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <LogOut className="h-4 w-4 mr-2" />
              )}
              Sign Out
            </Button>
          </div>
        </div>

        {/* Profile Section */}
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>Manage your account information</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label className="text-sm text-muted-foreground">Email</Label>
              <p className="font-medium">{user.email}</p>
              {user.is_admin && (
                <Badge variant="secondary" className="mt-1">Admin</Badge>
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
                  <p className="font-medium">{user.name || <span className="text-muted-foreground italic">Not set</span>}</p>
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

        {/* My Apps Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AppWindow className="h-5 w-5" />
              My Apps
            </CardTitle>
            <CardDescription>Apps you have access to</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingApps ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : apps.length === 0 ? (
              <p className="text-muted-foreground text-sm py-4">
                You don't have access to any apps yet.
              </p>
            ) : (
              <div className="space-y-3">
                {apps.map((app) => (
                  <div
                    key={app.app_slug}
                    className="flex items-center justify-between p-3 rounded-lg border bg-muted/30"
                  >
                    <div>
                      <p className="font-medium">{app.app_name}</p>
                      <p className="text-sm text-muted-foreground">{app.app_slug}</p>
                    </div>
                    {app.role && (
                      <Badge variant="outline">{app.role}</Badge>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <PasskeyManager />

        <DeleteAccount isSeeded={user.is_seeded} />
      </div>
    </div>
  );
}
