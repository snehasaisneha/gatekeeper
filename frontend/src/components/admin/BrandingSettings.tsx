import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api, type AccentColor, type BrandingAdmin, type AccentPreset } from '@/lib/api';
import { Loader2, Check, X, Palette, Image, RefreshCw } from 'lucide-react';
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
      const updated = await api.admin.updateBranding({
        logo_url: logoUrl || null,
        logo_square_url: logoSquareUrl || null,
        favicon_url: faviconUrl || null,
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
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Logo Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Image className="h-5 w-5" />
            Logo Settings
          </CardTitle>
          <CardDescription>
            Configure your organization's logos. Leave empty to use "{appName}" text.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Full Logo */}
          <div className="space-y-2">
            <Label htmlFor="logo-url">Full Logo URL</Label>
            <Input
              id="logo-url"
              placeholder="https://example.com/logo.png"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Used in page headers and emails. Recommended size: 200x48px
            </p>
            {logoUrl && (
              <div className="mt-2 p-4 border rounded bg-muted/50">
                <p className="text-xs text-muted-foreground mb-2">Preview:</p>
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
            <Label htmlFor="logo-square-url">Square Logo URL</Label>
            <Input
              id="logo-square-url"
              placeholder="https://example.com/logo-square.png"
              value={logoSquareUrl}
              onChange={(e) => setLogoSquareUrl(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Used in compact spaces and mobile views. Recommended size: 64x64px
            </p>
            {logoSquareUrl && (
              <div className="mt-2 p-4 border rounded bg-muted/50">
                <p className="text-xs text-muted-foreground mb-2">Preview:</p>
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
            <Label htmlFor="favicon-url">Favicon URL</Label>
            <Input
              id="favicon-url"
              placeholder="https://example.com/favicon.ico"
              value={faviconUrl}
              onChange={(e) => setFaviconUrl(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Browser tab icon. Recommended: .ico, .png, or .svg, 32x32px
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Accent Color */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Palette className="h-5 w-5" />
            Accent Color
          </CardTitle>
          <CardDescription>
            Choose the primary accent color for buttons, borders, and highlights.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-3">
            {presets.map((preset) => (
              <button
                key={preset.name}
                onClick={() => setAccentColor(preset.name as AccentColor)}
                className={`relative flex flex-col items-center gap-2 p-3 rounded border-2 transition-all ${
                  accentColor === preset.name
                    ? 'border-black ring-2 ring-offset-2 ring-black'
                    : 'border-gray-200 hover:border-gray-400'
                }`}
              >
                <div
                  className="w-10 h-10 rounded-sm border border-gray-300"
                  style={{ backgroundColor: preset.hex }}
                />
                <span className="text-xs font-medium capitalize">{preset.name}</span>
                {accentColor === preset.name && (
                  <Check className="absolute top-1 right-1 h-4 w-4 text-black" />
                )}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex items-center justify-between">
        <div>
          {error && (
            <p className="text-sm text-destructive flex items-center gap-1">
              <X className="h-4 w-4" />
              {error}
            </p>
          )}
          {success && (
            <p className="text-sm text-green-600 flex items-center gap-1">
              <Check className="h-4 w-4" />
              Branding saved successfully
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => window.location.reload()}
            disabled={saving}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Preview Changes
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
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
