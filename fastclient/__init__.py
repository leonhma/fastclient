from collections import defaultdict
from multiprocessing import JoinableQueue, Lock, Manager, Process
from multiprocessing.connection import Connection, Pipe
from multiprocessing.connection import wait as wait_for_connection
from queue import Empty
from time import time
from typing import Any, Callable, Iterable, List, Mapping

from fastclient.errors import NoListenersError
from fastclient.pools import RequestPool
from fastclient.types import Request, RequestEvent, Response
from threading import Lock

# TODO parameters (rate) and context dicts passed to callbacks


class FastClient():
    """
    Wicked-fast API-client that supports rate-limiting, proxy rotation, token rotation and multiprocessing.
    """

    def __init__(
            self, rate: float, pools: List[RequestPool],
            num_pools: int = 8, max_connections: int = None, use_context: bool = True) -> None:
        """
        Initialize the client.

        Parameters
        ----------
        rate : float
            The request ratelimit in requests per second
        pools : List[RequestPool]
            The list of request pools to use
        tokens : List[str]
            The list of tokens to use
        auth_mode : str
            The auth mode TODO
        auth_field_name : str
            The name of the auth field. (eg. 'Authorization' or 'key')
        num_pools : int, default = 8
            The number of pools to different hosts to keep open
        max_connections : int, default = None
            The maximum number of open connections. If a single request takes longer than one second, this will be a limit to the request speed,
            although setting this higher might cause rate-limiting by the API
        """
        self._rate = rate
        self._pools = pools
        # rate limited token queue
        self._requests = JoinableQueue()
        self._num_pools = num_pools
        self._max_connections = max_connections or self._rate

        self._use_context = use_context

        self._context_manager = Manager() if self._use_context else None
        self._context = self._context_manager.dict() if self._use_context else None
        self._context_lock = self._context_manager.Lock() if self._use_context else None

        self._callbacks = defaultdict(list)
        self._callback_registered = False

    def on(self, event: RequestEvent, callback: Callable[[Response], None]):
        """
        Set up a callback for e specific event.

        Parameters
        ----------
        event : RequestEvent
            The event to listen for
        callback : Callable[[Response, Mapping[str, Any]], None]
            A callback that receives the response and the context (this is synchronized between callbacks)
        """

        self._callbacks[event].append(callback)
        self._callback_registered = True

    def request(self, request: Request):
        """
        Add a request to the processing queue.

        Parameters
        ----------
        request : Request
            The request object.

        Note
        ----
            This method only stages the requests. Call :meth:`run` to start the processing.
            All responses will trigger their respective callbacks, which have been registered via :meth:`on`.
        """
        self._requests.put(request)

    def run(self):
        if not self._callback_registered:
            raise NoListenersError("No callback registered. Use FastClient.on to register a callback.")

        controllers: List[Process] = []
        # create groups based on the RequestPool's ids
        poolgroups = defaultdict(list)
        pools = []
        for pool in self._pools:
            if pool.id_ is None:
                pools.append(pool)
            else:
                poolgroups[pool.id_].append(pool)

        # create ticket connections
        connections = [Pipe() for _ in range(len(pools)+len(poolgroups))]
        ticket_recvs, ticket_sends = ([i for i, _ in connections], [j for _, j in connections])
        del connections

        # create their controllers
        controllers.extend(
            Process(
                name='FastClient-controller',
                target=FastClient._controller,
                args=((pool,),
                      self._num_pools, self._max_connections, self._requests, ticket_recvs.pop(),
                      self._callbacks, self._use_context, self._context_lock, self._context)) for pool in pools)
        del pools

        controllers.extend(
            Process(
                name='FastClient-controller',
                target=FastClient._controller,
                args=(tuple(poolgroup),
                      self._num_pools, self._max_connections, self._requests, ticket_recvs.pop(),
                      self._callbacks, self._use_context, self._context_lock, self._context))
            for poolgroup in poolgroups.values())
        del poolgroups

        # start all controllers
        for controller in controllers:
            controller.start()

        # start ticket creation
        tickets = Process(name='FastClient-ticket-manager',
                          target=FastClient._create_tickets, args=(self._rate, ticket_sends))
        tickets.start()

        # now all the processing happens...

        # wait for request queue to be empty
        self._requests.close()
        self._requests.join()

        # stop ticket creation
        tickets.terminate()
        tickets.join()

        # wait for all controllers to finish
        for controller in controllers:
            controller.join()

    @staticmethod
    def _controller(pools: Iterable[RequestPool],
                    num_pools: int,
                    max_connections: int,
                    requests: JoinableQueue,
                    tickets: Connection,
                    callbacks: Mapping[RequestEvent, Callable],
                    use_context: bool,
                    context_lock: Lock,
                    context: Mapping[str, Any]):
        # setup all connections to the attached RequestPools
        try:
            connections = [pool._setup(num_pools, max_connections) for pool in pools]
            counter = 0
            while True:
                try:
                    if counter == 0 and requests.empty() and max(pool._get_remaining_tasks() for pool in pools) == 0:
                        break
                    # check if a ticket is available
                    if tickets.poll():
                        tickets.recv()
                        # choose the least busy pool
                        pool = min(pools, key=lambda p: p._get_remaining_tasks())
                        # make the request
                        pool._request(requests.get(block=False))
                        counter += 1
                        requests.task_done()
                    # check if a response is available
                    for connection in wait_for_connection(connections, timeout=0):
                        result = connection.recv()
                        counter -= 1
                        # call the callbacks
                        if use_context:
                            context_lock.acquire()
                        if type(result) == Response:
                            for callback in callbacks[RequestEvent.RESPONSE]:
                                callback(result, context) if use_context else callback(result)
                        else:
                            for callback in callbacks[RequestEvent.ERROR]:
                                callback(result, context) if use_context else callback(result)
                        if use_context:
                            context_lock.release()
                except Empty:
                    pass
        finally:
            # close all pools
            for pool in pools:
                pool._teardown()
                del pool

    @staticmethod
    def _create_tickets(rate: float, connections: List[Connection]):
        # create tickets at the rate limit per connection and send them to the controllers
        last_tickets = 0
        while True:  # this is meant to be manually terminated
            time_ = time()
            if time_ - last_tickets > 1 / rate:
                for connection in connections:
                    connection.send('ticket')
                last_tickets = time_
