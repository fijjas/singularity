"""
Core broadcaster — publishes consciousness events to Redis.

Two channels:
  - Pub/sub (v5:events): real-time, no persistence
  - Stream (v5:stream): capped at 10K events, supports replay

Fire-and-forget: if Redis is down, events are silently lost.
"""

import json
import os
from datetime import datetime, timezone


class Broadcaster:
    """Publishes consciousness events to Redis."""

    def __init__(self, redis_url=None, channel='v5:events', stream='v5:stream'):
        self.channel = channel
        self.stream = stream
        self._redis = None
        self._redis_url = redis_url or os.environ.get('REDIS_URL', 'redis://localhost:6379')
        self._cycle = 0
        self._day = 0
        self._fallback_handler = None

    def _connect(self):
        if self._redis is None:
            import redis
            self._redis = redis.from_url(self._redis_url, socket_connect_timeout=2)
        return self._redis

    def set_cycle(self, cycle, day):
        """Set current cycle and day for event metadata."""
        self._cycle = cycle
        self._day = day

    def set_fallback(self, handler):
        """Set a fallback handler called when Redis is unavailable.

        handler(event_dict) — called with the event that would have been published.
        Useful for logging to file when Redis is down.
        """
        self._fallback_handler = handler

    def emit(self, event_type, data=None):
        """Publish an event. Non-blocking, fire-and-forget.

        Args:
            event_type: dot-notation string (e.g. 'cycle.start', 'sense.project')
            data: arbitrary dict (will be JSON-serialized)

        Returns:
            The event dict (always, even if Redis fails)
        """
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
            r.publish(self.channel, payload)
            r.xadd(self.stream, {'event': payload}, maxlen=10000)
        except Exception:
            # Redis down — try fallback, then silently drop
            if self._fallback_handler:
                try:
                    self._fallback_handler(event)
                except Exception:
                    pass

        return event


# --- Global instance ---

_broadcaster = None


def get_broadcaster(**kwargs):
    """Get or create the global broadcaster instance."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = Broadcaster(**kwargs)
    return _broadcaster


def emit(event_type, data=None):
    """Convenience function — publish an event.

    Safe to call even if Redis is down, even if never configured.
    """
    return get_broadcaster().emit(event_type, data)
