import { useState, useEffect, useRef, useCallback } from 'react'
import { Plus, Trash2, Send, MessageSquare, Terminal, FileCode, Cpu, User, CheckCircle, XCircle, AlertTriangle, Image, Paperclip, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { chatApi } from '@/lib/api'
import { chatStore } from '@/lib/chatStore'
import { MarkdownContent, HighlightedCode, RetryImage } from '@/components/MarkdownContent'
import type { ChatSession, ChatMessage } from '@/types'

const ChatMessageItem = ({ message }: { message: ChatMessage }) => {
  const isUser = message.role === 'User'
  const isPlanner = message.role === 'Planner'
  const isCodeInterpreter = message.role === 'CodeInterpreter'

  let bgColor = 'bg-muted'
  let align = 'justify-start'
  let icon = <MessageSquare className="h-5 w-5" />

  if (isUser) {
    bgColor = 'bg-blue-100 dark:bg-blue-900/30'
    align = 'justify-end'
    icon = <User className="h-5 w-5" />
  } else if (isPlanner) {
    bgColor = 'bg-green-50 dark:bg-green-900/20'
    icon = <Cpu className="h-5 w-5" />
  } else if (isCodeInterpreter) {
    bgColor = 'bg-purple-50 dark:bg-purple-900/20'
    icon = <Terminal className="h-5 w-5" />
  }

  return (
    <div className={`flex ${align} mb-4`}>
      <div className={`flex max-w-[80%] gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        <div className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${bgColor} border shadow-sm`}>
          {icon}
        </div>
        
        <div className="flex flex-col gap-2 min-w-0">
          <div className={`flex items-baseline gap-2 text-xs text-muted-foreground ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
            <span className="font-semibold">{message.role}</span>
            {message.sendTo && <span>→ {message.sendTo}</span>}
          </div>

          {message.attachments.length > 0 && (
            <div className="space-y-2">
              {message.attachments.map(att => (
                <div key={att.id} className="border rounded-md overflow-hidden bg-background text-sm">
                  <div className="bg-muted px-3 py-1 text-xs font-mono text-muted-foreground border-b flex items-center gap-2">
                    {att.type === 'code' && <FileCode className="h-3 w-3" />}
                    {att.type === 'execution_result' && <Terminal className="h-3 w-3" />}
                    {att.type === 'artifact_paths' && <Image className="h-3 w-3" />}
                    {att.type.toUpperCase()}
                  </div>
                  <div className="p-3 overflow-x-auto">
                    {att.type === 'code' ? (
                      <HighlightedCode code={att.content} language="python" />
                    ) : att.type === 'execution_result' ? (
                      <MarkdownContent content={att.content} className="font-mono text-xs text-muted-foreground" />
                    ) : att.type === 'artifact_paths' ? (
                      <div className="space-y-2">
                        {att.isStreaming ? (
                          <span className="text-xs text-muted-foreground animate-pulse">Loading artifacts…</span>
                        ) : (
                          att.content.split('\n').filter(Boolean).map((url, i) => (
                            <RetryImage key={i} src={url} alt={`Artifact ${i + 1}`} />
                          ))
                        )}
                      </div>
                    ) : (
                      <MarkdownContent content={att.content} className="text-sm" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {message.text && (
            <div className={`p-3 rounded-lg shadow-sm border ${bgColor} ${isUser ? 'rounded-tr-none' : 'rounded-tl-none'}`}>
              <MarkdownContent content={message.text} className="text-sm" />
            </div>
          )}

          {message.isStreaming && (
             <div className="flex items-center gap-1 text-xs text-muted-foreground animate-pulse">
               <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
               <span className="w-1.5 h-1.5 rounded-full bg-current animation-delay-200"></span>
               <span className="w-1.5 h-1.5 rounded-full bg-current animation-delay-400"></span>
             </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>(() => chatStore.getState().sessions)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(() => chatStore.getState().selectedSessionId)
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>(() => chatStore.getState().messages)
  const [inputValue, setInputValue] = useState('')
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected')
  const [confirmationRequest, setConfirmationRequest] = useState<{ id: string, code: string, roundId: string, postId: string } | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [executionCwd, setExecutionCwd] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const isReplayingHistoryRef = useRef<boolean>(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const uploadResolveRef = useRef<(() => void) | null>(null)
  const uploadCountRef = useRef<{ expected: number, received: number }>({ expected: 0, received: 0 })

  useEffect(() => {
    chatStore.setSessions(sessions)
  }, [sessions])

  useEffect(() => {
    chatStore.setSelectedSessionId(selectedSessionId)
  }, [selectedSessionId])

  useEffect(() => {
    Object.entries(messages).forEach(([sessionId, msgs]) => {
      chatStore.setMessages(sessionId, msgs)
    })
  }, [messages])
  
  const fetchSessions = useCallback(async () => {
    try {
      const data = await chatApi.listSessions()
      setSessions(data.sessions || [])
    } catch (err) {
      console.error('Failed to fetch sessions', err)
    }
  }, [])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, selectedSessionId])

  useEffect(() => {
    if (!selectedSessionId) return

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setConnectionStatus('connecting')
    setExecutionCwd(null)

    const wsUrl = chatApi.getWebSocketUrl(selectedSessionId)
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionStatus('connected')
    }

    ws.onclose = () => {
      setConnectionStatus('disconnected')
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setConnectionStatus('disconnected')
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        handleServerMessage(selectedSessionId, msg)
      } catch (e) {
        console.error('Failed to parse message:', e)
      }
    }

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }, [selectedSessionId])

  const handleServerMessage = (sessionId: string, msg: any) => {
    console.log('[WS Message]', msg.type, msg)
    
    if (msg.type === 'connected') {
      isReplayingHistoryRef.current = true
      setMessages(prev => ({ ...prev, [sessionId]: [] }))
      if (msg.execution_cwd) {
        setExecutionCwd(msg.execution_cwd)
      }
      return
    }
    
    if (msg.type === 'history_complete') {
      isReplayingHistoryRef.current = false
      return
    }

    if (msg.type === 'file_uploaded') {
      console.log('[WS] File uploaded:', msg.filename)
      uploadCountRef.current.received += 1
      if (uploadCountRef.current.received >= uploadCountRef.current.expected && uploadResolveRef.current) {
        uploadResolveRef.current()
        uploadResolveRef.current = null
      }
      return
    }
    
    const isReplaying = isReplayingHistoryRef.current
    
    if (msg.type === 'round_start' && !isReplaying) {
      setIsProcessing(true)
      return
    }
    
    if ((msg.type === 'round_end' || msg.type === 'message_complete' || msg.type === 'error') && !isReplaying) {
      setIsProcessing(false)
      return
    }
    
    setMessages(prev => {
      const sessionMessages = [...(prev[sessionId] || [])]
      
      switch (msg.type) {
        case 'post_start': {
          sessionMessages.push({
            id: msg.post_id,
            role: msg.role,
            text: '',
            attachments: [],
            isStreaming: !isReplaying,
            timestamp: Date.now()
          })
          break
        }
        
        case 'message_update': {
          const msgIdx = sessionMessages.findIndex(m => m.id === msg.post_id)
          if (msgIdx !== -1) {
            sessionMessages[msgIdx] = {
              ...sessionMessages[msgIdx],
              text: sessionMessages[msgIdx].text + msg.text,
              isStreaming: isReplaying ? false : !msg.is_end,
              isEnd: msg.is_end
            }
          }
          break
        }

        case 'attachment_start': {
          const msgIdx = sessionMessages.findIndex(m => m.id === msg.post_id)
          if (msgIdx !== -1) {
            const attachments = [...sessionMessages[msgIdx].attachments]
            attachments.push({
              id: msg.attachment_id,
              type: msg.attachment_type,
              content: '',
              isStreaming: !isReplaying
            })
            sessionMessages[msgIdx] = {
              ...sessionMessages[msgIdx],
              attachments
            }
          }
          break
        }

        case 'attachment_update': {
          const msgIdx = sessionMessages.findIndex(m => m.id === msg.post_id)
          if (msgIdx !== -1) {
            const attachments = [...sessionMessages[msgIdx].attachments]
            const attIdx = attachments.findIndex(a => a.id === msg.attachment_id)
            if (attIdx !== -1) {
              attachments[attIdx] = {
                ...attachments[attIdx],
                content: attachments[attIdx].content + msg.content,
                isStreaming: isReplaying ? false : !msg.is_end,
                isEnd: msg.is_end
              }
              sessionMessages[msgIdx] = { ...sessionMessages[msgIdx], attachments }
            }
          }
          break
        }

        case 'post_end': {
          const msgIdx = sessionMessages.findIndex(m => m.id === msg.post_id)
          if (msgIdx !== -1) {
             sessionMessages[msgIdx] = { ...sessionMessages[msgIdx], isStreaming: false }
          }
          break
        }

        case 'send_to_update': {
          const msgIdx = sessionMessages.findIndex(m => m.id === msg.post_id)
          if (msgIdx !== -1) {
            sessionMessages[msgIdx] = { ...sessionMessages[msgIdx], sendTo: msg.send_to }
          }
          break
        }

        case 'confirm_request': {
          setConfirmationRequest({
            id: msg.post_id,
            code: msg.code,
            roundId: msg.round_id,
            postId: msg.post_id
          })
          break
        }
      }

      return { ...prev, [sessionId]: sessionMessages }
    })
  }

  const handleCreateSession = async () => {
    try {
      const newSession = await chatApi.createSession()
      await fetchSessions()
      setSelectedSessionId(newSession.session_id)
    } catch (err) {
      console.error('Failed to create session:', err)
    }
  }

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await chatApi.deleteSession(sessionId)
      if (selectedSessionId === sessionId) {
        setSelectedSessionId(null)
      }
      chatStore.clearSession(sessionId)
      setMessages(prev => {
        const updated = { ...prev }
        delete updated[sessionId]
        return updated
      })
      await fetchSessions()
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }

  const readFileAsBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = reader.result as string
        const base64 = result.split(',')[1] || ''
        resolve(base64)
      }
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  const handleSendMessage = async () => {
    const hasText = inputValue.trim().length > 0
    const hasFiles = pendingFiles.length > 0
    if ((!hasText && !hasFiles) || !wsRef.current || !selectedSessionId) return

    const filesToSend = [...pendingFiles]
    const messageText = inputValue
    const displayText = hasFiles
      ? (hasText ? messageText : '') + '\n📎 ' + filesToSend.map(f => f.name).join(', ')
      : messageText

    const userMsgId = `user-${Date.now()}`
    setMessages(prev => ({
      ...prev,
      [selectedSessionId]: [
        ...(prev[selectedSessionId] || []),
        {
          id: userMsgId,
          role: 'User',
          text: displayText.trim(),
          attachments: [],
          isStreaming: false,
          timestamp: Date.now()
        }
      ]
    }))

    setInputValue('')
    setPendingFiles([])

    if (filesToSend.length > 0) {
      uploadCountRef.current = { expected: filesToSend.length, received: 0 }

      const uploadsDone = new Promise<void>((resolve) => {
        uploadResolveRef.current = resolve
      })

      for (const file of filesToSend) {
        const base64 = await readFileAsBase64(file)
        wsRef.current!.send(JSON.stringify({
          type: 'upload_file',
          filename: file.name,
          content: base64,
        }))
      }

      await uploadsDone
    }

    wsRef.current!.send(JSON.stringify({
      type: 'send_message',
      message: hasText ? messageText : `I've uploaded: ${filesToSend.map(f => f.name).join(', ')}`,
    }))
  }

  const handleConfirm = (approved: boolean) => {
    if (!wsRef.current || !confirmationRequest) return

    wsRef.current.send(JSON.stringify({
      type: 'confirm',
      approved,
    }))
    
    setConfirmationRequest(null)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files
    if (selected && selected.length > 0) {
      const newFiles = Array.from(selected)
      setPendingFiles(prev => [...prev, ...newFiles])
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleRemoveFile = (index: number) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const currentMessages = selectedSessionId ? (messages[selectedSessionId] || []) : []

  return (
    <div className="h-[calc(100vh-4rem)] flex gap-6">
      <Card className="w-80 flex flex-col flex-shrink-0">
        <CardHeader className="p-4 border-b">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Chat Sessions</CardTitle>
            <Button size="icon" variant="ghost" onClick={handleCreateSession}>
              <Plus className="h-5 w-5" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex-1 overflow-y-auto p-2 space-y-2">
          {sessions.length === 0 ? (
            <div className="text-center text-muted-foreground py-8 text-sm">
              No sessions yet
            </div>
          ) : (
            sessions.map(session => (
              <div
                key={session.session_id}
                onClick={() => setSelectedSessionId(session.session_id)}
                className={`p-3 rounded-lg cursor-pointer flex items-center justify-between group transition-colors ${
                  selectedSessionId === session.session_id 
                    ? 'bg-primary/10 text-primary font-medium' 
                    : 'hover:bg-muted'
                }`}
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <MessageSquare className="h-4 w-4 flex-shrink-0" />
                  <div className="truncate text-sm">
                    {session.session_id}
                  </div>
                </div>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => handleDeleteSession(session.session_id, e)}
                >
                  <Trash2 className="h-3 w-3 text-destructive" />
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card className="flex-1 flex flex-col min-w-0 relative">
        {!selectedSessionId ? (
           <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground">
             <MessageSquare className="h-12 w-12 mb-4 opacity-20" />
             <p>Select a session to start chatting</p>
           </div>
        ) : (
          <>
            <div className="border-b p-4 flex items-center justify-between bg-card">
               <div className="flex items-center gap-2">
                 <div className={`h-2 w-2 rounded-full ${
                   connectionStatus === 'connected' ? 'bg-green-500' :
                   connectionStatus === 'connecting' ? 'bg-yellow-500' : 'bg-red-500'
                 }`} />
                 <span className="font-mono text-sm">{selectedSessionId}</span>
                 {executionCwd && (
                   <span className="text-xs text-muted-foreground ml-2 truncate max-w-[400px]" title={executionCwd}>
                     CWD: {executionCwd}
                   </span>
                 )}
               </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 bg-slate-50/50 dark:bg-slate-900/50">
              {currentMessages.map((msg, idx) => (
                <ChatMessageItem key={msg.id || idx} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>

            {confirmationRequest && (
              <div className="absolute inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-6">
                <Card className="w-full max-w-2xl border-2 border-primary shadow-2xl">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-primary">
                      <AlertTriangle className="h-5 w-5" />
                      Execution Confirmation
                    </CardTitle>
                    <CardDescription>
                      The agent wants to execute the following code. Please review it carefully.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="bg-muted p-4 rounded-lg overflow-x-auto max-h-[40vh]">
                      <pre className="font-mono text-sm">{confirmationRequest.code}</pre>
                    </div>
                    <div className="flex justify-end gap-3 pt-2">
                      <Button 
                        variant="destructive" 
                        onClick={() => handleConfirm(false)}
                        className="gap-2"
                      >
                        <XCircle className="h-4 w-4" />
                        Reject
                      </Button>
                      <Button 
                        variant="default" 
                        onClick={() => handleConfirm(true)}
                        className="gap-2"
                      >
                        <CheckCircle className="h-4 w-4" />
                        Approve
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            <div className="p-4 border-t bg-card">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={handleFileSelect}
              />
              {pendingFiles.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {pendingFiles.map((file, index) => (
                    <div
                      key={`${file.name}-${index}`}
                      className="flex items-center gap-1.5 bg-muted text-sm px-2.5 py-1 rounded-full border"
                    >
                      <Paperclip className="h-3 w-3 text-muted-foreground" />
                      <span className="max-w-[150px] truncate">{file.name}</span>
                      <button
                        onClick={() => handleRemoveFile(index)}
                        className="ml-0.5 hover:bg-accent rounded-full p-0.5 transition-colors"
                      >
                        <X className="h-3 w-3 text-muted-foreground" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={connectionStatus !== 'connected' || !!confirmationRequest || isProcessing}
                  className="flex-shrink-0"
                >
                  <Paperclip className="h-4 w-4" />
                </Button>
                <Input 
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={isProcessing ? "Waiting for response..." : "Type a message..."}
                  className="flex-1"
                  disabled={connectionStatus !== 'connected' || !!confirmationRequest || isProcessing}
                />
                <Button 
                  onClick={handleSendMessage} 
                  disabled={(!inputValue.trim() && pendingFiles.length === 0) || connectionStatus !== 'connected' || !!confirmationRequest || isProcessing}
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
