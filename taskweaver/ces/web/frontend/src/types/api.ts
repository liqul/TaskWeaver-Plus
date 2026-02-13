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
