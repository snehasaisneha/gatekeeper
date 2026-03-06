import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api, type AccentColor, type BrandingAdmin, type AccentPreset } from '@/lib/api';
import { Check, X, Palette, Image, RefreshCw } from 'lucide-react';
import { getAppName } from '@/lib/branding';

interface BrandingSettingsProps {
  onRefresh?: () => void;
}

export function BrandingSettings({ onRefresh }: BrandingSettingsProps) {
  const [branding, setBranding] = React.useState<BrandingAdmin | null>(null);
  const [presets, setPresets] = React.useState<AccentPreset[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [success, setSuccess] = React.useState(false);

  // Form state
  const [logoUrl, setLogoUrl] = React.useState('');
  const [logoSquareUrl, setLogoSquareUrl] = React.useState('');
  const [faviconUrl, setFaviconUrl] = React.useState('');
  const [accentColor, setAccentColor] = React.useState<AccentColor>('ink');

  const appName = getAppName();

  React.useEffect(() => {
    async function fetchData() {
      try {
        const [brandingData, presetsData] = await Promise.all([
          api.admin.getBranding(),
          api.admin.getAccentPresets(),
        ]);
        setBranding(brandingData);
        setPresets(presetsData.presets);

        // Initialize form
        setLogoUrl(brandingData.logo_url || '');
        setLogoSquareUrl(brandingData.logo_square_url || '');
        setFaviconUrl(brandingData.favicon_url || '');
        setAccentColor(brandingData.accent_color);
      } catch (err) {
        setError('Failed to load branding settings');
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      // Send empty string to clear, actual URL to set
      // The backend will interpret empty string as "clear this field"
      const updated = await api.admin.updateBranding({
        logo_url: logoUrl,
        logo_square_url: logoSquareUrl,
        favicon_url: faviconUrl,
        accent_color: accentColor,
      });
      setBranding(updated);
      setSuccess(true);

      // Apply changes immediately
      document.documentElement.style.setProperty('--accent-color', updated.accent_hex);
      if (updated.favicon_url) {
        const favicon = document.getElementById('favicon');
        if (favicon) {
          favicon.setAttribute('href', updated.favicon_url);
        }
      }

      // Clear the cached branding so it reloads
      (window as any).__BRANDING__ = updated;

      onRefresh?.();

      // Clear success message after a delay
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError('Failed to save branding settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-4 border-black border-t-transparent animate-spin" />
          <p className="mt-4 text-sm font-bold uppercase tracking-wider">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Logo Settings */}
      <Card>
        <CardHeader className="border-b-4 border-black bg-black text-white p-4">
          <CardTitle className="flex items-center gap-2 text-white">
            <Image className="h-5 w-5" />
            Logo Settings
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-6">
          <p className="text-xs text-gray-500">
            Configure your organization's logos. Leave empty to use "{appName}" text.
          </p>

          {/* Full Logo */}
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wider">Full Logo URL</label>
            <Input
              placeholder="https://example.com/logo.png"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              slim
            />
            <p className="text-xs text-gray-500">
              Used in page headers and emails. Recommended size: 200x48px
            </p>
            {logoUrl && (
              <div className="mt-2 p-4 border-2 border-black bg-gray-50">
                <p className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Preview:</p>
                <img
                  src={logoUrl}
                  alt="Logo preview"
                  className="h-12 object-contain"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              </div>
            )}
          </div>

          {/* Square Logo */}
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wider">Square Logo URL</label>
            <Input
              placeholder="https://example.com/logo-square.png"
              value={logoSquareUrl}
              onChange={(e) => setLogoSquareUrl(e.target.value)}
              slim
            />
            <p className="text-xs text-gray-500">
              Used in compact spaces and mobile views. Recommended size: 64x64px
            </p>
            {logoSquareUrl && (
              <div className="mt-2 p-4 border-2 border-black bg-gray-50">
                <p className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Preview:</p>
                <img
                  src={logoSquareUrl}
                  alt="Square logo preview"
                  className="h-10 w-10 object-contain"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              </div>
            )}
          </div>

          {/* Favicon */}
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wider">Favicon URL</label>
            <Input
              placeholder="https://example.com/favicon.ico"
              value={faviconUrl}
              onChange={(e) => setFaviconUrl(e.target.value)}
              slim
            />
            <p className="text-xs text-gray-500">
              Browser tab icon. Recommended: .ico, .png, or .svg, 32x32px
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Accent Color */}
      <Card>
        <CardHeader className="border-b-4 border-black bg-black text-white p-4">
          <CardTitle className="flex items-center gap-2 text-white">
            <Palette className="h-5 w-5" />
            Accent Color
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <p className="text-xs text-gray-500 mb-4">
            Choose the primary accent color for buttons, borders, and highlights.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-3">
            {presets.map((preset) => (
              <button
                key={preset.name}
                onClick={() => setAccentColor(preset.name as AccentColor)}
                className={`relative flex flex-col items-center gap-2 p-3 border-4 transition-all ${
                  accentColor === preset.name
                    ? 'border-black'
                    : 'border-gray-200 hover:border-gray-400'
                }`}
              >
                <div
                  className="w-10 h-10 border-2 border-gray-300"
                  style={{ backgroundColor: preset.hex }}
                />
                <span className="text-xs font-bold uppercase tracking-wider">{preset.name}</span>
                {accentColor === preset.name && (
                  <Check className="absolute top-1 right-1 h-4 w-4 text-black" />
                )}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex items-center justify-between p-4 border-4 border-black">
        <div>
          {error && (
            <p className="text-sm text-red-600 flex items-center gap-1 font-bold">
              <X className="h-4 w-4" />
              {error}
            </p>
          )}
          {success && (
            <p className="text-sm text-green-600 flex items-center gap-1 font-bold">
              <Check className="h-4 w-4" />
              Branding saved successfully
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => window.location.reload()}
            disabled={saving}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Preview Changes
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin mr-2" />
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
