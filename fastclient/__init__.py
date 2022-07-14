from multiprocessing import JoinableQueue, Pool, Value
from multiprocessing.dummy import Process
from time import time
from typing import Callable

import requests
from requests import Request, Response


# TODO automatically scale up processes
class HTTPWorkerPool:
    """A multithreaded http client with a rate limit.

    Attributes
    ----------
        rps : multiprocessing.Value
            The current rate of requests per second. Access the value via `rps.value`.

    """

    def __init__(self, requests: int, period: float, processes: int = None, daemon: bool = False):
        """Initialize the worker pool.

        Parameters
        ----------
        requests : int
            The number of requests to send per period.
        period : float
            The period of time in seconds.
        processes : int, optional, default=os.cpu_count()
            The number of processes to use.
        daemon : bool, optional, default=False
            Whether to run in daemon mode. If `True`, the pool will be stopped when the program ends.
            If `False`, the program will continue running until all requests are finished.

        Raises
        ------


        """
        self._pool = Pool(processes=processes)  # name 'em
        self._queue = JoinableQueue()
        self._daemon = daemon
        self.rps = Value('f', 0.0)
        self._running = Value('b', True)
        self._manager = Process(name='fastclient-manager', target=self._manager_, args=(period,
                                requests, self._pool, self._queue, self.rps, self._running))
                                
        self._manager.daemon = True
        self._manager.start()

    def __del__(self):
        self.join()

    def _manager_(self, period, requests, pool, queue, rps, running):
        limited = False
        current_requests = 0
        last_clear = 0.0

        while running.value:
            if queue.empty():
                continue  # keep waiting for input. If join wasn't called, it will still be used.

            if current_requests >= requests:
                limited = True

            current_time = time()

            if last_clear + period <= current_time:
                rps.value = current_requests/(current_time-last_clear)
                last_clear = current_time
                limited = False
                current_requests = 0

            if not limited:
                print(f'in queue {queue.qsize()}')
                print(f'running worker, {current_requests=}, {last_clear=}')
                pool.apply_async(self._worker, queue)
                current_requests += 1

    def _worker(self, queue: JoinableQueue):
        (req, cb) = queue.get()
        print(f'worker: {req=}, {cb=}')
        print('calling cb')
        cb(requests.send(req.prepare()))
        queue.task_done()

    def _terminate(self):
        """Terminate the worker pool. If you want to use this, call `del <HTTPWorkerPool>` instead."""
        self._manager.terminate()
        self._pool.terminate()
        self._manager.join()
        self._pool.join()

    def join(self):
        """Wait for all submitted requests to finish. Blocks submission of further tasks."""
        self._queue.close()
        self._queue.join()
        self._running.value = False
        self._manager.join()
        self._pool.close()
        self._pool.terminate()
        self._pool.join()

    def submit(self, request: Request, callback: Callable[[Response], None]):
        """Submit a request to the worker pool.

        Parameters
        ----------
        request : Request
            The request object to fulfill.
        callback : Callable[[Response], None]
            The callback to call with the response.

        Raises
        ------

        """
        self._queue.put((request, callback))  # raises