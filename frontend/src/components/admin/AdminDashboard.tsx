import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { UserList } from './UserList';
import { PendingRegistrations } from './PendingRegistrations';
import { AppManagement } from './AppManagement';
import { AddUserModal } from './AddUserModal';
import { DomainManagement } from './DomainManagement';
import { BrandingSettings } from './BrandingSettings';
import { SecurityDashboard } from './SecurityDashboard';
import { api } from '@/lib/api';
import { UserPlus, AppWindow, Users, Clock, Globe, Palette, Shield, ExternalLink } from 'lucide-react';

type TabType = 'users' | 'apps' | 'domains' | 'branding' | 'security';

export function AdminDashboard() {
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [activeTab, setActiveTab] = React.useState<TabType>('users');
  const [showAddUserModal, setShowAddUserModal] = React.useState(false);

  // Summary stats
  const [pendingCount, setPendingCount] = React.useState(0);
  const [totalUsers, setTotalUsers] = React.useState(0);
  const [totalApps, setTotalApps] = React.useState(0);
  const [totalDomains, setTotalDomains] = React.useState(0);
  const [blockedToday, setBlockedToday] = React.useState(0);

  React.useEffect(() => {
    async function fetchStats() {
      try {
        const [pendingRes, usersRes, appsRes, domainsRes, securityRes] = await Promise.all([
          api.admin.listPendingUsers(),
          api.admin.listUsers(1, 1),
          api.admin.listApps(),
          api.admin.listDomains(),
          api.security.getStats(),
        ]);
        setPendingCount(pendingRes.total);
        setTotalUsers(usersRes.total);
        setTotalApps(appsRes.total);
        setTotalDomains(domainsRes.total);
        setBlockedToday(securityRes.blocked_today);
      } catch {
        // Silently fail
      }
    }
    fetchStats();
  }, [refreshKey]);

  const handleRefresh = () => {
    setRefreshKey((k) => k + 1);
  };

  const handleAddUserSuccess = () => {
    setShowAddUserModal(false);
    handleRefresh();
  };

  return (
    <div className="space-y-6" key={refreshKey}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold uppercase tracking-wider">Super Admin</h1>
          <p className="text-gray-500 text-sm">Manage users and apps across the platform</p>
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

      {/* Stats Overview */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <button
          onClick={() => setActiveTab('users')}
          className="border-4 border-black p-4 hover:bg-gray-50 transition-colors text-left"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Total Users</p>
              <p className="text-3xl font-bold mt-1">{totalUsers}</p>
            </div>
            <Users className="h-8 w-8 text-gray-400" />
          </div>
        </button>

        <button
          onClick={() => setActiveTab('users')}
          className={`border-4 p-4 hover:bg-gray-50 transition-colors text-left ${
            pendingCount > 0 ? 'border-orange-500 bg-orange-50' : 'border-black'
          }`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Pending</p>
              <p className="text-3xl font-bold mt-1">{pendingCount}</p>
            </div>
            <Clock className={`h-8 w-8 ${pendingCount > 0 ? 'text-orange-500' : 'text-gray-400'}`} />
          </div>
        </button>

        <button
          onClick={() => setActiveTab('apps')}
          className="border-4 border-black p-4 hover:bg-gray-50 transition-colors text-left"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Apps</p>
              <p className="text-3xl font-bold mt-1">{totalApps}</p>
            </div>
            <AppWindow className="h-8 w-8 text-gray-400" />
          </div>
        </button>

        <button
          onClick={() => setActiveTab('domains')}
          className="border-4 border-black p-4 hover:bg-gray-50 transition-colors text-left"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Domains</p>
              <p className="text-3xl font-bold mt-1">{totalDomains}</p>
            </div>
            <Globe className="h-8 w-8 text-gray-400" />
          </div>
        </button>

        <button
          onClick={() => setActiveTab('security')}
          className={`border-4 p-4 hover:bg-gray-50 transition-colors text-left ${
            blockedToday > 0 ? 'border-red-500 bg-red-50' : 'border-black'
          }`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Blocked Today</p>
              <p className="text-3xl font-bold mt-1">{blockedToday}</p>
            </div>
            <Shield className={`h-8 w-8 ${blockedToday > 0 ? 'text-red-500' : 'text-gray-400'}`} />
          </div>
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center justify-between border-b-4 border-black">
        <div className="flex">
          <button
            onClick={() => setActiveTab('users')}
            className={`flex items-center gap-2 px-4 py-3 font-bold uppercase tracking-wider text-sm transition-colors ${
              activeTab === 'users'
                ? 'bg-black text-white'
                : 'bg-white text-black hover:bg-gray-100'
            }`}
          >
            <Users className="h-4 w-4" />
            Users
            {pendingCount > 0 && (
              <Badge variant="warning" className="ml-1">
                {pendingCount}
              </Badge>
            )}
          </button>
          <button
            onClick={() => setActiveTab('apps')}
            className={`flex items-center gap-2 px-4 py-3 font-bold uppercase tracking-wider text-sm transition-colors ${
              activeTab === 'apps'
                ? 'bg-black text-white'
                : 'bg-white text-black hover:bg-gray-100'
            }`}
          >
            <AppWindow className="h-4 w-4" />
            Apps
          </button>
          <button
            onClick={() => setActiveTab('domains')}
            className={`flex items-center gap-2 px-4 py-3 font-bold uppercase tracking-wider text-sm transition-colors ${
              activeTab === 'domains'
                ? 'bg-black text-white'
                : 'bg-white text-black hover:bg-gray-100'
            }`}
          >
            <Globe className="h-4 w-4" />
            Domains
          </button>
          <button
            onClick={() => setActiveTab('branding')}
            className={`flex items-center gap-2 px-4 py-3 font-bold uppercase tracking-wider text-sm transition-colors ${
              activeTab === 'branding'
                ? 'bg-black text-white'
                : 'bg-white text-black hover:bg-gray-100'
            }`}
          >
            <Palette className="h-4 w-4" />
            Branding
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`flex items-center gap-2 px-4 py-3 font-bold uppercase tracking-wider text-sm transition-colors ${
              activeTab === 'security'
                ? 'bg-black text-white'
                : 'bg-white text-black hover:bg-gray-100'
            }`}
          >
            <Shield className="h-4 w-4" />
            Security
            {blockedToday > 0 && (
              <Badge variant="destructive" className="ml-1">
                {blockedToday}
              </Badge>
            )}
          </button>
        </div>

        {activeTab === 'users' && (
          <Button size="sm" onClick={() => setShowAddUserModal(true)}>
            <UserPlus className="h-4 w-4 mr-2" />
            Add User
          </Button>
        )}
      </div>

      {/* Tab Content */}
      {activeTab === 'users' && (
        <div className="space-y-6">
          {showAddUserModal && (
            <AddUserModal
              onClose={() => setShowAddUserModal(false)}
              onSuccess={handleAddUserSuccess}
            />
          )}

          {pendingCount > 0 && <PendingRegistrations onAction={handleRefresh} />}

          <div>
            <h2 className="text-lg font-bold uppercase tracking-wider mb-4">All Users</h2>
            <UserList onRefresh={handleRefresh} />
          </div>
        </div>
      )}

      {activeTab === 'apps' && (
        <div>
          <AppManagement onRefresh={handleRefresh} />
        </div>
      )}

      {activeTab === 'domains' && (
        <div>
          <DomainManagement onRefresh={handleRefresh} />
        </div>
      )}

      {activeTab === 'branding' && (
        <div>
          <BrandingSettings onRefresh={handleRefresh} />
        </div>
      )}

      {activeTab === 'security' && (
        <div>
          <SecurityDashboard onRefresh={handleRefresh} />
        </div>
      )}
    </div>
  );
}
