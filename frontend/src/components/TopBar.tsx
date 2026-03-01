import * as React from 'react';
import { useAuth } from './AuthContext';
import { api } from '@/lib/api';
import { useBranding } from '@/lib/branding';

interface TopBarProps {
  appName?: string;
}

export function TopBar({ appName = 'Gatekeeper' }: TopBarProps) {
  const { user, isAdmin } = useAuth();
  const { branding } = useBranding();
  const [isOpen, setIsOpen] = React.useState(false);
  const [isSigningOut, setIsSigningOut] = React.useState(false);
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSignOut = async () => {
    setIsSigningOut(true);
    try {
      await api.auth.signout();
      window.location.href = '/signin';
    } catch {
      setIsSigningOut(false);
    }
  };

  return (
    <header className="border-b-4 bg-white" style={{ borderColor: 'var(--accent-color)' }}>
      <div className="container mx-auto px-6 h-16 flex items-center justify-between">
        <a
          href="/"
          className="text-xl font-bold uppercase tracking-wider hover:opacity-70 transition-opacity px-2 -mx-2 flex items-center"
          style={{ color: 'var(--accent-color)' }}
        >
          {branding?.logo_url ? (
            <img src={branding.logo_url} alt={appName} className="h-8" />
          ) : (
            appName
          )}
        </a>

        {user && (
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="flex items-center gap-2 border-4 px-4 py-2 font-bold uppercase tracking-wider text-sm transition-colors"
              style={{
                borderColor: 'var(--accent-color)',
                color: 'var(--accent-color)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--accent-color)';
                e.currentTarget.style.color = 'white';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.color = 'var(--accent-color)';
              }}
            >
              <span className="max-w-[120px] truncate">
                {user.name || user.email.split('@')[0]}
              </span>
              <span className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}>▼</span>
            </button>

            {isOpen && (
              <div className="absolute right-0 mt-2 w-64 border-4 bg-white shadow-brutal-lg z-50" style={{ borderColor: 'var(--accent-color)' }}>
                {/* User info */}
                <div className="p-4 border-b-4 bg-gray-100" style={{ borderColor: 'var(--accent-color)' }}>
                  <p className="text-xs font-bold uppercase tracking-wider text-gray-500">
                    Signed in as
                  </p>
                  <p className="font-bold truncate mt-1">{user.email}</p>
                </div>

                {/* Menu items */}
                <div className="p-2">
                  <a
                    href="/settings"
                    onClick={() => setIsOpen(false)}
                    className="block px-4 py-2 font-bold uppercase tracking-wider text-sm hover:bg-black hover:text-white transition-colors"
                  >
                    → Settings
                  </a>

                  {isAdmin && (
                    <a
                      href="/admin"
                      onClick={() => setIsOpen(false)}
                      className="block px-4 py-2 font-bold uppercase tracking-wider text-sm hover:bg-black hover:text-white transition-colors"
                    >
                      → Admin
                    </a>
                  )}
                </div>

                <div className="border-t-4 p-2" style={{ borderColor: 'var(--accent-color)' }}>
                  <button
                    onClick={handleSignOut}
                    disabled={isSigningOut}
                    className="w-full text-left px-4 py-2 font-bold uppercase tracking-wider text-sm hover:text-white transition-colors disabled:opacity-50"
                    style={{ color: 'var(--accent-color)' }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = 'var(--accent-color)';
                      e.currentTarget.style.color = 'white';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                      e.currentTarget.style.color = 'var(--accent-color)';
                    }}
                  >
                    {isSigningOut ? '...' : '× Sign Out'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {!user && (
          <a
            href="/signin"
            className="border-4 px-4 py-2 font-bold uppercase tracking-wider text-sm transition-colors"
            style={{ borderColor: 'var(--accent-color)', color: 'var(--accent-color)' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'var(--accent-color)';
              e.currentTarget.style.color = 'white';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = 'var(--accent-color)';
            }}
          >
            Sign In
          </a>
        )}
      </div>
    </header>
  );
}
