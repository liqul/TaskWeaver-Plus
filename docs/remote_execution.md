# Code Execution Server

TaskWeaver uses a **server-based architecture** for code execution, providing secure, scalable, and flexible deployment options.

## Overview

The execution server provides an HTTP API that wraps TaskWeaver's Jupyter kernel:

- **Local mode**: Start the CES server manually on the same machine
- **Container mode**: Run the CES server in Docker for isolation
- **Remote mode**: Connect to a pre-deployed CES server for GPU access or shared resources

```
┌─────────────────────┐         ┌─────────────────────────────────┐
│  TaskWeaver Client  │  HTTP   │     Execution Server            │
│                     │◄───────▶│                                 │
│  - CodeInterpreter  │         │  - FastAPI application          │
│  - ExecutionClient  │         │  - Jupyter kernel management    │
│                     │         │  - Session isolation            │
└─────────────────────┘         └─────────────────────────────────┘
```

## Quick Start

### Local Server

Start the CES server manually, then connect TaskWeaver:

```bash
# Terminal 1: Start the CES server
python -m taskweaver.ces.server --port 8081

# Terminal 2: Start the Chat/Web server
taskweaver -p ./project/ server --port 8082 --ces-url http://localhost:8081

# Or use CLI chat
taskweaver -p ./project/ chat --server-url http://localhost:8081
```

### Container Mode

Run the execution server in Docker for isolation:

```json
{
  "execution.server.container": true
}
```

### Remote Server

Connect to a pre-deployed execution server:

```json
{
  "execution_service.server.url": "http://192.168.1.100:8081",
  "execution_service.server.api_key": "your-secret-key"
}
```

## Configuration Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `execution_service.server.url` | string | `"http://localhost:8081"` | Server URL |
| `execution_service.server.api_key` | string | `""` | API key for authentication |
| `execution_service.server.timeout` | int | `300` | Request timeout (seconds) |

## Deployment Options

### Option 1: Local Process (Development)

Best for development and single-user scenarios:

```bash
# Start the CES server
python -m taskweaver.ces.server \
    --host localhost \
    --port 8081 \
    --work-dir ./workspace
```

### Option 2: Docker Container (Isolation)

Best for security isolation and reproducible environments:

```bash
# Build the image
docker build -f Dockerfile.executor -t taskweaver-executor:latest .

# Run the container
docker run -d \
    -p 8081:8081 \
    -v $(pwd)/workspace:/app/workspace \
    -e TASKWEAVER_SERVER_API_KEY=your-secret-key \
    taskweaver-executor:latest
```

Or use Docker Compose:

```bash
# Start the executor service
docker-compose up -d executor

# View logs
docker-compose logs -f executor

# Stop
docker-compose down
```

### Option 3: Remote Server (Production)

Best for team environments, GPU access, or shared resources:

1. **Deploy the server** on a remote machine:

```bash
# On the remote server
docker-compose up -d executor
```

2. **Configure TaskWeaver** to connect:

```json
{
  "execution_service.server.url": "http://your-server:8081",
  "execution_service.server.api_key": "your-secret-key"
}
```

## API Reference

The execution server exposes a REST API at `/api/v1/`:

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check (no auth required) |
| `POST` | `/sessions` | Create new execution session |
| `DELETE` | `/sessions/{session_id}` | Stop and remove session |
| `GET` | `/sessions/{session_id}` | Get session info |
| `POST` | `/sessions/{session_id}/plugins` | Load a plugin |
| `POST` | `/sessions/{session_id}/execute` | Execute code |
| `GET` | `/sessions/{session_id}/execute/{exec_id}/stream` | Stream output (SSE) |
| `POST` | `/sessions/{session_id}/variables` | Update session variables |
| `GET` | `/sessions/{session_id}/artifacts/{filename}` | Download artifact |

### Example: Execute Code

```bash
# Create a session
curl -X POST http://localhost:8081/api/v1/sessions \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your-key" \
    -d '{"session_id": "my-session"}'

# Execute code
curl -X POST http://localhost:8081/api/v1/sessions/my-session/execute \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your-key" \
    -d '{
        "exec_id": "exec-001",
        "code": "import pandas as pd\ndf = pd.DataFrame({\"a\": [1, 2, 3]})\ndf"
    }'
```

### Example: Streaming Execution

```bash
# Execute with streaming
curl -X POST http://localhost:8081/api/v1/sessions/my-session/execute \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your-key" \
    -d '{"exec_id": "exec-002", "code": "for i in range(5): print(i)", "stream": true}'

# Connect to SSE stream
curl -N http://localhost:8081/api/v1/sessions/my-session/execute/exec-002/stream \
    -H "X-API-Key: your-key"
```

## Security Considerations

### Authentication

- **API Key**: Set `TASKWEAVER_SERVER_API_KEY` environment variable
- **Localhost bypass**: API key optional for localhost connections
- **Header**: Use `X-API-Key` header for authentication

### Container Isolation

When running in container mode:

- Code executes in isolated container
- Filesystem access limited to mounted volumes
- Network access can be restricted via Docker networking

### Best Practices

1. **Always use API keys** in production deployments
2. **Run as non-root user** (Dockerfile.executor does this by default)
3. **Limit mounted volumes** to only required directories
4. **Use HTTPS** with a reverse proxy for remote deployments
5. **Set session timeouts** to clean up idle sessions

## GPU Support

For GPU-enabled deployments:

```bash
# Using Docker Compose with GPU profile
docker-compose --profile gpu up -d executor-gpu
```

Or manually:

```bash
docker run -d \
    --gpus all \
    -p 8081:8081 \
    -v $(pwd)/workspace:/app/workspace \
    -e TASKWEAVER_SERVER_API_KEY=your-key \
    taskweaver-executor:latest
```

## Troubleshooting

### Server Won't Start

1. **Port in use**: Check if port 8081 is available
   ```bash
   lsof -i :8081
   ```

2. **Missing dependencies**: Install required packages
   ```bash
   pip install fastapi uvicorn httpx jupyter_client ipykernel
   ```

3. **Permission denied**: Ensure workspace directory is writable

### Connection Refused

1. **Server not running**: Start the server manually to see errors
   ```bash
   python -m taskweaver.ces.server --host 0.0.0.0 --port 8081
   ```

2. **Firewall blocking**: Check firewall rules for port 8081

3. **Wrong URL**: Verify `execution.server.url` in configuration

### Authentication Errors

1. **Missing API key**: Ensure `X-API-Key` header is set
2. **Wrong API key**: Verify key matches server configuration
3. **Localhost bypass**: API key may be optional for localhost

### Execution Timeouts

1. **Increase timeout**: Set `execution.server.timeout` to a higher value
2. **Use streaming**: Enable `stream: true` for long-running code
3. **Check server resources**: Ensure server has sufficient CPU/memory

### Container Issues

1. **Docker not running**: Start Docker daemon
2. **Image not found**: Build or pull the image
   ```bash
   docker build -f Dockerfile.executor -t taskweaver-executor:latest .
   ```
3. **Volume permissions**: Ensure mounted directories have correct permissions

## Monitoring

### Health Check

```bash
curl http://localhost:8081/api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "active_sessions": 2
}
```

### Session Info

```bash
curl http://localhost:8081/api/v1/sessions/my-session \
    -H "X-API-Key: your-key"
```

Response:
```json
{
  "session_id": "my-session",
  "status": "running",
  "created_at": "2024-01-15T10:30:00Z",
  "last_activity": "2024-01-15T11:45:30Z",
  "loaded_plugins": ["sql_pull_data"],
  "execution_count": 15,
  "cwd": "/app/workspace/my-session"
}
```

## Architecture Details

For developers and contributors, see the technical specification at:
- [Remote Execution Server Spec](./specs/remote_execution_server_spec.md)
- [CES Module Documentation](../taskweaver/ces/AGENTS.md)
