import * as React from 'react';
import { useAuth } from './AuthContext';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import {
  LogOut,
  Settings,
  Shield,
  ChevronDown,
  Loader2,
} from 'lucide-react';

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
    <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 h-14 flex items-center justify-between">
        <a href="/" className="font-semibold text-lg hover:opacity-80 transition-opacity">
          {appName}
        </a>

        {user && (
          <div className="relative" ref={dropdownRef}>
            <Button
              variant="ghost"
              className="flex items-center gap-2"
              onClick={() => setIsOpen(!isOpen)}
            >
              <span className="text-sm max-w-[200px] truncate">{user.name || user.email}</span>
              <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </Button>

            {isOpen && (
              <div className="absolute right-0 mt-2 w-56 rounded-md border bg-popover shadow-lg z-50">
                <div className="p-2">
                  <div className="px-2 py-1.5 text-sm text-muted-foreground">
                    Signed in as
                  </div>
                  <div className="px-2 py-1.5 text-sm font-medium truncate">
                    {user.email}
                  </div>
                </div>

                <div className="border-t" />

                <div className="p-1">
                  <a
                    href="/settings"
                    className="flex items-center gap-2 px-2 py-1.5 text-sm rounded-sm hover:bg-accent cursor-pointer"
                    onClick={() => setIsOpen(false)}
                  >
                    <Settings className="h-4 w-4" />
                    Settings
                  </a>

                  {isAdmin && (
                    <a
                      href="/admin"
                      className="flex items-center gap-2 px-2 py-1.5 text-sm rounded-sm hover:bg-accent cursor-pointer"
                      onClick={() => setIsOpen(false)}
                    >
                      <Shield className="h-4 w-4" />
                      Super Admin
                    </a>
                  )}
                </div>

                <div className="border-t" />

                <div className="p-1">
                  <button
                    onClick={handleSignOut}
                    disabled={isSigningOut}
                    className="flex items-center gap-2 px-2 py-1.5 text-sm rounded-sm hover:bg-accent w-full text-left disabled:opacity-50"
                  >
                    {isSigningOut ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <LogOut className="h-4 w-4" />
                    )}
                    Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {!user && (
          <a
            href="/signin"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Sign in
          </a>
        )}
      </div>
    </header>
  );
}
