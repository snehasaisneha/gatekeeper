import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { OTPInput } from './OTPInput';
import { PasskeyButton } from './PasskeyButton';
import { api, ApiError } from '@/lib/api';
import { Loader2, ArrowLeft } from 'lucide-react';

type Step = 'email' | 'otp';

export function SignInForm() {
  const [step, setStep] = React.useState<Step>('email');
  const [email, setEmail] = React.useState('');
  const [otp, setOtp] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.auth.signin(email);
      setMessage(response.detail || 'Check your email for the verification code.');
      setStep('otp');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to send verification code. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const verifyOtp = async (code: string) => {
    if (code.length !== 6 || isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      await api.auth.signinVerify(email, code);
      window.location.href = '/';
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to verify code. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleOtpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    verifyOtp(otp);
  };

  const handleBack = () => {
    setStep('email');
    setOtp('');
    setError(null);
    setMessage(null);
  };

  if (step === 'otp') {
    return (
      <form onSubmit={handleOtpSubmit} className="space-y-4 min-h-[320px]">
        <button
          type="button"
          onClick={handleBack}
          className="flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back
        </button>

        <div className="min-h-[56px]">
          {message && (
            <Alert variant="success">
              <AlertDescription>{message}</AlertDescription>
            </Alert>
          )}
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>

        <div className="space-y-2">
          <Label>Enter verification code</Label>
          <p className="text-sm text-muted-foreground">
            We sent a 6-digit code to {email}
          </p>
          <OTPInput value={otp} onChange={setOtp} onComplete={verifyOtp} disabled={isLoading} />
        </div>

        <Button type="submit" className="w-full" disabled={isLoading || otp.length !== 6}>
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Verify
        </Button>
      </form>
    );
  }

  return (
    <form onSubmit={handleEmailSubmit} className="space-y-4 min-h-[320px]">
      <div className="min-h-[56px]">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={isLoading}
        />
      </div>

      <Button type="submit" className="w-full" disabled={isLoading}>
        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        Continue with Email
      </Button>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">Or</span>
        </div>
      </div>

      <PasskeyButton onError={setError} className="w-full" />

      <p className="text-center text-sm text-muted-foreground">
        Don't have an account?{' '}
        <a href="/register" className="font-medium text-primary hover:underline">
          Register
        </a>
      </p>
    </form>
  );
}
