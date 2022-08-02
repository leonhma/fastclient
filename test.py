from time import time
from fastclient import FastClient
from fastclient.types import Request, RequestEvent
from fastclient.pools import SOCKSProxyRequestPool, ProxyRequestPool, RequestPool


def cb(response, ctx):
    print(f'received response {response.status} for request {response.id}. {ctx["rps"]=}')


if __name__ == '__main__':
    fc = FastClient(
        1000, [RequestPool()], use_store=False)
    for i in range(10000):
        fc.request(Request('GET', 'https://httpbin.org/get', id=i))
    fc.on(RequestEvent.RESPONSE, cb)
    start = time()
    fc.run()
    print(f'took {time()-start} seconds')
