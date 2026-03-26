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
  app_admin_apps: AppAdminScope[];
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

export interface UserLookupResponse {
  exists: boolean;
  user: User | null;
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
  admin_roles: string;
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
  user_id: string;
  email: string;
  role: string | null;
  is_app_admin: boolean;
  granted_at: string;
  granted_by: string | null;
}

export interface AppApiKey {
  id: string;
  name: string;
  key_prefix: string;
  created_by_email: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  revoked_by: string | null;
  created_at: string;
}

export interface AppDetail extends App {
  users: AppUserAccess[];
  api_keys: AppApiKey[];
}

export interface AppAdminScope {
  app_id: string;
  app_slug: string;
  app_name: string;
  app_description: string | null;
  app_url: string | null;
}

export interface UserAppAccess {
  app_slug: string;
  app_name: string;
  app_description: string | null;
  app_url: string | null;
  role: string | null;
  granted_at: string;
  granted_by?: string | null;
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
  manual_bans_today: number;
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

export interface UserSession {
  id: string;
  auth_method: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
}

export interface UserInvestigation {
  user: User;
  app_access: UserAppAccess[];
  active_sessions: UserSession[];
  recent_audit_logs: AuditLog[];
  active_ip_bans: BannedIP[];
  active_email_bans: BannedEmail[];
  recent_ip_addresses: string[];
  last_auth_method: string | null;
  last_seen_at: string | null;
}

export interface AuditLog {
  id: string;
  timestamp: string;
  actor_id: string | null;
  actor_email: string | null;
  event_type: string;
  target_type: string | null;
  target_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, unknown> | null;
}

export interface AuditLogList {
  logs: AuditLog[];
  total: number;
  page: number;
  page_size: number;
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

    getUserInvestigation: (id: string, auditLimit = 20) =>
      request<UserInvestigation>(`/admin/users/${id}/investigation?audit_limit=${auditLimit}`),

    lookupUserByEmail: (email: string) =>
      request<UserLookupResponse>(`/admin/users/lookup?email=${encodeURIComponent(email)}`),

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

    revokeUserSession: (userId: string, sessionId: string) =>
      request<MessageResponse>(`/admin/users/${userId}/sessions/${sessionId}`, {
        method: 'DELETE',
      }),

    revokeAllUserSessions: (userId: string) =>
      request<MessageResponse>(`/admin/users/${userId}/sessions/revoke-all`, {
        method: 'POST',
      }),

    // App management
    listApps: () => request<AppList>('/admin/apps'),

    createApp: (data: { slug: string; name: string; description?: string; app_url?: string; roles?: string; admin_roles?: string }) =>
      request<App>('/admin/apps', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    updateApp: (slug: string, data: { name?: string; description?: string; app_url?: string; roles?: string; admin_roles?: string }) =>
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

    createAppApiKey: (slug: string, name: string) =>
      request<{ api_key: AppApiKey; plain_text_key: string }>(`/admin/apps/${slug}/api-keys`, {
        method: 'POST',
        body: JSON.stringify({ name }),
      }),

    revokeAppApiKey: (slug: string, apiKeyId: string) =>
      request<MessageResponse>(`/admin/apps/${slug}/api-keys/${apiKeyId}`, {
        method: 'DELETE',
      }),

    listAppAuditLogs: (slug: string, page = 1, pageSize = 50) =>
      request<AuditLogList>(`/admin/apps/${slug}/audit-logs?page=${page}&page_size=${pageSize}`),

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

    listAuditLogs: (params: {
      page?: number;
      pageSize?: number;
      eventType?: string;
      actorEmail?: string;
      targetType?: string;
      targetId?: string;
      ipAddress?: string;
      since?: string;
      until?: string;
    } = {}) => {
      const search = new URLSearchParams();
      if (params.page) search.set('page', String(params.page));
      if (params.pageSize) search.set('page_size', String(params.pageSize));
      if (params.eventType) search.set('event_type', params.eventType);
      if (params.actorEmail) search.set('actor_email', params.actorEmail);
      if (params.targetType) search.set('target_type', params.targetType);
      if (params.targetId) search.set('target_id', params.targetId);
      if (params.ipAddress) search.set('ip_address', params.ipAddress);
      if (params.since) search.set('since', params.since);
      if (params.until) search.set('until', params.until);
      return request<AuditLogList>(`/admin/audit-logs?${search.toString()}`);
    },
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
