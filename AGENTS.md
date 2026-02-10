# AGENTS.md - TaskWeaver Development Guide

**Generated:** 2026-02-06 | **Commit:** d124f160 | **Branch:** experimental

This document provides guidance for AI coding agents working on the TaskWeaver codebase.

## Subdirectory Knowledge Bases
- [`taskweaver/llm/AGENTS.md`](taskweaver/llm/AGENTS.md) - LLM provider abstractions
- [`taskweaver/ces/AGENTS.md`](taskweaver/ces/AGENTS.md) - Code execution service (Jupyter kernels)
- [`taskweaver/code_interpreter/AGENTS.md`](taskweaver/code_interpreter/AGENTS.md) - Code interpreter role variants
- [`taskweaver/memory/AGENTS.md`](taskweaver/memory/AGENTS.md) - Memory data model (Post/Round/Conversation)
- [`taskweaver/ext_role/AGENTS.md`](taskweaver/ext_role/AGENTS.md) - Extended role definitions
- [`taskweaver/planner/AGENTS.md`](taskweaver/planner/AGENTS.md) - Planner role (task decomposition)
- [`taskweaver/plugin/AGENTS.md`](taskweaver/plugin/AGENTS.md) - Plugin base classes and registry
- [`taskweaver/role/AGENTS.md`](taskweaver/role/AGENTS.md) - Role base classes and registry
- [`taskweaver/chat/web/AGENTS.md`](taskweaver/chat/web/AGENTS.md) - Chat Web UI (WebSocket + React)

## Project Overview

TaskWeaver is a **code-first agent framework** for data analytics tasks. It uses Python 3.10+ and follows a modular architecture with dependency injection (using `injector`).

## Build & Development Commands

### Installation
```bash
# Use the existing conda environment
conda activate taskweaver

# Or create a new one
conda create -n taskweaver python=3.10
conda activate taskweaver

# Install dependencies
pip install -r requirements.txt

# Install in editable mode
pip install -e .
```

**Note**: The project uses a conda environment named `taskweaver`.

### Running Tests
```bash
# Run all unit tests
pytest tests/unit_tests -v

# Run a single test file
pytest tests/unit_tests/test_plugin.py -v

# Run a specific test function
pytest tests/unit_tests/test_plugin.py::test_load_plugin_yaml -v

# Run tests with coverage
pytest tests/unit_tests -v --cov=taskweaver --cov-report=html

# Collect tests without running (useful for verification)
pytest tests/unit_tests --collect-only
```

### Linting & Formatting
```bash
# Run pre-commit hooks (autoflake, isort, black, flake8)
pre-commit run --all-files

# Run individual tools
black --config=.linters/pyproject.toml .
isort --settings-path=.linters/pyproject.toml .
flake8 --config=.linters/tox.ini taskweaver/
```

### Running the Application
```bash
# CLI mode
python -m taskweaver -p ./project/

# Start server with Web UI
python -m taskweaver -p ./project/ server --port 8000
# Then open http://localhost:8000/chat in your browser

# In another terminal, connect to running server (CLI mode)
python -m taskweaver -p ./project/ chat --server-url http://localhost:8000

# As a module
python -m taskweaver
```

## Code Style Guidelines

### Formatting Configuration
- **Line length**: 120 characters (configured in `.linters/pyproject.toml`)
- **Formatter**: Black with `--config=.linters/pyproject.toml`
- **Import sorting**: isort with `profile = "black"`

### Import Organization
```python
# Standard library imports first
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Third-party imports
from injector import inject

# Local imports (known_first_party = ["taskweaver"])
from taskweaver.config.config_mgt import AppConfigSource
from taskweaver.logging import TelemetryLogger
```

### Type Annotations
- **Required**: All function parameters and return types must have type hints
- **Use `Optional[T]`** for nullable types
- **Use `List`, `Dict`, `Tuple`** from `typing` module
- **Dataclasses** are preferred for structured data

```python
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class Post:
    id: str
    send_from: str
    send_to: str
    message: str
    attachment_list: List[Attachment]

    @staticmethod
    def create(
        message: Optional[str],
        send_from: str,
        send_to: str = "Unknown",
    ) -> Post:
        ...
```

### Naming Conventions
- **Classes**: PascalCase (`CodeGenerator`, `PluginRegistry`)
- **Functions/methods**: snake_case (`compose_prompt`, `get_attachment`)
- **Variables**: snake_case (`plugin_pool`, `chat_history`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_RETRY_COUNT`)
- **Private members**: prefix with underscore (`_configure`, `_get_config_value`)
- **Config classes**: suffix with `Config` (`PlannerConfig`, `RoleConfig`)

### Dependency Injection Pattern
TaskWeaver uses the `injector` library for DI. Follow this pattern:

```python
from injector import inject, Module, provider

class MyConfig(ModuleConfig):
    def _configure(self) -> None:
        self._set_name("my_module")
        self.some_setting = self._get_str("setting_name", "default_value")

class MyService:
    @inject
    def __init__(
        self,
        config: MyConfig,
        logger: TelemetryLogger,
        other_dependency: OtherService,
    ):
        self.config = config
        self.logger = logger
```

### Error Handling
- Use specific exception types when possible
- Log errors with context before re-raising
- Use assertions for internal invariants

```python
try:
    result = self.llm_api.chat_completion_stream(...)
except (JSONDecodeError, AssertionError) as e:
    self.logger.error(f"Failed to parse LLM output due to {str(e)}")
    self.tracing.set_span_status("ERROR", str(e))
    raise
```

### Docstrings
Use triple-quoted docstrings for classes and public methods:

```python
def get_embeddings(self, strings: List[str]) -> List[List[float]]:
    """
    Embedding API

    :param strings: list of strings to be embedded
    :return: list of embeddings
    """
```

### Trailing Commas
Always use trailing commas in multi-line structures (enforced by `add-trailing-comma`):

```python
app_injector = Injector(
    [LoggingModule, PluginModule],  # trailing comma
)

config = {
    "key1": "value1",
    "key2": "value2",  # trailing comma
}
```

## Project Structure

```
taskweaver/
├── app/              # Application entry points and session management
├── ces/              # Code execution service (see ces/AGENTS.md)
├── chat/             # Chat interfaces (console, web)
│   ├── console/      # Terminal CLI chat interface
│   └── web/          # Web UI backend (see chat/web/AGENTS.md)
├── cli/              # CLI implementation
├── code_interpreter/ # Code generation and interpretation (see code_interpreter/AGENTS.md)
├── config/           # Configuration management
├── ext_role/         # Extended roles (see ext_role/AGENTS.md)
├── llm/              # LLM integrations (see llm/AGENTS.md)
├── logging/          # Logging and telemetry
├── memory/           # Conversation memory (see memory/AGENTS.md)
├── misc/             # Utilities and component registry
├── module/           # Core modules (tracing, events)
├── planner/          # Planning logic
├── plugin/           # Plugin system
├── role/             # Role base classes
├── session/          # Session management
├── utils/            # Helper utilities
├── web/              # Web frontend (React + Vite + TypeScript)
│   ├── __init__.py   # Frontend mounting and SPA routing
│   └── frontend/     # React source and build output
└── workspace/        # Workspace management

tests/
└── unit_tests/       # Unit tests (pytest)
    ├── data/         # Test fixtures (plugins, prompts, examples)
    └── ces/          # Code execution tests
```

### Module and Role Overview (what lives where)

- **app/**: Bootstraps dependency injection; wires TaskWeaverApp, SessionManager, config binding.
- **session/**: Orchestrates Planner + worker roles, memory, workspace management, event emitter, tracing.
- **planner/**: Planner role; LLM-powered task decomposition and planning logic.
- **code_interpreter/**: Code generation and execution (full, CLI-only, plugin-only); code verification/AST checks.
- **memory/**: Conversation history, rounds, posts, attachments, experiences; RoundCompressor utilities.
- **llm/**: LLM API facades; supports OpenAI and Azure OpenAI providers; embeddings via OpenAI/Azure.
- **plugin/**: Plugin base classes and registry/context for function-style plugins.
- **role/**: Core role abstractions, RoleRegistry, PostTranslator.
- **ext_role/**: Extended roles (web_search, web_explorer, image_reader, document_retriever, recepta, echo).
- **module/**: Core modules like tracing and event_emitter wiring.
- **logging/**: TelemetryLogger and logging setup.
- **workspace/**: Session-scoped working directories and execution cwd helpers.

### Directory Separation (Main Process vs Executor)

The main process (client) and execution server maintain **separate directory structures**. This separation is critical for remote/container deployments where the client and server may run on different machines.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MAIN PROCESS (CLIENT)                              │
│                                                                             │
│   {app_base_path}/workspace/sessions/{session_id}/                          │
│   ├── {session_id}.json              # Session metadata dump                │
│   ├── {session_id}_{round_id}.json   # Round logs                           │
│   ├── planner_prompt_log_*.json      # LLM prompt logs (Planner)            │
│   └── code_generator_prompt_log_*.json  # LLM prompt logs (CodeInterpreter) │
│                                                                             │
│   Note: The Session class creates this via Workspace.get_session_dir()      │
│         This is for local logging/debugging, NOT for code execution.        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP (file upload, code execution)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXECUTION SERVER                                   │
│                                                                             │
│   {work_dir}/sessions/{session_id}/                                         │
│   ├── cwd/                           # Code execution working directory     │
│   │   ├── uploaded_file.csv          # Files uploaded via /load command     │
│   │   ├── output_chart.png           # Artifacts generated by code          │
│   │   └── ...                        # Any files created during execution   │
│   └── (other session state)                                                 │
│                                                                             │
│   Note: ServerSessionManager creates this structure.                        │
│         The cwd path is returned to client via Session.ensure_execution_ready() │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Key Classes and Their Directories

| Class | Directory Property | Source | Purpose |
|-------|-------------------|--------|---------|
| `Session` | `workspace` | `Workspace.get_session_dir()` | Client-side logs, prompt dumps |
| `Session` | `execution_cwd` | CES server response | Execution working directory (on server) |
| `ServerSession` | `session_dir` | `{work_dir}/sessions/{id}/` | Server-side session root |
| `ServerSession` | `cwd` | `{session_dir}/cwd/` | Server-side execution cwd |

#### How `execution_cwd` is Resolved

1. `Session.__init__()` initializes `execution_cwd` to `{workspace}/cwd` (local fallback)
2. When the CES session starts (`_get_upload_client().start()`), the server returns its actual cwd
3. `Session._get_upload_client()` updates `execution_cwd` with the server-assigned path
4. Use `Session.ensure_execution_ready()` to trigger CES session creation and get the actual cwd

```python
# Example: Getting the execution directory
session = app.get_session()
cwd = session.ensure_execution_ready()  # Triggers CES session creation
print(f"Code will execute in: {cwd}")
```

#### When Directories Differ

| Deployment | Client `workspace` | Server `cwd` | Same Machine? |
|------------|-------------------|--------------|---------------|
| Local subprocess | `/app/workspace/sessions/abc/` | `/app/workspace/sessions/abc/cwd/` | Yes |
| Docker container | `/local/workspace/sessions/abc/` | `/app/workspace/sessions/abc/cwd/` | No |
| Remote server | `/local/workspace/sessions/abc/` | `/var/taskweaver/sessions/abc/cwd/` | No |

This separation ensures that:
- Uploaded files are always written to the execution server's filesystem
- Artifacts are accessible via HTTP download from the server
- Client logs remain on the client machine

## Testing Patterns

### Using Fixtures
```python
import pytest
from injector import Injector

@pytest.fixture()
def app_injector(request: pytest.FixtureRequest):
    from taskweaver.config.config_mgt import AppConfigSource
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

## Flake8 Ignores
The following are intentionally ignored (see `.linters/tox.ini`):
- `E402`: Module level import not at top of file
- `W503`: Line break before binary operator
- `W504`: Line break after binary operator
- `E203`: Whitespace before ':'
- `F401`: Import not used (only in `__init__.py`)

## Key Patterns

### Creating Unique IDs
```python
from taskweaver.utils import create_id
post_id = "post-" + create_id()  # Format: post-YYYYMMDD-HHMMSS-<random>
```

### Reading/Writing YAML
```python
from taskweaver.utils import read_yaml, write_yaml
data = read_yaml("path/to/file.yaml")
write_yaml("path/to/file.yaml", data)
```

### Configuration Access
```python
class MyConfig(ModuleConfig):
    def _configure(self) -> None:
        self._set_name("my_module")
        self.enabled = self._get_bool("enabled", False)
        self.path = self._get_path("base_path", "/default/path")
        self.model = self._get_str("model", None, required=False)
```

## CI/CD
- Tests run on Python 3.11 via GitHub Actions
- Pre-commit hooks include: autoflake, isort, black, flake8, gitleaks, detect-secrets
- All PRs to `main` trigger the pytest workflow
