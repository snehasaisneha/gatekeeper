import * as React from 'react';
import { useAuth } from './AuthContext';
import { api } from '@/lib/api';

interface TopBarProps {
  appName?: string;
}

export function TopBar({ appName = 'Gatekeeper' }: TopBarProps) {
  const { user, isAdmin } = useAuth();
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
    <header className="border-b-4 border-black bg-white">
      <div className="container mx-auto px-6 h-16 flex items-center justify-between">
        <a
          href="/"
          className="text-xl font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-colors px-2 -mx-2"
        >
          {appName}
        </a>

        {user && (
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="flex items-center gap-2 border-4 border-black px-4 py-2 font-bold uppercase tracking-wider text-sm hover:bg-black hover:text-white transition-colors"
            >
              <span className="max-w-[120px] truncate">
                {user.name || user.email.split('@')[0]}
              </span>
              <span className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}>▼</span>
            </button>

            {isOpen && (
              <div className="absolute right-0 mt-2 w-64 border-4 border-black bg-white shadow-brutal-lg z-50">
                {/* User info */}
                <div className="p-4 border-b-4 border-black bg-gray-100">
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

                <div className="border-t-4 border-black p-2">
                  <button
                    onClick={handleSignOut}
                    disabled={isSigningOut}
                    className="w-full text-left px-4 py-2 font-bold uppercase tracking-wider text-sm hover:bg-black hover:text-white transition-colors disabled:opacity-50"
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
            className="border-4 border-black px-4 py-2 font-bold uppercase tracking-wider text-sm hover:bg-black hover:text-white transition-colors"
          >
            Sign In
          </a>
        )}
      </div>
    </header>
  );
}
