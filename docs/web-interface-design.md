# TaskWeaver Web Interface Design Document

**Version:** 1.0  
**Date:** 2026-02-04  
**Status:** Draft

## 1. Overview

This document describes the design for a new web interface for TaskWeaver, providing:
1. **CES Admin UI** - Session management for the Code Execution Server
2. **Chatbot UI** - Conversational interface for interacting with TaskWeaver

### Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend Framework | React 18 + TypeScript |
| Styling | Tailwind CSS 3 |
| UI Components | shadcn/ui |
| State Management | React Context + useReducer (simple) / Zustand (if needed) |
| API Client | fetch + custom hooks |
| Build Tool | Vite |
| Deployment | Integrated with FastAPI (static file serving) |

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Web Browser                                  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    React Application                          │  │
│  │  ┌─────────────────┐  ┌────────────────────────────────────┐  │  │
│  │  │   CES Admin     │  │         Chatbot UI                 │  │  │
│  │  │   ┌───────────┐ │  │  ┌──────────┐  ┌───────────────┐   │  │  │
│  │  │   │ Sessions  │ │  │  │ Messages │  │ Input Area    │   │  │  │
│  │  │   │ List      │ │  │  │ Display  │  │ + File Upload │   │  │  │
│  │  │   └───────────┘ │  │  └──────────┘  └───────────────┘   │  │  │
│  │  │   ┌───────────┐ │  │  ┌──────────┐  ┌───────────────┐   │  │  │
│  │  │   │ Session   │ │  │  │ Code     │  │ Artifacts     │   │  │  │
│  │  │   │ Details   │ │  │  │ Blocks   │  │ Panel         │   │  │  │
│  │  │   └───────────┘ │  │  └──────────┘  └───────────────┘   │  │  │
│  │  └─────────────────┘  └────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP / SSE
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Server (CES)                             │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Static Files        │  API Routes (/api/v1/*)                │  │
│  │  /static/*           │  /sessions, /execute, /stream, etc.    │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Directory Structure

```
taskweaver/
├── web/                          # New web interface package
│   ├── frontend/                 # React application
│   │   ├── src/
│   │   │   ├── components/       # Reusable UI components
│   │   │   │   ├── ui/           # shadcn/ui components
│   │   │   │   ├── chat/         # Chat-specific components
│   │   │   │   └── admin/        # Admin-specific components
│   │   │   ├── hooks/            # Custom React hooks
│   │   │   ├── lib/              # Utilities, API client
│   │   │   ├── pages/            # Page components
│   │   │   ├── types/            # TypeScript type definitions
│   │   │   ├── App.tsx           # Root component
│   │   │   └── main.tsx          # Entry point
│   │   ├── public/               # Static assets
│   │   ├── index.html            # HTML template
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── vite.config.ts
│   │   └── tailwind.config.js
│   ├── static/                   # Built frontend files (git-ignored)
│   └── server.py                 # FastAPI static file serving integration
```

---

## 3. API Design

### 3.1 Existing CES API Endpoints (to use)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/sessions` | Create session |
| GET | `/api/v1/sessions/{id}` | Get session info |
| DELETE | `/api/v1/sessions/{id}` | Stop session |
| POST | `/api/v1/sessions/{id}/execute` | Execute code |
| GET | `/api/v1/sessions/{id}/stream/{exec_id}` | SSE stream |
| POST | `/api/v1/sessions/{id}/files` | Upload file |
| GET | `/api/v1/sessions/{id}/artifacts/{file}` | Download artifact |

### 3.2 New API Endpoints (to add)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/sessions` | **List all sessions** (new) |
| POST | `/api/v1/chat/sessions` | Create chat session |
| POST | `/api/v1/chat/sessions/{id}/messages` | Send message to chatbot |
| GET | `/api/v1/chat/sessions/{id}/messages` | Get chat history |
| GET | `/api/v1/chat/sessions/{id}/stream` | SSE stream for chat responses |

### 3.3 New API Models

```python
# List Sessions Response
class SessionListResponse(BaseModel):
    sessions: List[SessionInfo]
    total: int

class SessionInfo(BaseModel):
    session_id: str
    created_at: datetime
    last_activity: Optional[datetime]
    execution_count: int
    status: Literal["active", "idle", "stopped"]

# Chat Message Models
class ChatMessageRequest(BaseModel):
    message: str
    files: Optional[List[FileUpload]] = None

class ChatMessageResponse(BaseModel):
    message_id: str
    session_id: str
    stream_url: str  # SSE endpoint for response

class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    attachments: List[ChatAttachment] = []
    metadata: Optional[Dict[str, Any]] = None

class ChatAttachment(BaseModel):
    type: Literal["code", "plan", "artifact", "error", "thinking"]
    content: str
    language: Optional[str] = None  # For code blocks
    artifact_url: Optional[str] = None  # For downloadable files
```

---

## 4. Component Design

### 4.1 CES Admin UI Components

#### SessionList
```tsx
interface SessionListProps {
  onSelectSession: (sessionId: string) => void;
  selectedSessionId?: string;
}

// Features:
// - Display all active sessions in a table/list
// - Show session_id, created_at, last_activity, execution_count
// - Click to select and view details
// - Delete button to stop session
// - Auto-refresh every 5 seconds
```

#### SessionDetails
```tsx
interface SessionDetailsProps {
  sessionId: string;
}

// Features:
// - Display session metadata
// - Show loaded plugins
// - Display execution history (recent)
// - Show current working directory
// - Stop session button
```

### 4.2 Chatbot UI Components

#### ChatContainer
```tsx
// Main container managing chat state
// - Manages WebSocket/SSE connection
// - Handles message sending
// - Manages file uploads
```

#### MessageList
```tsx
interface MessageListProps {
  messages: ChatMessage[];
  isStreaming: boolean;
}

// Features:
// - Virtualized scrolling for performance
// - Auto-scroll to bottom on new messages
// - Different styling for user vs assistant messages
// - Support for markdown rendering
```

#### MessageBubble
```tsx
interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

// Features:
// - User messages: right-aligned, blue background
// - Assistant messages: left-aligned, gray background
// - Render attachments based on type
// - Show timestamp on hover
```

#### CodeBlock
```tsx
interface CodeBlockProps {
  code: string;
  language?: string;
  showLineNumbers?: boolean;
}

// Features:
// - Syntax highlighting (using highlight.js or Prism)
// - Copy to clipboard button
// - Line numbers (optional)
// - Language indicator badge
```

#### PlanDisplay
```tsx
interface PlanDisplayProps {
  steps: PlanStep[];
  currentStep?: number;
}

// Features:
// - Show numbered plan steps
// - Highlight current step being executed
// - Checkmarks for completed steps
```

#### ArtifactDisplay
```tsx
interface ArtifactDisplayProps {
  artifact: ChatAttachment;
}

// Features:
// - Image preview for image artifacts
// - Download button for file artifacts
// - Expandable preview for large content
```

#### ChatInput
```tsx
interface ChatInputProps {
  onSendMessage: (message: string, files?: File[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

// Features:
// - Multi-line text input (auto-resize)
// - Send button (+ keyboard shortcut Ctrl+Enter)
// - File attachment button
// - Show attached files as chips
// - Drag-and-drop file upload
```

#### FileUploadArea
```tsx
interface FileUploadAreaProps {
  files: File[];
  onFilesChange: (files: File[]) => void;
  maxFiles?: number;
}

// Features:
// - Drag-and-drop zone
// - File picker button
// - Display attached files with remove option
// - File type/size validation
```

---

## 5. State Management

### 5.1 Chat State

```typescript
interface ChatState {
  sessionId: string | null;
  messages: ChatMessage[];
  isLoading: boolean;
  isStreaming: boolean;
  streamingContent: string;
  error: string | null;
  pendingFiles: File[];
}

type ChatAction =
  | { type: 'SET_SESSION'; sessionId: string }
  | { type: 'ADD_MESSAGE'; message: ChatMessage }
  | { type: 'UPDATE_STREAMING'; content: string }
  | { type: 'FINISH_STREAMING' }
  | { type: 'SET_LOADING'; isLoading: boolean }
  | { type: 'SET_ERROR'; error: string }
  | { type: 'ADD_FILE'; file: File }
  | { type: 'REMOVE_FILE'; index: number }
  | { type: 'CLEAR_FILES' };
```

### 5.2 Admin State

```typescript
interface AdminState {
  sessions: SessionInfo[];
  selectedSessionId: string | null;
  isLoading: boolean;
  error: string | null;
}
```

---

## 6. API Client

```typescript
// lib/api.ts

const API_BASE = '/api/v1';

export const api = {
  // Health
  health: () => fetch(`${API_BASE}/health`).then(r => r.json()),

  // Sessions (CES)
  listSessions: () => fetch(`${API_BASE}/sessions`).then(r => r.json()),
  getSession: (id: string) => fetch(`${API_BASE}/sessions/${id}`).then(r => r.json()),
  createSession: () => fetch(`${API_BASE}/sessions`, { method: 'POST' }).then(r => r.json()),
  deleteSession: (id: string) => fetch(`${API_BASE}/sessions/${id}`, { method: 'DELETE' }),

  // Chat
  createChatSession: () => 
    fetch(`${API_BASE}/chat/sessions`, { method: 'POST' }).then(r => r.json()),
  
  sendMessage: (sessionId: string, message: string, files?: File[]) => {
    const formData = new FormData();
    formData.append('message', message);
    files?.forEach(f => formData.append('files', f));
    return fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: formData,
    }).then(r => r.json());
  },

  getChatHistory: (sessionId: string) =>
    fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`).then(r => r.json()),

  // SSE Stream
  streamChat: (sessionId: string, messageId: string): EventSource => {
    return new EventSource(`${API_BASE}/chat/sessions/${sessionId}/stream/${messageId}`);
  },

  // Files
  uploadFile: (sessionId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return fetch(`${API_BASE}/sessions/${sessionId}/files`, {
      method: 'POST',
      body: formData,
    }).then(r => r.json());
  },

  downloadArtifact: (sessionId: string, filename: string) =>
    `${API_BASE}/sessions/${sessionId}/artifacts/${filename}`,
};
```

---

## 7. SSE Streaming Protocol

### 7.1 Chat Response Stream

```
Event: thinking
Data: {"type": "thinking", "content": "Analyzing the request..."}

Event: plan
Data: {"type": "plan", "steps": ["Load data", "Process", "Display results"]}

Event: code
Data: {"type": "code", "language": "python", "content": "import pandas as pd\n..."}

Event: output
Data: {"type": "stdout", "content": "Processing complete\n"}

Event: artifact
Data: {"type": "artifact", "name": "result.png", "url": "/api/v1/sessions/.../artifacts/result.png"}

Event: message
Data: {"type": "message", "content": "Here's the analysis result:"}

Event: done
Data: {"type": "done"}
```

### 7.2 React Hook for SSE

```typescript
function useChatStream(sessionId: string, messageId: string) {
  const [content, setContent] = useState('');
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    const eventSource = new EventSource(
      `/api/v1/chat/sessions/${sessionId}/stream/${messageId}`
    );

    eventSource.addEventListener('message', (e) => {
      const data = JSON.parse(e.data);
      setContent(prev => prev + data.content);
    });

    eventSource.addEventListener('code', (e) => {
      const data = JSON.parse(e.data);
      setAttachments(prev => [...prev, { type: 'code', ...data }]);
    });

    eventSource.addEventListener('artifact', (e) => {
      const data = JSON.parse(e.data);
      setAttachments(prev => [...prev, { type: 'artifact', ...data }]);
    });

    eventSource.addEventListener('done', () => {
      setIsComplete(true);
      eventSource.close();
    });

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => eventSource.close();
  }, [sessionId, messageId]);

  return { content, attachments, isComplete };
}
```

---

## 8. UI/UX Design

### 8.1 Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Logo] TaskWeaver              [Admin] [Chat] [Settings]    [?]   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                                                             │   │
│  │                     Main Content Area                       │   │
│  │                                                             │   │
│  │   (Chat View or Admin View based on route)                  │   │
│  │                                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Chat View Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Session: abc123                              [New Chat] [History]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  [User Avatar]                                              │   │
│  │  "Analyze the sales data and create a chart"                │   │
│  │                                               10:30 AM      │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  [Bot Avatar]                                               │   │
│  │  ┌─ Thinking ───────────────────────────────────────────┐   │   │
│  │  │ Analyzing request... Planning steps...               │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │  ┌─ Plan ───────────────────────────────────────────────┐   │   │
│  │  │ 1. [✓] Load sales data                               │   │   │
│  │  │ 2. [→] Process and aggregate                         │   │   │
│  │  │ 3. [ ] Create visualization                          │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │  ┌─ Code ───────────────────────────────────────────────┐   │   │
│  │  │ ```python                              [Copy]        │   │   │
│  │  │ import pandas as pd                                  │   │   │
│  │  │ df = pd.read_csv('sales.csv')                        │   │   │
│  │  │ ```                                                  │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │  Here's your sales analysis chart:                          │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │         [Chart Image Preview]              [⬇️]       │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │                                               10:31 AM      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────┐ ┌───┐ ┌────────┐  │
│  │ Type your message...                        │ │ 📎│ │ Send → │  │
│  └─────────────────────────────────────────────┘ └───┘ └────────┘  │
│  [📄 data.csv ✕]                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.3 Admin View Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Sessions Overview                              [Refresh] [+ New]   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ Session ID    │ Created      │ Last Active │ Execs │ Actions  │ │
│  ├───────────────────────────────────────────────────────────────┤ │
│  │ ses_abc123    │ 10:00 AM     │ 10:30 AM    │ 15    │ [🗑️]    │ │
│  │ ses_def456    │ 09:15 AM     │ 09:45 AM    │ 8     │ [🗑️]    │ │
│  │ ses_ghi789    │ Yesterday    │ Yesterday   │ 42    │ [🗑️]    │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ Session Details: ses_abc123 ─────────────────────────────────┐ │
│  │                                                               │ │
│  │  Status: Active        CWD: /workspace/ses_abc123/cwd         │ │
│  │  Created: 2026-02-04 10:00:00                                 │ │
│  │  Last Activity: 2026-02-04 10:30:00                           │ │
│  │  Execution Count: 15                                          │ │
│  │                                                               │ │
│  │  Loaded Plugins:                                              │ │
│  │  • sql_query                                                  │ │
│  │  • web_search                                                 │ │
│  │                                                               │ │
│  │  [Stop Session]                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.4 Color Scheme (Tailwind)

```css
/* Light Mode */
--background: white
--foreground: slate-900
--primary: blue-600
--secondary: slate-100
--accent: blue-100
--user-bubble: blue-500
--assistant-bubble: slate-100
--code-bg: slate-900

/* Dark Mode */
--background: slate-950
--foreground: slate-50
--primary: blue-500
--secondary: slate-800
--accent: blue-900
--user-bubble: blue-600
--assistant-bubble: slate-800
--code-bg: slate-900
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Set up React + Vite + TypeScript project
- [ ] Configure Tailwind CSS + shadcn/ui
- [ ] Create basic routing (Chat, Admin pages)
- [ ] Implement API client utilities
- [ ] Add FastAPI static file serving

### Phase 2: CES Admin UI (Week 1-2)
- [ ] Implement SessionList component
- [ ] Implement SessionDetails component
- [ ] Add "List Sessions" API endpoint
- [ ] Wire up session management actions

### Phase 3: Chat UI Core (Week 2)
- [ ] Implement ChatContainer with state management
- [ ] Implement MessageList and MessageBubble
- [ ] Implement ChatInput component
- [ ] Create basic message send/receive flow

### Phase 4: Advanced Chat Features (Week 3)
- [ ] Add SSE streaming support
- [ ] Implement CodeBlock with syntax highlighting
- [ ] Implement PlanDisplay component
- [ ] Implement ArtifactDisplay component
- [ ] Add file upload functionality

### Phase 5: Polish (Week 3-4)
- [ ] Add loading states and error handling
- [ ] Implement dark mode
- [ ] Add keyboard shortcuts
- [ ] Performance optimization (virtualization)
- [ ] Testing and bug fixes

---

## 10. File Structure (Detailed)

```
taskweaver/web/frontend/
├── src/
│   ├── components/
│   │   ├── ui/                      # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── input.tsx
│   │   │   ├── scroll-area.tsx
│   │   │   ├── separator.tsx
│   │   │   ├── table.tsx
│   │   │   └── ...
│   │   ├── chat/
│   │   │   ├── ChatContainer.tsx    # Main chat orchestrator
│   │   │   ├── MessageList.tsx      # Message display list
│   │   │   ├── MessageBubble.tsx    # Individual message
│   │   │   ├── ChatInput.tsx        # Input area + file upload
│   │   │   ├── CodeBlock.tsx        # Syntax highlighted code
│   │   │   ├── PlanDisplay.tsx      # Plan steps visualization
│   │   │   ├── ArtifactDisplay.tsx  # Image/file preview
│   │   │   ├── ThinkingIndicator.tsx # Streaming thinking animation
│   │   │   └── FileChip.tsx         # Attached file indicator
│   │   ├── admin/
│   │   │   ├── SessionList.tsx      # Sessions table
│   │   │   ├── SessionDetails.tsx   # Selected session info
│   │   │   └── SessionActions.tsx   # Stop/delete buttons
│   │   └── layout/
│   │       ├── Header.tsx           # Top navigation bar
│   │       ├── Sidebar.tsx          # Optional sidebar
│   │       └── Layout.tsx           # Page layout wrapper
│   ├── hooks/
│   │   ├── useApi.ts                # Generic fetch hook
│   │   ├── useChatStream.ts         # SSE streaming hook
│   │   ├── useSessions.ts           # Sessions data hook
│   │   └── useChat.ts               # Chat state hook
│   ├── lib/
│   │   ├── api.ts                   # API client functions
│   │   ├── utils.ts                 # Utility functions
│   │   └── cn.ts                    # Class name helper
│   ├── pages/
│   │   ├── ChatPage.tsx             # Chat interface page
│   │   ├── AdminPage.tsx            # Admin dashboard page
│   │   └── NotFoundPage.tsx         # 404 page
│   ├── types/
│   │   ├── api.ts                   # API request/response types
│   │   ├── chat.ts                  # Chat-related types
│   │   └── session.ts               # Session-related types
│   ├── App.tsx                      # Root component with routing
│   ├── main.tsx                     # Entry point
│   └── index.css                    # Global styles + Tailwind
├── public/
│   └── favicon.ico
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
└── components.json                   # shadcn/ui config
```

---

## 11. Backend Changes Required

### 11.1 New File: `taskweaver/ces/server/chat_routes.py`

```python
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
# ... implementation

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

@router.post("/sessions")
async def create_chat_session(): ...

@router.post("/sessions/{session_id}/messages") 
async def send_message(session_id: str, request: ChatMessageRequest): ...

@router.get("/sessions/{session_id}/messages")
async def get_chat_history(session_id: str): ...

@router.get("/sessions/{session_id}/stream/{message_id}")
async def stream_response(session_id: str, message_id: str): ...
```

### 11.2 Modify: `taskweaver/ces/server/routes.py`

Add endpoint to list all sessions:

```python
@router.get("/sessions")
async def list_sessions() -> SessionListResponse:
    sessions = session_manager.list_sessions()
    return SessionListResponse(
        sessions=[...],
        total=len(sessions)
    )
```

### 11.3 New File: `taskweaver/web/server.py`

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

def mount_frontend(app: FastAPI):
    """Mount the built frontend static files."""
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
```

### 11.4 Modify: `taskweaver/ces/server/app.py`

```python
from taskweaver.web.server import mount_frontend

def create_app(...):
    app = FastAPI(...)
    # ... existing setup
    
    # Mount frontend (after API routes)
    mount_frontend(app)
    
    return app
```

---

## 12. Build & Development

### 12.1 Development

```bash
# Terminal 1: Start CES server
python -m taskweaver -p ./project server --port 8081

# Terminal 2: Start Vite dev server (with proxy)
cd taskweaver/web/frontend
npm run dev
```

### 12.2 Production Build

```bash
# Build frontend
cd taskweaver/web/frontend
npm run build

# Copy to static directory
cp -r dist/* ../static/

# Start server (serves both API and frontend)
python -m taskweaver -p ./project server --port 8081
```

### 12.3 Vite Config for Development

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8081',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
});
```

---

## 13. Dependencies

### Frontend (package.json)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "lucide-react": "^0.294.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.1.0",
    "highlight.js": "^11.9.0",
    "react-markdown": "^9.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32",
    "tailwindcss": "^3.3.6",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }
}
```

### Backend (requirements.txt additions)

```
sse-starlette>=1.6.0  # For SSE support (may already be present)
```

---

## 14. Success Criteria

### MVP (Minimum Viable Product)
- [ ] CES Admin: View list of active sessions
- [ ] CES Admin: View session details
- [ ] CES Admin: Stop/delete session
- [ ] Chat: Send text messages
- [ ] Chat: Receive responses with streaming
- [ ] Chat: Display code blocks with syntax highlighting
- [ ] Chat: Upload files
- [ ] Chat: Display/download artifacts

### Nice-to-Have (Future)
- [ ] Dark mode toggle
- [ ] Chat history persistence
- [ ] Multiple chat sessions
- [ ] Keyboard shortcuts
- [ ] Mobile responsive design
- [ ] Export chat as markdown

---

## Appendix A: Type Definitions

```typescript
// types/session.ts
export interface SessionInfo {
  session_id: string;
  created_at: string;
  last_activity: string | null;
  execution_count: number;
  status: 'active' | 'idle' | 'stopped';
  plugins: string[];
  cwd: string;
}

// types/chat.ts
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  attachments: ChatAttachment[];
  isStreaming?: boolean;
}

export interface ChatAttachment {
  type: 'code' | 'plan' | 'artifact' | 'error' | 'thinking';
  content: string;
  language?: string;
  artifactUrl?: string;
  artifactName?: string;
}

export interface PlanStep {
  index: number;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
}

// types/api.ts
export interface ApiResponse<T> {
  data?: T;
  error?: string;
}

export interface StreamEvent {
  type: 'thinking' | 'plan' | 'code' | 'output' | 'artifact' | 'message' | 'done';
  content?: string;
  data?: unknown;
}
```
