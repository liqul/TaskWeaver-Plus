<h1 align="center">
    <img src="./.asset/logo.color.svg" width="45" /> TaskWeaver+
</h1>

<div align="center">

![Python Version](https://img.shields.io/badge/Python-3776AB?&logo=python&logoColor=white-blue&label=3.10%20%7C%203.11)&ensp;
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)&ensp;
![Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)

</div>

TaskWeaver+ is a **code-first** agent framework for seamlessly planning and executing data analytics tasks.
This framework interprets user requests through code snippets and coordinates plugins (functions) to execute
data analytics tasks in a stateful manner. It is forked from [Microsoft TaskWeaver](https://github.com/microsoft/TaskWeaver) and independently maintained.

TaskWeaver preserves both the **chat history** and the **code execution history**, including in-memory data.
This enhances the expressiveness of the agent framework, making it ideal for processing complex data
structures like high-dimensional tabular data.

<h1 align="center">
    <img src="./.asset/taskweaver_arch.png"/>
</h1>

## Highlights

- **Planning for complex tasks** - Task decomposition and progress tracking
- **Reflective execution** - Reflect on execution and make adjustments
- **Rich data structures** - Work with Python data structures (DataFrames, etc.)
- **Customized algorithms** - Encapsulate algorithms into plugins and orchestrate them
- **Domain-specific knowledge** - Incorporate domain knowledge via experiences
- **Stateful execution** - Consistent user experience with stateful code execution
- **Code verification** - Detect potential issues before execution
- **Code execution confirmation** - User approval before running LLM-generated code
- **Separated agent and executor** - Client-server architecture with local, container, and remote deployment
- **Real-time streaming** - Live plugin output and execution results via SSE
- **Built-in Web UI** - React-based chat interface with WebSocket streaming and session management
- **Background memory compaction** - Non-blocking prompt compression in a separate thread
- **Easy to debug** - Detailed logs for LLM prompts, code generation, and execution

## Quick Start

### Installation

TaskWeaver requires **Python >= 3.10**.

```bash
conda create -n taskweaver python=3.10
conda activate taskweaver
pip install -r requirements.txt
```

### Configuration

Configure `project/taskweaver_config.json`:

```json
{
  "llm.api_type": "openai",
  "llm.api_key": "your-api-key",
  "llm.model": "gpt-4"
}
```

Supported LLM API types: `openai`, `azure`, `azure_ad`.

### Usage

TaskWeaver uses a **two-server architecture**: a CES (Code Execution Service) server manages Jupyter kernels, and a Chat/Web server handles the UI and agent logic. They can run on the same machine or on separate machines.

**Web UI (recommended):**
```bash
# Build the frontend (first time only)
cd taskweaver/web/frontend && npm install && npm run build && cd ../../..

# Terminal 1: Start the CES server
python -m taskweaver.ces.server --port 8081

# Terminal 2: Start the Chat/Web server
taskweaver -p ./project/ server --port 8082 --ces-url http://localhost:8081

# Open http://localhost:8082/chat in your browser
```

**CLI chat:**
```bash
# Terminal 1: Start the CES server
python -m taskweaver.ces.server --port 8081

# Terminal 2: Connect a CLI chat session
taskweaver -p ./project/ chat --server-url http://localhost:8081
```

**As a Library:**

Requires a running CES server (`python -m taskweaver.ces.server --port 8081`).

```python
from taskweaver.app.app import TaskWeaverApp

app = TaskWeaverApp(app_dir="./project/", config={
    "execution_service.server.url": "http://localhost:8081",
})
session = app.get_session()
response = session.send_message("Your request here")
```

## Recent Changes

### Two-Server Architecture

TaskWeaver uses two independent servers that can run on the same machine or separately:

1. **CES (Code Execution Service) server** - Manages Jupyter kernels and executes code. Each session gets its own working directory under `{work_dir}/sessions/{session_id}/cwd/`. Start with `python -m taskweaver.ces.server --port 8081`.

2. **Chat/Web server** - Serves the frontend UI, handles WebSocket chat connections, and runs the agent logic (Planner, CodeInterpreter). Communicates with the CES server over HTTP. Proxies CES API requests and artifact downloads transparently. Start with `taskweaver -p ./project/ server --port 8082 --ces-url http://localhost:8081`.

The CES server exposes a REST API (`/api/v1/sessions`, `/execute`, `/plugins`, `/files`, `/artifacts`) and supports SSE streaming for real-time execution output. File uploads use base64 encoding over HTTP, so the servers can run on different machines. The Chat/Web server checks CES connectivity at startup and will refuse to start if the CES server is not reachable.

### Code Execution Confirmation

Before executing LLM-generated code, TaskWeaver now prompts the user for approval. The `ConfirmationHandler` ABC is implemented by both the CLI (terminal prompt) and Web UI (WebSocket `confirm_request` event), allowing users to review, approve, or reject code before it runs. This can be configured via `code_interpreter.code_verification_on`.

### New Web UI

The Chainlit-based UI has been replaced with a custom **React + TypeScript** frontend (Vite, Tailwind CSS, shadcn/ui) backed by **FastAPI WebSocket** endpoints. The Web UI runs as a separate Chat/Web server that communicates with the CES server. Features include:

- Real-time streaming of agent steps (planning, code generation, execution results) via WebSocket
- Code execution confirmation dialog in the browser
- Session management (create, list, delete, reconnect with full history replay)
- File upload and artifact download with automatic CES proxy
- CES session admin panel
- Execution working directory display

Start the CES server with `python -m taskweaver.ces.server --port 8081`, then start the Chat/Web server with `taskweaver -p ./project/ server --port 8082 --ces-url http://localhost:8081` and open `http://localhost:8082/chat` in your browser.

### Memory Compaction Redesign

The synchronous `RoundCompressor` has been replaced with a **background compaction** system. Compaction runs in a separate thread, never blocking user interaction. Each agent can have its own compactor with customized prompts. A single compacted summary is maintained and updated incrementally as new rounds complete. See [docs/design/memory_compression_redesign.md](docs/design/memory_compression_redesign.md).

### Kernel Variable Surfacing

After each code execution, the kernel captures newly defined user variables (excluding modules, builtins, and internals) and surfaces them in the CodeInterpreter's prompt for subsequent turns. This prevents redundant redefinitions and enables the model to reuse prior computation results.

### Plugin Output Streaming

Plugin `print()` output and `ctx.log()` calls are now streamed back to the user in real time via SSE during execution, rather than buffered until completion.

### Simplified LLM Providers

Non-OpenAI LLM providers (Anthropic, Google GenAI, Groq, Ollama, Qwen, ZhipuAI) have been removed. The framework now supports `openai`, `azure`, and `azure_ad` API types. The Chainlit UI, Docker deployment files, and the documentation website have also been removed in favor of the new built-in Web UI and streamlined codebase.

### Auto-Eval Framework Improvements

- **Full conversation visibility for judge** - The LLM judge now sees all intermediate agent steps (code generation, execution results, function calls), not just the final summary.
- **File upload via CES API** - Test cases upload data files through the HTTP API instead of direct filesystem copy, supporting remote/container deployments.
- **Premature stop detection** - The tester detects when the Planner claims task completion prematurely and sends continuation messages to ensure all planned steps are executed.

## Documentation

Each module contains an `AGENTS.md` file with architecture and development details.

## License

MIT License - see [LICENSE](LICENSE) for details.
