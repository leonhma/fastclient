import unittest
from fastclient import FastClient

from fastclient.pools import RequestPool
from fastclient.types import Request, RequestEvent


class PoolTest(unittest.TestCase):
    def test_rate(self):
        def cb(_r, c):
            c['store']['rps'] = c['rps']

        fastclient = FastClient(50, [RequestPool()])
        for _ in range(100):
            fastclient.request(Request('GET', 'https://httpbin.org/get'))
        fastclient.on(RequestEvent.RESPONSE, cb)
        fastclient.run()
        self.assertLessEqual(fastclient['rps'], 50)

