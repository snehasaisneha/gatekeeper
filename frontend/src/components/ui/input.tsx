import * as React from 'react';
import { cn } from '@/lib/utils';

/**
 * Input Component - Gatekeeper Design System
 *
 * Brutalist input with thick border and no border-radius.
 * Focus state changes background color instead of adding ring.
 */

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Use thinner border for compact forms */
  slim?: boolean;
  /** Show error state */
  error?: boolean;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, slim = false, error = false, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          // Base styles
          'flex w-full bg-white px-4 text-sm text-black',
          'placeholder:text-gray-400',
          'transition-colors duration-150',
          'focus:outline-none focus:bg-gray-50',
          'disabled:cursor-not-allowed disabled:opacity-50',
          // Border thickness
          slim ? 'border-2 py-2 h-10' : 'border-4 py-3 h-12',
          // Border color
          error ? 'border-red-600' : 'border-black',
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = 'Input';

export { Input };
