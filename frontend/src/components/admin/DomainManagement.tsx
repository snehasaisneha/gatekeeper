import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { api, type Domain, ApiError } from '@/lib/api';
import { Plus, Trash2, Globe } from 'lucide-react';

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
        <CardHeader className="border-b-4 border-black bg-black text-white p-4">
          <CardTitle className="flex items-center gap-2 text-white">
            <Globe className="h-5 w-5" />
            Approved Domains
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="flex items-center justify-center py-8">
            <div className="inline-block w-6 h-6 border-4 border-black border-t-transparent animate-spin" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="border-b-4 border-black bg-black text-white p-4">
        <CardTitle className="flex items-center gap-2 text-white">
          <Globe className="h-5 w-5" />
          Approved Domains
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        <p className="text-xs text-gray-500">
          Users with emails from these domains are internal users with access to all apps.
        </p>

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
            slim
          />
          <Button type="submit" disabled={isAdding || !newDomain.trim()} size="sm">
            {isAdding ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin" />
            ) : (
              <>
                <Plus className="h-4 w-4 mr-1" />
                Add
              </>
            )}
          </Button>
        </form>

        {domains.length === 0 ? (
          <p className="text-center text-gray-500 py-4 font-bold uppercase tracking-wider">
            No approved domains
          </p>
        ) : (
          <div className="border-2 border-black">
            {domains.map((domain, index) => (
              <div
                key={domain.id}
                className={`flex items-center justify-between p-3 ${
                  index !== domains.length - 1 ? 'border-b-2 border-black' : ''
                }`}
              >
                <div>
                  <p className="font-bold text-sm">{domain.domain}</p>
                  <p className="text-xs text-gray-500">
                    Added {new Date(domain.created_at).toLocaleDateString()}
                    {domain.created_by && ` by ${domain.created_by}`}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleRemoveDomain(domain.domain)}
                  disabled={deletingDomain === domain.domain}
                  className="text-red-600 hover:text-red-600"
                >
                  {deletingDomain === domain.domain ? (
                    <div className="w-4 h-4 border-2 border-red-600 border-t-transparent animate-spin" />
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
