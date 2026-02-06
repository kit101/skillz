# Chat JSONL Schema Description

This document describes the schema for the `chat.jsonl` / `chat.json` file used in the chat replay system.

## File Format
The `chat.jsonl` / `chat.json` file contains one JSON object per line, following the JSON Lines format.

## Message Types

### System Messages
```json
{
  "type": "system",
  "subtype": "init",
  "uuid": "unique-identifier",
  "session_id": "session-identifier",
  "cwd": "/workspace",
  "tools": ["task", "skill", "run_shell_command", "send_email"],
  "mcp_servers": [{"name": "mcp-notification", "status": "connected"}],
  "model": "qwen-code",
  "permission_mode": "default"
}
```

### Assistant Messages
```json
{
  "type": "assistant",
  "uuid": "unique-identifier",
  "session_id": "session-identifier",
  "parent_tool_use_id": null,
  "message": {
    "id": "message-id",
    "type": "message",
    "role": "assistant",
    "model": "qwen-code",
    "content": [{"type": "text", "text": "message content"}],
    "stop_reason": null,
    "usage": {"input_tokens": 0, "output_tokens": 0}
  }
}
```

### Tool Use Messages
```json
{
  "type": "assistant",
  "uuid": "unique-identifier",
  "session_id": "session-identifier",
  "parent_tool_use_id": null,
  "message": {
    "id": "message-id",
    "type": "message",
    "role": "assistant",
    "model": "qwen-code",
    "content": [{
      "type": "tool_use",
      "id": "tool-call-id",
      "name": "skill",
      "input": {"skill": "ssl-checker"}
    }],
    "stop_reason": "tool_use",
    "usage": {"input_tokens": 1200, "output_tokens": 50}
  }
}
```

### User Messages (Tool Results)
```json
{
  "type": "user",
  "uuid": "unique-identifier",
  "session_id": "session-identifier",
  "parent_tool_use_id": null,
  "message": {
    "role": "user",
    "content": [{
      "type": "tool_result",
      "tool_use_id": "tool-call-id",
      "is_error": false,
      "content": "tool execution result"
    }]
  }
}
```

### Result Messages
```json
{
  "type": "result",
  "subtype": "success",
  "uuid": "unique-identifier",
  "session_id": "session-identifier",
  "is_error": false,
  "duration_ms": 4500,
  "result": "final task result summary",
  "usage": {"input_tokens": 8500, "output_tokens": 400}
}
```

## Field Descriptions

| Field Path | Purpose | Description |
|------------|---------|-------------|
| `type` | Message type | Determines the role in replay (system/assistant/user/result) |
| `message.role` | Conversation role | Corresponds to speaker in replay interface (assistant/user) |
| `message.content` | Core content | `text` type for plain text, `tool_use` for tool calls, `tool_result` for tool responses |
| `tool_use.input` | Tool parameters | Shows "executed operations/commands" during replay |
| `tool_result.content` | Tool execution result | Shows "specific information returned by operations" during replay |
| `result` | Final result | Shows "task summary" during replay |

## Content Types

### Text Content
```json
{
  "type": "text",
  "text": "Plain text message content"
}
```

### Tool Use Content
```json
{
  "type": "tool_use",
  "id": "unique-tool-call-id",
  "name": "tool-name",
  "input": {
    "parameter1": "value1",
    "parameter2": "value2"
  }
}
```

### Tool Result Content
```json
{
  "type": "tool_result",
  "tool_use_id": "corresponding-tool-call-id",
  "is_error": false,
  "content": "tool execution output"
}
```

## Usage Tracking
Each message can include usage statistics:
```json
{
  "usage": {
    "input_tokens": 1200,
    "output_tokens": 50
  }
}
```

## Session Management
All messages in a conversation share the same `session_id` to maintain context and continuity during replay.