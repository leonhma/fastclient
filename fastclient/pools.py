from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Value
from multiprocessing.connection import Connection, Pipe
from typing import Mapping

from urllib3 import PoolManager, ProxyManager
from urllib3.contrib.socks import SOCKSProxyManager
from urllib3.response import HTTPResponse

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
        self._tpool = None
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
        self._tpool = ThreadPoolExecutor(max_connections, 'FastClient-RequestPool')
        self._remaining_tasks = Value('L', 0)
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

        self._remaining_tasks.value += 1
        future = self._tpool.submit(RequestPool._handle_request, self._sendpipe, self._remaining_tasks, self._cpool,
                                    request.method, request.url, request.fields, request.headers, request.id)
        future.add_done_callback(RequestPool._handle_future)

    def _get_remaining_tasks(self) -> int:
        """Get the number of remaining tasks."""
        return self._remaining_tasks.value

    def _teardown(self):
        """Shutdown the pool."""
        self._tpool.shutdown(wait=False)
        self._sendpipe.close()

    @staticmethod
    def _handle_request(sendpipe, remaining_tasks, pool: PoolManager, method, url, fields, headers, id) -> HTTPResponse:
        return sendpipe, remaining_tasks, Response(pool.request(method, url, fields, headers), id)

    @staticmethod
    def _handle_future(future):
        sendpipe, remaining_tasks, res = future.result()
        sendpipe.send(res)
        remaining_tasks.value -= 1


class ProxyRequestPool(RequestPool):  # TODO test
    def __init__(
            self, proxy_url: str, headers: Mapping[str, str] = None, proxy_headers: Mapping[str, str] = None,
            proxy_ssl_context=None, use_forwarding_for_https: bool = False, id_: int = None):
        """
        Initialise a ProxyRequestPool.

        Parameters
        ----------
        proxy_url : str
            The url of the proxy
        headers : Mapping[str, str], default=None
            The headers to use by default
        proxy_headers : Mapping[str, str]
            The headers to send for the proxy
        proxy_ssl_context : Any
            The ssl context to use for the proxy when using HTTPS
        use_forwarding_for_https : bool
            The HTTPS request will originate from the proxy and will not be made via a prior established tunnel
        id_ : int, default=None
            The pool's id (used for ratelimit-grouping)
        """

        self.proxy_url = proxy_url
        self.headers = headers
        self.proxy_headers = proxy_headers
        self.proxy_ssl_context = proxy_ssl_context
        self.use_forwarding_for_https = use_forwarding_for_https
        self.id_ = id_
        self._cpool = None
        self._tpool = None
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

        self._cpool = ProxyManager(self.proxy_url, num_pools, self.headers, self.proxy_headers,
                                   self.proxy_ssl_context, self.use_forwarding_for_https, maxsize=max_connections, block=True)
        self._tpool = ThreadPoolExecutor(max_connections, 'FastClient-ProxyRequestPool')
        self._remaining_tasks = Value('L', 0)
        (conn1, conn2) = Pipe(duplex=False)
        self._sendpipe = conn2
        return conn1


class SOCKSProxyRequestPool(RequestPool):
    def __init__(
            self, proxy_url: str, username: str = None, password: str = None, headers: Mapping[str, str] = None, id_:
            int = None):
        """
        Initialise a RequestPool.

        Parameters
        ----------
        proxy_url : str
            The url of the socks proxy
        username : str, default=None
            The username to use for the proxy
        password : str, default=None
            The password to use for the proxy
        headers : Mapping[str, str], default=None
            The headers to use by default
        id_ : int, default=None
            The pool's id (used for ratelimit-grouping)
        """

        self.proxy_url = proxy_url
        self.username = username
        self.password = password
        self.headers = headers
        self.id_ = id_
        self._cpool = None
        self._tpool = None
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

        self._cpool = SOCKSProxyManager(self.proxy_url, self.username, self.password,
                                        num_pools, self.headers, maxsize=max_connections, block=True)
        self._tpool = ThreadPoolExecutor(max_connections, 'FastClient-RequestPool')
        self._remaining_tasks = Value('L', 0)
        (conn1, conn2) = Pipe(duplex=False)
        self._sendpipe = conn2
        return conn1
