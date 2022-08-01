from time import time
from fastclient import FastClient
from fastclient.types import Request, RequestEvent
from fastclient.pools import SOCKSProxyRequestPool, ProxyRequestPool, RequestPool


def cb(response, ctx):
    if 'num' not in ctx:
        ctx['num'] = 0
    ctx['num'] += 1
    print(f'received response {response.status} for request {response.id}. {ctx["num"]=}')


if __name__ == '__main__':
    fc = FastClient(
        100, [RequestPool()])
    for i in range(100):
        fc.request(Request('GET', 'https://httpbin.org/get', id=i))
    fc.on(RequestEvent.RESPONSE, cb)
    start = time()
    fc.run()
    print(f'took {time()-start} seconds')
