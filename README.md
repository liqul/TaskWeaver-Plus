<h1 align="center">
    <img src="./.asset/logo.color.svg" width="45" /> TaskWeaver
</h1>

<div align="center">

![Python Version](https://img.shields.io/badge/Python-3776AB?&logo=python&logoColor=white-blue&label=3.10%20%7C%203.11)&ensp;
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)&ensp;
![Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)

</div>

TaskWeaver is a **code-first** agent framework for seamlessly planning and executing data analytics tasks.
This framework interprets user requests through code snippets and coordinates plugins (functions) to execute
data analytics tasks in a stateful manner.

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

**CLI:**
```bash
python -m taskweaver -p ./project/
```

**Web UI:**
```bash
# Build the frontend (first time only)
cd taskweaver/web/frontend && npm install && npm run build && cd ../../..

# Start the server
taskweaver -p ./project/ server

# Open http://localhost:8000 in your browser
```

**Code Execution Server + CLI (separate processes):**
```bash
# Terminal 1: start the execution server
taskweaver -p ./project/ server

# Terminal 2: connect a chat session
taskweaver -p ./project/ chat --server-url http://localhost:8000
```

**As a Library:**
```python
from taskweaver.app.app import TaskWeaverApp

app = TaskWeaverApp(app_dir="./project/")
session = app.get_session()
response = session.send_message("Your request here")
```

## Documentation

Each module contains an `AGENTS.md` file with architecture and development details.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
