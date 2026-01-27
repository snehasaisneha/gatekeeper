const API_BASE = '/api/v1';

export interface User {
  id: string;
  email: string;
  status: 'pending' | 'approved' | 'rejected';
  is_admin: boolean;
  is_seeded: boolean;
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

    deleteAccount: () =>
      request<MessageResponse>('/auth/me', {
        method: 'DELETE',
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
  },
};

export { ApiError };
