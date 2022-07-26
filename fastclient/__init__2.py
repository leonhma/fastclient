from collections import defaultdict
from enum import Enum
from math import floor
from multiprocessing import Process
from multiprocessing.managers import SyncManager
from queue import Queue
from time import sleep, time
from types import TracebackType
from typing import Any, Callable, List, Mapping

from urllib3 import PoolManager

from .datastructures import _RateLimitedPoolBuffer, _RateLimitedTokenBuffer


class Event(Enum):
    RESPONSE = 'response'  # 2XX response
    ERROR = 'error'  # 4XX error
    UNCAUGHT = 'uncaught'  # unhandled error (and 5XX responses)


class NotBrokenList:
    def __init__(self) -> None:
        self.list = []

    def get(self, index: int) -> Any:
        return self.list[index]

    def set(self, index: int, value: Any) -> None:
        self.list[index] = value

    def len(self) -> int:
        return len(self.list)

    def pop(self, index: int) -> Any:
        return self.list.pop(index)

    def append(self, value: Any) -> None:
        self.list.append(value)

class _FastClientSyncManager(SyncManager):
    pass

# register synced variables
_FastClientSyncManager.register('rateLimitedTokenBuffer', _RateLimitedTokenBuffer)
_FastClientSyncManager.register('rateLimitedPoolBuffer', _RateLimitedPoolBuffer)
_FastClientSyncManager.register('poolManager', PoolManager)


class FastClient:
    def __init__(self,
                 ratelimit: float,
                 tokens: List[str],
                 pools: List = None,
                 threaded_callback: bool = False) -> None:
        print('init')
        self._manager = _FastClientSyncManager()
        print('starting manager')
        self._manager.start()
        print('instantiated manager')
        # create proxies for synced datastructures
        self._tokens = self._manager.rateLimitedTokenBuffer(1/ratelimit)
        self._pools = self._manager.rateLimitedPoolBuffer(1/ratelimit)
        self._responses = self._manager.Queue()
        self._requests = self._manager.Queue()
        self._completed = self._manager.list()
        self._context = self._manager.dict()
        self._active_workers = self._manager.Value('i', 0)
        print('instantiated synced datastructures')

        # create internal state
        self._listeners = defaultdict(list)
        self._listeners_registered = False

        # arguments
        self._ratelimit = ratelimit
        self._threaded_callback = threaded_callback

        # public state
        self.rps = 0.0
        print('finna initialise stuff')
        # initialize stuff
        # assuming one request doesn't take longer than 1 second, otherwise this may be inefficient
        self._pools.put(self._manager.poolManager(num_pools=1, maxsize=int(ratelimit)))
        for token in tokens:
            self._tokens.put(token)
        print('initialised stuff')

    def __getitem__(self, key: str) -> Any:
        return self._context[key]

    def __setitem__(self, key: str, value: Any):
        self._context[key] = value

    def _update_rps(self):
        time_ = time()
        while len(self._completed) != 0 and self._completed.pop(0) + 1 < time_:
            pass
        self.rps = len(self._completed)+1
        self._context.rps = self.rps

    def request(self, request, id=None):
        self._requests.put((request, id))

    def run(self):
        if not self._listeners_registered:
            raise ValueError('No listeners registered')  # TODO custom NoListenersError
        processes = []
        max_rps = self._pools.size()*(self._ratelimit-1)  # can never fully reach the ratelimit because of processing time.
        while not self._requests.empty() and self.rps < min(max_rps, self._requests.qsize()):
            print(self.rps)
            # scale up
            processes.append(
                Process(
                    name=f'fastclient-worker-{len(processes)}', target=_worker,
                    args=(self._requests, self._responses, self._pools, self._tokens, self._context,
                          self._completed, self._listeners, self._active_workers, self._threaded_callback),
                    daemon=(not self._threaded_callback)))
            processes[-1].start()
            sleep(1)
            self._update_rps()

        print('finished scaling up')
        while self._active_workers.value or not self._responses.empty():  # while everything is processing
            if self._threaded_callback:
                sleep(0.1)  # no need to update the rps that often
            self._update_rps()
            print(self.rps)
            if not self._threaded_callback:
                response = self._responses.get()
                if floor(response[0] % 100) == 2:
                    for listener in self._listeners[Event.RESPONSE]:
                        listener(self._context, response[1], response[2], lambda: None,
                                 lambda: None)  # TODO retry and stop methods
                elif floor(response[0] % 100) == 4:
                    for listener in self._listeners[Event.ERROR]:
                        listener(self._context, response[1], response[2], lambda: None, lambda: None)
                else:  # unhandled error
                    for listener in self._listeners[Event.UNCAUGHT]:
                        listener(self._context, response[1], response[2], lambda: None, lambda: None)

        # properly dispose of all processes
        for process in processes:
            process.join()
            process.close()

    def on(self, event: Event, callback: Callable[[Mapping, str, int, Callable[[], None], Callable[[], None]], None]):
        self._listeners[event].append(callback)
        self._listeners_registered = True


def _worker(
        requests: Queue, responses: Queue, pools: _RateLimitedPoolBuffer, tokens: _RateLimitedTokenBuffer,
        context: Mapping[str, Any],
        completed: List[float],
        listeners: Mapping[Event, List[Callable]],
        active_workers: int, threaded_callback: bool):
    active_workers.value += 1
    while not requests.empty():
        request, id = requests.get()
        try:
            fields = request['fields'] if 'fields' in request else {}
            fields['token'] = tokens.get()

            response = pools.get().request(request['method'], request['url'], fields, request['headers'] if 'headers' in request else {})
            completed.append(time())
            if threaded_callback:
                if floor(response.status % 100) == 2:
                    for listener in listeners[Event.RESPONSE]:
                        listener(context, response, id, lambda: None, lambda: None)
                elif floor(response.status % 100) == 4:
                    for listener in listeners[Event.ERROR]:
                        listener(context, response, id, lambda: None, lambda: None)
                else:  # unhandled error
                    for listener in listeners[Event.UNCAUGHT]:
                        listener(context, response, id, lambda: None, lambda: None)
            else:
                responses.put((response.status, response, id))
                print('put into backqueue')
        except Exception as e:
            if threaded_callback:
                for listener in listeners[Event.UNCAUGHT]:
                    listener(context, e, id, lambda: None, lambda: None)
            else:
                responses.put((999, e, id))
                print(e)
    active_workers.value -= 1
