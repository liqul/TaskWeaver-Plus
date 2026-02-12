# Role Module - AGENTS.md

Core role abstractions, registry, and message translation.

## Structure

```
role/
├── __init__.py       # Exports: Role, RoleConfig, RoleEntry, PostTranslator, RoleRegistry
├── role.py           # Role ABC, RoleConfig, RoleEntry, RoleRegistry (~350 lines)
└── translator.py     # PostTranslator - LLM output parsing (~400 lines)
```

## Key Classes

### RoleEntry (dataclass)

```python
@dataclass
class RoleEntry:
    name: str      # Directory name (e.g., "code_interpreter")
    alias: str     # Display name (e.g., "CodeInterpreter")
    module: type   # The Role subclass
    intro: str     # Capability description for prompts
    
    @staticmethod
    def from_yaml_file(file_path: str) -> RoleEntry
```

### RoleConfig (extends ModuleConfig)

```python
class RoleConfig(ModuleConfig):
    # Auto-set from parent directory name
    name: str
    
    # Experience settings
    use_experience: bool = False
    experience_dir: str
    dynamic_experience_sub_path: bool = False
    
    # Example settings  
    use_example: bool = True
    example_base_path: str
    dynamic_example_sub_path: bool = False
```

### Role (ABC)

```python
class Role:
    def __init__(
        self,
        config: RoleConfig,
        logger: TelemetryLogger,
        tracing: Tracing,
        event_emitter: SessionEventEmitter,
        role_entry: Optional[RoleEntry] = None,
    ):
        self.alias: str
        self.intro: str
        self.experiences: List[Experience]
        self.examples: List[Conversation]
    
    def reply(self, memory: Memory, **kwargs) -> Post:
        """Must be implemented by subclasses"""
        raise NotImplementedError()
    
    def get_intro(self) -> str
    def role_load_experience(query, memory) -> None
    def role_load_example(memory) -> None
```

### PostTranslator

Parses streaming LLM output into structured Post objects.

```python
class PostTranslator:
    def raw_text_to_post(
        llm_output: Iterable[ChatMessageType],
        post_proxy: PostEventProxy,
        early_stop: Optional[Callable],
        validation_func: Optional[Callable],
        use_v2_parser: bool = True,
    ) -> None
    
    def parse_llm_output_stream_v2(stream) -> Iterator[Tuple[str, str, bool]]
```

## RoleRegistry

Discovers roles from YAML files. Caches with 5-minute TTL.

Scan locations:
- `taskweaver/ext_role/*/*.role.yaml`
- `taskweaver/code_interpreter/*/*.role.yaml`

```python
class RoleRegistry:
    def get_role_list() -> List[RoleEntry]
    def get_role(name: str) -> Optional[RoleEntry]
```

## Role YAML Schema

```yaml
module: taskweaver.{path}.{ClassName}
alias: DisplayName
intro: |
  - Capability line 1
  - Capability line 2
```

## Naming Convention

**CRITICAL**: Directory name = role name = config namespace = YAML filename

```
taskweaver/ext_role/my_role/
├── my_role.py              # Contains MyRole class
├── my_role.role.yaml       # module: ...my_role.my_role.MyRole
└── __init__.py
```

## Creating a Custom Role

1. Create `taskweaver/ext_role/{name}/{name}.py`:
```python
class {Name}Config(RoleConfig):
    def _configure(self):
        self.custom_setting = self._get_str("setting", "default")

class {Name}(Role):
    @inject
    def __init__(self, config: {Name}Config, ...):
        super().__init__(config, ...)
    
    def reply(self, memory: Memory, **kwargs) -> Post:
        post_proxy = self.event_emitter.create_post_proxy(self.alias)
        # ... generate response
        return post_proxy.end()
```

2. Create `{name}.role.yaml` with module path, alias, intro

3. Enable in config: `"session.roles": ["planner", "code_interpreter", "{name}"]`
