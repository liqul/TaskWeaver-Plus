export interface ApiResponse<T> {
  data?: T
  error?: string
}

export interface HealthResponse {
  status: string
  version: string
  active_sessions: number
}

export interface ExecutionResult {
  execution_id: string
  is_success: boolean
  error?: string
  output: string
  stdout: string[]
  stderr: string[]
}

export interface ExecuteCodeResponse {
  execution_id: string
  is_success: boolean
  error?: string
  output: string | [string, string][]
  stdout: string[]
  stderr: string[]
  artifacts: ArtifactInfo[]
}

export interface ExecuteStreamResponse {
  execution_id: string
  stream_url: string
}

export interface ArtifactInfo {
  name: string
  type: string
  file_name: string
}
