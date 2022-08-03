from time import time
from fastclient import FastClient
from fastclient.types import Request, RequestEvent
from fastclient.pools import RequestPool

# the callback


def cb(response, ctx):
    print(f'received response {response.status} for request {response.id}. {ctx["rps"]=}')


# create the fastclient
fc = FastClient(100, [RequestPool(), RequestPool()], use_store=False)
# queue 10 requests to httpbin.org
for i in range(1000):
    fc.request(Request('GET', 'https://httpbin.org/get', id=i))
# register the listener for response events
fc.on(RequestEvent.RESPONSE, cb)

# save the start time
start_time = time()

# run all requests
fc.run()

# print out the time measurement
print(f'took {time()-start_time} seconds')
