from enum import Enum
from queue import LifoQueue
from typing import Callable
from multiprocessing import JoinableQueue, Value
from multiprocessing.managers import BaseManager
from urllib3 import HTTPConnectionPool


class Event(Enum):
    RESPONSE = 'response'  # 2XX response
    ERROR = 'error'  # 4XX error
    UNCAUGHT = 'uncaught'  # unhandled error (and 5XX responses)
        
class LIFOManager(BaseManager):
    pass

class FastClientContext:
    def __init__(self, manager):
        self.manager = manager
        self.manager.start()

    def retry(self):
        pass

    def exit(self, code: int):
        pass

    def set(self, key, val):
        self.manager.set(key, val)



LIFOManager.register('LIFOQueue', LifoQueue)

class FastClient:
    def __init__(self, host, port,
        requests, seconds, timeout,
        auth_strategy, auth_field_name,
        tokens, proxys, max_connections_per_ip) -> None:
        manager = LIFOManager()
        self._host = host
        self._port = port
        self._requests = requests
        self._seconds = seconds
        self._timeout = timeout
        self._auth_strategy = auth_strategy
        self._auth_field_name = auth_field_name
        self._tokens = manager.LIFOQueue()
        self._queue = JoinableQueue()
        self._connection_pools = []
        self._listeners = {key: [] for key in Event._member_names_}


        pass

    def on(self, event: Event, callback: Callable[[str, int], None]):  # pass the request id
        self._listeners[event].append(callback)

    def request(self, request: str) -> int:  # return a request id
        self._queue.put(request)

    def join(self):  # wait for all currently submitted tasks to complete
        pass

    def cb(self, response, rerun, end, context):
        pass

    # host
    # port
    # timeout
    # n_requests
    # n_seconds
    # auth_startegy: query | header
    # auth_field_name: "Authorization", "key", ...
    # tokens : iterable of string
    # proxys : optional iterable of proxies
    # max_connections_per_ip : int

