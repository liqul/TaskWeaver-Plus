# Memory Module - AGENTS.md

Conversation history data model: Post, Round, Conversation, Attachment.

## Structure

```
memory/
├── memory.py         # Memory class - session conversation store
├── conversation.py   # Conversation - list of Rounds
├── round.py          # Round - single user query + responses
├── post.py           # Post - single message between roles
├── attachment.py     # Attachment - typed data on Posts
├── type_vars.py      # Type aliases (RoleName, etc.)
├── experience.py     # Experience system (handcrafted, LLM-selected)
├── experience_selection_prompt.yaml  # LLM prompt template for selection
├── compaction.py     # Background context compaction (ContextCompactor)
├── plugin.py         # PluginModule for DI
├── shared_memory_entry.py  # SharedMemoryEntry for cross-role data
└── utils.py          # Utility functions
```

## Data Model Hierarchy

```
Memory
└── Conversation
    └── Round[]
        ├── user_query: str
        ├── state: "created" | "finished" | "failed"
        └── Post[]
            ├── send_from: str (role name)
            ├── send_to: str (role name)
            ├── message: str
            └── Attachment[]
                ├── type: AttachmentType
                ├── content: str
                └── extra: Any
```

## Key Classes

### Post (post.py)
```python
@dataclass
class Post:
    id: str
    send_from: str
    send_to: str
    message: str
    attachment_list: List[Attachment]

    @staticmethod
    def create(message: str, send_from: str, send_to: str) -> Post
```

### AttachmentType (attachment.py)
```python
class AttachmentType(Enum):
    # Planner
    plan = "plan"
    current_plan_step = "current_plan_step"
    plan_reasoning = "plan_reasoning"
    stop = "stop"

    # CodeInterpreter - code generation
    thought = "thought"
    reply_type = "reply_type"
    reply_content = "reply_content"
    verification = "verification"

    # CodeInterpreter - execution
    code_error = "code_error"
    execution_status = "execution_status"
    execution_result = "execution_result"
    artifact_paths = "artifact_paths"
    revise_message = "revise_message"

    # Function calling
    function = "function"

    # WebExplorer
    web_exploring_plan = "web_exploring_plan"
    web_exploring_screenshot = "web_exploring_screenshot"
    web_exploring_link = "web_exploring_link"

    # Shared state
    session_variables = "session_variables"
    shared_memory_entry = "shared_memory_entry"

    # Misc
    invalid_response = "invalid_response"
    text = "text"
    image_url = "image_url"
```

### Backward Compatibility
`Attachment.from_dict()` returns `None` for removed types (e.g., `init_plan`).
`Post.from_dict()` filters out `None` attachments when loading old data.

### SharedMemoryEntry (shared_memory_entry.py)
Cross-role communication:
```python
@dataclass
class SharedMemoryEntry:
    type: str           # "plan", "experience_sub_path", etc.
    scope: str          # "round" or "conversation"
    content: str
```

## Memory Patterns

### Role-specific Round Filtering
```python
# Get rounds relevant to a specific role
rounds = memory.get_role_rounds(role="Planner", include_failure_rounds=False)
```

### Shared Memory Queries
```python
# Get shared entries by type
entries = memory.get_shared_memory_entries(entry_type="plan")
```

## Serialization

All dataclasses support `to_dict()` and `from_dict()` for YAML/JSON persistence.

## Experience System

Only handcrafted experiences are supported. Files are loaded from the experience directory, LLM selects relevant ones, and selected instructions are injected into role prompts.

### Experience Dataclass
```python
@dataclass
class Experience:
    exp_id: str        # Unique ID (must match in yaml file)
    who: List[str]     # Target roles (empty = all roles)
    when: str          # Selection criteria (shown to LLM)
    what: str          # Instructions (injected into prompts)
```

Backward compat: `from_dict()` handles legacy `experience_text` field by copying it to both `when` and `what`.

### Experience File Format

Files in `project/experience/` named `handcrafted_exp_{anything}.yaml`:
```yaml
exp_id: file-validation
who:
  - CodeInterpreter
when: |
  Use when user requests file operations or FileNotFoundError occurred.
what: |
  Always check os.path.exists() before reading files.
```

### Selection Flow

1. `role_load_experience()` in `role.py` orchestrates the full flow
2. `ExperienceGenerator.load_experience()` reads all `handcrafted_exp_*.yaml` files, deduplicates by `exp_id`
3. `retrieve_experience(query, role, context, prompt_log_path)` does:
   - Filter candidates by `who` field (role targeting)
   - Format only `when` sections into the selection prompt template
   - Build conversation context from `memory.get_role_rounds(alias)`
   - Send to LLM, parse JSON object response (`{"id": true/false}`)
   - Return matched Experience objects
4. `format_experience_in_prompt()` injects only `what` sections of selected experiences

### Prompt Logging

Selection prompts are dumped to the session directory alongside main prompts:
- Main: `planner_prompt_log_{round}_{post}.json`
- Experience: `planner_experience_selection_log_{round}_{post}.json`

Uses `logger.dump_prompt_file(messages, path)`.

### Configuration

```json
{
  "planner.use_experience": true,
  "code_generator.use_experience": true,
  "experience.selection_prompt_path": "path/to/custom/prompt.yaml",
  "experience.llm_alias": ""
}
```

The selection prompt template (`experience_selection_prompt.yaml`) uses `{experiences}`, `{user_query}`, `{context}` placeholders. Literal braces in the template must be doubled (`{{`/`}}`) for `str.format()`.

### LLM Response Format

Because `llm.response_format` may be `json_object`, the prompt asks for and the parser handles:
```json
{"exp-1": true, "exp-2": false}
```
Also handles JSON arrays `["exp-1"]` and regex fallback for plain text.
