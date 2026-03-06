import * as React from 'react';
import { startRegistration } from '@simplewebauthn/browser';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { api, ApiError } from '@/lib/api';
import { KeyRound, Trash2, Plus, X } from 'lucide-react';

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
      <CardHeader className="border-b-4 border-black bg-black text-white p-4">
        <CardTitle className="flex items-center gap-2 text-white">
          <KeyRound className="h-5 w-5" />
          Passkeys
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        <p className="text-xs text-gray-500">
          Manage your passkeys for passwordless sign-in
        </p>

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
          <div className="space-y-3 p-4 border-4 border-black bg-gray-50">
            <label className="text-xs font-bold uppercase tracking-wider">
              Passkey Name (optional)
            </label>
            <Input
              placeholder="e.g., MacBook Pro, iPhone"
              value={passkeyName}
              onChange={(e) => setPasskeyName(e.target.value)}
              maxLength={50}
              slim
            />
            <div className="flex gap-2">
              <Button onClick={handleRegister} disabled={isRegistering} size="sm">
                {isRegistering ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin mr-2" />
                ) : (
                  <Plus className="h-4 w-4 mr-2" />
                )}
                Register
              </Button>
              <Button
                variant="secondary"
                onClick={handleCancelRegister}
                disabled={isRegistering}
                size="sm"
              >
                <X className="h-4 w-4 mr-2" />
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button onClick={handleStartRegister} size="sm">
            <Plus className="h-4 w-4 mr-2" />
            Add Passkey
          </Button>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="inline-block w-6 h-6 border-4 border-black border-t-transparent animate-spin" />
          </div>
        ) : passkeys.length === 0 ? (
          <p className="text-center text-gray-500 py-4 text-sm">
            No passkeys registered yet.
          </p>
        ) : (
          <div className="space-y-2">
            {passkeys.map((passkey) => (
              <div
                key={passkey.id}
                className="flex items-center justify-between p-3 border-2 border-black hover:bg-gray-50"
              >
                <div>
                  <p className="font-bold text-sm">{passkey.name}</p>
                  <p className="text-xs text-gray-500">
                    Added {new Date(passkey.created_at).toLocaleDateString()}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(passkey.id)}
                  disabled={deletingId === passkey.id}
                  className="text-red-600 hover:text-red-600"
                >
                  {deletingId === passkey.id ? (
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
