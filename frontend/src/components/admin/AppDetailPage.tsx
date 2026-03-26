import * as React from 'react';
import { AuthProvider, useAuth, useRequireAuth } from '../AuthContext';
import { TopBar } from '../TopBar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { api, ApiError, type AppDetail, type AuditLog } from '@/lib/api';
import { ArrowLeft, Check, Copy, KeyRound, Shield, Trash2, Users } from 'lucide-react';

interface AppDetailPageProps {
  appName: string;
  slug: string;
}

function AppDetailPageContent({ appName, slug }: AppDetailPageProps) {
  const { user, loading: authLoading } = useRequireAuth();
  const { hasAdminAccess } = useAuth();
  const [resolvedSlug, setResolvedSlug] = React.useState(slug);
  const [app, setApp] = React.useState<AppDetail | null>(null);
  const [logs, setLogs] = React.useState<AuditLog[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [saveState, setSaveState] = React.useState<'idle' | 'saving'>('idle');
  const [grantState, setGrantState] = React.useState<'idle' | 'saving'>('idle');
  const [apiKeyState, setApiKeyState] = React.useState<'idle' | 'saving'>('idle');
  const [revealedKey, setRevealedKey] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);
  const [editName, setEditName] = React.useState('');
  const [editDescription, setEditDescription] = React.useState('');
  const [editUrl, setEditUrl] = React.useState('');
  const [editRoles, setEditRoles] = React.useState('');
  const [editAdminRoles, setEditAdminRoles] = React.useState('');
  const [grantEmail, setGrantEmail] = React.useState('');
  const [grantRole, setGrantRole] = React.useState('');
  const [apiKeyName, setApiKeyName] = React.useState('');

  React.useEffect(() => {
    if (slug) {
      setResolvedSlug(slug);
      return;
    }
    const querySlug = new URLSearchParams(window.location.search).get('slug') || '';
    setResolvedSlug(querySlug);
  }, [slug]);

  const load = React.useCallback(async () => {
    if (!resolvedSlug) {
      setError('Missing app slug');
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const [appResponse, logsResponse] = await Promise.all([
        api.admin.getApp(resolvedSlug),
        api.admin.listAppAuditLogs(resolvedSlug),
      ]);
      setApp(appResponse);
      setLogs(logsResponse.logs);
      setEditName(appResponse.name);
      setEditDescription(appResponse.description || '');
      setEditUrl(appResponse.app_url || '');
      setEditRoles(appResponse.roles);
      setEditAdminRoles(appResponse.admin_roles);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load app settings');
    } finally {
      setIsLoading(false);
    }
  }, [resolvedSlug]);

  React.useEffect(() => {
    if (!authLoading && hasAdminAccess) {
      load();
    }
  }, [authLoading, hasAdminAccess, load]);

  if (authLoading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-4 border-black border-t-transparent animate-spin" />
          <p className="mt-4 text-sm font-bold uppercase tracking-wider">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) return null;

  if (!hasAdminAccess) {
    return (
      <div className="min-h-screen flex flex-col">
        <TopBar appName={appName} />
        <main className="flex-1 flex items-center justify-center">
          <div className="border-4 border-black p-8 text-center">
            <h1 className="text-2xl font-bold uppercase tracking-wider">Access Denied</h1>
            <p className="mt-2 text-sm text-gray-500">You do not have permission to manage admin settings.</p>
          </div>
        </main>
      </div>
    );
  }

  const roleOptions = (app?.roles || 'admin,user').split(',').map((role) => role.trim()).filter(Boolean);

  async function handleSave() {
    if (!app) return;
    setSaveState('saving');
    setError(null);
    try {
      const updated = await api.admin.updateApp(resolvedSlug, {
        name: editName !== app.name ? editName : undefined,
        description: editDescription !== (app.description || '') ? editDescription : undefined,
        app_url: editUrl !== (app.app_url || '') ? editUrl : undefined,
        roles: editRoles !== app.roles ? editRoles : undefined,
        admin_roles: editAdminRoles !== app.admin_roles ? editAdminRoles : undefined,
      });
      setApp({ ...app, ...updated });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to save app settings');
    } finally {
      setSaveState('idle');
    }
  }

  async function handleGrant(e: React.FormEvent) {
    e.preventDefault();
    setGrantState('saving');
    setError(null);
    try {
      await api.admin.grantAccess(resolvedSlug, grantEmail, grantRole || undefined);
      setGrantEmail('');
      setGrantRole('');
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to grant access');
    } finally {
      setGrantState('idle');
    }
  }

  async function handleRevoke(email: string) {
    if (!confirm(`Revoke access for ${email}?`)) return;
    try {
      await api.admin.revokeAccess(resolvedSlug, email);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to revoke access');
    }
  }

  async function handleCreateApiKey(e: React.FormEvent) {
    e.preventDefault();
    setApiKeyState('saving');
    setError(null);
    try {
      const response = await api.admin.createAppApiKey(resolvedSlug, apiKeyName);
      setApiKeyName('');
      setRevealedKey(response.plain_text_key);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create API key');
    } finally {
      setApiKeyState('idle');
    }
  }

  async function handleCopyKey() {
    if (!revealedKey) return;
    await navigator.clipboard.writeText(revealedKey);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  async function handleRevokeKey(apiKeyId: string, name: string) {
    if (!confirm(`Revoke API key "${name}"?`)) return;
    try {
      await api.admin.revokeAppApiKey(resolvedSlug, apiKeyId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to revoke API key');
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <TopBar appName={appName} />
      <main className="flex-1 container mx-auto px-4 py-8">
        <div className="space-y-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <a href="/admin" className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-gray-500 hover:text-black">
                <ArrowLeft className="h-4 w-4" />
                Back To Admin
              </a>
              <h1 className="mt-3 text-2xl font-bold uppercase tracking-wider">{app?.name || resolvedSlug}</h1>
              <p className="mt-1 text-sm font-mono text-gray-500">{resolvedSlug}</p>
            </div>
            {app?.app_url && (
              <a
                href={app.app_url}
                target="_blank"
                rel="noreferrer"
                className="border-4 border-black px-4 py-2 font-bold uppercase tracking-wider text-sm hover:bg-black hover:text-white transition-colors"
              >
                Open App
              </a>
            )}
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {isLoading || !app ? (
            <div className="flex items-center justify-center py-12">
              <div className="inline-block w-8 h-8 border-4 border-black border-t-transparent animate-spin" />
            </div>
          ) : (
            <>
              {revealedKey && (
                <Alert className="border-4 border-black">
                  <AlertDescription className="space-y-3">
                    <p className="font-bold uppercase tracking-wider">New API Key</p>
                    <p className="text-sm">This secret is shown once. Store it in your app-side secret manager.</p>
                    <div className="border-2 border-black bg-gray-100 p-3 font-mono text-sm break-all">{revealedKey}</div>
                    <Button type="button" size="sm" variant="secondary" onClick={handleCopyKey}>
                      {copied ? <Check className="h-4 w-4 mr-2" /> : <Copy className="h-4 w-4 mr-2" />}
                      {copied ? 'Copied' : 'Copy Key'}
                    </Button>
                  </AlertDescription>
                </Alert>
              )}

              <section className="border-4 border-black">
                <div className="bg-black text-white p-4">
                  <h2 className="font-bold uppercase tracking-wider">App Settings</h2>
                </div>
                <div className="p-6 space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-wider">Display Name</label>
                      <Input value={editName} onChange={(e) => setEditName(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-wider">App URL</label>
                      <Input value={editUrl} onChange={(e) => setEditUrl(e.target.value)} />
                    </div>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-wider">Description</label>
                      <textarea
                        value={editDescription}
                        onChange={(e) => setEditDescription(e.target.value)}
                        className="min-h-28 w-full border-4 border-black p-3 text-sm"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-wider">Roles</label>
                      <Input value={editRoles} onChange={(e) => setEditRoles(e.target.value)} />
                      <p className="text-xs text-gray-500">Comma-separated roles. Gatekeeper forwards the selected role in `X-Auth-Role`.</p>
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-wider">Admin Roles</label>
                      <Input value={editAdminRoles} onChange={(e) => setEditAdminRoles(e.target.value)} />
                      <p className="text-xs text-gray-500">Any grant using one of these roles becomes an app admin in Gatekeeper automatically.</p>
                    </div>
                  </div>
                  <Button onClick={handleSave} disabled={saveState === 'saving'}>
                    {saveState === 'saving' && <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin mr-2" />}
                    Save App Settings
                  </Button>
                </div>
              </section>

              <section className="grid gap-6 xl:grid-cols-[2fr_1fr]">
                <div className="border-4 border-black">
                  <div className="bg-black text-white p-4 flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    <h2 className="font-bold uppercase tracking-wider">User Access</h2>
                  </div>
                  <div className="p-6 space-y-6">
                    <form onSubmit={handleGrant} className="grid gap-4 md:grid-cols-[2fr_1fr_auto]">
                      <Input
                        type="email"
                        value={grantEmail}
                        onChange={(e) => setGrantEmail(e.target.value)}
                        placeholder="user@example.com"
                        required
                      />
                      <select
                        value={grantRole}
                        onChange={(e) => setGrantRole(e.target.value)}
                        className="h-11 border-4 border-black px-3 text-sm"
                      >
                        <option value="">No role</option>
                        {roleOptions.map((role) => (
                          <option key={role} value={role}>{role}</option>
                        ))}
                      </select>
                      <Button type="submit" disabled={grantState === 'saving'}>
                        {grantState === 'saving' ? 'Saving' : 'Grant Access'}
                      </Button>
                    </form>
                    <p className="text-xs text-gray-500">
                      App admin status is derived from the app&apos;s configured admin roles: {app.admin_roles || 'none'}.
                    </p>

                    <div className="overflow-x-auto border-2 border-black">
                      <table className="w-full text-sm">
                        <thead className="bg-black text-white">
                          <tr>
                            <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">User</th>
                            <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">Role</th>
                            <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">Scope</th>
                            <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">Granted</th>
                            <th className="p-3 text-right text-xs font-bold uppercase tracking-wider">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {app.users.length === 0 ? (
                            <tr className="border-t-2 border-black">
                              <td colSpan={5} className="p-4 text-center text-gray-500">
                                No explicit access grants yet.
                              </td>
                            </tr>
                          ) : (
                            app.users.map((access) => (
                              <tr key={access.user_id} className="border-t-2 border-black">
                                <td className="p-3">{access.email}</td>
                                <td className="p-3">{access.role ? <Badge>{access.role}</Badge> : <span className="text-gray-400">No role</span>}</td>
                                <td className="p-3">
                                  {access.is_app_admin ? <Badge variant="solid">App Admin</Badge> : <span className="text-gray-500">User</span>}
                                </td>
                                <td className="p-3 text-gray-500">{new Date(access.granted_at).toLocaleString()}</td>
                                <td className="p-3 text-right">
                                  <Button variant="ghost" size="icon" onClick={() => handleRevoke(access.email)}>
                                    <Trash2 className="h-4 w-4 text-red-600" />
                                  </Button>
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                <div className="space-y-6">
                  <section className="border-4 border-black">
                    <div className="bg-black text-white p-4 flex items-center gap-2">
                      <KeyRound className="h-4 w-4" />
                      <h2 className="font-bold uppercase tracking-wider">Scoped API Keys</h2>
                    </div>
                    <div className="p-6 space-y-4">
                      <form onSubmit={handleCreateApiKey} className="space-y-3">
                        <Input
                          value={apiKeyName}
                          onChange={(e) => setApiKeyName(e.target.value)}
                          placeholder="CI sync key"
                          required
                        />
                        <Button type="submit" className="w-full" disabled={apiKeyState === 'saving'}>
                          {apiKeyState === 'saving' ? 'Creating' : 'Create API Key'}
                        </Button>
                      </form>
                      <div className="space-y-3">
                        {app.api_keys.map((apiKey) => (
                          <div key={apiKey.id} className="border-2 border-black p-3">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="font-bold uppercase tracking-wider text-sm">{apiKey.name}</p>
                                <p className="mt-1 text-xs font-mono text-gray-500">{apiKey.key_prefix}</p>
                                <p className="mt-2 text-xs text-gray-500">
                                  Created by {apiKey.created_by_email || 'unknown'}
                                </p>
                                <p className="text-xs text-gray-500">
                                  Last used {apiKey.last_used_at ? new Date(apiKey.last_used_at).toLocaleString() : 'never'}
                                </p>
                              </div>
                              {apiKey.revoked_at ? (
                                <Badge variant="destructive">Revoked</Badge>
                              ) : (
                                <Button variant="ghost" size="icon" onClick={() => handleRevokeKey(apiKey.id, apiKey.name)}>
                                  <Trash2 className="h-4 w-4 text-red-600" />
                                </Button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </section>

                  <section className="border-4 border-black">
                    <div className="bg-black text-white p-4 flex items-center gap-2">
                      <Shield className="h-4 w-4" />
                      <h2 className="font-bold uppercase tracking-wider">Recent Audit</h2>
                    </div>
                    <div className="p-4 space-y-3">
                      {logs.length === 0 ? (
                        <p className="text-sm text-gray-500">No app admin activity yet.</p>
                      ) : (
                        logs.slice(0, 8).map((log) => (
                          <div key={log.id} className="border-2 border-black p-3">
                            <p className="text-xs font-bold uppercase tracking-wider">{log.event_type}</p>
                            <p className="mt-1 text-xs text-gray-500">
                              {new Date(log.timestamp).toLocaleString()} by {log.actor_email || 'system'}
                            </p>
                            {log.details && (
                              <pre className="mt-2 whitespace-pre-wrap break-all text-xs text-gray-600">
                                {JSON.stringify(log.details, null, 2)}
                              </pre>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </section>
                </div>
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export function AppDetailPage(props: AppDetailPageProps) {
  return (
    <AuthProvider>
      <AppDetailPageContent {...props} />
    </AuthProvider>
  );
}
