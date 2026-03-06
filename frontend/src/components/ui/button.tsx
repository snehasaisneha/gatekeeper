import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

/**
 * Button Component - Gatekeeper Design System
 *
 * Brutalist button with thick borders and bold typography.
 * No border-radius (sharp edges).
 *
 * Variants:
 * - default: Solid black background, inverts on hover
 * - secondary: White background with black border, fills on hover
 * - ghost: Minimal, for icon buttons and inline actions
 * - destructive: Red variant for dangerous actions
 * - link: Text-only with underline
 */

const buttonVariants = cva(
  // Base styles - brutalist: no rounded corners, bold text
  'inline-flex items-center justify-center whitespace-nowrap font-bold uppercase tracking-wider transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: [
          'border-4 border-black bg-black text-white',
          'hover:bg-white hover:text-black',
        ].join(' '),
        secondary: [
          'border-4 border-black bg-white text-black',
          'hover:bg-black hover:text-white',
        ].join(' '),
        ghost: [
          'border-2 border-transparent',
          'hover:border-black hover:bg-gray-50',
        ].join(' '),
        destructive: [
          'border-4 border-red-600 bg-red-600 text-white',
          'hover:bg-white hover:text-red-600',
        ].join(' '),
        link: [
          'underline decoration-2 underline-offset-4 text-black',
          'hover:bg-black hover:text-white',
        ].join(' '),
        // Accent variant uses CSS variable for theming
        accent: [
          'border-4 text-white',
          'brutal-btn-primary', // Uses CSS class from globals.css
        ].join(' '),
      },
      size: {
        default: 'h-11 px-6 py-3 text-sm',
        sm: 'h-9 px-4 py-2 text-xs',
        lg: 'h-12 px-8 py-4 text-base',
        icon: 'h-10 w-10 p-2',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
