import * as React from 'react';
import { AuthProvider, useRequireAuth } from './AuthContext';
import { TopBar } from './TopBar';
import { AppCard } from './AppCard';
import { NameSetupModal } from './auth/NameSetupModal';
import { api } from '@/lib/api';
import type { UserAppAccess } from '@/lib/api';

interface HomePageProps {
  appName: string;
}

function HomePageContent({ appName }: HomePageProps) {
  const { user, loading: authLoading, refreshUser } = useRequireAuth();
  const [apps, setApps] = React.useState<UserAppAccess[]>([]);
  const [isLoadingApps, setIsLoadingApps] = React.useState(true);
  const [showNameSetup, setShowNameSetup] = React.useState(false);

  // Check if we should show name setup modal
  React.useEffect(() => {
    if (user && !user.name) {
      // Check if user has skipped this session
      const hasSkipped = sessionStorage.getItem('nameSetupSkipped') === 'true';
      if (!hasSkipped) {
        setShowNameSetup(true);
      }
    }
  }, [user]);

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

  const handleNameSetupComplete = () => {
    setShowNameSetup(false);
    refreshUser();
  };

  const handleNameSetupSkip = () => {
    sessionStorage.setItem('nameSetupSkipped', 'true');
    setShowNameSetup(false);
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-4 border-black border-t-transparent animate-spin"></div>
          <p className="mt-4 text-sm font-bold uppercase tracking-wider">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {showNameSetup && user && (
        <NameSetupModal
          user={user}
          onComplete={handleNameSetupComplete}
          onSkip={handleNameSetupSkip}
        />
      )}
      <TopBar appName={appName} />

      <main className="flex-1 container mx-auto px-6 py-8">
        <div className="max-w-4xl mx-auto space-y-8">
          {/* Welcome Header */}
          <div className="border-4 border-black">
            <div className="bg-black text-white p-6">
              <p className="text-xs font-bold uppercase tracking-wider mb-2">Welcome back</p>
              <h1 className="text-3xl font-bold uppercase">
                {user.name || user.email.split('@')[0]}
              </h1>
            </div>
            <div className="p-4 bg-white flex flex-wrap gap-2 items-center">
              <span className="text-sm">{user.email}</span>
              {user.is_internal && (
                <span className="border-2 border-black px-2 py-0.5 text-xs font-bold uppercase">
                  Internal
                </span>
              )}
              {user.is_admin && (
                <span className="border-2 border-black bg-black text-white px-2 py-0.5 text-xs font-bold uppercase">
                  Super Admin
                </span>
              )}
              {!user.is_admin && user.app_admin_apps.length > 0 && (
                <span className="border-2 border-black px-2 py-0.5 text-xs font-bold uppercase">
                  App Admin
                </span>
              )}
            </div>
          </div>

          {/* Apps Section */}
          <section>
            <h2 className="text-xl font-bold uppercase tracking-wider mb-6 border-b-4 border-black pb-2">
              Your Apps
            </h2>
            <p className="text-sm text-gray-600 mb-4">
              Open any app below to launch it with your current Gatekeeper session.
            </p>

            {isLoadingApps ? (
              <div className="flex items-center justify-center py-16">
                <div className="inline-block w-8 h-8 border-4 border-black border-t-transparent animate-spin"></div>
              </div>
            ) : apps.length === 0 ? (
              <div className="border-4 border-dashed border-black p-8 text-center">
                <p className="font-bold uppercase tracking-wider">No Apps</p>
                <p className="text-sm text-gray-600 mt-2">
                  Contact an administrator for access.
                </p>
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
