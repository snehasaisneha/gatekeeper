import * as React from 'react';
import { AuthProvider, useAuth, useRequireAuth } from './AuthContext';
import { TopBar } from './TopBar';
import { AppCard } from './AppCard';
import { PublicAppsList } from './PublicAppsList';
import { Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { UserAppAccess } from '@/lib/api';

interface HomePageProps {
  appName: string;
}

function HomePageContent({ appName }: HomePageProps) {
  const { user, loading: authLoading } = useRequireAuth();
  const [apps, setApps] = React.useState<UserAppAccess[]>([]);
  const [isLoadingApps, setIsLoadingApps] = React.useState(true);

  React.useEffect(() => {
    async function fetchApps() {
      try {
        const userApps = await api.auth.myApps();
        setApps(userApps);
      } catch {
        // Silently fail
      } finally {
        setIsLoadingApps(false);
      }
    }

    if (user) {
      fetchApps();
    }
  }, [user]);

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!user) {
    return null; // Will redirect in useRequireAuth
  }

  return (
    <div className="min-h-screen flex flex-col">
      <TopBar appName={appName} />

      <main className="flex-1 container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto space-y-8">
          <div>
            <h1 className="text-3xl font-bold">Welcome back!</h1>
            <p className="text-muted-foreground mt-1">
              Signed in as {user.email}
            </p>
          </div>

          {/* User's Apps Section */}
          <section>
            <h2 className="text-xl font-semibold mb-4">Your Apps</h2>
            {isLoadingApps ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : apps.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground border rounded-lg bg-muted/30">
                <p>You don't have any apps with assigned roles yet.</p>
                <p className="text-sm mt-1">Public apps are available below.</p>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {apps.map((app) => (
                  <AppCard
                    key={app.app_slug}
                    name={app.app_name}
                    description={app.app_description}
                    url={app.app_url}
                    role={app.role}
                  />
                ))}
              </div>
            )}
          </section>

          {/* Public Apps Section */}
          <section>
            <h2 className="text-xl font-semibold mb-4">Public Apps</h2>
            <PublicAppsList userApps={apps} />
          </section>
        </div>
      </main>
    </div>
  );
}

export function HomePage(props: HomePageProps) {
  return (
    <AuthProvider>
      <HomePageContent {...props} />
    </AuthProvider>
  );
}
