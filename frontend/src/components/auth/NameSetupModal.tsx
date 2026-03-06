import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api, type User, ApiError } from '@/lib/api';
import { X } from 'lucide-react';

interface NameSetupModalProps {
  user: User;
  onComplete: () => void;
  onSkip: () => void;
}

export function NameSetupModal({ user, onComplete, onSkip }: NameSetupModalProps) {
  const [name, setName] = React.useState('');
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Handle Escape key to dismiss
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onSkip();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onSkip]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await api.auth.updateProfile({ name: name.trim() });
      onComplete();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to update profile');
      }
      setIsSubmitting(false);
    }
  };

  // Handle click outside to dismiss
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onSkip();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="name-setup-title"
    >
      <div className="border-4 border-black bg-white max-w-md w-full mx-4">
        <div className="bg-black text-white p-6 flex items-center justify-between">
          <h2 id="name-setup-title" className="text-xl font-bold uppercase tracking-wider">
            Complete Your Profile
          </h2>
          <button
            type="button"
            onClick={onSkip}
            className="text-white hover:text-gray-300 transition-colors"
            aria-label="Close"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div className="text-center">
            <p className="text-sm text-gray-600">You're signed in as:</p>
            <p className="font-bold font-mono">{user.email}</p>
          </div>

          <div className="border-t-4 border-black pt-6">
            <label className="block text-xs font-bold uppercase tracking-wider mb-2">
              What should we call you?
            </label>
            <Input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              autoFocus
              slim
            />
            <p className="text-xs text-gray-500 mt-2">
              This name will be shown to admins and in your profile.
            </p>
          </div>

          {error && (
            <div className="border-4 border-red-600 bg-red-50 p-4">
              <p className="text-sm font-bold text-red-800">{error}</p>
            </div>
          )}

          <div className="flex gap-4">
            <Button
              type="button"
              variant="secondary"
              onClick={onSkip}
              className="flex-1"
            >
              Skip for now
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || !name.trim()}
              className="flex-1"
            >
              {isSubmitting ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent animate-spin" />
              ) : (
                'Continue'
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
