import contextlib
import threading
import typing


class VariableLock(object):
    def __init__(self):
        self._global_lock = threading.Lock()
        self._var_locks: typing.Dict[typing.Hashable, threading.Lock] = {}

    def acquire_lock(self, var: typing.Hashable) -> threading.Lock:
        """Acquire a var lock. If no lock exists a new lock will be created.
        return the acquired lock so caller can release it.

        you can use context manager instead:

            with var_lock.lock(name):
                do_something()

        """
        while True:
            if var in self._var_locks:
                lock = self._var_locks[var]
                lock.acquire()
                if self._var_locks.get(var, None) is not lock:
                    # the lock is released by another thread. release it and
                    # retry.
                    lock.release()
                    continue
                else:
                    break
            else:
                with self._global_lock:
                    if var not in self._var_locks:
                        # we're the first one to create the lock.
                        lock = threading.Lock()
                        lock.acquire()
                        self._var_locks[var] = lock
                        break
                    else:
                        # someone created the lock before us, retry.
                        continue
        return lock

    def remove_lock(
        self, var: typing.Hashable, lock_to_remove: threading.Lock
    ):
        # we need to acquire the lock first.
        lock_to_remove.acquire()
        try:
            with self._global_lock:
                if self._var_locks.get(var, None) is lock_to_remove:
                    del self._var_locks[var]
        finally:
            lock_to_remove.release()

    @contextlib.contextmanager
    def lock(self, var: typing.Hashable):
        lock = self.acquire_lock(var)
        try:
            yield lock
        finally:
            lock.release()
