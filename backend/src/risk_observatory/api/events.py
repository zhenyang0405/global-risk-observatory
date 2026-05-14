"""Tiny in-process pub/sub for SSE.

Sync `publish()` is called from BackgroundTasks running in FastAPI's threadpool.
Async SSE handlers `subscribe()` and pull from the returned queue.

Lifted from Global-Resilience and generalised to a Union envelope.
"""

from __future__ import annotations

import threading
from queue import Full, Queue
from typing import Union

from ..schemas import BriefEnvelope, EventEnvelope

Envelope = Union[EventEnvelope, BriefEnvelope]

_subscribers: list[Queue] = []
_lock = threading.Lock()


def subscribe(maxsize: int = 200) -> Queue:
    q: Queue = Queue(maxsize=maxsize)
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: Queue) -> None:
    with _lock:
        if q in _subscribers:
            _subscribers.remove(q)


def publish(envelope: Envelope) -> None:
    with _lock:
        subs = list(_subscribers)
    for q in subs:
        try:
            q.put_nowait(envelope)
        except Full:
            # Drop on slow consumer rather than block the publisher.
            pass
