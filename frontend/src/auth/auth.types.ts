// Shared authentication types. Kept separate from services/schemas so both the AuthProvider and
// UI components can import lightweight types without pulling in axios.

export interface AuthUser {
  id: string
  email: string
  username: string
  full_name: string
  role: string
  permissions: string[]
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}

export interface AuthApiError {
  error: {
    code: string
    message: string
    request_id?: string | null
  }
}

export type AuthStatus = 'initializing' | 'authenticated' | 'unauthenticated'
