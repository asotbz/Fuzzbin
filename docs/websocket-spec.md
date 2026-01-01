## WebSocket

Real-time event streaming via WebSocket connections with first-message authentication and push-based job updates.

### Architecture Overview

The WebSocket system uses a push-based event model with server-side debouncing:

- **Unified endpoint**: All real-time updates flow through `/ws/events`
- **Job subscriptions**: Clients opt-in to job events with optional filters
- **Debounced progress**: Progress events are batched (250ms) to reduce noise
- **Immediate terminal events**: Completed/failed/cancelled events bypass debouncing
- **No replay**: On reconnect, clients receive current state snapshot, not missed events

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
   |  5. Client subscribes to jobs (optional)      |
   |  {"type": "subscribe_jobs", ...}              |
   |---------------------------------------------->|
   |                                               |
   |  6. Server sends current job state            |
   |  {"type": "job_state", "jobs": [...]}         |
   |<----------------------------------------------|
   |                                               |
   |  7. Server pushes job events as they occur    |
   |<----------------------------------------------|
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

**Subscribe Jobs** (opt-in to job events):
```json
{
  "type": "subscribe_jobs",
  "job_types": ["download_youtube", "import_nfo"],
  "job_ids": null,
  "include_active_state": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `job_types` | `string[] \| null` | Filter by job types (null = all types) |
| `job_ids` | `string[] \| null` | Filter by specific job IDs (null = all jobs) |
| `include_active_state` | `boolean` | If true, immediately receive current state of active jobs |

**Unsubscribe Jobs**:
```json
{"type": "unsubscribe_jobs"}
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

**Subscribe Jobs Success**:
```json
{
  "type": "subscribe_jobs_success",
  "job_types": ["download_youtube"],
  "job_ids": null
}
```

**Unsubscribe Jobs Success**:
```json
{"type": "unsubscribe_jobs_success"}
```

**Job State** (sent after subscribing with `include_active_state: true`):
```json
{
  "type": "job_state",
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "job_type": "download_youtube",
      "status": "running",
      "progress": 0.45,
      "current_step": "Downloading: 45.0% at 2.5 MB/s (ETA: 30s)",
      "processed_items": 45,
      "total_items": 100,
      "created_at": "2025-12-30T10:00:00Z",
      "started_at": "2025-12-30T10:00:05Z",
      "metadata": {"url": "https://youtube.com/watch?v=..."}
    }
  ]
}
```

**Pong Response**:
```json
{"type": "pong"}
```

### Event Types

Events are broadcast to subscribed clients. Job events require an active job subscription.

| Event Type | Description | Debounced |
|------------|-------------|-----------|
| `config_changed` | Configuration field was modified | No |
| `client_reloaded` | API client was reloaded with new configuration | No |
| `job_started` | Background job began execution | No |
| `job_progress` | Background job progress update | Yes (250ms) |
| `job_completed` | Background job completed successfully | No |
| `job_failed` | Background job failed with error | No |
| `job_cancelled` | Background job was cancelled | No |
| `job_timeout` | Background job exceeded timeout | No |

### Event Payloads

**Job Started**:
```json
{
  "event_type": "job_started",
  "timestamp": "2025-12-30T10:00:05Z",
  "payload": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "job_type": "download_youtube",
    "priority": 5,
    "metadata": {"url": "https://youtube.com/watch?v=..."}
  }
}
```

**Job Progress** (debounced at 250ms):
```json
{
  "event_type": "job_progress",
  "timestamp": "2025-12-30T10:00:15Z",
  "payload": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "job_type": "download_youtube",
    "progress": 0.45,
    "current_step": "Downloading: 45.0% at 2.5 MB/s (ETA: 30s)",
    "processed_items": 45,
    "total_items": 100,
    "download_speed": 2.5,
    "eta_seconds": 30
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `download_speed` | `float \| null` | Download speed in MB/s (download jobs only) |
| `eta_seconds` | `int \| null` | Estimated time remaining in seconds (download jobs only) |

**Job Completed**:
```json
{
  "event_type": "job_completed",
  "timestamp": "2025-12-30T10:01:00Z",
  "payload": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "job_type": "download_youtube",
    "result": {
      "url": "https://youtube.com/watch?v=...",
      "file_path": "/library/Artist/Video.mp4",
      "file_size": 104857600
    }
  }
}
```

**Job Failed**:
```json
{
  "event_type": "job_failed",
  "timestamp": "2025-12-30T10:01:00Z",
  "payload": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "job_type": "download_youtube",
    "error": "Network timeout",
    "error_type": "TimeoutError"
  }
}
```

**Job Cancelled**:
```json
{
  "event_type": "job_cancelled",
  "timestamp": "2025-12-30T10:01:00Z",
  "payload": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "job_type": "download_youtube"
  }
}
```

**Job Timeout**:
```json
{
  "event_type": "job_timeout",
  "timestamp": "2025-12-30T10:01:00Z",
  "payload": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "job_type": "download_youtube",
    "timeout_seconds": 3600
  }
}
```

**Config Changed**:
```json
{
  "event_type": "config_changed",
  "timestamp": "2025-12-30T15:30:00Z",
  "payload": {
    "path": "http.timeout",
    "old_value": 30,
    "new_value": 60,
    "safety_level": "safe",
    "required_actions": []
  }
}
```

### Endpoints

- `WS /ws/events` — Unified real-time event endpoint
  - Broadcasts configuration changes, job events, and system events
  - Requires first-message authentication when auth is enabled
  - Job events require explicit subscription via `subscribe_jobs` message
  - Supports filtering by job type and/or job ID

### Reconnection Pattern

When a client reconnects, it should:

1. Authenticate with the auth message
2. Subscribe to jobs with `include_active_state: true`
3. Process the `job_state` message to restore UI state
4. Continue processing push events

```typescript
async function reconnect() {
  await client.connect('ws://localhost:8000/ws/events');
  
  // Re-subscribe with active state to restore context
  client.send({
    type: 'subscribe_jobs',
    job_types: ['download_youtube', 'import_nfo'],
    include_active_state: true
  });
}
```

### Debounce Behavior

Progress events are debounced per-job with a 250ms interval:

- Multiple rapid progress updates are batched
- Only the latest progress state is sent after the interval
- Terminal events (completed, failed, cancelled, timeout) flush pending progress immediately then send the terminal event
- This reduces WebSocket traffic while ensuring timely terminal notifications

### TypeScript Client Example

```typescript
interface WSAuthMessage {
  type: 'auth';
  token: string;
}

interface WSSubscribeJobsMessage {
  type: 'subscribe_jobs';
  job_types?: string[] | null;
  job_ids?: string[] | null;
  include_active_state?: boolean;
}

interface WSUnsubscribeJobsMessage {
  type: 'unsubscribe_jobs';
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

interface WSJobState {
  type: 'job_state';
  jobs: JobStateItem[];
}

interface JobStateItem {
  job_id: string;
  job_type: string;
  status: string;
  progress: number;
  current_step: string;
  processed_items: number;
  total_items: number;
  created_at: string;
  started_at: string | null;
  metadata: Record<string, unknown>;
}

interface WSEvent {
  event_type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

interface JobProgressPayload {
  job_id: string;
  job_type: string;
  progress: number;
  current_step: string;
  processed_items: number;
  total_items: number;
  download_speed?: number;
  eta_seconds?: number;
}

class FuzzbinWebSocket {
  private ws: WebSocket | null = null;
  private token: string;
  private jobSubscription: WSSubscribeJobsMessage | null = null;
  
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
        
        switch (data.type) {
          case 'auth_success':
            console.log(`Authenticated as ${data.username}`);
            // Re-subscribe if we had a previous subscription
            if (this.jobSubscription) {
              this.subscribeToJobs(this.jobSubscription);
            }
            resolve();
            break;
          case 'auth_error':
            reject(new Error(data.message));
            break;
          case 'subscribe_jobs_success':
            console.log('Subscribed to job events');
            break;
          case 'job_state':
            this.onJobState(data as WSJobState);
            break;
          case 'pong':
            // Keep-alive response
            break;
          default:
            // Handle events
            if (data.event_type) {
              this.onEvent(data as WSEvent);
            }
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
  
  subscribeToJobs(options: Partial<WSSubscribeJobsMessage> = {}): void {
    const msg: WSSubscribeJobsMessage = {
      type: 'subscribe_jobs',
      job_types: options.job_types ?? null,
      job_ids: options.job_ids ?? null,
      include_active_state: options.include_active_state ?? true,
    };
    this.jobSubscription = msg;
    this.ws?.send(JSON.stringify(msg));
  }
  
  unsubscribeFromJobs(): void {
    const msg: WSUnsubscribeJobsMessage = { type: 'unsubscribe_jobs' };
    this.jobSubscription = null;
    this.ws?.send(JSON.stringify(msg));
  }
  
  onJobState(state: WSJobState): void {
    console.log(`Received state for ${state.jobs.length} active jobs`);
    for (const job of state.jobs) {
      console.log(`  ${job.job_id}: ${job.status} (${(job.progress * 100).toFixed(1)}%)`);
    }
  }
  
  onEvent(event: WSEvent): void {
    console.log(`Event: ${event.event_type}`, event.payload);
    
    // Handle job-specific events
    if (event.event_type.startsWith('job_')) {
      const payload = event.payload as JobProgressPayload;
      switch (event.event_type) {
        case 'job_started':
          console.log(`Job ${payload.job_id} started`);
          break;
        case 'job_progress':
          const speed = payload.download_speed 
            ? ` (${payload.download_speed.toFixed(1)} MB/s)` 
            : '';
          console.log(`Job ${payload.job_id}: ${(payload.progress * 100).toFixed(1)}%${speed}`);
          break;
        case 'job_completed':
          console.log(`Job ${payload.job_id} completed`);
          break;
        case 'job_failed':
          console.log(`Job ${payload.job_id} failed: ${(event.payload as any).error}`);
          break;
      }
    }
  }
  
  disconnect(): void {
    this.ws?.close();
  }
}

// Usage
const client = new FuzzbinWebSocket(accessToken);
await client.connect('ws://localhost:8000/ws/events');

// Subscribe to all download jobs with current state
client.subscribeToJobs({
  job_types: ['download_youtube'],
  include_active_state: true
});

// Or subscribe to a specific job
client.subscribeToJobs({
  job_ids: ['550e8400-e29b-41d4-a716-446655440000'],
  include_active_state: true
});
```
