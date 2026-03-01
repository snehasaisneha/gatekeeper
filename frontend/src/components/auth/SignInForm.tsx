import * as React from 'react';
import { OTPInput } from './OTPInput';
import { PasskeyButton } from './PasskeyButton';
import { api, ApiError } from '@/lib/api';

type Step = 'email' | 'otp' | 'pending';

export function SignInForm() {
  const [step, setStep] = React.useState<Step>('email');
  const [email, setEmail] = React.useState('');
  const [otp, setOtp] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);
  const [oauthProviders, setOauthProviders] = React.useState({ google: false, github: false });

  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const errorParam = params.get('error');
    const pendingParam = params.get('pending');

    if (pendingParam === 'true') {
      setStep('pending');
    } else if (errorParam) {
      const errorMessages: Record<string, string> = {
        'account_rejected': 'ACCOUNT REJECTED. CONTACT ADMIN.',
        'oauth_failed': 'AUTHENTICATION FAILED. RETRY.',
        'invalid_state': 'SESSION EXPIRED. RETRY.',
        'no_email': 'NO EMAIL FROM PROVIDER.',
        'internal_error': 'SYSTEM ERROR.',
        'github_no_org_email': 'NO APPROVED EMAIL FOUND. LINK YOUR ORGANISATIONAL EMAIL TO GITHUB, OR SIGN IN WITH EMAIL/PASSKEY.',
      };
      setError(errorMessages[errorParam] || 'ERROR OCCURRED.');
    }

    api.auth.oauthProviders().then(setOauthProviders).catch(() => {});
  }, []);

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.auth.signin(email);
      setMessage(response.detail || 'CODE SENT TO EMAIL');
      setStep('otp');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message.toUpperCase());
      } else {
        setError('FAILED TO SEND CODE');
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
      const response = await api.auth.signinVerify(email, code);

      if (response.user) {
        const params = new URLSearchParams(window.location.search);
        window.location.href = params.get('redirect') || '/';
      } else {
        setStep('pending');
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message.toUpperCase());
      } else {
        setError('VERIFICATION FAILED');
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

  const handleGoogleSignIn = () => {
    const params = new URLSearchParams(window.location.search);
    const redirect = params.get('redirect') || '/';
    window.location.href = api.auth.getGoogleLoginUrl(redirect);
  };

  const handleGithubSignIn = () => {
    const params = new URLSearchParams(window.location.search);
    const redirect = params.get('redirect') || '/';
    window.location.href = api.auth.getGithubLoginUrl(redirect);
  };

  const hasOAuthProviders = oauthProviders.google || oauthProviders.github;

  // Pending state
  if (step === 'pending') {
    return (
      <div className="space-y-6">
        <div className="border-4 border-black bg-gray-200 p-4">
          <p className="font-bold uppercase text-sm">⏳ PENDING APPROVAL</p>
        </div>
        <p className="text-sm">
          Your account is waiting for admin approval. You will receive an email when approved.
        </p>
        <button
          onClick={() => window.location.href = '/signin'}
          className="w-full border-4 border-black bg-white text-black px-6 py-3 font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-colors"
        >
          ← Back
        </button>
      </div>
    );
  }

  // OTP verification step
  if (step === 'otp') {
    return (
      <form onSubmit={handleOtpSubmit} className="space-y-6">
        <button
          type="button"
          onClick={handleBack}
          className="text-sm font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-colors px-2 -mx-2"
        >
          ← Back
        </button>

        <div className="space-y-2">
          <p className="text-sm">
            Code sent to <span className="font-bold">{email}</span>
          </p>
        </div>

        {message && (
          <div className="border-4 border-black bg-gray-100 p-4">
            <p className="font-bold uppercase text-sm">✓ {message}</p>
          </div>
        )}

        {error && (
          <div className="border-4 border-black bg-black text-white p-4">
            <p className="font-bold uppercase text-sm">✗ {error}</p>
          </div>
        )}

        <div className="space-y-2">
          <label className="block text-xs font-bold uppercase tracking-wider">
            6-Digit Code
          </label>
          <OTPInput value={otp} onChange={setOtp} onComplete={verifyOtp} disabled={isLoading} />
        </div>

        <button
          type="submit"
          disabled={isLoading || otp.length !== 6}
          className="w-full border-4 border-black bg-black text-white px-6 py-3 font-bold uppercase tracking-wider hover:bg-white hover:text-black transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? 'VERIFYING...' : 'VERIFY →'}
        </button>
      </form>
    );
  }

  // Email entry step
  return (
    <form onSubmit={handleEmailSubmit} className="space-y-6">
      {error && (
        <div className="border-4 border-black bg-black text-white p-4">
          <p className="font-bold uppercase text-sm">✗ {error}</p>
        </div>
      )}

      {/* OAuth Providers */}
      {hasOAuthProviders && (
        <>
          <div className="space-y-3">
            {oauthProviders.google && (
              <button
                type="button"
                onClick={handleGoogleSignIn}
                disabled={isLoading}
                className="w-full border-4 border-black bg-white text-black px-6 py-3 font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-colors flex items-center justify-center gap-3"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Google
              </button>
            )}

            {oauthProviders.github && (
              <button
                type="button"
                onClick={handleGithubSignIn}
                disabled={isLoading}
                className="w-full border-4 border-black bg-white text-black px-6 py-3 font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-colors flex items-center justify-center gap-3"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="currentColor" d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
                </svg>
                GitHub
              </button>
            )}
          </div>

          <div className="flex items-center gap-4">
            <div className="flex-1 border-t-2 border-black"></div>
            <span className="text-xs font-bold uppercase tracking-wider">Or</span>
            <div className="flex-1 border-t-2 border-black"></div>
          </div>
        </>
      )}

      <div className="space-y-2">
        <label htmlFor="email" className="block text-xs font-bold uppercase tracking-wider">
          Email Address
        </label>
        <input
          id="email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={isLoading}
          className="w-full border-4 border-black bg-white px-4 py-3 text-black placeholder:text-gray-400 focus:outline-none focus:bg-gray-100 transition-colors disabled:opacity-50"
        />
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full border-4 border-black bg-black text-white px-6 py-3 font-bold uppercase tracking-wider hover:bg-white hover:text-black transition-colors disabled:opacity-50"
      >
        {isLoading ? 'SENDING...' : 'CONTINUE →'}
      </button>

      {!hasOAuthProviders && (
        <div className="flex items-center gap-4">
          <div className="flex-1 border-t-2 border-black"></div>
          <span className="text-xs font-bold uppercase tracking-wider">Or</span>
          <div className="flex-1 border-t-2 border-black"></div>
        </div>
      )}

      <PasskeyButton
        onError={(err) => setError(err?.toUpperCase() || null)}
        className="w-full border-4 border-black bg-white text-black px-6 py-3 font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-colors"
      />
    </form>
  );
}
