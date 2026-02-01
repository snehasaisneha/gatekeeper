import * as React from 'react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

interface OTPInputProps {
  value: string;
  onChange: (value: string) => void;
  onComplete?: (value: string) => void;
  disabled?: boolean;
  className?: string;
}

export function OTPInput({ value, onChange, onComplete, disabled, className }: OTPInputProps) {
  const inputRefs = React.useRef<(HTMLInputElement | null)[]>([]);
  const [localValues, setLocalValues] = React.useState<string[]>(
    value.split('').concat(Array(6 - value.length).fill(''))
  );

  React.useEffect(() => {
    setLocalValues(value.split('').concat(Array(6 - value.length).fill('')));
  }, [value]);

  const handleChange = (index: number, newValue: string) => {
    if (!/^\d*$/.test(newValue)) return;

    const newValues = [...localValues];

    if (newValue.length > 1) {
      const chars = newValue.split('').slice(0, 6 - index);
      chars.forEach((char, i) => {
        if (index + i < 6) {
          newValues[index + i] = char;
        }
      });
      const nextIndex = Math.min(index + chars.length, 5);
      inputRefs.current[nextIndex]?.focus();
    } else {
      newValues[index] = newValue;
      if (newValue && index < 5) {
        inputRefs.current[index + 1]?.focus();
      }
    }

    setLocalValues(newValues);
    onChange(newValues.join(''));
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !localValues[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
    if (e.key === 'ArrowLeft' && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
    if (e.key === 'ArrowRight' && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pastedData) {
      const newValues = pastedData.split('').concat(Array(6 - pastedData.length).fill(''));
      setLocalValues(newValues);
      const fullValue = newValues.join('');
      onChange(fullValue);
      inputRefs.current[Math.min(pastedData.length, 5)]?.focus();
      if (fullValue.length === 6 && onComplete) {
        onComplete(fullValue);
      }
    }
  };

  return (
    <div className={cn('flex gap-2 justify-center', className)}>
      {Array.from({ length: 6 }).map((_, index) => (
        <Input
          key={index}
          ref={(el) => {
            inputRefs.current[index] = el;
          }}
          type="text"
          inputMode="numeric"
          maxLength={6}
          value={localValues[index]}
          onChange={(e) => handleChange(index, e.target.value)}
          onKeyDown={(e) => handleKeyDown(index, e)}
          onPaste={handlePaste}
          disabled={disabled}
          className="w-12 h-12 text-center text-lg font-semibold"
          autoComplete="one-time-code"
        />
      ))}
    </div>
  );
}
