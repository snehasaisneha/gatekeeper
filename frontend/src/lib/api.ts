const API_BASE = '/api/v1';

export interface User {
  id: string;
  email: string;
  name: string | null;
  status: 'pending' | 'approved' | 'rejected';
  is_admin: boolean;
  is_seeded: boolean;
  notify_private_app_requests: boolean;
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

// App types
export interface App {
  id: string;
  slug: string;
  name: string;
  is_public: boolean;
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

export interface AccessRequest {
  id: string;
  user_email: string;
  user_name: string | null;
  app_slug: string;
  app_name: string;
  message: string | null;
  status: 'pending' | 'approved' | 'rejected';
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
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
    register: (email: string) =>
      request<MessageResponse>('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email }),
      }),

    registerVerify: (email: string, code: string) =>
      request<AuthResponse>('/auth/register/verify', {
        method: 'POST',
        body: JSON.stringify({ email, code }),
      }),

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

    signout: () =>
      request<MessageResponse>('/auth/signout', {
        method: 'POST',
      }),

    me: () => request<User>('/auth/me'),

    updateProfile: (data: { name?: string; notify_private_app_requests?: boolean }) =>
      request<User>('/auth/me', {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),

    deleteAccount: () =>
      request<MessageResponse>('/auth/me', {
        method: 'DELETE',
      }),

    myApps: () => request<UserAppAccess[]>('/auth/me/apps'),

    publicApps: () => request<AppPublic[]>('/auth/apps/public'),

    requestAppAccess: (slug: string, message?: string) =>
      request<MessageResponse>(`/auth/me/apps/${slug}/request`, {
        method: 'POST',
        body: JSON.stringify({ message }),
      }),

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
  },

  admin: {
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

    updateUser: (id: string, data: { status?: string; is_admin?: boolean }) =>
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

    createApp: (data: { slug: string; name: string; is_public?: boolean; description?: string; app_url?: string }) =>
      request<App>('/admin/apps', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    updateApp: (slug: string, data: { name?: string; is_public?: boolean; description?: string; app_url?: string; roles?: string }) =>
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

    listAccessRequests: (slug: string, status?: string) => {
      const params = status ? `?status_filter=${status}` : '';
      return request<AccessRequest[]>(`/admin/apps/${slug}/requests${params}`);
    },

    approveAccessRequest: (slug: string, requestId: string, role?: string) =>
      request<MessageResponse>(`/admin/apps/${slug}/requests/${requestId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ role }),
      }),

    rejectAccessRequest: (slug: string, requestId: string) =>
      request<MessageResponse>(`/admin/apps/${slug}/requests/${requestId}/reject`, {
        method: 'POST',
      }),

    bulkGrantAccess: (data: { emails: string[]; app_slugs: string[]; role?: string }) =>
      request<MessageResponse>('/admin/users/grant-bulk', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    listAllAccessRequests: () => request<AccessRequest[]>('/admin/requests'),
  },
};

export { ApiError };
