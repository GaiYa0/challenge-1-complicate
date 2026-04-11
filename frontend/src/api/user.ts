import http from './request'

export interface LoginPayload {
  username: string
  password: string
}

export interface LoginResult {
  access_token: string
  token_type?: string
}

/** 与后端 UserProfile 对齐 */
export interface UserProfile {
  id: number
  name: string
  role: string
  tenant_id: string
}

export function login(body: LoginPayload): Promise<LoginResult> {
  return http.post('/auth/login', body, { silentError: true }) as Promise<LoginResult>
}

export function fetchUserProfile(): Promise<UserProfile> {
  return http.get('/auth/me', { silentError: true }) as Promise<UserProfile>
}

export function getHealth(): Promise<{ status: string }> {
  return http.get('/health') as Promise<{ status: string }>
}
