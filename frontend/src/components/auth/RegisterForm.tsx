import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { OTPInput } from './OTPInput';
import { api, ApiError } from '@/lib/api';
import { Loader2, ArrowLeft, CheckCircle2, Clock } from 'lucide-react';

type Step = 'email' | 'otp' | 'pending' | 'success';

export function RegisterForm() {
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
      const response = await api.auth.register(email);
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
      const response = await api.auth.registerVerify(email, code);

      if (response.user) {
        setStep('success');
        setTimeout(() => {
          window.location.href = '/';
        }, 2000);
      } else {
        setStep('pending');
      }
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

  if (step === 'success') {
    return (
      <div className="space-y-4 text-center min-h-[240px] flex flex-col items-center justify-center">
        <div className="mx-auto w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
          <CheckCircle2 className="h-6 w-6 text-green-600" />
        </div>
        <div>
          <h3 className="text-lg font-semibold">Registration successful!</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Redirecting you to the dashboard...
          </p>
        </div>
      </div>
    );
  }

  if (step === 'pending') {
    return (
      <div className="space-y-4 text-center min-h-[240px] flex flex-col items-center justify-center">
        <div className="mx-auto w-12 h-12 rounded-full bg-yellow-100 flex items-center justify-center">
          <Clock className="h-6 w-6 text-yellow-600" />
        </div>
        <div>
          <h3 className="text-lg font-semibold">Registration pending</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Your registration is pending admin approval. You'll receive an email when your account
            is approved.
          </p>
        </div>
        <Button variant="outline" asChild className="w-full">
          <a href="/signin">Back to Sign In</a>
        </Button>
      </div>
    );
  }

  if (step === 'otp') {
    return (
      <form onSubmit={handleOtpSubmit} className="space-y-4 min-h-[240px]">
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
          <p className="text-sm text-muted-foreground">We sent a 6-digit code to {email}</p>
          <OTPInput value={otp} onChange={setOtp} onComplete={verifyOtp} disabled={isLoading} />
        </div>

        <Button type="submit" className="w-full" disabled={isLoading || otp.length !== 6}>
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Verify & Register
        </Button>
      </form>
    );
  }

  return (
    <form onSubmit={handleEmailSubmit} className="space-y-4 min-h-[240px]">
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
        Continue
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{' '}
        <a href="/signin" className="font-medium text-primary hover:underline">
          Sign in
        </a>
      </p>
    </form>
  );
}
