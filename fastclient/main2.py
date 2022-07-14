from collections import defaultdict
from enum import Enum
from multiprocessing.managers import BaseManager
from typing import Any, Callable, List, Mapping
from datastructures import _RateLimitedPoolBuffer, _RateLimitedTokenBuffer
from queue import Queue
from urllib3 import PoolManager


class Event(Enum):
    RESPONSE = 'response'  # 2XX response
    ERROR = 'error'  # 4XX error
    UNCAUGHT = 'uncaught'  # unhandled error (and 5XX responses)


class _FastClientSyncManager(BaseManager):
    context: Mapping[str, Any]
    tokens: _RateLimitedTokenBuffer
    pools: _RateLimitedPoolBuffer
    requests: Queue
    responses: Queue

    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)

        # register synced variables
        self.register('context', dict)
        self.register('tokens', _RateLimitedTokenBuffer)
        self.register('pools', _RateLimitedPoolBuffer)
        self.register('requests', Queue)
        self.register('responses', Queue)

        # start
        self.start()


class FastClient:
    def __init__(self, requests_per_second: float, pools: List) -> None:
        self._manager = _FastClientSyncManager()

        # create proxies for synced datastructures
        self._context = self._manager.context()
        self._tokens = self._manager.tokens(1/requests_per_second)
        self._pools = self._manager.pools(1/requests_per_second)
        self._requests = self._manager.requests()
        self._responses = self._manager.responses()

        self._listeners = defaultdict(list)
        self._listener_registered = False

        # initialize stuff
        # assuming one request doesn't take longer than 1 second, otherwise this may be inefficient
        for pool in pools | [PoolManager(num_pools=1, maxsize=requests_per_second)]:
            self._pools.put(pool)

    def __getitem__(self, key: str) -> Any:
        return self._context[key]

    def __setitem__(self, key: str, value: Any):
        self._context[key] = value

    def request(self, request, id=None):
        self._requests.put((request, id))

    def join(self):
        if not self._listener_registered:
            raise Exception('No listeners registered')
        # start processing
        # spawn a bunch of processes
        # process the responses queue (in the same thread or threaded)

    def on(self, event: Event, callback: Callable[[Mapping, str, int, Callable[[], None], Callable[[], None]], None]):
        self._listeners[event].append(callback)
        self._listener_registered = True


def _worker(queue, tokens, context, limits):
    while not queue.empty():
        request, id = queue.get()
