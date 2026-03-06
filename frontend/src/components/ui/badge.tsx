import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

/**
 * Badge Component - Gatekeeper Design System
 *
 * Brutalist badges with thick borders, no border-radius.
 * Uppercase text with tracking.
 */

const badgeVariants = cva(
  // Base styles - no rounded corners, uppercase, bold
  'inline-flex items-center border-2 px-2 py-0.5 text-xs font-bold uppercase tracking-wider transition-colors',
  {
    variants: {
      variant: {
        // Outline variants (border + text color)
        default: 'border-black text-black',
        secondary: 'border-gray-400 text-gray-600',
        destructive: 'border-red-600 text-red-600',
        success: 'border-green-600 text-green-600',
        warning: 'border-amber-600 text-amber-600',

        // Solid variants (filled background)
        solid: 'border-black bg-black text-white',
        'solid-secondary': 'border-gray-400 bg-gray-400 text-white',
        'solid-destructive': 'border-red-600 bg-red-600 text-white',
        'solid-success': 'border-green-600 bg-green-600 text-white',
        'solid-warning': 'border-amber-600 bg-amber-600 text-white',

        // Legacy support
        outline: 'border-black text-black',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
