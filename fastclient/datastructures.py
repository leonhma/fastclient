from random import randrange
from time import sleep, time


class _BaseRateLimitedItemBuffer:
    def __init__(self, seconds_per_view: float = float('+inf')):
        # how many times an item can be 'viewed' per second
        self._sec_per_view = seconds_per_view

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
        idx = randrange(0, len(self._items))
        while self._next_view[idx] >= time():
            idx = randrange(0, len(self._items))
        self._next_view[idx] = time() + self._seconds_per_view
        return self._items[idx]


class _RateLimitedPoolBuffer(_BaseRateLimitedItemBuffer):
    """A rate-limited buffer that returns the left-most item that isn't rate-limited from the list."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._idx = 0

    def get(self):
        time_ = time()
        if self._next_view[self._idx] > time_:  # if the current item is rate-limited
            self._idx += 1  # go one right
            if self._idx >= len(self._items):
                self._idx = 0
            if self._next_view[self._idx] > time_:  # everything is rate-limited
                sleep(min(self._next_view)-time_)
                return self.get()

        self._next_view[self._idx] = time_ + self._seconds_per_view
        return self._items[self._idx]
