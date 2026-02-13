# Chat Web UI - AGENTS.md

Browser-based chat interface using FastAPI WebSocket backend and React frontend.

## Structure

```
chat/web/
├── __init__.py       # Exports chat_router
├── routes.py         # WebSocket + REST endpoints (~450 lines)
└── DESIGN.md         # Comprehensive design document
```

## Architecture

```
Browser (React)  ←── WebSocket ──→  FastAPI Backend  ←→  TaskWeaver Session
    ChatPage.tsx                    routes.py             Session.send_message()
```

Both CLI and Web interfaces share the same core:
- `TaskWeaverApp` → creates sessions
- `Session.send_message()` → orchestrates Planner + workers
- `SessionEventHandlerBase` ABC → receives events
- `ConfirmationHandler` ABC → handles code execution approval

## Key Classes

### ChatSessionManager
```python
class ChatSessionManager:
    _sessions: Dict[str, ChatSession]    # Active sessions
    _app: Optional[TaskWeaverApp]        # Lazy-initialized
    
    def create_session() -> ChatSession
    def get_session(id) -> Optional[ChatSession]
    def delete_session(id) -> bool
    def list_sessions() -> List[str]
```

### ChatSession
```python
@dataclass
class ChatSession:
    session_id: str
    tw_session: Session              # Core TaskWeaver session
    websocket: Optional[WebSocket]   # Current connection
    is_processing: bool              # Mutex for message handling
    pending_files: List[Dict]        # Files for next message
```

### WebSocketEventHandler
Implements `SessionEventHandlerBase` to forward events to WebSocket:

| TaskWeaver Event | WebSocket Type |
|------------------|----------------|
| `round_start/end` | `round_start/end` |
| `post_start/end` | `post_start/end` |
| `post_message_update` | `message_update` |
| `post_attachment_update` | `attachment_start/update` |
| `post_confirmation_request` | `confirm_request` |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat/sessions` | Create new session |
| GET | `/api/v1/chat/sessions` | List all sessions |
| DELETE | `/api/v1/chat/sessions/{id}` | Delete session |
| WS | `/api/v1/chat/ws/{id}` | WebSocket connection |
| GET | `/api/v1/chat/sessions/{id}/artifacts/{file}` | Download artifact |

## WebSocket Protocol

### Client → Server
```json
{"type": "send_message", "message": "...", "files": []}
{"type": "confirm", "approved": true}
{"type": "upload_file", "filename": "...", "content": "base64..."}
```

### Server → Client
```json
{"type": "connected", "session_id": "..."}
{"type": "round_start", "round_id": "..."}
{"type": "post_start", "post_id": "...", "role": "Planner"}
{"type": "message_update", "post_id": "...", "text": "...", "is_end": false}
{"type": "attachment_start", "attachment_id": "...", "attachment_type": "code"}
{"type": "confirm_request", "code": "...", "round_id": "..."}
{"type": "message_complete", "result": "..."}
{"type": "history_complete"}  // After replaying on reconnect
```

## History Persistence

On WebSocket reconnect, server replays full conversation from `memory.conversation.rounds`:
1. For each round: `round_start` → posts → `round_end`
2. Send `history_complete` marker
3. Frontend reconstructs UI using same event handlers

## Integration Points

- **CES Server**: `ces/server/app.py` mounts `chat_router` and sets `chat_manager.set_app_dir()`
- **Frontend**: `web/__init__.py` mounts static files and handles SPA routing
- **Artifacts**: Falls back to chat sessions if CES session not found

## Where to Look

| Task | File | Notes |
|------|------|-------|
| Add WebSocket event | `routes.py` | `WebSocketEventHandler` class |
| Add REST endpoint | `routes.py` | Use `router.post/get/delete` |
| Modify session lifecycle | `routes.py` | `ChatSessionManager` class |
| Understand protocol | `DESIGN.md` | Full documentation |

## Anti-Patterns

- **Don't** access `_sessions` directly from outside `ChatSessionManager`
- **Don't** send WebSocket messages without proper JSON structure
- **Don't** skip `is_processing` check when handling messages

## See Also

- `DESIGN.md` in this directory for comprehensive protocol documentation
- `taskweaver/web/frontend/src/pages/ChatPage.tsx` for frontend implementation
- `taskweaver/module/event_emitter.py` for `SessionEventHandlerBase` ABC
