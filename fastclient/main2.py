from collections import defaultdict
from enum import Enum
from multiprocessing.managers import BaseManager
from typing import Any, Callable, List, Mapping
from datastructures import _RateLimitedPoolBuffer, _RateLimitedTokenBuffer
from queue import Queue
from urllib3 import PoolManager
from math import floor


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
    def __init__(self, requests_per_second: float, pools: List, tokens: List[str]) -> None:
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
        for token in tokens:
            self._tokens.put(token)

    def __getitem__(self, key: str) -> Any:
        return self._context[key]

    def __setitem__(self, key: str, value: Any):
        self._context[key] = value

    def request(self, request, id=None):
        self._requests.put((request, id))

    def run(self):
        if not self._listener_registered:
            raise Exception('No listeners registered')
        # start processing
        # spawn a bunch of processes
        # process the responses queue (in the same thread or threaded)

    def on(self, event: Event, callback: Callable[[Mapping, str, int, Callable[[], None], Callable[[], None]], None]):
        self._listeners[event].append(callback)
        self._listener_registered = True


def _worker(queue, pools, tokens, context, listeners):
    while not queue.empty():
        request, id = queue.get()
        response = pools.get().request_encode_url('GET', request, fields={'key': tokens.get()})
        if floor(response.status % 100) == 2:
            for listener in listeners[Event.RESPONSE]:
                listener(context, response, id, lambda: None, lambda: None)
        elif floor(response.status % 100) == 4:
            for listener in listeners[Event.ERROR]:
                listener(context, response, id, lambda: None, lambda: None)
