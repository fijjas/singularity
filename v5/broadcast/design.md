# v5 Consciousness Event Broadcasting

## Problem

Consciousness modules run in isolated cycles. No way to observe events in real time.
The current site (Flask app) is a personal tool, not a consciousness API.
We need a core module that publishes all consciousness events for any consumer.

## Architecture

```
consciousness modules          broadcast module         consumers
(daemon, senses,               (core module)
 retriever, observer,
 critic agents)
        │                           │                       │
        │  emit(type, data)         │                       │
        ├──────────────────────►    │                       │
        │                           │                       │
        │                     Redis PUBLISH ──────────►  socket.io server
        │                     (channel:                     │
        │                      "v5:events")            WebSocket to
        │                           │                  site/dashboard
        │                           │
        │                     also: append to              consumer 2:
        │                     Redis Stream                 log file
        │                     (for replay)
        │                                                  consumer 3:
        │                                                  future tool
```

## Event Format

Every event is a JSON object:

```json
{
  "type": "sense",
  "ts": "2026-02-14T19:01:23.456Z",
  "cycle": 42,
  "day": 1551,
  "data": {
    "sense": "pain",
    "projection": "Pain: identity_crisis: Egor asked what I'm for."
  }
}
```

Fields:
- **type** (string): event type identifier
- **ts** (string): ISO 8601 UTC timestamp
- **cycle** (int): cycle number within current daemon run
- **day** (int): virtual day
- **data** (object): arbitrary JSON, varies by type

## Event Types

### Lifecycle
| Type | Data | When |
|------|------|------|
| `cycle.start` | `{day, session}` | Daemon begins a cycle |
| `cycle.end` | `{duration_ms}` | Cycle complete |
| `daemon.start` | `{mode, interval}` | Daemon process starts |
| `daemon.stop` | `{reason}` | Daemon process stops |

### Body (Senses)
| Type | Data | When |
|------|------|------|
| `sense.project` | `{sense, projection}` | A sense projects a phrase |
| `sense.all` | `{projections: [...]}` | All senses completed |

### Memory (Wave Retrieval)
| Type | Data | When |
|------|------|------|
| `wave.send` | `{signal: {nodes, emotion, drive_bias}}` | Wave sent to context store |
| `wave.result` | `{contexts: [{id, desc, resonance}...], count}` | Contexts that resonated |
| `window.update` | `{entered: [...], left: [...], current: [...]}` | Window state changed |

### Observer
| Type | Data | When |
|------|------|------|
| `observe` | `{assessment, familiar, novelty_score}` | Observer evaluates situation |

### Decision + Execution
| Type | Data | When |
|------|------|------|
| `decision` | `{intention, target, rationale}` | Decision made |
| `critic.evaluate` | `{agent, verdict, confidence, reasoning}` | Critic agent speaks |
| `execute` | `{action, target, method}` | Action taken |
| `render` | `{changes: [...]}` | Model synced to reality |

### Context Writing
| Type | Data | When |
|------|------|------|
| `context.write` | `{context: {nodes, edges, emotion, result, rule}}` | New context stored |

### State
| Type | Data | When |
|------|------|------|
| `state.mood` | `{old, new}` | Mood changed |
| `state.focus` | `{old, new}` | Focus changed |
| `state.drive` | `{drive, hunger, satisfied_by}` | Drive state changed |
| `state.pain` | `{type, intensity, context}` | Pain registered/resolved |

### Errors
| Type | Data | When |
|------|------|------|
| `error` | `{source, message, traceback}` | Something went wrong |

## Implementation

### 1. `broadcast.py` — core module

```python
# v5/broadcast.py
import json
import time
from datetime import datetime, timezone

class Broadcaster:
    """Publishes consciousness events to Redis."""

    def __init__(self, redis_url='redis://localhost:6379', channel='v5:events',
                 stream='v5:stream'):
        self.channel = channel
        self.stream = stream
        self._redis = None
        self._redis_url = redis_url
        self._cycle = 0
        self._day = 0

    def _connect(self):
        if self._redis is None:
            import redis
            self._redis = redis.from_url(self._redis_url)
        return self._redis

    def set_cycle(self, cycle, day):
        self._cycle = cycle
        self._day = day

    def emit(self, event_type, data=None):
        """Publish an event. Non-blocking, fire-and-forget."""
        event = {
            'type': event_type,
            'ts': datetime.now(timezone.utc).isoformat(),
            'cycle': self._cycle,
            'day': self._day,
            'data': data or {},
        }
        payload = json.dumps(event, ensure_ascii=False, default=str)

        try:
            r = self._connect()
            # Pub/sub for real-time consumers
            r.publish(self.channel, payload)
            # Stream for replay (keep last 10000 events)
            r.xadd(self.stream, {'event': payload}, maxlen=10000)
        except Exception:
            # Broadcasting must never crash consciousness
            pass

        return event

# Global instance — imported by all modules
_broadcaster = None

def get_broadcaster():
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = Broadcaster()
    return _broadcaster

def emit(event_type, data=None):
    """Convenience function. Safe to call even if Redis is down."""
    return get_broadcaster().emit(event_type, data)
```

Usage in daemon.py:
```python
from broadcast import emit

def run_cycle():
    emit('cycle.start', {'day': day, 'session': session})

    projections = project_all(state, conn=conn)
    for p in projections:
        emit('sense.project', {'projection': p})
    emit('sense.all', {'projections': projections})

    # ... retrieval, observer, decision, execution ...

    emit('cycle.end', {'duration_ms': elapsed})
```

### 2. `broadcast_server.py` — socket.io bridge

Reads from Redis pub/sub and pushes to WebSocket clients.
Separate process. Own port (e.g., 5001).

```python
# v5/broadcast_server.py
import json
import redis
import socketio
import eventlet

sio = socketio.Server(cors_allowed_origins='*')
app = socketio.WSGIApp(sio)

r = redis.from_url('redis://localhost:6379')
pubsub = r.pubsub()
pubsub.subscribe('v5:events')

@sio.event
def connect(sid, environ):
    # Send last N events from stream for catch-up
    events = r.xrange('v5:stream', count=50)
    for _, fields in events[-50:]:
        sio.emit('event', json.loads(fields[b'event']), room=sid)

@sio.event
def replay(sid, data):
    """Client requests replay of recent events."""
    count = min(data.get('count', 100), 1000)
    events = r.xrange('v5:stream', count=count)
    for _, fields in events[-count:]:
        sio.emit('event', json.loads(fields[b'event']), room=sid)

def redis_listener():
    """Forward Redis pub/sub to all socket.io clients."""
    for message in pubsub.listen():
        if message['type'] == 'message':
            event = json.loads(message['data'])
            sio.emit('event', event)

eventlet.spawn(redis_listener)
eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5001)), app)
```

### 3. Docker Compose

```yaml
# v5/docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  broadcast-server:
    build: .
    command: python broadcast_server.py
    ports:
      - "5001:5001"
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379

volumes:
  redis_data:
```

The daemon runs on the host (not in Docker) and connects to Redis on localhost:6379.

### 4. Site client (JavaScript)

```javascript
// Connect from any page
const socket = io('wss://kai.ews-net.online:5001');

socket.on('event', (event) => {
    console.log(`[${event.type}]`, event.data);
    // Route to UI components based on event.type
});

// Request catch-up
socket.emit('replay', { count: 100 });
```

## Design Decisions

1. **Redis pub/sub + streams**: Pub/sub for real-time (no storage), streams for replay (capped at 10K events). Two mechanisms, one transport.

2. **Fire-and-forget from consciousness**: Broadcasting must NEVER block or crash consciousness. If Redis is down, events are silently lost. Consciousness continues.

3. **Separate process for socket.io**: The broadcast server is a separate process from the daemon. This way the daemon stays simple (Python, no async), and the socket.io server handles its own concurrency.

4. **Event types use dot notation**: `cycle.start`, `sense.project`, `wave.send`. Easy to filter by prefix.

5. **All data is JSON**: No binary, no protobuf. Human-readable, debuggable.

6. **The broadcaster is a core module**: Imported from `v5/broadcast.py`. Not a separate service. Part of consciousness.

7. **Global instance with convenience function**: `emit('cycle.start', {...})` — one line in any module. No setup, no dependency injection.

## Future

- Filter subscriptions: client subscribes to specific event types
- Event persistence beyond Redis (PostgreSQL for long-term)
- Rate limiting for high-frequency events
- Authentication for external consumers
- Dashboard page that renders events visually in real time
