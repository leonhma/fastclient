from collections import defaultdict
from multiprocessing import JoinableQueue, Process
from multiprocessing.connection import Connection, Pipe, wait as wait_for_connection
from random import choice
from time import time
from typing import Any, Callable, Iterable, List, Mapping
from fastclient.errors import NoListenersError
from fastclient.pools import RequestPool
from fastclient.types import Request, RequestEvent, Response

# TODO parameters (rate) and context dicts passed to callbacks


class FastClient():
    """
    Wicked-fast API-client that supports rate-limiting, proxy rotation, token rotation and multiprocessing.
    """

    def __init__(
            self, rate: float, pools: List[RequestPool],
            tokens: List[str],
            auth_mode: str, auth_field_name: str, /, num_pools: int = 8,
            max_connections: int = None) -> None:
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
        self._auth_mode = auth_mode
        self._auth_field_name = auth_field_name
        self._num_pools = num_pools
        self._max_connections = max_connections or self._rate

        self._callbacks = defaultdict(list)
        self._callback_registered = False

    def on(self, event: RequestEvent, callback: Callable[[Response, Mapping[str, Any]], None]):  # cb(res, ctx)
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
        # TODO start a controller server for synchronization purposes, excange locks for context manipulation, hand out 'tickets' to the controllers
        if not self._callback_registered:
            raise NoListenersError("No callback registered. Use FastClient.on to register a callback.")

        controllers: List[Process] = []
        # create groups based on the RequestPool's ids
        poolgroups = defaultdict(list)
        pools = []
        for pool in self._pools:
            if pool._id is None:
                pools.append(pool)
            else:
                poolgroups[pool._id].append(pool)

        # create ticket connections
        connections = [Pipe() for _ in range(len(pools)+len(poolgroups))]
        ticket_recvs, ticket_sends = ([i for i, _ in connections], [j for _, j in connections])

        # start their controllers
        print(f'callbacks are: {self._callbacks=}')
        controllers.extend(
            Process(
                name='FastClient-controller',
                target=FastClient._controller,
                args=((pool,),
                      self._num_pools, self._max_connections, self._requests, ticket_recvs.pop(),
                      self._callbacks)) for pool in pools)
        controllers.extend(
            Process(
                name='FastClient-controller',
                target=FastClient._controller,
                args=(tuple(poolgroup),
                      self._num_pools, self._max_connections, self._requests, ticket_recvs.pop(),
                      self._callbacks))
            for poolgroup in poolgroups.values())

        print("Starting controllers...")
        # start all controllers
        for controller in controllers:
            controller.start()

        print('starting ticket creation')
        # start ticket creation
        tickets = Process(name='FastClient-ticket-manager', target=FastClient._create_tickets, args=(self._rate, ticket_sends))
        tickets.start()

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
    def _controller(pools: Iterable[RequestPool], num_pools: int, max_connections: int,
                    requests: JoinableQueue, tickets: Connection, callbacks: Mapping[RequestEvent, Callable]):
        # setup all connections to the attached RequestPools
        connections = [pool._setup(num_pools, max_connections) for pool in pools]
        while True:
            if requests.empty() and max(pool._get_remaining_tasks() for pool in pools) == 0:
                break
            # wait for a ticket
            if tickets.poll():
                tickets.recv()
                # choose the least busy pool
                pool = choice(pools)
                # make the request
                pool._request(requests.get(block=False))
                requests.task_done()
            # await the responses from the connections
            for connection in wait_for_connection(connections, timeout=0):
                result = connection.recv()
                print(f'got response {type(result)}')
                if type(result) == Response:
                    for callback in callbacks[RequestEvent.RESPONSE]:
                        print('calling cb')
                        callback(result)
                else:
                    for callback in callbacks[RequestEvent.ERROR]:
                        callback(result)
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
                    print('sending a ticket')
                    connection.send('ticket')
                last_tickets = time_
