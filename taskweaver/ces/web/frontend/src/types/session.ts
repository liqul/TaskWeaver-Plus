export interface SessionInfo {
  session_id: string
  created_at: string
  last_activity: string | null
  execution_count: number
  status: 'running' | 'stopped'
  loaded_plugins: string[]
  cwd: string
}

export interface SessionListResponse {
  sessions: SessionInfo[]
  total_count: number
}

export interface SessionCreateResponse {
  session_id: string
  status: string
  cwd: string
}
