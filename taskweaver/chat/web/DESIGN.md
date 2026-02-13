# Chat Web UI - Design Document

## Overview

The Chat Web UI provides a browser-based interface for interacting with TaskWeaver. It consists of a FastAPI backend with WebSocket support and a React frontend.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     React Frontend (ChatPage)                         │  │
│  │  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────────┐   │  │
│  │  │  Sessions   │  │  Message List   │  │    Input + Controls     │   │  │
│  │  │  Sidebar    │  │  (streaming)    │  │  (send, confirm, etc)   │   │  │
│  │  └─────────────┘  └─────────────────┘  └─────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    │ WebSocket                              │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI SERVER                                     │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Chat Router (/api/v1/chat)                         │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │  │
│  │  │ POST /sessions  │  │ WS /ws/{id}     │  │ GET /sessions/{id}/ │   │  │
│  │  │ GET /sessions   │  │ (bidirectional) │  │     artifacts/{file}│   │  │
│  │  │ DELETE /sessions│  │                 │  │                     │   │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      ChatSessionManager                               │  │
│  │   _sessions: Dict[session_id, ChatSession]                            │  │
│  │   _app: TaskWeaverApp (lazy initialized)                              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      TaskWeaver Session                               │  │
│  │   - memory: Conversation history (rounds, posts, attachments)         │  │
│  │   - event_emitter: Streams events to WebSocket                        │  │
│  │   - execution_cwd: Working directory for artifacts                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### Backend (`taskweaver/chat/web/routes.py`)

#### ChatSessionManager
Manages the lifecycle of chat sessions.

```python
class ChatSessionManager:
    _sessions: Dict[str, ChatSession]  # Active sessions
    _app: Optional[TaskWeaverApp]      # Lazy-initialized app instance
    _app_dir: Optional[str]            # TaskWeaver project directory
```

**Methods:**
- `create_session()` → Creates a new TaskWeaver session
- `get_session(id)` → Retrieves an existing session
- `delete_session(id)` → Stops and removes a session
- `list_sessions()` → Returns all session IDs
- `cleanup_all()` → Cleanup on shutdown

#### ChatSession
Wraps a TaskWeaver session with WebSocket state.

```python
@dataclass
class ChatSession:
    session_id: str
    tw_session: Session           # TaskWeaver session
    websocket: Optional[WebSocket]
    is_processing: bool
    pending_files: List[Dict]     # Files queued for next message
```

#### WebSocketEventHandler
Implements `SessionEventHandlerBase` to forward TaskWeaver events to WebSocket.

**Event Types Forwarded:**
| TaskWeaver Event | WebSocket Message Type |
|------------------|------------------------|
| `session_*` | `session_{event_name}` |
| `round_start` | `round_start` |
| `round_end` | `round_end` |
| `round_error` | `error` |
| `post_start` | `post_start` |
| `post_end` | `post_end` |
| `post_message_update` | `message_update` |
| `post_attachment_update` | `attachment_start`, `attachment_update` |
| `post_send_to_update` | `send_to_update` |
| `post_status_update` | `status_update` |
| `post_execution_output` | `execution_output` |
| `post_confirmation_request` | `confirm_request` |

### Frontend (`taskweaver/web/frontend/src/pages/ChatPage.tsx`)

#### State Management
- `sessions`: List of available sessions
- `selectedSessionId`: Currently active session
- `messages`: Record<session_id, ChatMessage[]>
- `connectionStatus`: 'connected' | 'disconnected' | 'connecting'
- `confirmationRequest`: Pending code execution approval

#### Message Handling
The frontend maintains message state and updates it based on WebSocket events:

```typescript
interface ChatMessage {
  id: string
  role: 'User' | 'Planner' | 'CodeInterpreter' | string
  sendTo?: string
  text: string
  attachments: ChatAttachment[]
  isStreaming: boolean
  timestamp: number
}
```

## WebSocket Protocol

### Connection Flow

```
Client                                    Server
  │                                          │
  │──── WS Connect /ws/{session_id} ────────▶│
  │                                          │
  │◀──── { type: "connected" } ─────────────│
  │                                          │
  │◀──── History Replay (if exists) ────────│
  │      (round_start, post_start,          │
  │       message_update, attachment_*,      │
  │       post_end, round_end, ...)         │
  │                                          │
  │◀──── { type: "history_complete" } ──────│
  │                                          │
  │──── { type: "send_message", ... } ──────▶│
  │                                          │
  │◀──── Streaming Events ──────────────────│
  │                                          │
```

### Client → Server Messages

#### send_message
```json
{
  "type": "send_message",
  "message": "What is 2+2?",
  "files": []
}
```

#### confirm
```json
{
  "type": "confirm",
  "approved": true
}
```

#### upload_file
```json
{
  "type": "upload_file",
  "filename": "data.csv",
  "content": "base64-encoded-content"
}
```

### Server → Client Messages

#### connected
```json
{
  "type": "connected",
  "session_id": "20260205-123456-abc123"
}
```

#### history_complete
Sent after replaying conversation history on reconnect.
```json
{
  "type": "history_complete"
}
```

#### post_start
```json
{
  "type": "post_start",
  "post_id": "post-20260205-123456-abc123",
  "round_id": "round-123",
  "role": "Planner"
}
```

#### message_update
```json
{
  "type": "message_update",
  "post_id": "post-123",
  "text": "incremental text chunk",
  "is_end": false
}
```

#### attachment_start
```json
{
  "type": "attachment_start",
  "post_id": "post-123",
  "attachment_id": "atta-456",
  "attachment_type": "code"
}
```

#### attachment_update
```json
{
  "type": "attachment_update",
  "post_id": "post-123",
  "attachment_id": "atta-456",
  "content": "print('hello')",
  "is_end": true
}
```

#### send_to_update
```json
{
  "type": "send_to_update",
  "post_id": "post-123",
  "send_to": "CodeInterpreter"
}
```

#### confirm_request
```json
{
  "type": "confirm_request",
  "code": "import os\nos.listdir('/')",
  "round_id": "round-123",
  "post_id": "post-456"
}
```

#### message_complete
```json
{
  "type": "message_complete",
  "result": "The answer is 4"
}
```

#### error
```json
{
  "type": "error",
  "message": "Already processing a message"
}
```

## Conversation History Persistence

### Storage
Conversation history is stored in TaskWeaver's `Memory` object:

```
Memory
└── Conversation
    └── Round[]
        ├── user_query: str
        ├── state: "created" | "finished" | "failed"
        └── Post[]
            ├── send_from: str
            ├── send_to: str
            ├── message: str
            └── Attachment[]
```

### History Replay on Reconnect
When a WebSocket connects to an existing session, the server replays the full conversation history:

1. For each round in `session.tw_session.memory.conversation.rounds`:
   - Send `round_start`
   - Send user query as a User post
   - For each post in the round:
     - Send `post_start` with role
     - Send `send_to_update`
     - Send all attachments (`attachment_start` + `attachment_update`)
     - Send message (`message_update`)
     - Send `post_end`
   - Send `round_end`
2. Send `history_complete`

This allows the frontend to reconstruct the full conversation using the same event handlers used for live streaming.

## Artifact Serving

### Problem
Images and files generated during code execution need to be accessible via HTTP. TaskWeaver stores artifacts in the session's `execution_cwd` directory.

### Solution
Two artifact endpoints with fallback:

1. **CES Artifact Endpoint** (`/api/v1/sessions/{id}/artifacts/{file}`)
   - Primary endpoint for CES sessions
   - Falls back to chat sessions if CES session not found

2. **Chat Artifact Endpoint** (`/api/v1/chat/sessions/{id}/artifacts/{file}`)
   - Dedicated endpoint for chat sessions
   - Serves files from `tw_session.execution_cwd`

### Security
Path traversal protection:
```python
real_path = os.path.realpath(artifact_path)
real_cwd = os.path.realpath(session.execution_cwd)
if not real_path.startswith(real_cwd):
    raise HTTPException(403, "Access denied")
```

### Image Rendering
The frontend detects image URLs in content and renders them as `<img>` tags:

```typescript
const ARTIFACT_URL_REGEX = /\/api\/v1\/sessions\/[^/]+\/artifacts\/[^\s]+\.(?:png|jpg|...)/gi

function renderContentWithImages(content: string): React.ReactNode {
  // Find image URLs and replace with <img> tags
}
```

## SPA Routing

### Problem
React Router uses client-side routing, but refreshing at `/chat` returns 404 from FastAPI.

### Solution
Explicit route handlers serve `index.html` for frontend routes:

```python
@app.get("/chat")
@app.get("/chat/{path:path}")
@app.get("/sessions")
@app.get("/sessions/{path:path}")
async def spa_fallback(request: Request):
    return FileResponse(str(index_html))
```

## Code Execution Confirmation

### Flow
1. Code is generated and needs execution
2. Backend sends `confirm_request` with code
3. Frontend shows modal with code preview
4. User clicks Approve/Reject
5. Frontend sends `confirm` message
6. Backend calls `event_emitter.provide_confirmation(approved)`
7. Execution proceeds or is cancelled

### WebSocketConfirmationHandler
Placeholder that signals the event emitter to block:
```python
class WebSocketConfirmationHandler(ConfirmationHandler):
    def request_confirmation(self, code, round_id, post_id) -> bool:
        return True  # Actual confirmation via event_emitter.provide_confirmation()
```

## File Structure

```
taskweaver/chat/web/
├── __init__.py           # Exports chat_router
├── routes.py             # WebSocket + REST endpoints
└── DESIGN.md             # This document

taskweaver/web/
├── __init__.py           # mount_frontend(), SPA routing
├── static/               # Built frontend assets
│   ├── index.html
│   └── assets/
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   └── ChatPage.tsx
    │   ├── lib/
    │   │   ├── api.ts        # REST API client
    │   │   └── chatStore.ts  # In-memory state persistence
    │   └── types/
    │       └── chat.ts       # TypeScript interfaces
    └── dist/             # Alternative build output location
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat/sessions` | Create new session |
| GET | `/api/v1/chat/sessions` | List all sessions |
| DELETE | `/api/v1/chat/sessions/{id}` | Delete session |
| WS | `/api/v1/chat/ws/{id}` | WebSocket connection |
| GET | `/api/v1/chat/sessions/{id}/artifacts/{file}` | Download artifact |

## Configuration

The chat manager is initialized via `ChatSessionManager.set_app_dir()` during server startup in `taskweaver/ces/server/app.py`.

```python
if app_dir:
    chat_manager.set_app_dir(app_dir)
```

## Future Improvements

- [ ] File upload UI in frontend
- [ ] Session renaming/metadata
- [ ] Export conversation to file
- [ ] Multiple concurrent sessions in tabs
- [ ] Markdown rendering in messages
- [ ] Syntax highlighting for code blocks
- [ ] Session persistence across server restarts
