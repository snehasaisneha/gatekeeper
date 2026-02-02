import * as React from 'react';
import { startAuthentication } from '@simplewebauthn/browser';
import { Button } from '@/components/ui/button';
import { api, ApiError } from '@/lib/api';
import { KeyRound, Loader2 } from 'lucide-react';

interface PasskeyButtonProps {
  email?: string;
  onSuccess?: () => void;
  onError?: (error: string) => void;
  className?: string;
}

export function PasskeyButton({ email, onSuccess, onError, className }: PasskeyButtonProps) {
  const [isLoading, setIsLoading] = React.useState(false);

  const handleClick = async () => {
    setIsLoading(true);
    try {
      const options = await api.auth.passkeySigninOptions(email);

      const credential = await startAuthentication({ optionsJSON: options as any });

      await api.auth.passkeySigninVerify(credential);

      onSuccess?.();
      const params = new URLSearchParams(window.location.search);
      window.location.href = params.get('redirect') || '/';
    } catch (err) {
      if (err instanceof ApiError) {
        onError?.(err.message);
      } else if (err instanceof Error) {
        if (err.name === 'NotAllowedError') {
          onError?.('Passkey authentication was cancelled.');
        } else {
          onError?.(err.message || 'Passkey authentication failed.');
        }
      } else {
        onError?.('Passkey authentication failed.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Button
      type="button"
      variant="outline"
      onClick={handleClick}
      disabled={isLoading}
      className={className}
    >
      {isLoading ? (
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      ) : (
        <KeyRound className="mr-2 h-4 w-4" />
      )}
      Sign in with Passkey
    </Button>
  );
}
