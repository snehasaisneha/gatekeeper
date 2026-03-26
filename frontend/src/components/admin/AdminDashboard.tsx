import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { UserList } from './UserList';
import { PendingRegistrations } from './PendingRegistrations';
import { AppManagement } from './AppManagement';
import { AddUserModal } from './AddUserModal';
import { DomainManagement } from './DomainManagement';
import { BrandingSettings } from './BrandingSettings';
import { SecurityDashboard } from './SecurityDashboard';
import { api } from '@/lib/api';
import { useAuth } from '../AuthContext';
import { UserPlus, AppWindow, Users, Clock, Globe, Palette, Shield, ExternalLink } from 'lucide-react';

type TabType = 'users' | 'apps' | 'domains' | 'branding' | 'security';

interface AdminDashboardProps {
  isGlobalAdmin: boolean;
}

export function AdminDashboard({ isGlobalAdmin }: AdminDashboardProps) {
  const { user } = useAuth();
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [activeTab, setActiveTab] = React.useState<TabType>(isGlobalAdmin ? 'users' : 'apps');
  const [showAddUserModal, setShowAddUserModal] = React.useState(false);
  const [pendingCount, setPendingCount] = React.useState(0);
  const [totalUsers, setTotalUsers] = React.useState(0);
  const [totalApps, setTotalApps] = React.useState(0);
  const [totalDomains, setTotalDomains] = React.useState(0);
  const [blockedToday, setBlockedToday] = React.useState(0);
  const [authIndexingProtection, setAuthIndexingProtection] = React.useState<'checking' | 'ok' | 'warning'>('checking');

  React.useEffect(() => {
    if (!isGlobalAdmin) return;
    async function fetchStats() {
      try {
        const pendingRes = await api.admin.listPendingUsers();
        setPendingCount(pendingRes.total);
      } catch {}
      try {
        const usersRes = await api.admin.listUsers(1, 1);
        setTotalUsers(usersRes.total);
      } catch {}
      try {
        const appsRes = await api.admin.listApps();
        setTotalApps(appsRes.total);
      } catch {}
      try {
        const domainsRes = await api.admin.listDomains();
        setTotalDomains(domainsRes.total);
      } catch {}
      try {
        const securityRes = await api.security.getStats();
        setBlockedToday(securityRes.blocked_today);
      } catch {}
    }
    fetchStats();
  }, [isGlobalAdmin, refreshKey]);

  React.useEffect(() => {
    if (!isGlobalAdmin) return;
    async function checkAuthIndexingProtection() {
      try {
        const [rootResponse, robotsResponse] = await Promise.all([
          fetch('/', { method: 'HEAD', credentials: 'include', cache: 'no-store' }),
          fetch('/robots.txt', { credentials: 'include', cache: 'no-store' }),
        ]);
        const xRobotsTag = rootResponse.headers.get('x-robots-tag')?.toLowerCase() || '';
        const robotsText = robotsResponse.ok ? (await robotsResponse.text()).toLowerCase() : '';
        setAuthIndexingProtection(
          xRobotsTag.includes('noindex') && robotsText.includes('disallow: /') ? 'ok' : 'warning'
        );
      } catch {
        setAuthIndexingProtection('warning');
      }
    }
    checkAuthIndexingProtection();
  }, [isGlobalAdmin]);

  const handleRefresh = () => setRefreshKey((k) => k + 1);

  return (
    <div className="space-y-6" key={refreshKey}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold uppercase tracking-wider">
            {isGlobalAdmin ? 'Super Admin' : 'App Admin'}
          </h1>
          <p className="text-gray-500 text-sm">
            {isGlobalAdmin
              ? 'Manage users and apps across the platform'
              : 'Manage access and settings for your assigned apps'}
          </p>
        </div>
        <a
          href="https://gatekeeper-gk.readthedocs.io/en/latest/guides/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-black hover:underline flex items-center gap-1 font-bold uppercase tracking-wider"
        >
          Admin Guide <ExternalLink className="h-3 w-3" />
        </a>
      </div>

      {isGlobalAdmin && authIndexingProtection === 'warning' && (
        <Alert className="border-2 border-yellow-500 bg-yellow-50">
          <AlertDescription className="text-sm">
            <strong>Auth host indexing protection is incomplete.</strong> Add
            <code className="mx-1 bg-yellow-200 px-1 font-mono text-xs">X-Robots-Tag: noindex, nofollow, noarchive</code>
            to the public auth nginx server block and make sure
            <code className="mx-1 bg-yellow-200 px-1 font-mono text-xs">/robots.txt</code>
            disallows crawlers.
          </AlertDescription>
        </Alert>
      )}

      {isGlobalAdmin ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <button onClick={() => setActiveTab('users')} className="border-4 border-black p-4 hover:bg-gray-50 text-left">
            <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Total Users</p>
            <div className="mt-2 flex items-center justify-between">
              <p className="text-3xl font-bold">{totalUsers}</p>
              <Users className="h-8 w-8 text-gray-400" />
            </div>
          </button>
          <button
            onClick={() => setActiveTab('users')}
            className={`border-4 p-4 hover:bg-gray-50 text-left ${pendingCount > 0 ? 'border-orange-500 bg-orange-50' : 'border-black'}`}
          >
            <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Pending</p>
            <div className="mt-2 flex items-center justify-between">
              <p className="text-3xl font-bold">{pendingCount}</p>
              <Clock className={`h-8 w-8 ${pendingCount > 0 ? 'text-orange-500' : 'text-gray-400'}`} />
            </div>
          </button>
          <button onClick={() => setActiveTab('apps')} className="border-4 border-black p-4 hover:bg-gray-50 text-left">
            <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Apps</p>
            <div className="mt-2 flex items-center justify-between">
              <p className="text-3xl font-bold">{totalApps}</p>
              <AppWindow className="h-8 w-8 text-gray-400" />
            </div>
          </button>
          <button onClick={() => setActiveTab('domains')} className="border-4 border-black p-4 hover:bg-gray-50 text-left">
            <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Domains</p>
            <div className="mt-2 flex items-center justify-between">
              <p className="text-3xl font-bold">{totalDomains}</p>
              <Globe className="h-8 w-8 text-gray-400" />
            </div>
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`border-4 p-4 hover:bg-gray-50 text-left ${blockedToday > 0 ? 'border-red-500 bg-red-50' : 'border-black'}`}
          >
            <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Requests Blocked Today</p>
            <div className="mt-2 flex items-center justify-between">
              <p className="text-3xl font-bold">{blockedToday}</p>
              <Shield className={`h-8 w-8 ${blockedToday > 0 ? 'text-red-500' : 'text-gray-400'}`} />
            </div>
          </button>
        </div>
      ) : (
        <div className="border-4 border-black p-4 bg-gray-50">
          <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Assigned Apps</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {user?.app_admin_apps.map((app) => (
              <a
                key={app.app_id}
                href={`/admin/app?slug=${encodeURIComponent(app.app_slug)}`}
                className="border-4 border-black bg-white p-4 hover:bg-black hover:text-white transition-colors"
              >
                <p className="font-bold uppercase tracking-wider">{app.app_name}</p>
                <p className="mt-1 text-xs font-mono">{app.app_slug}</p>
              </a>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between border-b-4 border-black">
        <div className="flex">
          {isGlobalAdmin && (
            <button
              onClick={() => setActiveTab('users')}
              className={`flex items-center gap-2 px-4 py-3 font-bold uppercase tracking-wider text-sm ${activeTab === 'users' ? 'bg-black text-white' : 'bg-white text-black hover:bg-gray-100'}`}
            >
              <Users className="h-4 w-4" />
              Users
              {pendingCount > 0 && <Badge variant="warning" className="ml-1">{pendingCount}</Badge>}
            </button>
          )}
          <button
            onClick={() => setActiveTab('apps')}
            className={`flex items-center gap-2 px-4 py-3 font-bold uppercase tracking-wider text-sm ${activeTab === 'apps' ? 'bg-black text-white' : 'bg-white text-black hover:bg-gray-100'}`}
          >
            <AppWindow className="h-4 w-4" />
            Apps
          </button>
          {isGlobalAdmin && (
            <button
              onClick={() => setActiveTab('domains')}
              className={`flex items-center gap-2 px-4 py-3 font-bold uppercase tracking-wider text-sm ${activeTab === 'domains' ? 'bg-black text-white' : 'bg-white text-black hover:bg-gray-100'}`}
            >
              <Globe className="h-4 w-4" />
              Domains
            </button>
          )}
          {isGlobalAdmin && (
            <button
              onClick={() => setActiveTab('branding')}
              className={`flex items-center gap-2 px-4 py-3 font-bold uppercase tracking-wider text-sm ${activeTab === 'branding' ? 'bg-black text-white' : 'bg-white text-black hover:bg-gray-100'}`}
            >
              <Palette className="h-4 w-4" />
              Branding
            </button>
          )}
          {isGlobalAdmin && (
            <button
              onClick={() => setActiveTab('security')}
              className={`flex items-center gap-2 px-4 py-3 font-bold uppercase tracking-wider text-sm ${activeTab === 'security' ? 'bg-black text-white' : 'bg-white text-black hover:bg-gray-100'}`}
            >
              <Shield className="h-4 w-4" />
              Security
              {blockedToday > 0 && <Badge variant="destructive" className="ml-1">{blockedToday}</Badge>}
            </button>
          )}
        </div>
        {isGlobalAdmin && activeTab === 'users' && (
          <Button size="sm" onClick={() => setShowAddUserModal(true)}>
            <UserPlus className="h-4 w-4 mr-2" />
            Add User
          </Button>
        )}
      </div>

      {isGlobalAdmin && activeTab === 'users' && (
        <div className="space-y-6">
          {showAddUserModal && (
            <AddUserModal onClose={() => setShowAddUserModal(false)} onSuccess={() => {
              setShowAddUserModal(false);
              handleRefresh();
            }} />
          )}
          {pendingCount > 0 && <PendingRegistrations onAction={handleRefresh} />}
          <div>
            <h2 className="text-lg font-bold uppercase tracking-wider mb-4">All Users</h2>
            <UserList onRefresh={handleRefresh} />
          </div>
        </div>
      )}

      {activeTab === 'apps' && <AppManagement onRefresh={handleRefresh} />}
      {isGlobalAdmin && activeTab === 'domains' && <DomainManagement onRefresh={handleRefresh} />}
      {isGlobalAdmin && activeTab === 'branding' && <BrandingSettings onRefresh={handleRefresh} />}
      {isGlobalAdmin && activeTab === 'security' && <SecurityDashboard onRefresh={handleRefresh} />}
    </div>
  );
}
