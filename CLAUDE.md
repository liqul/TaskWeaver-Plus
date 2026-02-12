# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

### Installation
```bash
# Create/activate conda environment
conda create -n taskweaver python=3.10
conda activate taskweaver

# Install dependencies
pip install -r requirements.txt

# Install in editable mode
pip install -e .
```

### Running TaskWeaver
```bash
# CLI mode
python -m taskweaver -p ./project/

# Web UI (starts server + frontend)
python -m taskweaver -p ./project/ server --port 8000
# Open http://localhost:8000/chat

# Connect CLI to running server
python -m taskweaver -p ./project/ chat --server-url http://localhost:8000
```

### Running Tests
```bash
# Run all unit tests
pytest tests/unit_tests -v

# Run a single test file
pytest tests/unit_tests/test_plugin.py -v

# Run a specific test function
pytest tests/unit_tests/test_plugin.py::test_load_plugin_yaml -v

# Run with coverage
pytest tests/unit_tests -v --cov=taskweaver --cov-report=html
```

### Linting & Formatting
```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Individual tools
black --config=.linters/pyproject.toml .
isort --settings-path=.linters/pyproject.toml .
flake8 --config=.linters/tox.ini taskweaver/
```

## Architecture Overview

TaskWeaver is a **code-first agent framework** for data analytics tasks. It uses Python 3.10+ with dependency injection via the `injector` library.

### Core Architecture

```
User Request
    ↓
Session (orchestrator)
    ↓
Planner (LLM-powered task decomposition)
    ↓
Workers (CodeInterpreter, ext_roles)
    ↓
CodeExecutor → CES (Code Execution Service)
    ↓
Jupyter Kernel (stateful execution)
```

### Key Data Flow

1. **Session** orchestrates the conversation, maintains memory, and coordinates roles
2. **Memory** stores conversation history as Post/Round/Conversation objects
3. **Planner** decomposes tasks and routes to workers
4. **CodeInterpreter** generates Python code via LLM, executes it in CES
5. **CES** manages Jupyter kernels for stateful code execution
6. **Plugins** are loaded into the kernel as callable functions

### Critical Modules

- **app/**: Dependency injection setup, TaskWeaverApp entry point
- **session/**: Session management, role coordination, event emission
- **memory/**: Conversation state (Post/Round/Conversation/Attachment)
- **planner/**: LLM-powered task decomposition
- **code_interpreter/**: Code generation and execution (3 variants: full, cli-only, plugin-only)
- **ces/**: Code Execution Service (Jupyter kernel management with client-server architecture)
- **llm/**: LLM provider abstractions (OpenAI, Azure OpenAI)
- **plugin/**: Plugin system (class-based or function-based)
- **role/**: Base role abstractions and registry
- **chat/web/**: Web UI (FastAPI WebSocket + React frontend)

## Key Patterns

### Dependency Injection
All major components use the `injector` library:

```python
from injector import inject

class MyService:
    @inject
    def __init__(
        self,
        config: MyConfig,
        logger: TelemetryLogger,
    ):
        self.config = config
        self.logger = logger
```

### Configuration Management
Config classes inherit from `ModuleConfig`:

```python
class MyConfig(ModuleConfig):
    def _configure(self) -> None:
        self._set_name("my_module")  # Creates my_module.* namespace
        self.setting = self._get_str("setting", "default")
        self.path = self._get_path("base_path", "/default")
        self.enabled = self._get_bool("enabled", False)
```

Configuration lives in `project/taskweaver_config.json`:

```json
{
  "llm.api_type": "openai",
  "llm.api_key": "YOUR_API_KEY",
  "llm.model": "gpt-4",
  "session.roles": ["planner", "code_interpreter"]
}
```

### Memory Model
Conversation state is hierarchical:

- **Memory**: Session-level store
- **Conversation**: List of rounds
- **Round**: User query + role responses
- **Post**: Single message between roles
- **Attachment**: Typed data on posts (code, results, plans, etc.)

### Role System
Roles are registered via YAML files:

```yaml
module: taskweaver.planner.planner.Planner
alias: Planner
intro: |
  Description of capabilities
```

Workers are instantiated per session and coordinated by the Planner.

### Plugin System
Plugins are defined in `project/plugins/*.yaml`:

```yaml
name: my_plugin
enabled: true
description: Brief description for LLM
code: |
  from taskweaver.plugin import Plugin, register_plugin

  @register_plugin
  class MyPlugin(Plugin):
      def __call__(self, x: int) -> int:
          return x * 2
```

### Code Execution Service (CES)
CES provides client-server architecture for code execution:

- **Server**: FastAPI app managing Jupyter kernels (`taskweaver/ces/server/`)
- **Client**: HTTP client implementing `Client` ABC (`taskweaver/ces/client/`)
- **Manager**: Factory providing session clients (`taskweaver/ces/manager/`)

Three deployment modes:
1. Local process (server auto-starts as subprocess)
2. Local container (Docker with volume mapping)
3. Remote server (connect to pre-started instance)

Key endpoints:
- `POST /api/v1/sessions` - Create session
- `POST /api/v1/sessions/{id}/execute` - Execute code
- `GET /api/v1/sessions/{id}/stream/{exec_id}` - SSE stream
- `POST /api/v1/sessions/{id}/files` - Upload file

### Web UI Architecture
The Web UI consists of:

- **Backend**: `taskweaver/chat/web/routes.py` (WebSocket + REST)
- **Frontend**: `taskweaver/web/frontend/` (React + Vite + TypeScript)
- **Integration**: CES server mounts chat router via `app.include_router(chat_router)`

WebSocket protocol handles bidirectional streaming:
- Client sends: `send_message`, `confirm`, `upload_file`
- Server sends: `message_update`, `attachment_start`, `confirm_request`, etc.

## Code Style

### Formatting
- Line length: 120 characters
- Formatter: Black (config in `.linters/pyproject.toml`)
- Import sorting: isort with `profile = "black"`

### Type Annotations
All function parameters and return types must have type hints:

```python
from typing import Any, Dict, List, Optional

def process_data(
    input_data: List[str],
    config: Optional[Dict[str, Any]] = None,
) -> str:
    ...
```

### Naming Conventions
- Classes: PascalCase (`CodeGenerator`, `PluginRegistry`)
- Functions/methods: snake_case (`compose_prompt`, `get_attachment`)
- Constants: UPPER_SNAKE_CASE (`MAX_RETRY_COUNT`)
- Private members: prefix with underscore (`_configure`)
- Config classes: suffix with `Config` (`PlannerConfig`)

### Import Organization
```python
# Standard library
import os
from typing import Any, Dict

# Third-party
from injector import inject

# Local (known_first_party = ["taskweaver"])
from taskweaver.config.config_mgt import AppConfigSource
```

### Trailing Commas
Always use trailing commas in multi-line structures:

```python
config = {
    "key1": "value1",
    "key2": "value2",  # trailing comma required
}
```

## LLM Provider Support

TaskWeaver supports **OpenAI and Azure OpenAI only**. Other LLM providers have been removed. Configuration:

```json
{
  "llm.api_type": "openai",
  "llm.api_key": "sk-...",
  "llm.model": "gpt-4"
}
```

For Azure OpenAI:
```json
{
  "llm.api_type": "azure",
  "llm.api_key": "...",
  "llm.api_base": "https://your-resource.openai.azure.com/",
  "llm.api_version": "2024-02-01",
  "llm.model": "your-deployment-name"
}
```

## Extended Roles

TaskWeaver includes several extended roles in `taskweaver/ext_role/`:

- **web_search**: Web search capabilities
- **web_explorer**: Browser automation
- **image_reader**: Image analysis
- **document_retriever**: Document retrieval
- **recepta**: Reception/routing role
- **echo**: Simple echo role for testing

## Testing Patterns

### Fixtures with Dependency Injection
```python
import pytest
from injector import Injector

@pytest.fixture()
def app_injector(request: pytest.FixtureRequest):
    config = {"llm.api_key": "test_key"}
    app_injector = Injector([LoggingModule, PluginModule])
    app_config = AppConfigSource(config=config)
    app_injector.binder.bind(AppConfigSource, to=app_config)
    return app_injector
```

### Test Markers
```python
@pytest.mark.app_config({"custom.setting": "value"})
def test_with_custom_config(app_injector):
    ...
```

## Experience System

The experience system uses **handcrafted experiences** with **when/what structure** and **LLM-based selection**:

### Key Features
- ✅ **When/What Format**: Separate selection criteria from instructions
- ✅ **LLM Selection**: LLM evaluates "when" sections to select relevant experiences
- ✅ **Clean Injection**: Only "what" sections injected into prompts
- ❌ **No Embeddings**: No embedding generation or similarity search

### Creating Experiences
Create files in `project/experience/` with this structure:

```yaml
# handcrafted_exp_file-validation.yaml
exp_id: file-validation
when: |
  Use this experience when:
  - User requests to read/process CSV or data files
  - File path is provided in query
  - FileNotFoundError or file access errors occurred

  Triggers:
  - Keywords: "CSV", "file", "read data", "load file"
  - Error patterns: FileNotFoundError, PermissionError

what: |
  Best Practices for File Operations:
  1. Always check if file exists:
     ```python
     if os.path.exists(file_path):
         data = pd.read_csv(file_path)
     ```

  2. Handle errors with clear messages

  Common Mistakes:
  - Don't assume files exist without checking
  - Don't ignore FileNotFoundError
```

### How It Works
1. **Selection**: LLM reads all "when" sections and selects relevant experience IDs
2. **Injection**: Only "what" sections of selected experiences are injected into prompts
3. **Efficient**: Separates selection criteria from detailed instructions

### Configuration
```json
{
  "planner.use_experience": true,
  "planner.experience_dir": "./project/experience"
}
```

See `taskweaver/memory/AGENTS.md` for details.

## Important Notes

### Agent Documentation
Each major subdirectory has its own `AGENTS.md` file with detailed component documentation:
- `taskweaver/llm/AGENTS.md` - LLM provider layer
- `taskweaver/ces/AGENTS.md` - Code execution service
- `taskweaver/code_interpreter/AGENTS.md` - Code interpreter variants
- `taskweaver/memory/AGENTS.md` - Memory data model
- `taskweaver/planner/AGENTS.md` - Planner role
- `taskweaver/plugin/AGENTS.md` - Plugin system
- `taskweaver/chat/web/AGENTS.md` - Web UI

**Always consult the relevant AGENTS.md when working in a subdirectory.**

### Common Gotchas
- CodeInterpreter has 3 variants (full, cli-only, plugin-only) - make sure you're editing the right one
- CES server can auto-start, run in container, or connect to remote - check config
- Memory model uses dataclasses with `to_dict()`/`from_dict()` for serialization
- Attachment types are strongly typed via `AttachmentType` enum
- Plugin loading happens in CES kernel via IPython magic commands
- Web UI WebSocket connections replay full history on reconnect

### File Upload Flow
When execution server runs remotely or in container, use the file upload API:
1. Session exposes `_upload_file(name, path=None, content=None)`
2. Client encodes file as base64 and POSTs to `/api/v1/sessions/{id}/files`
3. Server sanitizes filename, decodes, writes to session's cwd
4. Uploaded files are then accessible in code execution

### Frontend Development
The React frontend is in `taskweaver/web/frontend/`:
- Built with Vite + TypeScript + Tailwind CSS
- Uses shadcn/ui component library
- Build output served by FastAPI at `/chat` route
- WebSocket connection handles real-time streaming

To rebuild frontend:
```bash
cd taskweaver/web/frontend
npm install
npm run build
```

### Flake8 Ignores
Intentionally ignored (see `.linters/tox.ini`):
- E402: Module level import not at top of file
- W503/W504: Line break before/after binary operator
- E203: Whitespace before ':'
- F401: Import not used (only in `__init__.py`)

### Pre-commit Hooks
Hooks run automatically on commit:
- autoflake (remove unused imports/variables)
- isort (sort imports)
- black (format code)
- flake8 (lint)
- gitleaks (detect secrets)
- detect-secrets (scan for credentials)
