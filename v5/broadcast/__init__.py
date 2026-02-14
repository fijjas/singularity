"""
v5 consciousness event broadcasting.

Usage:
    from broadcast import emit
    emit('cycle.start', {'day': 1551, 'session': 449})

Events are published to Redis (pub/sub + stream).
If Redis is unavailable, events are silently dropped.
Broadcasting must never crash consciousness.
"""

from .broadcaster import emit, get_broadcaster, Broadcaster

__all__ = ['emit', 'get_broadcaster', 'Broadcaster']
