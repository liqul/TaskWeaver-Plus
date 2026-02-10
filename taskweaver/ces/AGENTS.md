# Code Execution Service (CES) - AGENTS.md

Jupyter kernel-based code execution with server architecture supporting local, container, and remote deployment modes.

## Structure

```
ces/
├── __init__.py           # Factory: code_execution_service_factory()
├── common.py             # Client/Manager ABCs, ExecutionResult, ExecutionArtifact
├── environment.py        # Environment class - kernel management (~700 lines)
│
├── server/               # HTTP server package (FastAPI)
│   ├── __init__.py       # Exports
│   ├── models.py         # Pydantic request/response models
│   ├── session_manager.py # ServerSessionManager - wraps Environment
│   ├── routes.py         # API route handlers with SSE streaming
│   ├── app.py            # FastAPI application factory
│   └── __main__.py       # CLI: python -m taskweaver.ces.server
│
├── client/               # HTTP client package
│   ├── __init__.py       # Exports
│   ├── execution_client.py # ExecutionClient - implements Client ABC
│   └── server_launcher.py  # Auto-start server subprocess/container
│
├── manager/              # Manager implementations
│   ├── __init__.py       # Exports
│   ├── sub_proc.py       # SubProcessManager (used internally by server)
│   └── execution_service.py # ExecutionServiceProvider
│
├── kernel/               # Custom Jupyter kernel implementation
│   └── ext.py            # IPython magic commands for TaskWeaver
│
└── runtime/              # Runtime support files
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TASKWEAVER CLIENT                                  │
│                                                                             │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────────────┐  │
│  │ CodeInterpreter │───▶│   CodeExecutor   │───▶│ExecutionServiceProv. │  │
│  └─────────────────┘    └──────────────────┘    └───────────┬───────────┘  │
│                                                             │               │
│                                                             ▼               │
│                                                ┌───────────────────┐        │
│                                                │ ExecutionClient   │        │
│                                                │ (HTTP)            │        │
│                                                └─────────┬─────────┘        │
└──────────────────────────────────────────────────────────┼──────────────────┘
                                                           │
                                                           │ HTTP (localhost:8000 or remote)
                                                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXECUTION SERVER                                   │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                       FastAPI Application                             │  │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌─────────────────┐     │  │
│  │  │ /sessions │  │ /plugins  │  │ /execute  │  │ /artifacts      │     │  │
│  │  └───────────┘  └───────────┘  └───────────┘  └─────────────────┘     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    ServerSessionManager                               │  │
│  │   sessions: Dict[session_id, ServerSession]                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                   Environment (EnvMode.Local)                         │  │
│  │   - Jupyter kernel management via MultiKernelManager                  │  │
│  │   - Plugin loading via magic commands                                 │  │
│  │   - Code execution and output capture                                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Classes

### ABCs (common.py)

```python
class Client(ABC):
    """Interface for execution clients."""
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def load_plugin(self, name: str, code: str, config: Dict) -> None: ...
    def execute_code(self, exec_id: str, code: str, on_output: Callable = None) -> ExecutionResult: ...

class Manager(ABC):
    """Interface for execution managers."""
    def initialize(self) -> None: ...
    def clean_up(self) -> None: ...
    def get_session_client(self, session_id: str, ...) -> Client: ...
    def get_kernel_mode(self) -> KernelModeType: ...
```

### ExecutionResult (common.py)

```python
@dataclass
class ExecutionResult:
    execution_id: str
    code: str
    is_success: bool = False
    error: Optional[str] = None
    output: Union[str, List[Tuple[str, str]]] = ""
    stdout: List[str] = field(default_factory=list)
    stderr: List[str] = field(default_factory=list)
    log: List[Tuple[str, str, str]] = field(default_factory=list)
    artifact: List[ExecutionArtifact] = field(default_factory=list)
    variables: List[Tuple[str, str]] = field(default_factory=list)
```

### Server-Side Classes

| Class | File | Purpose |
|-------|------|---------|
| `ServerSessionManager` | `server/session_manager.py` | Manages multiple sessions, wraps Environment |
| `ServerSession` | `server/session_manager.py` | Per-session state (environment, plugins, stats) |
| Pydantic Models | `server/models.py` | Request/response models for HTTP API |

### Client-Side Classes

| Class | File | Purpose |
|-------|------|---------|
| `ExecutionClient` | `client/execution_client.py` | HTTP client implementing Client ABC |
| `ServerLauncher` | `client/server_launcher.py` | Auto-start server as subprocess/container |
| `ExecutionServiceProvider` | `manager/execution_service.py` | Manager implementation using HTTP client |
| `ExecutionServiceClient` | `manager/execution_service.py` | Client wrapper for Provider |

## Deployment Modes

### 1. Local Process (Default)
```
TaskWeaver ──HTTP──▶ Server (subprocess) ──▶ Jupyter Kernel
                     localhost:8000
```

Server auto-starts when needed. Full filesystem access.

### 2. Local Container
```
TaskWeaver ──HTTP──▶ Docker Container ──▶ Jupyter Kernel
                     localhost:8000
```

Isolated filesystem. Volumes mapped for workspace.

### 3. Remote Server
```
TaskWeaver ──HTTP──▶ Remote Machine ──▶ Jupyter Kernel
                     remote:8000
```

Connect to pre-started server. API key required.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/sessions` | List all active sessions |
| POST | `/api/v1/sessions` | Create session (auto-generates ID if not provided) |
| DELETE | `/api/v1/sessions/{id}` | Stop session |
| GET | `/api/v1/sessions/{id}` | Get session info |
| POST | `/api/v1/sessions/{id}/plugins` | Load plugin |
| POST | `/api/v1/sessions/{id}/execute` | Execute code |
| GET | `/api/v1/sessions/{id}/stream/{exec_id}` | SSE stream |
| POST | `/api/v1/sessions/{id}/variables` | Update variables |
| POST | `/api/v1/sessions/{id}/files` | Upload file to session cwd |
| GET | `/api/v1/sessions/{id}/artifacts/{file}` | Download artifact (falls back to chat sessions) |

## Usage

### CLI Integration

The Code Execution Service can be started as a standalone server via the TaskWeaver CLI. This is the recommended way to run CES for remote or containerized deployments. The implementation resides in `taskweaver/cli/server.py`.

```bash
# Start CES server via CLI
python -m taskweaver -p ./project server \
    --host 0.0.0.0 \
    --port 8000 \
    --api-key "secret" \
    --log-level info \
    --reload
```

The server command wraps `taskweaver.ces.server.app:app` and runs it using `uvicorn`. Note that when using `--server-url` with the `chat` command, `server_auto_start` is automatically disabled to connect to the existing instance.

### Starting the Server Manually

```bash
# Basic
python -m taskweaver.ces.server

# With options
python -m taskweaver.ces.server \
    --host 0.0.0.0 \
    --port 8000 \
    --work-dir /var/taskweaver \
    --api-key "secret"
```

### Using the Factory

```python
from taskweaver.ces import code_execution_service_factory

# Default: local server with auto-start
manager = code_execution_service_factory(env_dir="/tmp/work")

# Containerized server
manager = code_execution_service_factory(
    env_dir="/tmp/work",
    server_container=True,
)

# Remote server
manager = code_execution_service_factory(
    env_dir="/tmp/work",
    server_url="http://remote:8000",
    server_api_key="secret",
    server_auto_start=False,
)
```

### Using the Client Directly

```python
from taskweaver.ces.client import ExecutionClient

with ExecutionClient(
    session_id="my-session",
    server_url="http://localhost:8000",
) as client:
    client.start()
    client.load_plugin("my_plugin", plugin_code, {"key": "value"})
    result = client.execute_code("exec-1", "print('Hello')")
    print(result.stdout)  # ['Hello\n']
    client.stop()
```

## Execution Flow

1. **Session Creation**: `POST /sessions` → ServerSessionManager creates Environment
2. **Plugin Loading**: `POST /sessions/{id}/plugins` → Environment.load_plugin()
3. **Code Execution**: `POST /sessions/{id}/execute` → Environment.execute_code()
4. **Streaming**: SSE events for stdout/stderr during execution
5. **Session Cleanup**: `DELETE /sessions/{id}` → Environment.stop_session()

## File Upload Flow

File upload enables the `/load` CLI command to transfer files from the client machine to the execution server's working directory. This is essential when the execution server runs in a container or on a remote machine where the client's local filesystem is not accessible.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TASKWEAVER CLIENT                                  │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌───────────────────────────────┐   │
│  │   Session   │───▶│ _upload_file│───▶│ ExecutionServiceClient        │   │
│  │  /load cmd  │    │   (lazy)    │    │   .upload_file()              │   │
│  └─────────────┘    └─────────────┘    └───────────────┬───────────────┘   │
│                                                        │                    │
│                                                        ▼                    │
│                                        ┌───────────────────────────────┐   │
│                                        │ ExecutionClient.upload_file() │   │
│                                        │  - Read file content          │   │
│                                        │  - Base64 encode              │   │
│                                        │  - HTTP POST                  │   │
│                                        └───────────────┬───────────────┘   │
└────────────────────────────────────────────────────────┼────────────────────┘
                                                         │
                                                         │ POST /api/v1/sessions/{id}/files
                                                         │ {filename, content (base64), encoding}
                                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXECUTION SERVER                                   │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    routes.upload_file()                               │  │
│  │  - Validate session exists                                            │  │
│  │  - Base64 decode content                                              │  │
│  │  - Call session_manager.upload_file()                                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │              ServerSessionManager.upload_file()                       │  │
│  │  - Sanitize filename (prevent path traversal)                         │  │
│  │  - Write to {session.cwd}/{filename}                                  │  │
│  │  - Return full path                                                   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Session Working Directory                          │  │
│  │                    /workspace/{session_id}/cwd/                       │  │
│  │                         └── uploaded_file.csv                         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Request/Response Models

```python
# Request (server/models.py)
class UploadFileRequest(BaseModel):
    filename: str       # Target filename (basename extracted, path traversal prevented)
    content: str        # File content (base64 encoded for binary)
    encoding: Literal["base64", "text"] = "base64"

# Response (server/models.py)
class UploadFileResponse(BaseModel):
    filename: str       # Uploaded filename
    status: Literal["uploaded"] = "uploaded"
    path: str           # Full path where file was saved on server
```

### Client Usage

```python
from taskweaver.ces.client import ExecutionClient

with ExecutionClient(session_id="my-session", server_url="http://localhost:8000") as client:
    client.start()
    
    # Upload a file
    with open("/local/path/data.csv", "rb") as f:
        content = f.read()
    saved_path = client.upload_file("data.csv", content)
    
    # Now the file is available in the session's cwd
    result = client.execute_code("exec-1", "import pandas as pd; df = pd.read_csv('data.csv')")
```

### Session Integration

The `Session` class uses a lazily-initialized upload client:

```python
# In taskweaver/session/session.py
class Session:
    def _get_upload_client(self):
        """Lazy client creation - only created when first upload occurs."""
        if not hasattr(self, "_upload_client"):
            self._upload_client = self.exec_mgr.get_session_client(
                self.session_id,
                session_dir=self.workspace,
                cwd=self.execution_cwd,
            )
            self._upload_client_started = False
        
        if not self._upload_client_started:
            self._upload_client.start()
            self._upload_client_started = True
        
        return self._upload_client

    def _upload_file(self, name: str, path: str = None, content: bytes = None) -> str:
        """Upload file to execution server."""
        target_name = os.path.basename(name)
        
        if path is not None:
            with open(path, "rb") as f:
                file_content = f.read()
        elif content is not None:
            file_content = content
        else:
            raise ValueError("path or content must be provided")
        
        client = self._get_upload_client()
        client.upload_file(target_name, file_content)
        return target_name
```

### Security Considerations

1. **Path Traversal Prevention**: Server sanitizes filename using `os.path.basename()` to prevent `../../etc/passwd` attacks
2. **Session Isolation**: Files are written only to the session's own cwd directory
3. **API Key Authentication**: Upload endpoint respects the same API key auth as other endpoints
4. **Size Limits**: Large files should be chunked or streamed (not yet implemented)

## Custom Kernel Magics (kernel/ext.py)

```python
%_taskweaver_session_init {session_id}
%_taskweaver_plugin_register {name}
%_taskweaver_plugin_load {name}
%_taskweaver_exec_pre_check {index} {exec_id}
%_taskweaver_exec_post_check {index} {exec_id}
%%_taskweaver_update_session_var
```

## Error Handling

| HTTP Status | Meaning |
|-------------|---------|
| 200 | Success (execution errors in response body) |
| 201 | Session created |
| 400 | Bad request (plugin load failed, invalid request) |
| 401 | Unauthorized (invalid API key) |
| 404 | Session/artifact not found |
| 409 | Session already exists |
| 500 | Internal server error |

## Testing

Unit tests in `tests/unit_tests/ces/`:

| File | Coverage |
|------|----------|
| `test_server_models.py` | Pydantic models, utility functions |
| `test_session_manager.py` | ServerSessionManager (mocked Environment) |
| `test_execution_client.py` | ExecutionClient (mocked HTTP) |
| `test_server_launcher.py` | ServerLauncher (mocked subprocess/docker) |
| `test_execution_service.py` | ExecutionServiceProvider |

**TODO**: Add tests for file upload functionality:
- `ExecutionClient.upload_file()` - mock HTTP POST, verify base64 encoding
- `ServerSessionManager.upload_file()` - verify file written, path traversal blocked
- `routes.upload_file()` - integration test with mocked session manager

Run tests:
```bash
pytest tests/unit_tests/ces/ -v
```

## Configuration

Configuration options (in `taskweaver_config.json`):

```json
{
  "execution.server.url": "http://localhost:8000",
  "execution.server.api_key": "",
  "execution.server.auto_start": true,
  "execution.server.container": false,
  "execution.server.container_image": "taskweavercontainers/taskweaver-executor:latest",
  "execution.server.timeout": 300
}
```

## Container Mode Details

When `server_container=true`:
- Image: `taskweavercontainers/taskweaver-executor:latest`
- Port mapping: `8000/tcp` → host port
- Volume: `{env_dir}` → `/app/workspace`
- Server runs inside container with local kernel

## Directory Separation (Client vs Server)

The main process (client) and execution server maintain **separate directory structures**. This is critical for remote/container deployments.

### Client-Side (Session class)

```python
# In taskweaver/session/session.py
self.workspace = workspace.get_session_dir(self.session_id)  # For logs, prompts
self.execution_cwd = os.path.join(self.workspace, "cwd")     # Initial value (local fallback)

# After CES session starts:
self.execution_cwd = self._upload_client.get_cwd()  # Updated from server response
```

The `workspace` directory stores:
- `{session_id}.json` - Session metadata
- `{session_id}_{round_id}.json` - Round logs
- `planner_prompt_log_*.json` - LLM prompt logs
- `code_generator_prompt_log_*.json` - Code generator prompt logs

### Server-Side (ServerSessionManager)

```python
# In taskweaver/ces/server/session_manager.py
session_dir = os.path.join(self.work_dir, "sessions", session_id)
cwd = os.path.join(session_dir, "cwd")
```

The server `cwd` directory is where:
- Uploaded files are written
- Code is executed
- Artifacts (charts, images) are saved
- Files can be downloaded via HTTP

### Directory Resolution Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│  1. Session.__init__()                                                   │
│     └── execution_cwd = {workspace}/cwd (local fallback)                 │
│                                                                          │
│  2. Session._get_upload_client() [lazy, on first file upload]            │
│     └── Calls ExecutionClient.start()                                    │
│         └── POST /api/v1/sessions → returns {cwd: "/server/path/cwd"}    │
│                                                                          │
│  3. Session updates execution_cwd from server response                   │
│     └── execution_cwd = client.get_cwd()                                 │
│                                                                          │
│  4. All file uploads go to server's cwd via HTTP                         │
│     └── POST /api/v1/sessions/{id}/files                                 │
└──────────────────────────────────────────────────────────────────────────┘
```

### Key Insight

- **Local deployment**: Client and server may share the same `workspace/cwd` path
- **Remote/container**: Paths are completely different (client: `/local/...`, server: `/container/...`)
- **File access**: Client cannot directly read server's `cwd`; must use HTTP artifact download

## Web UI Integration

The CES server integrates with the Chat Web UI when started via CLI:

### Mounting the Chat Router

In `server/app.py`, the FastAPI application mounts the chat router:
```python
from taskweaver.chat.web import chat_router, chat_manager

app.include_router(chat_router)
chat_manager.set_app_dir(app_dir)  # Configure TaskWeaver project path
```

### Artifact Fallback

The artifact download endpoint (`GET /sessions/{id}/artifacts/{file}`) falls back to chat sessions when a CES session is not found:

```python
# In routes.py download_artifact()
if session_manager.session_exists(session_id):
    artifact_path = session_manager.get_artifact_path(session_id, file_name)
else:
    # Fallback: check chat sessions for artifacts
    from taskweaver.chat.web.routes import chat_manager
    chat_session = chat_manager.get_session(session_id)
    if chat_session:
        artifact_path = chat_session.get_artifact_path(file_name)
```

This enables the Web UI to download artifacts generated during chat sessions, even when those sessions are managed by the chat layer rather than directly by CES.

### Session Listing

The `GET /api/v1/sessions` endpoint returns all active CES sessions:
```python
@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(...) -> SessionListResponse:
    """List all active sessions with metadata."""
    sessions = session_manager.list_sessions()
    return SessionListResponse(sessions=sessions)
```

See also: [`taskweaver/chat/web/AGENTS.md`](../chat/web/AGENTS.md) for chat-specific documentation.
