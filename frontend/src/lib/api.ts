const API_BASE = '/api/v1';

export interface User {
  id: string;
  email: string;
  name: string | null;
  status: 'pending' | 'approved' | 'rejected';
  is_admin: boolean;
  is_seeded: boolean;
  is_internal: boolean;
  notify_new_registrations: boolean;
  notify_all_registrations: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  message: string;
  user: User | null;
}

export interface MessageResponse {
  message: string;
  detail?: string;
}

export interface UserListResponse {
  users: User[];
  total: number;
  page: number;
  page_size: number;
}

export interface PendingUsersResponse {
  users: User[];
  total: number;
}

// Domain types
export interface Domain {
  id: string;
  domain: string;
  created_at: string;
  created_by: string | null;
}

export interface DomainList {
  domains: Domain[];
  total: number;
}

// App types
export interface App {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  app_url: string | null;
  roles: string;
  created_at: string;
}

export interface AppPublic {
  slug: string;
  name: string;
  description: string | null;
  app_url: string | null;
}

export interface AppList {
  apps: App[];
  total: number;
}

export interface AppUserAccess {
  email: string;
  role: string | null;
  granted_at: string;
  granted_by: string | null;
}

export interface AppDetail extends App {
  users: AppUserAccess[];
}

export interface UserAppAccess {
  app_slug: string;
  app_name: string;
  app_description: string | null;
  app_url: string | null;
  role: string | null;
  granted_at: string;
}

// Branding types
export type AccentColor = 'ink' | 'charcoal' | 'navy' | 'forest' | 'amber' | 'plum' | 'sage';

export interface Branding {
  logo_url: string | null;
  logo_square_url: string | null;
  favicon_url: string | null;
  accent_color: AccentColor;
  accent_hex: string;
}

// Deployment config types
export interface DeploymentConfig {
  cookie_domain: string | null;
  app_url: string;
}

// Security types
export type BanReason =
  | 'brute_force'
  | 'spam'
  | 'rejected_user'
  | 'associated_ip'
  | 'associated_email'
  | 'rate_limit'
  | 'manual'
  | 'disposable_email';

export interface BannedIP {
  id: string;
  ip_address: string;
  reason: string;
  details: string | null;
  banned_at: string;
  banned_by: string | null;
  expires_at: string | null;
  is_active: boolean;
  associated_email: string | null;
}

export interface BannedIPList {
  banned_ips: BannedIP[];
  total: number;
}

export interface BannedEmail {
  id: string;
  email: string;
  is_pattern: boolean;
  reason: string;
  details: string | null;
  banned_at: string;
  banned_by: string | null;
  expires_at: string | null;
  is_active: boolean;
  associated_ip: string | null;
}

export interface BannedEmailList {
  banned_emails: BannedEmail[];
  total: number;
}

export interface SecurityStats {
  blocked_today: number;
  banned_ips: number;
  banned_emails: number;
  failed_logins_today: number;
}

export interface SecurityEvent {
  id: string;
  event_type: string;
  ip_address: string | null;
  email: string | null;
  details: string | null;
  created_at: string;
}

export interface SecurityEventList {
  events: SecurityEvent[];
  total: number;
}

export interface BrandingAdmin extends Branding {
  updated_at: string | null;
  updated_by: string | null;
}

export interface AccentPreset {
  name: string;
  hex: string;
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
    throw new ApiError(response.status, error.detail || 'An error occurred');
  }

  return response.json();
}

export const api = {
  auth: {
    signin: (email: string) =>
      request<MessageResponse>('/auth/signin', {
        method: 'POST',
        body: JSON.stringify({ email }),
      }),

    signinVerify: (email: string, code: string) =>
      request<AuthResponse>('/auth/signin/verify', {
        method: 'POST',
        body: JSON.stringify({ email, code }),
      }),

    googleEnabled: () => request<{ enabled: boolean }>('/auth/google/enabled'),

    getGoogleLoginUrl: (redirect?: string) => {
      const params = new URLSearchParams();
      if (redirect) params.set('redirect', redirect);
      return `${API_BASE}/auth/google/login${params.toString() ? '?' + params.toString() : ''}`;
    },

    githubEnabled: () => request<{ enabled: boolean }>('/auth/github/enabled'),

    getGithubLoginUrl: (redirect?: string) => {
      const params = new URLSearchParams();
      if (redirect) params.set('redirect', redirect);
      return `${API_BASE}/auth/github/login${params.toString() ? '?' + params.toString() : ''}`;
    },

    oauthProviders: () => request<{ google: boolean; github: boolean }>('/auth/oauth/providers'),

    signout: () =>
      request<MessageResponse>('/auth/signout', {
        method: 'POST',
      }),

    me: () => request<User>('/auth/me'),

    updateProfile: (data: {
      name?: string;
      notify_new_registrations?: boolean;
      notify_all_registrations?: boolean;
    }) =>
      request<User>('/auth/me', {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),

    deleteAccount: () =>
      request<MessageResponse>('/auth/me', {
        method: 'DELETE',
      }),

    myApps: () => request<UserAppAccess[]>('/auth/me/apps'),

    passkeyRegisterOptions: () =>
      request<PublicKeyCredentialCreationOptions>('/auth/passkey/register/options', {
        method: 'POST',
      }),

    passkeyRegisterVerify: (credential: object, name?: string) =>
      request<MessageResponse>('/auth/passkey/register/verify', {
        method: 'POST',
        body: JSON.stringify({ credential, name }),
      }),

    passkeySigninOptions: (email?: string) =>
      request<PublicKeyCredentialRequestOptions>('/auth/passkey/signin/options', {
        method: 'POST',
        body: JSON.stringify({ email: email || null }),
      }),

    passkeySigninVerify: (credential: object) =>
      request<AuthResponse>('/auth/passkey/signin/verify', {
        method: 'POST',
        body: JSON.stringify({ credential }),
      }),

    listPasskeys: () =>
      request<Array<{ id: string; name: string; created_at: string }>>('/auth/passkeys'),

    deletePasskey: (id: string) =>
      request<MessageResponse>(`/auth/passkeys/${id}`, {
        method: 'DELETE',
      }),

    branding: () => request<Branding>('/auth/branding'),
  },

  admin: {
    // Domain management
    listDomains: () => request<DomainList>('/admin/domains'),

    addDomain: (domain: string) =>
      request<Domain>('/admin/domains', {
        method: 'POST',
        body: JSON.stringify({ domain }),
      }),

    removeDomain: (domain: string) =>
      request<MessageResponse>(`/admin/domains/${encodeURIComponent(domain)}`, {
        method: 'DELETE',
      }),

    // User management
    listUsers: (page = 1, pageSize = 20, status?: string) => {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (status) params.set('status_filter', status);
      return request<UserListResponse>(`/admin/users?${params}`);
    },

    listPendingUsers: () => request<PendingUsersResponse>('/admin/users/pending'),

    getUser: (id: string) => request<User>(`/admin/users/${id}`),

    createUser: (email: string, isAdmin = false, autoApprove = true) =>
      request<User>('/admin/users', {
        method: 'POST',
        body: JSON.stringify({ email, is_admin: isAdmin, auto_approve: autoApprove }),
      }),

    updateUser: (id: string, data: {
      status?: string;
      is_admin?: boolean;
      notify_new_registrations?: boolean;
      notify_all_registrations?: boolean;
    }) =>
      request<User>(`/admin/users/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),

    approveUser: (id: string) =>
      request<User>(`/admin/users/${id}/approve`, {
        method: 'POST',
      }),

    rejectUser: (id: string) =>
      request<User>(`/admin/users/${id}/reject`, {
        method: 'POST',
      }),

    deleteUser: (id: string) =>
      request<MessageResponse>(`/admin/users/${id}`, {
        method: 'DELETE',
      }),

    // App management
    listApps: () => request<AppList>('/admin/apps'),

    createApp: (data: { slug: string; name: string; description?: string; app_url?: string }) =>
      request<App>('/admin/apps', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    updateApp: (slug: string, data: { name?: string; description?: string; app_url?: string; roles?: string }) =>
      request<App>(`/admin/apps/${slug}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),

    getApp: (slug: string) => request<AppDetail>(`/admin/apps/${slug}`),

    deleteApp: (slug: string) =>
      request<MessageResponse>(`/admin/apps/${slug}`, {
        method: 'DELETE',
      }),

    grantAccess: (slug: string, email: string, role?: string) =>
      request<MessageResponse>(`/admin/apps/${slug}/grant`, {
        method: 'POST',
        body: JSON.stringify({ email, role }),
      }),

    revokeAccess: (slug: string, email: string) =>
      request<MessageResponse>(`/admin/apps/${slug}/revoke?email=${encodeURIComponent(email)}`, {
        method: 'DELETE',
      }),

    bulkGrantAccess: (data: { emails: string[]; app_slugs: string[]; role?: string }) =>
      request<MessageResponse>('/admin/users/grant-bulk', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    // Branding
    getBranding: () => request<BrandingAdmin>('/admin/branding'),

    updateBranding: (data: {
      logo_url?: string | null;
      logo_square_url?: string | null;
      favicon_url?: string | null;
      accent_color?: AccentColor;
    }) =>
      request<BrandingAdmin>('/admin/branding', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),

    getAccentPresets: () => request<{ presets: AccentPreset[] }>('/admin/branding/presets'),

    // Deployment config
    getDeploymentConfig: () => request<DeploymentConfig>('/admin/config'),
  },

  // Security endpoints
  security: {
    getStats: () => request<SecurityStats>('/admin/security/stats'),

    // Banned IPs
    listBannedIPs: (includeExpired = false, includeInactive = false) =>
      request<BannedIPList>(
        `/admin/security/banned-ips?include_expired=${includeExpired}&include_inactive=${includeInactive}`
      ),

    banIP: (data: {
      ip_address: string;
      reason?: BanReason;
      details?: string;
      expires_at?: string;
      associated_email?: string;
    }) =>
      request<BannedIP>('/admin/security/banned-ips', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    unbanIP: (banId: string) =>
      request<MessageResponse>(`/admin/security/banned-ips/${banId}`, {
        method: 'DELETE',
      }),

    // Banned emails
    listBannedEmails: (includeExpired = false, includeInactive = false) =>
      request<BannedEmailList>(
        `/admin/security/banned-emails?include_expired=${includeExpired}&include_inactive=${includeInactive}`
      ),

    banEmail: (data: {
      email: string;
      is_pattern?: boolean;
      reason?: BanReason;
      details?: string;
      expires_at?: string;
      associated_ip?: string;
    }) =>
      request<BannedEmail>('/admin/security/banned-emails', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    unbanEmail: (banId: string) =>
      request<MessageResponse>(`/admin/security/banned-emails/${banId}`, {
        method: 'DELETE',
      }),

    // Security events
    listEvents: (limit = 50) =>
      request<SecurityEventList>(`/admin/security/events?limit=${limit}`),
  },
};

export { ApiError };
