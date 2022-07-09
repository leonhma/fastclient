from multiprocessing import Value
from time import sleep
from fastclient.threaded import HTTPWorkerPool

recv = Value('i', 0)
def cb(res):
    global recv
    recv.value += 1
    print('response')


if __name__ == '__main__':
    pool = HTTPWorkerPool(10, 1, 16)
    for _ in range(100):
        pool.submit({'method': 'GET', 'url': 'https://httpbin.org/get'}, cb)

    for _ in range(10):
        sleep(1)
        print(pool.rps.value)

    print(f'sent: 100 recevied: {recv.value}')
