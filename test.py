from time import time
from fastclient import FastClient
from fastclient.types import Request, RequestEvent
from fastclient.pools import RequestPool


def cb(response):
    print(f'received response {response.status} for request {response.id}')


if __name__ == '__main__':
    fc = FastClient(
        100, [RequestPool()])
    for i in range(100):
        fc.request(Request('GET', 'https://httpbin.org/get', id=i))
    fc.on(RequestEvent.RESPONSE, cb)
    start = time()
    fc.run()
    print(f'took {time()-start} seconds')
