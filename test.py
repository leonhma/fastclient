from fastclient.pooled import FastClient, Event
from fastclient.data import Request, FastClientPool


def cb(context, response, repeat, exit_):
    if 'cnt' not in context:
        context['cnt'] = 0
    context['cnt'] += 1
    print(f'received response {response.status} for request {response.id}. current ctx: {context}')


def cb_err(context, response, repeat, exit_):
    print(f'received err {response.status} for request {response.id}. current ctx: {context}')


def cb_unh(context, error, repeat, exit_):
    print(f'received unhandled for request {error.id}: {error.error}. current ctx: {context}')


if __name__ == '__main__':

    fc = FastClient(
        100, 10, [],
        [FastClientPool(None)],
        None, None, False)
    for i in range(50):
        fc.request(Request('GET', 'https://httpbin.org/get', id=i))
    fc.on(Event.RESPONSE, cb)
    fc.on(Event.ERROR, cb_err)
    fc.on(Event.UNCAUGHT, cb_unh)
    fc.run()
