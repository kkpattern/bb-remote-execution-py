import threading
import typing


T = typing.TypeVar("T")


class ThreadWorkerState(typing.Generic[T]):
    def __init__(self, initial_state: T):
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._state = initial_state
        self._event.set()

    def get_state(
        self, timeout: typing.Optional[typing.Union[float, int]] = None
    ) -> T:
        self._lock.acquire()
        need_to_release_lock = True
        try:
            # If new state already be set, return immediately.
            # else we wait for timeout.
            if not self._event.is_set():
                self._lock.release()
                need_to_release_lock = False
                self._event.wait(timeout)
                self._lock.acquire()
                need_to_release_lock = True
            state = self._state
            self._event.clear()
        finally:
            if need_to_release_lock:
                self._lock.release()
        return state

    def set_state(self, new_state: T) -> None:
        with self._lock:
            self._state = new_state
            self._event.set()
