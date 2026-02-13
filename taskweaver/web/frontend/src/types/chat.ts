export interface ChatMessage {
  id: string
  role: 'User' | 'Planner' | 'CodeInterpreter' | string
  sendTo?: string
  text: string
  attachments: ChatAttachment[]
  isStreaming: boolean
  isEnd?: boolean
  executionOutput?: { stdout: string[], stderr: string[] }
  timestamp: number
}

export interface ChatAttachment {
  id: string
  type: 'code' | 'plan' | 'thought' | 'execution_result' | string
  content: string
  isStreaming: boolean
  isEnd?: boolean
}

export interface ChatSession {
  session_id: string
  created_at?: string
  last_activity?: string
}

export interface ChatSessionListResponse {
  sessions: ChatSession[]
}
