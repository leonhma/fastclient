from multiprocessing import JoinableQueue, Pool, Queue, Value
from multiprocessing.dummy import Process
from time import sleep, time
from typing import Callable, Optional

import requests
from requests import Request, Response


def _worker(running, p: Queue):
    """Run tasks on the processing queue."""
    while running.value:
        if p.empty():
            sleep(0.01)
        request, callback = p.get()
        print('doing request')
        response = requests.request(request['method'], request['url'])
        callback(response)
        p.task_done()


class HTTPWorkerPool:
    """A multithreaded http client with a rate limit.

    Attributes
    ----------
        rps : multiprocessing.Value
            The current rate of requests per second. Access the value via `rps.value`.

    """

    def __init__(
            self, requests: int, period: float, processes: Optional[int] = None):
        """Initialize the worker pool.

        Parameters
        ----------
        requests : int
            The number of requests to send per period.
        period : float
            The period of time in seconds.
        processes : int, optional, default=os.cpu_count()
            The number of processes to use.

        Raises
        ------


        """
        self._queue = JoinableQueue()
        self._processing = JoinableQueue()
        self.rps = Value('f', 0.0)
        self._running = Value('b', True)
        self._ratelimiter = Process(name='fastclient-ratelimiter', target=self._ratelimiter_,
                                    args=(requests, period, self.rps, self._running, self._queue, self._processing))
        self._ratelimiter.daemon = True
        self._ratelimiter.start()
        self._workers = Pool(processes=processes, initializer=_worker,
                             initargs=(self._running, self._processing), maxtasksperchild=50)

    def __del__(self):  # keep running until everything is done if this is garbage-collected
        self.join()

    def _ratelimiter_(self, requests, period, rps, running, q: Queue, p: Queue):
        """Move items between queue and processing according to the ratelimit."""
        limited = False
        current_requests = 0
        last_clear = 0.0

        while running.value:
            if q.empty():
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
                print(f'{q.qsize()=}, {p.qsize()=}')
                p.put(q.get())
                q.task_done()
                current_requests += 1

    def join(self):
        """Wait for all submitted requests to finish. Blocks submission of further tasks."""
        print('closing queue')
        self._queue.close()
        print('joining queue')
        self._queue.join()
        print('closing processing')
        self._processing.close()
        print('joining processing')
        self._processing.join()
        print('closing ratelimiter')
        self._running.value = False
        print('closing workers')
        self._workers.close()
        print('terminating workers')
        self._workers.terminate()
        print('joining workers')
        self._workers.join()

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
