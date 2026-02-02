import * as React from 'react';
import { api, ApiError } from '@/lib/api';
import type { App } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, X, AppWindow } from 'lucide-react';

interface AddUserModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export function AddUserModal({ onClose, onSuccess }: AddUserModalProps) {
  const [email, setEmail] = React.useState('');
  const [isAdmin, setIsAdmin] = React.useState(false);
  const [selectedApps, setSelectedApps] = React.useState<Set<string>>(new Set());
  const [apps, setApps] = React.useState<App[]>([]);
  const [isLoadingApps, setIsLoadingApps] = React.useState(true);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    async function fetchApps() {
      try {
        const response = await api.admin.listApps();
        setApps(response.apps);
      } catch {
        // Silently fail - app selection just won't be available
      } finally {
        setIsLoadingApps(false);
      }
    }
    fetchApps();
  }, []);

  const toggleApp = (slug: string) => {
    setSelectedApps((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(slug)) {
        newSet.delete(slug);
      } else {
        newSet.add(slug);
      }
      return newSet;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      // Create the user
      const user = await api.admin.createUser(email, isAdmin, true);

      // Grant access to selected apps (if any) - skip for super admins
      if (!isAdmin && selectedApps.size > 0) {
        await api.admin.bulkGrantAccess({
          emails: [user.email],
          app_slugs: Array.from(selectedApps),
        });
      }

      onSuccess();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to create user');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-background border rounded-lg shadow-lg w-full max-w-lg mx-4 p-6 max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-muted-foreground hover:text-foreground"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Add New User</h2>
            <p className="text-sm text-muted-foreground">
              Create a user account and optionally grant access to apps.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                required
                disabled={isSubmitting}
              />
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is-admin"
                checked={isAdmin}
                onChange={(e) => {
                  setIsAdmin(e.target.checked);
                  if (e.target.checked) {
                    setSelectedApps(new Set()); // Super admins have access to all apps
                  }
                }}
                className="h-4 w-4"
                disabled={isSubmitting}
              />
              <Label htmlFor="is-admin">Make Super Admin (has access to all apps)</Label>
            </div>

            {!isAdmin && (
              <div className="space-y-2">
                <Label>Grant access to apps (optional)</Label>
                <p className="text-xs text-muted-foreground">
                  User will receive an email notification for each app they're granted access to.
                </p>
                {isLoadingApps ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                ) : apps.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-2">No apps available.</p>
                ) : (
                  <div className="rounded-md border max-h-48 overflow-y-auto">
                    {apps.map((app) => (
                      <label
                        key={app.slug}
                        className="flex items-center gap-3 p-3 hover:bg-muted/50 cursor-pointer border-b last:border-b-0"
                      >
                        <input
                          type="checkbox"
                          checked={selectedApps.has(app.slug)}
                          onChange={() => toggleApp(app.slug)}
                          className="h-4 w-4"
                          disabled={isSubmitting}
                        />
                        <AppWindow className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="font-medium text-sm">{app.name}</p>
                          <p className="text-xs text-muted-foreground truncate">{app.slug}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Create User
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
