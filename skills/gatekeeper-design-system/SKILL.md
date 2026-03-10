---
name: gatekeeper-design-system
description: Gatekeeper's brutalist design system. MUST be read before implementing any frontend feature to ensure UI consistency.
autoContext: frontend/**/*.tsx, frontend/**/*.astro
---

# Gatekeeper Design System

**IMPORTANT**: Read this before implementing ANY frontend feature. All UI must follow these patterns for consistency.

## Design Philosophy

Gatekeeper uses a **brutalist design aesthetic**:
- **Sharp edges**: No border-radius on interactive elements
- **Thick borders**: 4px borders on cards, buttons, inputs
- **High contrast**: Black/white with accent color highlights
- **Bold typography**: Uppercase headings, monospace fonts, wide letter-spacing
- **No shadows**: Flat design (optional offset shadows for hover states)

## Core CSS Variables

```css
--accent-color: #000000;  /* Configurable via branding settings */
--radius: 0;              /* Always 0 - no rounded corners */
```

## Typography

| Element | Classes |
|---------|---------|
| Page title | `text-2xl font-bold uppercase tracking-wider` |
| Section title | `text-lg font-bold uppercase tracking-wider` |
| Card title | `text-base font-bold uppercase tracking-wider` |
| Labels | `text-xs font-bold uppercase tracking-wider` |
| Body text | `text-sm` |
| Help text | `text-xs text-gray-500` |
| Monospace | `font-mono` (default font) |

## Components

### Buttons

```tsx
import { Button } from '@/components/ui/button';

// Primary (default) - black bg, white text
<Button>Save Changes</Button>

// Secondary - white bg, black border
<Button variant="secondary">Cancel</Button>

// Ghost - minimal, for icons
<Button variant="ghost" size="icon"><X /></Button>

// Destructive - red
<Button variant="destructive">Delete</Button>

// Sizes
<Button size="sm">Small</Button>
<Button size="default">Default</Button>
<Button size="lg">Large</Button>
<Button size="icon"><Plus /></Button>
```

### Inputs

```tsx
import { Input } from '@/components/ui/input';

// Standard input (4px border)
<Input placeholder="Enter email" />

// Slim input (2px border, compact)
<Input slim placeholder="Search..." />

// Error state
<Input error placeholder="Invalid input" />
```

### Cards

```tsx
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';

// Standard card
<Card>
  <CardHeader>
    <CardTitle>Settings</CardTitle>
    <CardDescription>Manage your account</CardDescription>
  </CardHeader>
  <CardContent>
    Content here
  </CardContent>
</Card>

// Emphasized card with black header (use CardHeaderBrutal)
import { CardHeaderBrutal } from '@/components/ui/card';

<Card>
  <CardHeaderBrutal>
    <CardTitle className="text-white">Important</CardTitle>
  </CardHeaderBrutal>
  <CardContent className="pt-4">
    Content here
  </CardContent>
</Card>
```

### Badges

```tsx
import { Badge } from '@/components/ui/badge';

// Outline variants
<Badge>Default</Badge>
<Badge variant="success">Approved</Badge>
<Badge variant="warning">Pending</Badge>
<Badge variant="destructive">Rejected</Badge>

// Solid variants
<Badge variant="solid">Admin</Badge>
<Badge variant="solid-success">Active</Badge>
```

### Alerts

```tsx
import { Alert, AlertDescription } from '@/components/ui/alert';

<Alert>
  <AlertDescription>Info message</AlertDescription>
</Alert>

<Alert variant="destructive">
  <AlertDescription>Error occurred</AlertDescription>
</Alert>

<Alert variant="success">
  <AlertDescription>Operation successful</AlertDescription>
</Alert>
```

### Loading Spinners

Use the border-based spinner, not Loader2 icon:

```tsx
// Full-page loading
<div className="min-h-screen bg-white flex items-center justify-center">
  <div className="text-center">
    <div className="inline-block w-8 h-8 border-4 border-black border-t-transparent animate-spin" />
    <p className="mt-4 text-sm font-bold uppercase tracking-wider">Loading...</p>
  </div>
</div>

// Inline/section loading (no text)
<div className="flex items-center justify-center py-8">
  <div className="inline-block w-6 h-6 border-4 border-black border-t-transparent animate-spin" />
</div>

// Small spinner (in buttons, etc.)
<div className="inline-block w-4 h-4 border-4 border-black border-t-transparent animate-spin" />
```

### Modals

```tsx
// Modal structure
<div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
  <div className="bg-white border-4 border-black max-w-lg w-full mx-4">
    {/* Header */}
    <div className="bg-black text-white p-4 flex justify-between items-center">
      <h2 className="font-bold uppercase tracking-wider">Modal Title</h2>
      <button className="text-white hover:text-gray-300">
        <X className="h-5 w-5" />
      </button>
    </div>

    {/* Content */}
    <div className="p-6">
      Modal content here
    </div>

    {/* Footer */}
    <div className="border-t-4 border-black p-4 flex justify-end gap-4">
      <Button variant="secondary">Cancel</Button>
      <Button>Confirm</Button>
    </div>
  </div>
</div>
```

### Tables

```tsx
<div className="border-4 border-black">
  <table className="w-full">
    <thead className="bg-black text-white">
      <tr>
        <th className="p-3 text-left text-xs font-bold uppercase tracking-wider">
          Column
        </th>
      </tr>
    </thead>
    <tbody>
      <tr className="border-t-2 border-black hover:bg-gray-50">
        <td className="p-3 text-sm">Cell content</td>
      </tr>
    </tbody>
  </table>
</div>
```

### Form Labels

```tsx
<div className="space-y-2">
  <label className="text-xs font-bold uppercase tracking-wider">
    Email Address
  </label>
  <Input placeholder="you@example.com" />
  <p className="text-xs text-gray-500">We'll never share your email.</p>
</div>
```

## Spacing

Use consistent spacing scale:
- `gap-2` / `space-y-2`: Tight (8px) - between related elements
- `gap-4` / `space-y-4`: Standard (16px) - between form fields
- `gap-6` / `space-y-6`: Section (24px) - between sections
- `gap-8` / `space-y-8`: Large (32px) - between major page sections

## DO NOT

- ❌ Use `rounded-*` classes on buttons, inputs, cards, badges
- ❌ Use `Loader2` icon for loading states (use border spinner)
- ❌ Use thin borders (< 2px) on interactive elements
- ❌ Use lowercase for headings and labels
- ❌ Add blur effects or soft shadows
- ❌ Use muted colors for primary actions

## DO

- ✅ Use sharp edges (no border-radius)
- ✅ Use 4px borders on primary elements, 2px on secondary
- ✅ Use uppercase + tracking-wider for headings/labels
- ✅ Use high contrast (black/white)
- ✅ Use the border-based spinner for all loading states
- ✅ Keep hover states simple (color inversion)

## File Reference

- **CSS System**: `frontend/src/styles/globals.css`
- **Button**: `frontend/src/components/ui/button.tsx`
- **Input**: `frontend/src/components/ui/input.tsx`
- **Card**: `frontend/src/components/ui/card.tsx`
- **Badge**: `frontend/src/components/ui/badge.tsx`
- **Alert**: `frontend/src/components/ui/alert.tsx`
