import * as React from 'react';
import { cn } from '@/lib/utils';

/**
 * Card Components - Gatekeeper Design System
 *
 * Brutalist cards with thick black borders and no border-radius.
 * CardHeader has solid black background with white text.
 */

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'bg-white border-4 border-black',
        className
      )}
      {...props}
    />
  )
);
Card.displayName = 'Card';

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex flex-col space-y-1.5 p-4',
        // Default: standard header. Use bg-black text-white for emphasis
        className
      )}
      {...props}
    />
  )
);
CardHeader.displayName = 'CardHeader';

/**
 * Emphasized card header with solid background
 */
const CardHeaderBrutal = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'bg-black text-white p-4',
        className
      )}
      {...props}
    />
  )
);
CardHeaderBrutal.displayName = 'CardHeaderBrutal';

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      className={cn(
        'font-bold uppercase tracking-wider leading-none',
        className
      )}
      {...props}
    />
  )
);
CardTitle.displayName = 'CardTitle';

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn('text-sm text-muted-foreground', className)}
    {...props}
  />
));
CardDescription.displayName = 'CardDescription';

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('p-4 pt-0', className)} {...props} />
  )
);
CardContent.displayName = 'CardContent';

const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex items-center p-4 pt-0',
        className
      )}
      {...props}
    />
  )
);
CardFooter.displayName = 'CardFooter';

/**
 * Card footer with top border for separation
 */
const CardFooterBrutal = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex items-center p-4 border-t-4 border-black',
        className
      )}
      {...props}
    />
  )
);
CardFooterBrutal.displayName = 'CardFooterBrutal';

export {
  Card,
  CardHeader,
  CardHeaderBrutal,
  CardFooter,
  CardFooterBrutal,
  CardTitle,
  CardDescription,
  CardContent,
};
