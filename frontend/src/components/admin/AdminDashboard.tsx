import * as React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { UserList } from './UserList';
import { PendingRegistrations } from './PendingRegistrations';
import { AppManagement } from './AppManagement';
import { AddUserModal } from './AddUserModal';
import { DomainManagement } from './DomainManagement';
import { BrandingSettings } from './BrandingSettings';
import { api } from '@/lib/api';
import { UserPlus, AppWindow, Users, Clock, Globe, Palette, ExternalLink } from 'lucide-react';

type TabType = 'users' | 'apps' | 'domains' | 'branding';

export function AdminDashboard() {
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [activeTab, setActiveTab] = React.useState<TabType>('users');
  const [showAddUserModal, setShowAddUserModal] = React.useState(false);

  // Summary stats
  const [pendingCount, setPendingCount] = React.useState(0);
  const [totalUsers, setTotalUsers] = React.useState(0);
  const [totalApps, setTotalApps] = React.useState(0);
  const [totalDomains, setTotalDomains] = React.useState(0);

  React.useEffect(() => {
    async function fetchStats() {
      try {
        const [pendingRes, usersRes, appsRes, domainsRes] = await Promise.all([
          api.admin.listPendingUsers(),
          api.admin.listUsers(1, 1),
          api.admin.listApps(),
          api.admin.listDomains(),
        ]);
        setPendingCount(pendingRes.total);
        setTotalUsers(usersRes.total);
        setTotalApps(appsRes.total);
        setTotalDomains(domainsRes.total);
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
          <h1 className="text-2xl font-bold">Super Admin</h1>
          <p className="text-muted-foreground text-sm">Manage users and apps across the platform</p>
        </div>
        <a
          href="https://gatekeeper-gk.readthedocs.io/en/latest/guides/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-primary hover:underline flex items-center gap-1"
        >
          Admin Guide <ExternalLink className="h-3 w-3" />
        </a>
      </div>

      {/* Stats Overview */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="cursor-pointer hover:border-primary/50 transition-colors" onClick={() => setActiveTab('users')}>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Users</p>
                <p className="text-2xl font-bold">{totalUsers}</p>
              </div>
              <Users className="h-8 w-8 text-muted-foreground/50" />
            </div>
          </CardContent>
        </Card>

        <Card
          className={`cursor-pointer hover:border-primary/50 transition-colors ${pendingCount > 0 ? 'border-orange-500/50' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Pending Approvals</p>
                <p className="text-2xl font-bold">{pendingCount}</p>
              </div>
              <Clock className={`h-8 w-8 ${pendingCount > 0 ? 'text-orange-500' : 'text-muted-foreground/50'}`} />
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:border-primary/50 transition-colors" onClick={() => setActiveTab('apps')}>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Apps</p>
                <p className="text-2xl font-bold">{totalApps}</p>
              </div>
              <AppWindow className="h-8 w-8 text-muted-foreground/50" />
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:border-primary/50 transition-colors" onClick={() => setActiveTab('domains')}>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Approved Domains</p>
                <p className="text-2xl font-bold">{totalDomains}</p>
              </div>
              <Globe className="h-8 w-8 text-muted-foreground/50" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center justify-between border-b">
        <div className="flex gap-1">
          <button
            onClick={() => setActiveTab('users')}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
              activeTab === 'users'
                ? 'border-primary text-foreground font-medium'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <Users className="h-4 w-4" />
            Users
            {pendingCount > 0 && (
              <Badge variant="secondary" className="ml-1 bg-orange-100 text-orange-700 text-xs">
                {pendingCount}
              </Badge>
            )}
          </button>
          <button
            onClick={() => setActiveTab('apps')}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
              activeTab === 'apps'
                ? 'border-primary text-foreground font-medium'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <AppWindow className="h-4 w-4" />
            Apps
          </button>
          <button
            onClick={() => setActiveTab('domains')}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
              activeTab === 'domains'
                ? 'border-primary text-foreground font-medium'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <Globe className="h-4 w-4" />
            Domains
          </button>
          <button
            onClick={() => setActiveTab('branding')}
            className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
              activeTab === 'branding'
                ? 'border-primary text-foreground font-medium'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <Palette className="h-4 w-4" />
            Branding
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
            <h2 className="text-lg font-semibold mb-4">All Users</h2>
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
    </div>
  );
}
