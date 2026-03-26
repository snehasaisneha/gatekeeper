import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { api, type App, ApiError } from '@/lib/api';
import { useAuth } from '../AuthContext';
import { Plus, Trash2, AppWindow, ArrowRight } from 'lucide-react';
import { CreateAppModal } from './CreateAppModal';

interface AppManagementProps {
  onRefresh?: () => void;
}

export function AppManagement({ onRefresh }: AppManagementProps) {
  const { isAdmin } = useAuth();
  const [apps, setApps] = React.useState<App[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = React.useState(false);
  const [actionLoading, setActionLoading] = React.useState<string | null>(null);

  const loadApps = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.admin.listApps();
      setApps(response.apps);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load apps');
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadApps();
  }, [loadApps]);

  const handleDeleteApp = async (slug: string) => {
    if (!isAdmin) return;
    if (!confirm(`Are you sure you want to delete the app "${slug}"? This will remove all access grants.`)) return;
    setActionLoading(slug);
    try {
      await api.admin.deleteApp(slug);
      await loadApps();
      onRefresh?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to delete app');
    } finally {
      setActionLoading(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="inline-block w-6 h-6 border-4 border-black border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AppWindow className="h-5 w-5" />
          <span className="font-bold uppercase tracking-wider">Apps ({apps.length})</span>
        </div>
        {isAdmin && (
          <Button size="sm" onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4 mr-1" />
            Add App
          </Button>
        )}
      </div>

      {showCreateModal && (
        <CreateAppModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={async () => {
            setShowCreateModal(false);
            await loadApps();
            onRefresh?.();
          }}
        />
      )}

      {apps.length === 0 ? (
        <div className="text-center py-8 text-gray-500 border-4 border-dashed border-gray-300">
          <p className="font-bold uppercase tracking-wider">No apps available</p>
          <p className="text-sm mt-1">
            {isAdmin ? 'Create one to get started.' : 'You have not been assigned any app admin scopes.'}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {apps.map((app) => (
            <div key={app.slug} className="border-4 border-black bg-white p-5 space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-bold uppercase tracking-wider">{app.name}</p>
                  <p className="mt-1 text-xs font-mono text-gray-500">{app.slug}</p>
                </div>
                {isAdmin && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDeleteApp(app.slug)}
                    disabled={actionLoading === app.slug}
                    className="text-red-600 hover:text-red-600"
                  >
                    {actionLoading === app.slug ? (
                      <div className="w-4 h-4 border-2 border-red-600 border-t-transparent animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                )}
              </div>
              {app.description && <p className="text-sm text-gray-600">{app.description}</p>}
              {app.app_url && <p className="text-xs font-mono break-all text-gray-500">{app.app_url}</p>}
              <a
                href={`/admin/app?slug=${encodeURIComponent(app.slug)}`}
                className="inline-flex items-center gap-2 border-4 border-black px-4 py-2 font-bold uppercase tracking-wider text-sm hover:bg-black hover:text-white transition-colors"
              >
                Open App Settings
                <ArrowRight className="h-4 w-4" />
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
