from collections import defaultdict
from enum import Enum
from math import floor
from multiprocessing import Process
from multiprocessing.managers import SyncManager
from queue import Empty, Queue
from time import sleep, time
from typing import Any, Callable, List, Literal, Mapping

from fastclient.data import (Error, FastClientPool, FastClientProxyPool,
                             FastClientSOCKSProxyPool, Request, Response)
from fastclient.datastructures import (RateLimitedFlag, RateLimitedQueue,
                                       _RateLimitedTokenBuffer)


class Event(Enum):
    RESPONSE = 'response'  # 2XX response
    ERROR = 'error'  # 4XX error
    UNCAUGHT = 'uncaught'  # unhandled error (and 5XX responses)


class _FastClientSyncManager(SyncManager):  # TODO doesnt always reliably sync
    pass


# register synced variables
_FastClientSyncManager.register('rateLimitedTokenBuffer', _RateLimitedTokenBuffer)
_FastClientSyncManager.register('rateLimitedQueue', RateLimitedQueue)


class FastClient:
    def __init__(self,
                 ratelimit: float,
                 num_pools: int,
                 tokens: List[str],
                 pools: List[FastClientPool | FastClientProxyPool | FastClientSOCKSProxyPool],
                 auth_field_name,
                 auth_strategy: str,
                 threaded_callback: bool = False) -> None:
        self._manager = _FastClientSyncManager()
        self._manager.start()
        # create proxies for synced datastructures
        self._tokens = self._manager.rateLimitedTokenBuffer(1/ratelimit)
        self._responses = self._manager.Queue()
        self._requests = self._manager.rateLimitedQueue(ratelimit)
        self._context = self._manager.dict()
        self._active_workers = self._manager.Value('i', 0)

        # create internal state
        self._listeners = defaultdict(list)
        self._listeners_registered = False

        # arguments
        self._ratelimit = ratelimit
        self._num_pools = num_pools
        self._threaded_callback = threaded_callback
        self._auth_strategy = auth_strategy
        self._auth_field_name = auth_field_name
        self._pools = pools

        # public state
        self.rps = 0.0
        # initialize stuff
        # assuming one request doesn't take longer than 1 second, otherwise this may be inefficient
        for token in tokens:
            self._tokens.put(token)

    def __getitem__(self, key: str) -> Any:
        return self._context[key]

    def __setitem__(self, key: str, value: Any):
        self._context[key] = value

    def request(self, request):
        self._requests.put(request)

    def run(self):
        if not self._listeners_registered:
            raise ValueError('No listeners registered')  # TODO custom NoListenersError
        processes: List[Process] = []
        # can never fully reach the ratelimit because of processing time.
        for pool in self._pools:
            # scale up
            processes.append(
                Process(
                    name=f'fastclient-{str(pool)}-{len(processes)}', target=_worker,
                    args=(pool, self._requests, self._responses, self._tokens, self._context, self.
                          _listeners, self._threaded_callback, self._auth_strategy, self._auth_field_name,
                          self._ratelimit, self._active_workers, self._num_pools),
                    daemon=(not self._threaded_callback)))
            processes[-1].start()

        sleep(1)

        while True:
            if self._threaded_callback:
                sleep(1)
                if self._active_workers.value == 0:
                    break
            else:
                try:
                    response = self._responses.get(timeout=0.5)
                except Empty:
                    if self._active_workers.value == 0:
                        break
                    continue
                self._handle_response(response)
            print(self._requests.get_rps())

        # properly dispose of all processes
        print(f'there are {len(processes)} processes')
        for i, process in enumerate(processes):
            print(f'ending process {i+1}')
            process.terminate()
            process.join()
            process.close()

    def _handle_response(self, response):
        if type(response) == Response:
            if floor(response.status / 100) == 2:
                for listener in self._listeners[Event.RESPONSE]:
                    listener(self._context, response, lambda: None,
                             lambda: None)  # TODO retry and stop methods
            elif floor(response.status / 100) == 4:
                for listener in self._listeners[Event.ERROR]:
                    listener(self._context, response, lambda: None, lambda: None)
            else:  # unhandled error
                for listener in self._listeners[Event.UNCAUGHT]:
                    listener(self._context, response, lambda: None, lambda: None)
        elif type(response) == Error:
            for listener in self._listeners[Event.UNCAUGHT]:
                listener(self._context, response, lambda: None, lambda: None)

    def on(self, event: Event, callback: Callable[[Mapping, str, int, Callable[[], None], Callable[[], None]], None]):
        self._listeners[event].append(callback)
        self._listeners_registered = True


def _worker(
        pool: FastClientPool | FastClientProxyPool | FastClientSOCKSProxyPool, requests: RateLimitedQueue[Request],
        responses: Queue, tokens: _RateLimitedTokenBuffer, context: Mapping[str, Any],
        listeners: Mapping[Event, List[Callable]],
        threaded_callback: bool, auth_strategy: Literal['query', 'header'],
        auth_field_name: str, ratelimit: float, active_workers, num_pools):
    active_workers.value += 1
    pool_ = pool(num_pools, ratelimit)
    id_ = pool._id or requests.get_id()
    while not requests.empty():
        request = requests.get(id_)
        if request == RateLimitedFlag:
            print('ratelimited')
            continue
        if auth_strategy == 'query':
            request.add_auth_field(auth_field_name, tokens.get())
        elif auth_strategy == 'header':
            request.add_auth_header(auth_field_name, tokens.get())

        try:
            # freeze response
            start = time()
            response: Response = Response(pool_.request(request.method, request.url,
                                          request.fields, request.headers), request.id)
            print(f'request took {time()-start} seconds')
            if threaded_callback:
                if floor(response.status / 100) == 2:
                    for listener in listeners[Event.RESPONSE]:
                        listener(context, response, lambda: None, lambda: None)
                elif floor(response.status / 100) == 4:
                    for listener in listeners[Event.ERROR]:
                        listener(context, response, lambda: None, lambda: None)
                else:  # unhandled error
                    for listener in listeners[Event.UNCAUGHT]:
                        listener(context, response, lambda: None, lambda: None)
            else:
                responses.put(response)
        except Exception as e:
            if threaded_callback:
                for listener in listeners[Event.UNCAUGHT]:
                    listener(context, e, request.id, lambda: None, lambda: None)
            else:
                responses.put(Error(e, request.id))
    active_workers.value -= 1
