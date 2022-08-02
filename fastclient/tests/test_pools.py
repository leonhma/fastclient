from multiprocessing.connection import Connection
import unittest

from fastclient.pools import RequestPool
from fastclient.types import Request

class PoolTest(unittest.TestCase):
    def setUp(self):
        self.pool = RequestPool()
        self.conn = self.pool._setup(8, 8)

    def test_setup_return(self):
        self.assertEqual(type(self.conn), Connection)

    def test_request(self):
        self.pool._request(Request('GET', 'https://httpbin.org/get', id=999))
        self.assertEqual(self.conn.poll(5), True)  # assert that a response is received
        response = self.conn.recv()
        self.assertEqual(response.status, 200)  # assert a response of 200
        self.assertEqual(response.id, 999)  # assert the id is carried
