import * as React from 'react';
import { api, ApiError } from '@/lib/api';
import type { User } from '@/lib/api';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  error: string | null;
  isAdmin: boolean;
  refresh: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const fetchUser = React.useCallback(async () => {
    try {
      const userData = await api.auth.me();
      setUser(userData);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
      } else {
        setError('Failed to load user data');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    await fetchUser();
  }, [fetchUser]);

  const value = React.useMemo(
    () => ({
      user,
      loading,
      error,
      isAdmin: user?.is_admin ?? false,
      refresh,
    }),
    [user, loading, error, refresh]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export function useRequireAuth(redirectTo = '/signin') {
  const { user, loading, refresh } = useAuth();

  React.useEffect(() => {
    if (!loading && !user) {
      const currentPath = window.location.pathname;
      window.location.href = `${redirectTo}?redirect=${encodeURIComponent(currentPath)}`;
    }
  }, [user, loading, redirectTo]);

  return { user, loading, authenticated: !!user, refreshUser: refresh };
}
