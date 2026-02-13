# LLM Module - AGENTS.md

Provider abstraction layer for LLM and embedding services. Supports OpenAI and Azure OpenAI APIs.

## Structure

```
llm/
├── base.py           # Abstract base: CompletionService, EmbeddingService, LLMModuleConfig
├── util.py           # ChatMessageType, format_chat_message, token counting
├── openai.py         # OpenAI/Azure OpenAI provider (~430 lines)
├── mock.py           # Mock provider for testing
├── placeholder.py    # Placeholder when no embedding configured
└── __init__.py       # LLMApi facade class
```

## Supported Providers

| API Type | Provider | Description |
|----------|----------|-------------|
| `openai` | OpenAIService | OpenAI API (GPT-4, GPT-3.5, etc.) |
| `azure` | OpenAIService | Azure OpenAI Service |
| `azure_ad` | OpenAIService | Azure OpenAI with Azure AD auth |

All providers use the same `OpenAIService` class since Azure OpenAI uses a compatible API.

## Key Patterns

### Provider Registration
New providers must:
1. Subclass `CompletionService` or `EmbeddingService` from `base.py`
2. Implement `chat_completion()` generator or `get_embeddings()` 
3. Register in `__init__.py` LLMApi class's provider mapping

### Config Hierarchy
```python
class MyProviderConfig(LLMServiceConfig):
    def _configure(self) -> None:
        self._set_name("my_provider")  # creates llm.my_provider.* namespace
        self.custom_setting = self._get_str("custom_setting", "default")
```

### ChatMessageType
```python
ChatMessageType = TypedDict("ChatMessageType", {
    "role": str,        # "system", "user", "assistant"
    "content": str,
    "name": NotRequired[str],
})
```

## Configuration

```json
{
  "llm.api_type": "openai",
  "llm.api_key": "sk-...",
  "llm.model": "gpt-4",
  "llm.api_base": "https://api.openai.com/v1"
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

## Common Gotchas

- `response_format` options: `"json_object"`, `"text"`, `"json_schema"`
- Streaming: All providers return `Generator[ChatMessageType, None, None]`
- OpenAI file handles both OpenAI and Azure OpenAI via the same class
