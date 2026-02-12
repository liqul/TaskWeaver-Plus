# Plugin Module - AGENTS.md

Plugin base classes, registration, and execution context.

## Structure

```
plugin/
├── __init__.py             # Exports: Plugin, register_plugin, PluginRegistry
├── base.py                 # Plugin ABC (~44 lines)
├── context.py              # PluginContext ABC, TestPluginContext (~214 lines)
├── register.py             # register_plugin decorator (~70 lines)
├── utils.py                # Plugin loading utilities
└── *.schema.json           # JSON schemas for plugin YAML
```

## Key Classes

### Plugin (ABC in base.py)

```python
class Plugin(ABC):
    def __init__(self, name: str, ctx: PluginContext, config: Dict[str, Any]):
        self.name = name
        self.ctx = ctx       # Execution context
        self.config = config # From plugin YAML
    
    @abstractmethod
    def __call__(self, *args, **kwargs) -> Any:
        """Entry point for plugin execution"""
    
    def log(self, level: LogErrorLevel, message: str) -> None
    def get_env(self, variable_name: str) -> str
```

### PluginContext (ABC in context.py)

```python
class PluginContext(ABC):
    @property
    def env_id(self) -> str: ...
    @property
    def session_id(self) -> str: ...
    @property
    def execution_id(self) -> str: ...
    
    def add_artifact(name, file_name, type, val, desc) -> str
    def create_artifact_path(name, file_name, type, desc) -> Tuple[str, str]
    def get_session_var(variable_name, default) -> Optional[str]
    def log(level, tag, message) -> None
    def get_env(plugin_name, variable_name) -> str
```

### ArtifactType

```python
ArtifactType = Literal["chart", "image", "df", "file", "txt", "svg", "html"]
```

## Plugin Registration

### Class-based Plugin
```python
from taskweaver.plugin import Plugin, register_plugin

@register_plugin
class MyPlugin(Plugin):
    def __call__(self, input_data: str) -> str:
        self.log("info", f"Processing: {input_data}")
        return f"Result: {input_data}"
```

### Function-based Plugin
```python
from taskweaver.plugin import register_plugin

@register_plugin
def my_simple_plugin(x: int, y: int) -> int:
    return x + y
```

## Plugin YAML Schema

Located in `project/plugins/{plugin_name}.yaml`:

```yaml
name: my_plugin
enabled: true
plugin_only: false  # If true, only callable via plugin system
description: |
  Brief description for LLM
code: |  # Optional inline code
  from taskweaver.plugin import Plugin, register_plugin
  
  @register_plugin
  class MyPlugin(Plugin):
      def __call__(self, x: int) -> int:
          return x * 2
configurations:
  key: value
```

## Testing Plugins

```python
from taskweaver.plugin.context import temp_context

with temp_context() as ctx:
    plugin = MyPlugin("test", ctx, {"key": "value"})
    result = plugin("input")
```

## Plugin Loading Flow

1. `PluginRegistry` scans `plugin.base_path` for `*.yaml` files
2. YAML parsed, code loaded (inline or from `.py` file)
3. `register_plugin_inner` callback stores plugin class
4. CodeExecutor loads plugins into Jupyter kernel via magic commands
