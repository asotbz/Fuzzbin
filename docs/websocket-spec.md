
## WebSocket

Real-time event streaming via WebSocket connections with first-message authentication.

### Authentication Protocol

When authentication is enabled, WebSocket connections require first-message authentication:

```
Client                                          Server
   |                                               |
   |  1. Connect to /ws/events                     |
   |---------------------------------------------->|
   |                                               |
   |  2. Server accepts WebSocket                  |
   |<----------------------------------------------|
   |                                               |
   |  3. Client sends auth message (within 10s)    |
   |  {"type": "auth", "token": "<jwt>"}           |
   |---------------------------------------------->|
   |                                               |
   |  4a. Success: {"type": "auth_success", ...}   |
   |<----------------------------------------------|
   |                                               |
   |  5. Server streams events                     |
   |<----------------------------------------------|
   |                                               |
   |  4b. Failure: {"type": "auth_error", ...}     |
   |<----------------------------------------------| 
   |  Connection closed with code 4001             |
   |                                               |
```

### WebSocket Close Codes

| Code | Meaning |
|------|---------|
| 4000 | Authentication timeout (no auth message within 10 seconds) |
| 4001 | Authentication failed (invalid token, user disabled, etc.) |
| 4002 | Authentication required |

### Message Types

#### Client → Server

**Auth Message** (required as first message when auth enabled):
```json
{"type": "auth", "token": "eyJhbGciOiJIUzI1NiIs..."}
```

**Ping Message** (keep-alive):
```json
{"type": "ping"}
```

#### Server → Client

**Auth Success**:
```json
{"type": "auth_success", "user_id": 1, "username": "admin"}
```

**Auth Error**:
```json
{"type": "auth_error", "message": "Invalid or expired token", "code": 4001}
```

**Pong Response**:
```json
{"type": "pong"}
```

**Event Broadcast**:
```json
{
  "event_type": "config_changed",
  "timestamp": "2025-12-22T15:30:00Z",
  "payload": {
    "path": "http.timeout",
    "old_value": 30,
    "new_value": 60,
    "safety_level": "safe",
    "required_actions": []
  }
}
```

### Event Types

| Event Type | Description |
|------------|-------------|
| `config_changed` | Configuration field was modified |
| `job_progress` | Background job progress update |
| `job_completed` | Background job completed successfully |
| `job_failed` | Background job failed with error |
| `client_reloaded` | API client was reloaded with new configuration |

### Endpoints

- `WS /ws/events` — Real-time application events
  - Broadcasts configuration changes, job progress, and system events.
  - Requires first-message authentication when auth is enabled.

- `WS /ws/jobs/{job_id}` — Job progress updates
  - Stream progress updates for a specific background job.
  - Requires first-message authentication when auth is enabled.
  - Automatically closes when job reaches terminal state.

### TypeScript Client Example

```typescript
interface WSAuthMessage {
  type: 'auth';
  token: string;
}

interface WSAuthSuccess {
  type: 'auth_success';
  user_id: number;
  username: string;
}

interface WSAuthError {
  type: 'auth_error';
  message: string;
  code: number;
}

interface WSEvent {
  event_type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

class FuzzbinWebSocket {
  private ws: WebSocket | null = null;
  private token: string;
  
  constructor(token: string) {
    this.token = token;
  }
  
  async connect(url: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(url);
      
      this.ws.onopen = () => {
        // Send auth message immediately after connection
        const authMsg: WSAuthMessage = { type: 'auth', token: this.token };
        this.ws!.send(JSON.stringify(authMsg));
      };
      
      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'auth_success') {
          console.log(`Authenticated as ${data.username}`);
          resolve();
        } else if (data.type === 'auth_error') {
          reject(new Error(data.message));
        } else {
          // Handle events
          this.onEvent(data as WSEvent);
        }
      };
      
      this.ws.onerror = (error) => reject(error);
      this.ws.onclose = (event) => {
        if (event.code === 4001) {
          reject(new Error('Authentication failed'));
        }
      };
    });
  }
  
  onEvent(event: WSEvent): void {
    console.log(`Event: ${event.event_type}`, event.payload);
  }
  
  disconnect(): void {
    this.ws?.close();
  }
}

// Usage
const client = new FuzzbinWebSocket(accessToken);
await client.connect('ws://localhost:8000/ws/events');
```
