import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

/**
 * Alert Component - Gatekeeper Design System
 *
 * Brutalist alerts with thick left border and solid background colors.
 * No border-radius.
 */

const alertVariants = cva(
  // Base styles - thick left border, no rounded corners
  'relative w-full border-l-4 p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4',
  {
    variants: {
      variant: {
        default: 'bg-gray-50 border-black text-black [&>svg]:text-black',
        destructive: 'bg-red-50 border-red-600 text-red-800 [&>svg]:text-red-600',
        success: 'bg-green-50 border-green-600 text-green-800 [&>svg]:text-green-600',
        warning: 'bg-amber-50 border-amber-600 text-amber-800 [&>svg]:text-amber-600',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

const Alert = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>
>(({ className, variant, ...props }, ref) => (
  <div ref={ref} role="alert" className={cn(alertVariants({ variant }), className)} {...props} />
));
Alert.displayName = 'Alert';

const AlertTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h5
      ref={ref}
      className={cn('mb-1 font-bold uppercase tracking-wider leading-none', className)}
      {...props}
    />
  )
);
AlertTitle.displayName = 'AlertTitle';

const AlertDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('text-sm [&_p]:leading-relaxed', className)} {...props} />
));
AlertDescription.displayName = 'AlertDescription';

export { Alert, AlertTitle, AlertDescription };
