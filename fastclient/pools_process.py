from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process, Queue, Value
from multiprocessing.connection import Connection, Pipe
from typing import Mapping, Set

from urllib3 import PoolManager, ProxyManager
from urllib3.contrib.socks import SOCKSProxyManager

from fastclient.types import Request, Response


class RequestPool:
    def __init__(self, headers: Mapping[str, str] = None, id_: int = None):
        """
        Initialise a RequestPool.

        Parameters
        ----------
        headers : Mapping[str, str], default=None
            The headers to use by default
        id_ : int, default=None
            The pool's id (used for ratelimit-grouping)
        """

        self.headers = headers
        self.id_ = id_
        self._cpool = None
        self._processes = None
        self._taskqueue = None
        self._max_processes = None
        self._remaining_tasks = None
        self._sendpipe = None

    def _setup(self, num_pools: int, max_connections: int) -> Connection:
        """
        Set up the connection pool with parameters determined at runtime.

        Parameters
        ----------
        num_pools : int
            The number of pools to keep open.
        max_connections : int
            The maximum number of connections to open.

        Returns
        -------
        Connection
            The end of a Pipe. This will receive the responses.
        """

        self._cpool = PoolManager(headers=self.headers, num_pools=num_pools, maxsize=max_connections, block=True)
        self._processes: Set[Process] = set()

        self._taskqueue = Queue()
        self._max_processes = max_connections
        self._remaining_tasks = Value('L', 0)
        (conn1, conn2) = Pipe(duplex=False)
        self._sendpipe = conn2
        for i in range(self._max_processes):
            self._processes.add(Process(
                target=RequestPool._worker,
                name=F'FastClient-requestpool-{self.id_ or "X"}-{i}',
                args=(self._taskqueue, self._sendpipe, self._cpool, self._remaining_tasks)
            ))
        for process in self._processes:
            process.start()
        return conn1

    def _request(self, request: Request):
        """
        Apply a request to the pool.

        Parameters
        ----------
        request : Request
            The request object.

        Note
        ----
            This method asynchronously returns the result via the pipe returned by :meth:`_setup`.
        """

        self._remaining_tasks.value += 1
        self._taskqueue.put(request)

    def _get_remaining_tasks(self) -> int:
        """Get the number of remaining tasks."""
        return self._remaining_tasks.value

    def _teardown(self):
        """Shutdown the pool."""
        for process in self._processes:
            process.kill()
        for process in self._processes:
            process.join()
        self._taskqueue.close()
        self._sendpipe.close()

    @staticmethod
    def _worker(inqueue: Queue, sendpipe: Connection, pool: PoolManager, remaining_tasks):
        while True:
            req: Request = inqueue.get(block=True)
            res = Response(pool.request(req.method, req.url, req.fields, req.headers), req.id)
            remaining_tasks.value -= 1
            sendpipe.send(res)
