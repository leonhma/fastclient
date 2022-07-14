from fastclient import FastClient, Event

def cb(context, response, id, repeat, exit_):
    print(f'received response {response.status} for request {id}. current rps: {context["rps"]}')


if __name__ == '__main__':

    fc = FastClient(10, [])
    print('created client')
    for i in range(1):
        fc.request({'method': 'GET', 'url': 'https://httpbin.org/get'}, i)
    print('added 5 requests')
    fc.on(Event.RESPONSE, cb)
    print('reqistred cb')
    fc.run()
    print('ran client')
