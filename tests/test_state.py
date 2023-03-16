import threading
import time

from remoteworker.remoteworker_pb2 import CurrentState
from bbworker.state import ThreadWorkerState


IDLE = 1
PREPARING = 2
EXECUTING = 3
FINISHED = 4


ALL_STATES = [
    IDLE,
    PREPARING,
    EXECUTING,
    FINISHED
]


def test_thread_state_get_state():
    worker_state = ThreadWorkerState(CurrentState(idle={}))
    worker_state.set_state(PREPARING)
    assert worker_state.get_state() == PREPARING


def test_thread_state_get_state_multiple_times():
    worker_state = ThreadWorkerState(CurrentState(idle={}))
    for s in ALL_STATES:
        worker_state.set_state(s)
        assert worker_state.get_state() == s
        assert worker_state.get_state(0.01) == s


def test_thread_state_override():
    worker_state = ThreadWorkerState(CurrentState(idle={}))
    worker_state.set_state(PREPARING)
    worker_state.set_state(EXECUTING)
    assert worker_state.get_state() == EXECUTING


def test_get_state_wait():
    worker_state = ThreadWorkerState(CurrentState(idle={}))
    worker_state.get_state()
    start_time = time.time()
    sleep_for = 0.3

    def _thread_get_state():
        assert worker_state.get_state() == FINISHED
        assert (time.time() - start_time) >= sleep_for

    t = threading.Thread(target=_thread_get_state)
    t.start()
    time.sleep(sleep_for)
    worker_state.set_state(FINISHED)
    t.join()


def test_get_state_already_set_no_wait():
    worker_state = ThreadWorkerState(CurrentState(idle={}))
    worker_state.set_state(FINISHED)

    def _thread_get_state():
        start_time = time.time()
        assert worker_state.get_state() == FINISHED
        assert (time.time() - start_time) < 0.001

    t = threading.Thread(target=_thread_get_state)
    t.start()
    t.join()


def test_get_state_timeout():
    worker_state = ThreadWorkerState(CurrentState(idle={}))
    worker_state.set_state(FINISHED)
    assert worker_state.get_state() == FINISHED
    sleep_for = 0.3

    def _thread_get_state():
        start_time = time.time()
        assert worker_state.get_state(timeout=sleep_for) == FINISHED
        assert (time.time() - start_time) >= sleep_for

    t = threading.Thread(target=_thread_get_state)
    t.start()
    t.join()


def test_get_state_multiple_set():
    worker_state = ThreadWorkerState(CurrentState(idle={}))
    worker_state.set_state(PREPARING)
    worker_state.set_state(EXECUTING)

    def _thread_get_state():
        assert worker_state.get_state() == EXECUTING

    t = threading.Thread(target=_thread_get_state)
    t.start()
    t.join()
