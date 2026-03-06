import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { api, ApiError } from '@/lib/api';
import { Trash2, AlertTriangle } from 'lucide-react';

interface DeleteAccountProps {
  isSeeded: boolean;
}

export function DeleteAccount({ isSeeded }: DeleteAccountProps) {
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [confirmText, setConfirmText] = React.useState('');

  const handleDelete = async () => {
    if (confirmText !== 'DELETE') return;

    setIsDeleting(true);
    setError(null);

    try {
      await api.auth.deleteAccount();
      window.location.href = '/signin';
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to delete account');
      }
      setIsDeleting(false);
    }
  };

  return (
    <Card className="border-red-600">
      <CardHeader className="border-b-4 border-red-600 bg-red-600 text-white p-4">
        <CardTitle className="flex items-center gap-2 text-white">
          <AlertTriangle className="h-5 w-5" />
          Danger Zone
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {isSeeded ? (
          <p className="text-sm text-gray-500">
            This is a seeded admin account and cannot be deleted.
          </p>
        ) : (
          <>
            <p className="text-sm text-gray-600">
              Permanently delete your account and all associated data. This action cannot be undone.
            </p>
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-wider">
                Type <span className="font-mono bg-gray-100 px-1">DELETE</span> to confirm
              </label>
              <Input
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="DELETE"
                slim
                error={confirmText.length > 0 && confirmText !== 'DELETE'}
              />
            </div>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting || confirmText !== 'DELETE'}
              size="sm"
            >
              {isDeleting ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin mr-2" />
              ) : (
                <Trash2 className="h-4 w-4 mr-2" />
              )}
              Delete Account
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
