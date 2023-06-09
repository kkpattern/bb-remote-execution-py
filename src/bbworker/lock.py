import contextlib
import threading
import typing


T = typing.TypeVar("T", bound=typing.Union[threading.Lock, threading.RLock])


class _VariableLock(typing.Generic[T]):
    def __init__(self, lock_factory: typing.Callable[[], T]) -> None:
        self._lock_factory = lock_factory
        self._global_lock = self._lock_factory()
        self._var_locks: typing.Dict[typing.Hashable, T] = {}

    def acquire_lock(self, var: typing.Hashable) -> T:
        """Acquire a var lock. If no lock exists a new lock will be created.
        return the acquired lock so caller can release it.

        you can use context manager instead:

            with var_lock.lock(name):
                do_something()

        """
        while True:
            with self._global_lock:
                if var not in self._var_locks:
                    # we're the first one to create the lock.
                    lock = self._lock_factory()
                    self._var_locks[var] = lock
                else:
                    lock = self._var_locks[var]
            lock.acquire()
            if self._var_locks.get(var, None) is lock:
                break
            else:
                # lock has been removed by others, retry.
                lock.release()
        return lock

    def remove_lock(self, var: typing.Hashable, lock_to_remove: T):
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


class VariableLock(_VariableLock):
    def __init__(self) -> None:
        super().__init__(threading.Lock)


class VariableRLock(_VariableLock):
    def __init__(self) -> None:
        super().__init__(threading.RLock)
