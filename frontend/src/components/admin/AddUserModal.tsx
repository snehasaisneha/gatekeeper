import * as React from 'react';
import { api, ApiError } from '@/lib/api';
import type { App } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { X, AppWindow, UserPlus } from 'lucide-react';

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
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      <div className="relative bg-white border-4 border-black w-full max-w-lg mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="bg-black text-white p-4 flex justify-between items-center">
          <h2 className="font-bold uppercase tracking-wider flex items-center gap-2">
            <UserPlus className="h-5 w-5" />
            Add New User
          </h2>
          <button
            onClick={onClose}
            className="text-white hover:text-gray-300"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto flex-1">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-wider">
                Email
              </label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                required
                disabled={isSubmitting}
                slim
              />
            </div>

            <div className="flex items-center gap-3 p-3 border-2 border-black">
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
                className="h-5 w-5 border-2 border-black"
                disabled={isSubmitting}
              />
              <label htmlFor="is-admin" className="text-sm font-bold uppercase tracking-wider cursor-pointer">
                Make Super Admin
              </label>
            </div>

            {!isAdmin && (
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider">
                  Grant Access to Apps (optional)
                </label>
                <p className="text-xs text-gray-500">
                  User will receive an email notification for each app.
                </p>
                {isLoadingApps ? (
                  <div className="flex items-center justify-center py-4">
                    <div className="inline-block w-5 h-5 border-4 border-black border-t-transparent animate-spin" />
                  </div>
                ) : apps.length === 0 ? (
                  <p className="text-sm text-gray-500 py-2 text-center">No apps available.</p>
                ) : (
                  <div className="border-2 border-black max-h-48 overflow-y-auto">
                    {apps.map((app) => (
                      <label
                        key={app.slug}
                        className="flex items-center gap-3 p-3 hover:bg-gray-50 cursor-pointer border-b-2 border-black last:border-b-0"
                      >
                        <input
                          type="checkbox"
                          checked={selectedApps.has(app.slug)}
                          onChange={() => toggleApp(app.slug)}
                          className="h-4 w-4 border-2 border-black"
                          disabled={isSubmitting}
                        />
                        <AppWindow className="h-4 w-4 text-gray-500 flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="font-bold text-sm">{app.name}</p>
                          <p className="text-xs text-gray-500 truncate">{app.slug}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}
          </form>
        </div>

        {/* Footer */}
        <div className="border-t-4 border-black p-4 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting || !email}>
            {isSubmitting ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin mr-2" />
            ) : (
              <UserPlus className="h-4 w-4 mr-2" />
            )}
            Create User
          </Button>
        </div>
      </div>
    </div>
  );
}
