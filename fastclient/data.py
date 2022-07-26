from multiprocessing import Pool
from urllib3 import PoolManager, ProxyManager
from urllib3.contrib.socks import SOCKSProxyManager
from urllib3.response import HTTPResponse


class Request:
    def __init__(self, method, url, fields=None, headers=None, id=None):
        self.method = method
        self.url = url
        self.fields = fields or {}
        self.headers = headers or {}
        self.id = id

    def add_auth_header(self, key, value):
        self.headers[key] = value

    def add_auth_field(self, key, value):
        self.fields[key] = value


class Response:
    """
    A wrapper for urllib3.response.HTTPResponse that doesn't include the `pool` and `connection` attributes.
    """

    def __init__(self, response: HTTPResponse, id):
        self.headers = response.headers
        self.status = response.status
        self.version = response.version
        self.reason = response.reason
        self.strict = response.strict
        self.decode_content = response.decode_content
        self.msg = response.msg
        self.retries = response.retries
        self.enforce_content_length = response.enforce_content_length
        self.id = id


class Error:
    def __init__(self, error: Exception, id: str):
        self.error = error
        self.id = id


def _request(pool, method, url, fields, headers):
    return pool.request(method, url, fields, headers)


class FastClientPool:
    def __init__(self, headers, id: int = None):
        self.headers = headers
        self._id = id
        self._pool = None

    def __call__(self, num_pools, ratelimit) -> PoolManager:
        # assuming one request doesn't take longer than 2 seconds, otherwise this may be inefficient
        self._mngr = PoolManager(num_pools=num_pools, headers=self.headers, maxsize=ratelimit*2)
        self._mngr.id = self._id
        self._pool = Pool(ratelimit*2)

    def request(self, request: Request) -> Response:
        return Response(
            self._pool.apply_async(
                _request, (self._mngr, request.method, request.url, request.fields, request.headers), request.id))

    def __str__(self) -> str:
        return self.__class__.__name__


class FastClientProxyPool(FastClientPool):
    def __init__(self, headers, proxy_url, proxy_headers, proxy_ssl_context, use_forwarding_for_https, id: int = None):
        self.headers = headers
        self.proxy_url = proxy_url
        self.proxy_headers = proxy_headers
        self.proxy_ssl_context = proxy_ssl_context
        self.use_forwarding_for_https = use_forwarding_for_https
        self._id = id

    def __call__(self, num_pools, ratelimit) -> ProxyManager:
        # assuming one request doesn't take longer than 2 seconds, otherwise this may be inefficient
        mngr = ProxyManager(num_pools=num_pools, headers=self.headers, maxsize=ratelimit*2)
        mngr.id = self._id
        return mngr


class FastClientSOCKSProxyPool(FastClientPool):
    def __init__(self, headers, proxy_url, username, password, id: int = None):
        self.headers = headers
        self.proxy_url = proxy_url
        self.username = username
        self.password = password
        self._id = id

    def __call__(self, num_pools, ratelimit) -> SOCKSProxyManager:
        # assuming one request doesn't take longer than 2 seconds, otherwise this may be inefficient
        mngr = SOCKSProxyManager(
            num_pools=num_pools, headers=self.headers, maxsize=ratelimit*2)
        mngr.id = self._id
        return mngr
