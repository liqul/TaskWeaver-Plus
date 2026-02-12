# Planner Role - AGENTS.md

LLM-powered task decomposition and planning. Orchestrates worker roles.

## Structure

```
planner/
├── __init__.py
├── planner.py              # Planner role (~500 lines)
├── planner_prompt.yaml     # Prompt templates
└── compaction_prompt.yaml  # Context compression prompts
```

## Key Classes

### PlannerConfig (extends RoleConfig)
```python
class PlannerConfig(RoleConfig):
    prompt_file_path: str       # planner_prompt.yaml location
    prompt_compression: bool    # Enable context compaction (default: False)
    compaction_threshold: int   # Rounds before compaction (default: 10)
    compaction_retain_recent: int  # Keep N recent rounds (default: 3)
    llm_alias: str              # LLM model alias (optional)
```

### Planner (extends Role)
```python
class Planner(Role):
    workers: Dict[str, Role]         # Available worker roles
    planner_post_translator: PostTranslator
    compactor: Optional[ContextCompactor]
```

## Core Methods

| Method | Purpose |
|--------|---------|
| `compose_sys_prompt(context)` | Build system prompt with worker descriptions |
| `compose_conversation_for_prompt()` | Format conversation history for LLM |
| `reply(memory)` | Main entry: decompose task, route to workers |
| `_process_llm_response()` | Parse JSON response, extract plan/send_to |

## LLM Response Schema

```json
{
  "response": {
    "thought": "...",
    "message": "...",
    "send_to": "CodeInterpreter | User | Worker..."
  }
}
```

## Attachment Types Used

| Type | Purpose |
|------|---------|
| `plan` | Task decomposition plan |
| `current_plan_step` | Active step being executed |
| `plan_reasoning` | Planner's reasoning |
| `stop` | Conversation termination signal |

## Context Compaction

When `prompt_compression=true`:
1. After `compaction_threshold` rounds, summarize old context
2. Retain `compaction_retain_recent` most recent rounds in full
3. Uses separate LLM call via `ContextCompactor`

## Extension Points

- Override `compose_sys_prompt()` for custom instructions
- Modify `planner_prompt.yaml` for different planning styles
- Add workers via session config: `session.roles`
