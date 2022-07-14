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


class _RateLimitedPoolBuffer(_BaseRateLimitedItemBuffer):
    """A rate-limited buffer that returns the left-most item that isn't rate-limited from the list."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._idx = 0

    def get(self):
        time_ = time()
        prev_idx = self._idx
        while self._idx > 0 and self._next_view[self._idx] > time_:
            self._idx -= 1
            if self._next_view[self._idx] <= time_:
                break
        else:
            self._idx = prev_idx
            if self._next_view[self._idx] > time_:
                while self._idx < len(self._items) - 1:
                    self._idx += 1
                    if self._next_view[self._idx] <= time_:
                        break
                else:
                    sleep_ = min(self._next_view)-time_
                    sleep_ = max(sleep_, 0)
                    sleep(sleep_)
                    return self.get()

        print(self._idx)
        self._next_view[self._idx] = time_ + self._seconds_per_view
        return self._items[self._idx]
