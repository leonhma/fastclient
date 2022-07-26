from collections import defaultdict
from queue import Queue
from random import randrange
from time import sleep, time


class _BaseRateLimitedItemBuffer:
    def __init__(self, seconds_per_view: float = float('+inf')):
        # how many times an item can be 'viewed' per second
        self._seconds_per_view = seconds_per_view

        self._items = []
        self._next_view = []

    def put(self, item):
        self._items.append(item)
        self._next_view.append(0)

    def get(self):
        raise NotImplementedError('Subclass this and provide a custom get method!')

    def size(self):
        return len(self._items)

    def empty(self):
        return self.size() == 0


class _RateLimitedTokenBuffer(_BaseRateLimitedItemBuffer):
    """A rate-limited buffer that returns a random item from the buffer."""

    def get(self):
        if self.empty():
            return None
        idx = randrange(0, len(self._items))
        while self._next_view[idx] >= time():
            idx = randrange(0, len(self._items))
        self._next_view[idx] = time() + self._seconds_per_view
        return self._items[idx]


class RateLimitedQueue(Queue):
    def __init__(self, rate: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rate = rate
        self._last_items = defaultdict(list)

    def get(self, block=True, timeout=None, id=0):
        time_ = time()
        # remove items more than one second ago
        if len(self._last_items[id]) > 0:
            while self._last_items[id][0] + 1 < time_ and len(self._last_items[id]) > 1: # TODO list index out of range
                self._last_items[id].pop(0)
        # return RateLimited if rate limited
        if len(self._last_items[id]) >= self._rate:
            return RateLimitedFlag
        # get item
        self._last_items[id].append(time_)
        return super().get(block, timeout)

    def get_id(self):
        id_ = randrange(0, (2**32))
        while id in self._last_items:
            id_ = randrange(0, (2**32))
        return id_

    def get_rps(self, id_=None):
        """
        Get the number of requests made in the last second.

        Parameters
        ----------
        id_ : int, optional
            The id of the limit to get this data for, by default returns the average of all rps values.

        Returns
        -------
        int
            The number of requests made in the last second.
        """
        time_ = time()
        for id__ in self._last_items:
            while len(self._last_items[id__]) > 0 and self._last_items[id__][0] + 1 < time_:
                self._last_items[id__].pop(0)
        if id_ is None:
            return sum(len(self._last_items[id__]) for id__ in self._last_items) / len(self._last_items)
        else:
            return len(self._last_items[id_])

class RateLimitedFlag:
    pass
