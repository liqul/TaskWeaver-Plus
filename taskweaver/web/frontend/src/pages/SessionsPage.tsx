import { useState, useEffect, useCallback, useRef } from 'react'
import { RefreshCw, Plus, Trash2, Server, Play, Terminal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api } from '@/lib/api'
import { formatRelativeTime, generateId } from '@/lib/utils'
import type { SessionInfo, ExecuteCodeResponse, ExecuteStreamResponse } from '@/types'

interface ExecutionEntry {
  id: string
  code: string
  stdout: string[]
  stderr: string[]
  result: ExecuteCodeResponse | null
  error: string | null
  timestamp: Date
  isStreaming: boolean
}

type SessionHistoryMap = Record<string, ExecutionEntry[]>

export function SessionsPage() {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [selectedSession, setSelectedSession] = useState<SessionInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [codeBySession, setCodeBySession] = useState<Record<string, string>>({})
  const [executingSessionIds, setExecutingSessionIds] = useState<Set<string>>(new Set())
  const [historyBySession, setHistoryBySession] = useState<SessionHistoryMap>({})
  
  const eventSourceRef = useRef<Map<string, EventSource>>(new Map())

  const currentHistory = selectedSession ? (historyBySession[selectedSession.session_id] || []) : []
  const isExecuting = selectedSession ? executingSessionIds.has(selectedSession.session_id) : false
  const code = selectedSession ? (codeBySession[selectedSession.session_id] ?? 'print("Hello, TaskWeaver!")') : ''

  const setCode = useCallback((newCode: string) => {
    if (!selectedSession) return
    setCodeBySession((prev) => ({
      ...prev,
      [selectedSession.session_id]: newCode,
    }))
  }, [selectedSession])

  const setSessionExecuting = useCallback((sessionId: string, executing: boolean) => {
    setExecutingSessionIds((prev) => {
      const next = new Set(prev)
      if (executing) {
        next.add(sessionId)
      } else {
        next.delete(sessionId)
      }
      return next
    })
  }, [])

  const updateSessionHistory = useCallback((sessionId: string, updater: (prev: ExecutionEntry[]) => ExecutionEntry[]) => {
    setHistoryBySession((prev) => ({
      ...prev,
      [sessionId]: updater(prev[sessionId] || []),
    }))
  }, [])

  const fetchSessions = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const response = await api.listSessions()
      setSessions(response.sessions || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch sessions')
      setSessions([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSessions()
    const interval = setInterval(fetchSessions, 10000)
    return () => clearInterval(interval)
  }, [fetchSessions])

  useEffect(() => {
    return () => {
      // Clean up all event sources on unmount
      eventSourceRef.current.forEach((es) => es.close())
      eventSourceRef.current.clear()
    }
  }, [])

  const handleCreateSession = async () => {
    try {
      setIsCreating(true)
      setError(null)
      const response = await api.createSession()
      await fetchSessions()
      const newSession = await api.getSession(response.session_id)
      setSelectedSession(newSession)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session')
    } finally {
      setIsCreating(false)
    }
  }

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await api.deleteSession(sessionId)
      if (selectedSession?.session_id === sessionId) {
        setSelectedSession(null)
      }
      setHistoryBySession((prev) => {
        const updated = { ...prev }
        delete updated[sessionId]
        return updated
      })
      setCodeBySession((prev) => {
        const updated = { ...prev }
        delete updated[sessionId]
        return updated
      })
      await fetchSessions()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete session')
    }
  }

  const handleSelectSession = async (sessionId: string) => {
    try {
      const session = await api.getSession(sessionId)
      setSelectedSession(session)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch session details')
    }
  }

  const handleExecuteCode = async () => {
    if (!selectedSession || !code.trim()) return

    const sessionId = selectedSession.session_id
    const execId = `exec-${generateId()}`
    const historyEntry: ExecutionEntry = {
      id: execId,
      code: code,
      stdout: [],
      stderr: [],
      result: null,
      error: null,
      timestamp: new Date(),
      isStreaming: true,
    }

    updateSessionHistory(sessionId, (prev) => [historyEntry, ...prev])
    setSessionExecuting(sessionId, true)

    try {
      const streamResponse = await api.executeCode(sessionId, execId, code, true)
      
      if ('stream_url' in streamResponse) {
        const response = streamResponse as ExecuteStreamResponse
        const eventSource = new EventSource(response.stream_url)
        eventSourceRef.current.set(sessionId, eventSource)

        eventSource.addEventListener('output', (event) => {
          const data = JSON.parse(event.data)
          updateSessionHistory(sessionId, (prev) =>
            prev.map((entry) => {
              if (entry.id !== execId) return entry
              if (data.type === 'stdout') {
                return { ...entry, stdout: [...entry.stdout, data.text] }
              } else if (data.type === 'stderr') {
                return { ...entry, stderr: [...entry.stderr, data.text] }
              }
              return entry
            })
          )
        })

        eventSource.addEventListener('result', (event) => {
          const data = JSON.parse(event.data) as ExecuteCodeResponse
          updateSessionHistory(sessionId, (prev) =>
            prev.map((entry) =>
              entry.id === execId ? { ...entry, result: data, isStreaming: false } : entry
            )
          )
        })

        eventSource.addEventListener('done', () => {
          eventSource.close()
          eventSourceRef.current.delete(sessionId)
          setSessionExecuting(sessionId, false)
          api.getSession(sessionId).then(setSelectedSession)
        })

        eventSource.onerror = () => {
          eventSource.close()
          eventSourceRef.current.delete(sessionId)
          setSessionExecuting(sessionId, false)
          updateSessionHistory(sessionId, (prev) =>
            prev.map((entry) =>
              entry.id === execId && entry.isStreaming
                ? { ...entry, isStreaming: false, error: 'Stream connection lost' }
                : entry
            )
          )
        }
      }
    } catch (err) {
      updateSessionHistory(sessionId, (prev) =>
        prev.map((entry) =>
          entry.id === execId
            ? { ...entry, error: err instanceof Error ? err.message : 'Execution failed', isStreaming: false }
            : entry
        )
      )
      setSessionExecuting(sessionId, false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      handleExecuteCode()
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Code Execution Sessions</h1>
          <p className="text-muted-foreground">Manage Jupyter kernel sessions and execute code</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchSessions} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button size="sm" onClick={handleCreateSession} disabled={isCreating}>
            {isCreating ? (
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Plus className="h-4 w-4 mr-2" />
            )}
            {isCreating ? 'Creating...' : 'New Session'}
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-destructive/15 text-destructive px-4 py-3 rounded-md">{error}</div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Sessions ({sessions.length})
            </CardTitle>
            <CardDescription>Click to select a session</CardDescription>
          </CardHeader>
          <CardContent>
            {sessions.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">
                No active sessions. Create one to start executing code.
              </p>
            ) : (
              <div className="space-y-2">
                {sessions.map((session) => (
                  <div
                    key={session.session_id}
                    className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors hover:bg-accent ${
                      selectedSession?.session_id === session.session_id ? 'bg-accent border-primary' : ''
                    }`}
                    onClick={() => handleSelectSession(session.session_id)}
                  >
                    <div className="space-y-1 overflow-hidden">
                      <p className="font-mono text-sm truncate">{session.session_id}</p>
                      <p className="text-xs text-muted-foreground">
                        {session.execution_count} executions
                        {session.last_activity && ` • ${formatRelativeTime(session.last_activity)}`}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteSession(session.session_id)
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Code Execution
            </CardTitle>
            <CardDescription>
              {selectedSession
                ? `Session: ${selectedSession.session_id}`
                : 'Select or create a session to execute code'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {selectedSession ? (
              <>
                <div className="grid grid-cols-2 gap-4 p-3 bg-muted rounded-lg text-sm">
                  <div>
                    <span className="text-muted-foreground">Status:</span>{' '}
                    <span className="capitalize">{selectedSession.status}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Executions:</span>{' '}
                    {selectedSession.execution_count}
                  </div>
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Working Dir:</span>{' '}
                    <span className="font-mono text-xs">{selectedSession.cwd}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Python Code</label>
                  <textarea
                    className="w-full h-32 p-3 font-mono text-sm border rounded-lg bg-slate-900 text-slate-100 focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Enter Python code..."
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={isExecuting}
                  />
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-muted-foreground">
                      Press Ctrl+Enter to execute
                    </span>
                    <Button onClick={handleExecuteCode} disabled={isExecuting || !code.trim()}>
                      <Play className="h-4 w-4 mr-2" />
                      {isExecuting ? 'Executing...' : 'Execute'}
                    </Button>
                  </div>
                </div>

                {currentHistory.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-medium">Execution History</h4>
                    <div className="space-y-3 max-h-96 overflow-y-auto">
                      {currentHistory.map((entry) => (
                        <div key={entry.id} className="border rounded-lg overflow-hidden">
                          <div className="bg-slate-800 p-3">
                            <pre className="text-xs text-slate-200 whitespace-pre-wrap overflow-x-auto">
                              {entry.code}
                            </pre>
                          </div>
                          <div className="p-3 bg-muted">
                            {entry.stdout.length > 0 && (
                              <div className="mb-2">
                                <span className="text-xs font-medium text-green-600">stdout:</span>
                                <pre className="text-xs mt-1 whitespace-pre-wrap font-mono">
                                  {entry.stdout.join('')}
                                </pre>
                              </div>
                            )}
                            {entry.stderr.length > 0 && (
                              <div className="mb-2">
                                <span className="text-xs font-medium text-yellow-600">stderr:</span>
                                <pre className="text-xs mt-1 whitespace-pre-wrap text-yellow-700 font-mono">
                                  {entry.stderr.join('')}
                                </pre>
                              </div>
                            )}
                            {entry.result ? (
                              <div className="space-y-2">
                                {!entry.result.is_success && (
                                  <div>
                                    <span className="text-xs font-medium text-red-600">Error:</span>
                                    <pre className="text-xs mt-1 whitespace-pre-wrap text-red-600 font-mono">
                                      {entry.result.error || 'Unknown error'}
                                    </pre>
                                  </div>
                                )}
                                {entry.result.is_success && entry.stdout.length === 0 && entry.stderr.length === 0 && (
                                  <span className="text-xs text-muted-foreground">
                                    Execution completed (no output)
                                  </span>
                                )}
                              </div>
                            ) : entry.error ? (
                              <div className="text-xs text-red-600">{entry.error}</div>
                            ) : entry.isStreaming ? (
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <RefreshCw className="h-3 w-3 animate-spin" />
                                Executing...
                              </div>
                            ) : null}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <Terminal className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Select a session from the list or create a new one</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
