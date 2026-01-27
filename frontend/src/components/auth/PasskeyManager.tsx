import * as React from 'react';
import { startRegistration } from '@simplewebauthn/browser';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api, ApiError } from '@/lib/api';
import { Loader2, KeyRound, Trash2, Plus, X } from 'lucide-react';

interface Passkey {
  id: string;
  name: string;
  created_at: string;
}

export function PasskeyManager() {
  const [passkeys, setPasskeys] = React.useState<Passkey[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isRegistering, setIsRegistering] = React.useState(false);
  const [showNameInput, setShowNameInput] = React.useState(false);
  const [passkeyName, setPasskeyName] = React.useState('');
  const [deletingId, setDeletingId] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [success, setSuccess] = React.useState<string | null>(null);

  const loadPasskeys = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.auth.listPasskeys();
      setPasskeys(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load passkeys');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadPasskeys();
  }, [loadPasskeys]);

  const handleStartRegister = () => {
    setShowNameInput(true);
    setPasskeyName('');
    setError(null);
    setSuccess(null);
  };

  const handleCancelRegister = () => {
    setShowNameInput(false);
    setPasskeyName('');
  };

  const handleRegister = async () => {
    setIsRegistering(true);
    setError(null);
    setSuccess(null);

    try {
      const options = await api.auth.passkeyRegisterOptions();
      const credential = await startRegistration({ optionsJSON: options as any });
      await api.auth.passkeyRegisterVerify(credential, passkeyName || undefined);

      setSuccess('Passkey registered successfully');
      setShowNameInput(false);
      setPasskeyName('');
      await loadPasskeys();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        if (err.name === 'NotAllowedError') {
          setError('Passkey registration was cancelled.');
        } else {
          setError(err.message || 'Passkey registration failed.');
        }
      } else {
        setError('Passkey registration failed.');
      }
    } finally {
      setIsRegistering(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this passkey?')) return;

    setDeletingId(id);
    setError(null);
    setSuccess(null);

    try {
      await api.auth.deletePasskey(id);
      setSuccess('Passkey deleted successfully');
      await loadPasskeys();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to delete passkey');
      }
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="h-5 w-5" />
          Passkeys
        </CardTitle>
        <CardDescription>
          Manage your passkeys for passwordless sign-in
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert variant="success">
            <AlertDescription>{success}</AlertDescription>
          </Alert>
        )}

        {showNameInput ? (
          <div className="space-y-3 p-3 rounded-lg border bg-muted/50">
            <Label htmlFor="passkey-name">Passkey Name (optional)</Label>
            <Input
              id="passkey-name"
              placeholder="e.g., MacBook Pro, iPhone"
              value={passkeyName}
              onChange={(e) => setPasskeyName(e.target.value)}
              maxLength={50}
            />
            <div className="flex gap-2">
              <Button onClick={handleRegister} disabled={isRegistering}>
                {isRegistering ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4 mr-2" />
                )}
                Register Passkey
              </Button>
              <Button variant="outline" onClick={handleCancelRegister} disabled={isRegistering}>
                <X className="h-4 w-4 mr-2" />
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button onClick={handleStartRegister}>
            <Plus className="h-4 w-4 mr-2" />
            Add Passkey
          </Button>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : passkeys.length === 0 ? (
          <p className="text-center text-muted-foreground py-4">
            No passkeys registered yet. Add one to enable passwordless sign-in.
          </p>
        ) : (
          <div className="space-y-2">
            {passkeys.map((passkey) => (
              <div
                key={passkey.id}
                className="flex items-center justify-between p-3 rounded-lg border"
              >
                <div>
                  <p className="font-medium">{passkey.name}</p>
                  <p className="text-sm text-muted-foreground">
                    Added {new Date(passkey.created_at).toLocaleDateString()}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(passkey.id)}
                  disabled={deletingId === passkey.id}
                  className="text-destructive hover:text-destructive"
                >
                  {deletingId === passkey.id ? (
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
