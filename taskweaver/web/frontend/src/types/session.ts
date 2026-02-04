export interface SessionInfo {
  session_id: string
  created_at: string
  last_activity: string | null
  execution_count: number
  status: 'active' | 'idle' | 'stopped'
  plugins: string[]
  cwd: string
}

export interface SessionListResponse {
  sessions: SessionInfo[]
  total: number
}

export interface SessionCreateResponse {
  session_id: string
  status: string
  cwd: string
}
