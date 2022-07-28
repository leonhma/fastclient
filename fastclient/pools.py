from multiprocessing.connection import Connection, Pipe
from typing import Mapping

from urllib3 import PoolManager
from urllib3.response import HTTPResponse

from concurrent.futures import ThreadPoolExecutor

from fastclient.types import Request, Response


class RequestPool:
    def __init__(self, headers: Mapping[str, str] = None, id: int = None):
        self._headers = headers or {}
        self._id = id

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
        self._cpool = PoolManager(headers=self._headers, num_pools=num_pools, maxsize=max_connections, block=True)
        self._tpool = ThreadPoolExecutor(max_connections, 'FastClient-RequestPool')
        (conn1, conn2) = Pipe(duplex=False)
        self._sendpipe = conn2
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
        print('called _request')
        future = self._tpool.submit(RequestPool._handle_request, self._sendpipe, self._cpool,
                                    request.method, request.url, request.fields, request.headers, request.id)
        future.add_done_callback(RequestPool._handle_future)

    def _teardown(self):
        self._tpool.shutdown()

    @staticmethod
    def _handle_request(sendpipe, pool: PoolManager, method, url, fields, headers, id) -> HTTPResponse:
        print('making request')
        return sendpipe, Response(pool.request(method, url, fields, headers), id)

    @staticmethod
    def _handle_future(future):
        sendpipe, res = future.result()
        print('handling response')
        sendpipe.send(res)
