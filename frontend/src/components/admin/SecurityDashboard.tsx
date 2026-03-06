import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  api,
  type BannedIP,
  type BannedEmail,
  type SecurityStats,
  type SecurityEvent,
  type BanReason,
  ApiError,
} from '@/lib/api';
import {
  Shield,
  ShieldAlert,
  ShieldX,
  Mail,
  Globe,
  Plus,
  X,
  AlertTriangle,
  Clock,
  Ban,
} from 'lucide-react';

interface SecurityDashboardProps {
  onRefresh?: () => void;
}

export function SecurityDashboard({ onRefresh }: SecurityDashboardProps) {
  const [stats, setStats] = React.useState<SecurityStats | null>(null);
  const [bannedIPs, setBannedIPs] = React.useState<BannedIP[]>([]);
  const [bannedEmails, setBannedEmails] = React.useState<BannedEmail[]>([]);
  const [events, setEvents] = React.useState<SecurityEvent[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Add ban forms
  const [showAddIP, setShowAddIP] = React.useState(false);
  const [showAddEmail, setShowAddEmail] = React.useState(false);
  const [newIP, setNewIP] = React.useState('');
  const [newIPReason, setNewIPReason] = React.useState('');
  const [newEmail, setNewEmail] = React.useState('');
  const [newEmailReason, setNewEmailReason] = React.useState('');
  const [isPattern, setIsPattern] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  // Action loading
  const [actionLoading, setActionLoading] = React.useState<string | null>(null);

  const loadData = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [statsRes, ipsRes, emailsRes, eventsRes] = await Promise.all([
        api.security.getStats(),
        api.security.listBannedIPs(),
        api.security.listBannedEmails(),
        api.security.listEvents(20),
      ]);
      setStats(statsRes);
      setBannedIPs(ipsRes.banned_ips);
      setBannedEmails(emailsRes.banned_emails);
      setEvents(eventsRes.events);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load security data');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  const handleBanIP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newIP.trim()) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await api.security.banIP({
        ip_address: newIP.trim(),
        reason: (newIPReason as BanReason) || 'manual',
        details: newIPReason ? undefined : 'Manually banned',
      });
      setNewIP('');
      setNewIPReason('');
      setShowAddIP(false);
      await loadData();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to ban IP');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBanEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.trim()) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await api.security.banEmail({
        email: newEmail.trim(),
        is_pattern: isPattern,
        reason: (newEmailReason as BanReason) || 'manual',
        details: newEmailReason ? undefined : 'Manually banned',
      });
      setNewEmail('');
      setNewEmailReason('');
      setIsPattern(false);
      setShowAddEmail(false);
      await loadData();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to ban email');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUnbanIP = async (ban: BannedIP) => {
    if (!confirm(`Unban IP ${ban.ip_address}?`)) return;

    setActionLoading(`ip-${ban.id}`);
    try {
      await api.security.unbanIP(ban.id);
      await loadData();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleUnbanEmail = async (ban: BannedEmail) => {
    if (!confirm(`Unban email ${ban.email}?`)) return;

    setActionLoading(`email-${ban.id}`);
    try {
      await api.security.unbanEmail(ban.id);
      await loadData();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const getReasonBadge = (reason: string) => {
    switch (reason) {
      case 'brute_force':
        return <Badge variant="destructive">Brute Force</Badge>;
      case 'rejected_user':
        return <Badge variant="destructive">Rejected User</Badge>;
      case 'spam':
        return <Badge variant="warning">Spam</Badge>;
      case 'rate_limit':
        return <Badge variant="warning">Rate Limit</Badge>;
      case 'associated_ip':
      case 'associated_email':
        return <Badge variant="secondary">Cross-Ban</Badge>;
      case 'disposable_email':
        return <Badge variant="warning">Disposable</Badge>;
      case 'manual':
      default:
        return <Badge variant="default">Manual</Badge>;
    }
  };

  const getEventIcon = (eventType: string) => {
    if (eventType.includes('banned')) return <Ban className="h-4 w-4 text-red-500" />;
    if (eventType.includes('unbanned')) return <Shield className="h-4 w-4 text-green-500" />;
    if (eventType.includes('blocked')) return <ShieldX className="h-4 w-4 text-orange-500" />;
    if (eventType.includes('failed')) return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    return <Shield className="h-4 w-4 text-gray-500" />;
  };

  const formatTimeAgo = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="inline-block w-6 h-6 border-4 border-black border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Stats Overview */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="border-4 border-black p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Blocked Today</p>
              <p className="text-3xl font-bold mt-1">{stats?.blocked_today || 0}</p>
            </div>
            <ShieldX className="h-8 w-8 text-gray-400" />
          </div>
        </div>

        <div className="border-4 border-black p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Banned IPs</p>
              <p className="text-3xl font-bold mt-1">{stats?.banned_ips || 0}</p>
            </div>
            <Globe className="h-8 w-8 text-gray-400" />
          </div>
        </div>

        <div className="border-4 border-black p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Banned Emails</p>
              <p className="text-3xl font-bold mt-1">{stats?.banned_emails || 0}</p>
            </div>
            <Mail className="h-8 w-8 text-gray-400" />
          </div>
        </div>

        <div className="border-4 border-red-500 bg-red-50 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-gray-500">Failed Logins</p>
              <p className="text-3xl font-bold mt-1">{stats?.failed_logins_today || 0}</p>
            </div>
            <ShieldAlert className="h-8 w-8 text-red-500" />
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Banned IPs */}
        <Card>
          <CardHeader className="border-b-4 border-black bg-black text-white p-4">
            <CardTitle className="flex items-center justify-between text-white">
              <div className="flex items-center gap-2">
                <Globe className="h-5 w-5" />
                Banned IPs
              </div>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setShowAddIP(!showAddIP)}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            {showAddIP && (
              <form onSubmit={handleBanIP} className="p-4 border-2 border-black bg-gray-50 space-y-3">
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider">IP Address</label>
                  <Input
                    value={newIP}
                    onChange={(e) => setNewIP(e.target.value)}
                    placeholder="192.168.1.100"
                    slim
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider">Reason (optional)</label>
                  <Input
                    value={newIPReason}
                    onChange={(e) => setNewIPReason(e.target.value)}
                    placeholder="Suspicious activity"
                    slim
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" size="sm" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin" />
                    ) : (
                      'Ban IP'
                    )}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => setShowAddIP(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}

            {bannedIPs.length === 0 ? (
              <p className="text-center text-gray-500 py-4 font-bold uppercase tracking-wider">
                No banned IPs
              </p>
            ) : (
              <div className="space-y-2">
                {bannedIPs.map((ban) => (
                  <div
                    key={ban.id}
                    className="p-3 border-2 border-black hover:bg-gray-50"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-mono font-bold">{ban.ip_address}</p>
                        <div className="flex items-center gap-2 mt-1">
                          {getReasonBadge(ban.reason)}
                          <span className="text-xs text-gray-500">
                            {formatTimeAgo(ban.banned_at)}
                          </span>
                        </div>
                        {ban.associated_email && (
                          <p className="text-xs text-gray-500 mt-1">
                            → Also banned: {ban.associated_email}
                          </p>
                        )}
                        {ban.details && (
                          <p className="text-xs text-gray-500 mt-1">{ban.details}</p>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleUnbanIP(ban)}
                        disabled={actionLoading === `ip-${ban.id}`}
                        className="text-green-600 hover:text-green-600"
                        title="Unban"
                      >
                        {actionLoading === `ip-${ban.id}` ? (
                          <div className="w-4 h-4 border-2 border-green-600 border-t-transparent animate-spin" />
                        ) : (
                          <X className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Banned Emails */}
        <Card>
          <CardHeader className="border-b-4 border-black bg-black text-white p-4">
            <CardTitle className="flex items-center justify-between text-white">
              <div className="flex items-center gap-2">
                <Mail className="h-5 w-5" />
                Banned Emails
              </div>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setShowAddEmail(!showAddEmail)}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            {showAddEmail && (
              <form onSubmit={handleBanEmail} className="p-4 border-2 border-black bg-gray-50 space-y-3">
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider">Email or Pattern</label>
                  <Input
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    placeholder="spam@example.com or *@tempmail.com"
                    slim
                    required
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is-pattern"
                    checked={isPattern}
                    onChange={(e) => setIsPattern(e.target.checked)}
                    className="h-4 w-4 border-2 border-black"
                  />
                  <label htmlFor="is-pattern" className="text-sm font-bold">
                    Pattern (use * as wildcard)
                  </label>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider">Reason (optional)</label>
                  <Input
                    value={newEmailReason}
                    onChange={(e) => setNewEmailReason(e.target.value)}
                    placeholder="Spam account"
                    slim
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" size="sm" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin" />
                    ) : (
                      'Ban Email'
                    )}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => setShowAddEmail(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}

            {bannedEmails.length === 0 ? (
              <p className="text-center text-gray-500 py-4 font-bold uppercase tracking-wider">
                No banned emails
              </p>
            ) : (
              <div className="space-y-2">
                {bannedEmails.map((ban) => (
                  <div
                    key={ban.id}
                    className="p-3 border-2 border-black hover:bg-gray-50"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-mono font-bold">{ban.email}</p>
                          {ban.is_pattern && (
                            <Badge variant="secondary">Pattern</Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          {getReasonBadge(ban.reason)}
                          <span className="text-xs text-gray-500">
                            {formatTimeAgo(ban.banned_at)}
                          </span>
                        </div>
                        {ban.associated_ip && (
                          <p className="text-xs text-gray-500 mt-1">
                            → Also banned IP: {ban.associated_ip}
                          </p>
                        )}
                        {ban.details && (
                          <p className="text-xs text-gray-500 mt-1">{ban.details}</p>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleUnbanEmail(ban)}
                        disabled={actionLoading === `email-${ban.id}`}
                        className="text-green-600 hover:text-green-600"
                        title="Unban"
                      >
                        {actionLoading === `email-${ban.id}` ? (
                          <div className="w-4 h-4 border-2 border-green-600 border-t-transparent animate-spin" />
                        ) : (
                          <X className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Security Events */}
      <Card>
        <CardHeader className="border-b-4 border-black bg-black text-white p-4">
          <CardTitle className="flex items-center gap-2 text-white">
            <Clock className="h-5 w-5" />
            Recent Security Events
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          {events.length === 0 ? (
            <p className="text-center text-gray-500 py-4 font-bold uppercase tracking-wider">
              No recent security events
            </p>
          ) : (
            <div className="space-y-2">
              {events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center gap-3 p-3 border-2 border-black hover:bg-gray-50"
                >
                  {getEventIcon(event.event_type)}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold">
                      {event.event_type.replace(/^security\./, '').replace(/\./g, ' ')}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      {event.ip_address && `IP: ${event.ip_address}`}
                      {event.ip_address && event.email && ' • '}
                      {event.email && `Email: ${event.email}`}
                      {!event.ip_address && !event.email && event.details}
                    </p>
                  </div>
                  <span className="text-xs text-gray-500 whitespace-nowrap">
                    {formatTimeAgo(event.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
