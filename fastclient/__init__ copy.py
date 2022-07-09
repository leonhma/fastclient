from multiprocessing import JoinableQueue, Pool, Queue, Value
from multiprocessing.dummy import Process
from time import time
from typing import Callable, Optional

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

    def __init__(
            self, requests: int, period: float, min_processes: Optional[int],
            max_processes: Optional[int],
            daemon: bool = False):
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
        self._processes = Queue(maxsize=max_processes)
        self._queue = JoinableQueue()
        self._processing = JoinableQueue()
        self.rps = Value('f', 0.0)
        self._running = Value('b', True)
        self._manager = Process(name='fastclient-process-manager', target=self._manager_, args=(period,
                                requests, self._processes, self._queue, self.rps, self._running))
        self._manager.daemon = True
        self._ratelimiter = Process(name='fastclient-ratelimiter', target=self._ratelimiter_, args=(period,))
        self._ratelimiter.daemon = True
        self._ratelimiter.start()
        self._manager.start()

    def __del__(self):
        self.join()

    def _manager_(self, period, requests, processes, queue, rps, running, processing: Queue, min_processes=0,):
        """Scale up workers if needed."""
        while running.value:
            if processes.full():  # no scaling up
                continue
            # scale up if there is stuff to process and the current rps isn't right below the ratelimit
            if processing.qsize() > 0 and rps+1 < (requests/period):
                processes.put(Process(name='fastclient-worker', target=self._worker,
                              args=(running, processing)))
            # scale down if there has been no stuff to process for one period
            elif processing.empty() and queue.empty():
                process = processes.get()
                process.terminate()


    def _ratelimiter_(self, requests, period):
        """Move items between queue and processing according to the ratelimit."""

    def _worker(self, running, p: Queue):
        """Run tasks on the processing queue."""
        while running.value:
            request, callback = p.get()
            response = requests.request(request.method, request.url, **request.kwargs)
            callback(response)
            p.task_done()

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
