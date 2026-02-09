import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { api, type Domain, ApiError } from '@/lib/api';
import { Loader2, Plus, Trash2, Globe } from 'lucide-react';

interface DomainManagementProps {
  onRefresh?: () => void;
}

export function DomainManagement({ onRefresh }: DomainManagementProps) {
  const [domains, setDomains] = React.useState<Domain[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [newDomain, setNewDomain] = React.useState('');
  const [isAdding, setIsAdding] = React.useState(false);
  const [deletingDomain, setDeletingDomain] = React.useState<string | null>(null);

  const loadDomains = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.admin.listDomains();
      setDomains(response.domains);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load domains');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadDomains();
  }, [loadDomains]);

  const handleAddDomain = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDomain.trim()) return;

    setIsAdding(true);
    setError(null);
    try {
      await api.admin.addDomain(newDomain.trim().toLowerCase());
      setNewDomain('');
      await loadDomains();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to add domain');
      }
    } finally {
      setIsAdding(false);
    }
  };

  const handleRemoveDomain = async (domain: string) => {
    if (!confirm(`Remove "${domain}"? Users from this domain will become external users.`)) return;

    setDeletingDomain(domain);
    setError(null);
    try {
      await api.admin.removeDomain(domain);
      await loadDomains();
      onRefresh?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to remove domain');
      }
    } finally {
      setDeletingDomain(null);
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Approved Domains</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Globe className="h-5 w-5" />
          Approved Domains
        </CardTitle>
        <CardDescription>
          Users with emails from these domains are internal users with access to all apps.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleAddDomain} className="flex gap-2">
          <Input
            value={newDomain}
            onChange={(e) => setNewDomain(e.target.value)}
            placeholder="example.com"
            type="text"
            className="flex-1"
          />
          <Button type="submit" disabled={isAdding || !newDomain.trim()}>
            {isAdding ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <Plus className="h-4 w-4 mr-1" />
                Add
              </>
            )}
          </Button>
        </form>

        {domains.length === 0 ? (
          <p className="text-center text-muted-foreground py-4">
            No approved domains. Add domains to designate internal users.
          </p>
        ) : (
          <div className="rounded-md border divide-y">
            {domains.map((domain) => (
              <div
                key={domain.id}
                className="flex items-center justify-between p-3"
              >
                <div>
                  <p className="font-medium">{domain.domain}</p>
                  <p className="text-sm text-muted-foreground">
                    Added {new Date(domain.created_at).toLocaleDateString()}
                    {domain.created_by && ` by ${domain.created_by}`}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRemoveDomain(domain.domain)}
                  disabled={deletingDomain === domain.domain}
                  className="text-destructive hover:text-destructive"
                >
                  {deletingDomain === domain.domain ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
