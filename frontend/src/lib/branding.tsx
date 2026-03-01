import { useEffect, useState } from 'react';
import { api, type Branding } from './api';

// Extend window type for branding
declare global {
  interface Window {
    __BRANDING__?: Branding;
  }
}

const defaultBranding: Branding = {
  logo_url: null,
  logo_square_url: null,
  favicon_url: null,
  accent_color: 'ink',
  accent_hex: '#000000',
};

// Get app name from meta tag (set by Astro from env)
export function getAppName(): string {
  if (typeof document === 'undefined') return 'Gatekeeper';
  return document.querySelector('meta[name="app-name"]')?.getAttribute('content') || 'Gatekeeper';
}

// Hook to get branding data
export function useBranding() {
  const [branding, setBranding] = useState<Branding>(() => {
    // Check if branding was already loaded by Astro script
    if (typeof window !== 'undefined' && window.__BRANDING__) {
      return window.__BRANDING__;
    }
    return defaultBranding;
  });
  const [loading, setLoading] = useState(!window?.__BRANDING__);

  useEffect(() => {
    // If already loaded from Astro script, no need to fetch
    if (window.__BRANDING__) {
      setBranding(window.__BRANDING__);
      setLoading(false);
      return;
    }

    // Fetch branding
    const fetchBranding = async () => {
      try {
        const data = await api.auth.branding();
        setBranding(data);
        window.__BRANDING__ = data;
      } catch (error) {
        console.error('Failed to fetch branding:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchBranding();
  }, []);

  return { branding, loading, appName: getAppName() };
}

// Component for displaying logo with fallback to app name
export function Logo({
  variant = 'full',
  className = '',
}: {
  variant?: 'full' | 'square';
  className?: string;
}) {
  const { branding, appName } = useBranding();

  const logoUrl = variant === 'full' ? branding?.logo_url : branding?.logo_square_url;

  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt={appName}
        className={className}
        style={{ maxHeight: variant === 'square' ? '40px' : '48px' }}
      />
    );
  }

  // Fallback to text
  if (variant === 'square') {
    // Show first letter in a square
    return (
      <div
        className={`flex items-center justify-center font-mono font-bold text-white ${className}`}
        style={{
          width: '40px',
          height: '40px',
          backgroundColor: branding?.accent_hex || '#000000',
        }}
      >
        {appName.charAt(0).toUpperCase()}
      </div>
    );
  }

  // Full text logo
  return (
    <span
      className={`font-mono font-bold uppercase tracking-wider ${className}`}
      style={{ color: branding?.accent_hex || '#000000' }}
    >
      {appName}
    </span>
  );
}
