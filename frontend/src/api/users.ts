import http from './request'

export interface UserListItem {
  id: number
  username: string
  role: string
  created_at: string | null
}

/** GET /auth/users（admin） */
export function fetchUsers(): Promise<UserListItem[]> {
  return http.get('/auth/users') as Promise<UserListItem[]>
}

/** DELETE /auth/users/{id}（admin） */
export function deleteUser(userId: number): Promise<void> {
  return http.delete(`/auth/users/${userId}`) as Promise<void>
}
