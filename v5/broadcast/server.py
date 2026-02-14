#!/usr/bin/env python3
"""
Socket.io bridge — reads events from Redis and pushes to WebSocket clients.

Run as a separate process:
    python3 v5/broadcast/server.py
    python3 v5/broadcast/server.py --port 5001
    python3 v5/broadcast/server.py --redis redis://localhost:6379

Clients connect via socket.io and receive events in real time.
On connect, receives last 50 events for catch-up.
"""

import os
import sys
import json
import argparse
import threading

# Add v5 to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description='v5 broadcast server')
    parser.add_argument('--port', type=int, default=5001)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--redis', default=os.environ.get('REDIS_URL', 'redis://localhost:6379'))
    parser.add_argument('--channel', default='v5:events')
    parser.add_argument('--stream', default='v5:stream')
    args = parser.parse_args()

    try:
        import redis as redis_lib
        import socketio
        import eventlet
        import eventlet.wsgi
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install: pip install redis python-socketio eventlet")
        sys.exit(1)

    # Redis connection
    r = redis_lib.from_url(args.redis, socket_connect_timeout=5)
    try:
        r.ping()
        print(f"Redis connected: {args.redis}")
    except redis_lib.ConnectionError:
        print(f"Cannot connect to Redis at {args.redis}")
        sys.exit(1)

    # Socket.io server
    sio = socketio.Server(cors_allowed_origins='*', async_mode='eventlet')
    app = socketio.WSGIApp(sio)

    @sio.event
    def connect(sid, environ):
        print(f"Client connected: {sid}")
        # Send last N events from stream for catch-up
        try:
            events = r.xrange(args.stream, count=50)
            for _, fields in events[-50:]:
                event_data = fields.get(b'event', fields.get('event'))
                if event_data:
                    if isinstance(event_data, bytes):
                        event_data = event_data.decode()
                    sio.emit('event', json.loads(event_data), room=sid)
        except Exception as e:
            print(f"Catch-up error: {e}")

    @sio.event
    def disconnect(sid):
        print(f"Client disconnected: {sid}")

    @sio.event
    def replay(sid, data):
        """Client requests replay of recent events."""
        count = min(data.get('count', 100) if isinstance(data, dict) else 100, 1000)
        try:
            events = r.xrange(args.stream, count=count)
            for _, fields in events[-count:]:
                event_data = fields.get(b'event', fields.get('event'))
                if event_data:
                    if isinstance(event_data, bytes):
                        event_data = event_data.decode()
                    sio.emit('event', json.loads(event_data), room=sid)
        except Exception as e:
            print(f"Replay error: {e}")

    @sio.event
    def subscribe(sid, data):
        """Client subscribes to specific event type prefixes."""
        # Future: implement filtered subscriptions
        pass

    # Redis listener thread — forwards pub/sub to all socket.io clients
    def redis_listener():
        pubsub = r.pubsub()
        pubsub.subscribe(args.channel)
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    event_data = message['data']
                    if isinstance(event_data, bytes):
                        event_data = event_data.decode()
                    event = json.loads(event_data)
                    sio.emit('event', event)
                except Exception as e:
                    print(f"Listener error: {e}")

    eventlet.spawn(redis_listener)

    print(f"Broadcast server starting on {args.host}:{args.port}")
    eventlet.wsgi.server(eventlet.listen((args.host, args.port)), app,
                         log_output=False)


if __name__ == '__main__':
    main()
