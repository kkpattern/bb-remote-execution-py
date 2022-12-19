import queue
import time
import threading
import typing

import grpc
from remoteworker.remoteworker_pb2 import CurrentState
from remoteworker.remoteworker_pb2 import DesiredState
from remoteworker.remoteworker_pb2 import SynchronizeRequest
from remoteworker.remoteworker_pb2 import SynchronizeResponse
from remoteworker.remoteworker_pb2_grpc import OperationQueueStub
from google.bytestream.bytestream_pb2_grpc import ByteStreamStub
from build.bazel.remote.execution.v2.remote_execution_pb2_grpc import (
    ActionCacheStub,
)
from build.bazel.remote.execution.v2.remote_execution_pb2_grpc import (
    ContentAddressableStorageStub,
)

from .cas import CASHelper
from .config import Platform
from .metrics import MeterBase
from .runner import RunnerThread
from .directorybuilder import IDirectoryBuilder


class WorkerThreadMain(threading.Thread):
    def __init__(
        self,
        operation_queue_channel,
        cas_channel,
        platform: Platform,
        worker_id: typing.Dict[str, str],
        filesystem,
        directory_builder: IDirectoryBuilder,
        build_root: str,
        worker_iid: int,
        meter: MeterBase,
    ):
        super().__init__()
        self._operation_queue_channel = operation_queue_channel
        self._cas_channel = cas_channel
        self._current_state_queue: "queue.Queue[CurrentState]" = queue.Queue()
        self._desired_state_queue: "queue.Queue[DesiredState]" = queue.Queue()
        self._worker_id = {}
        self._worker_id.update(worker_id)
        self._worker_id["thread"] = str(worker_iid)

        self._operation_queue_stub = OperationQueueStub(
            self._operation_queue_channel
        )
        cas_stub = ContentAddressableStorageStub(self._cas_channel)
        action_cache_stub = ActionCacheStub(self._cas_channel)
        cas_byte_stream_stub = ByteStreamStub(self._cas_channel)
        cas_helper = CASHelper(cas_stub, cas_byte_stream_stub)
        self._runner_thread = RunnerThread(
            cas_stub,
            cas_helper,
            action_cache_stub,
            directory_builder,
            f"{build_root}/{worker_iid}",
            self._current_state_queue,
            self._desired_state_queue,
            meter,
        )
        self._platform = platform.dict()
        self._sync_future: typing.Optional[grpc.Future] = None
        self._shutdown_notified = threading.Event()

    def run(self):
        self._runner_thread.start()
        current_state = self._current_state_queue.get(block=True, timeout=None)
        while True:
            if self._shutdown_notified.is_set():
                # Wait runner thread to finish.
                self._runner_thread.join()
                break
            else:
                self._sync_future = self._synchronize_future(current_state)
                try:
                    response = self._sync_future.result()
                except grpc.FutureCancelledError:
                    self._sync_future = None
                else:
                    self._sync_future = None
                    sync_at = response.next_synchronization_at
                    sync_time = sync_at.seconds + sync_at.nanos * 0.000000001
                    sync_after = max(0, sync_time - time.time())
                    self._desired_state_queue.put(response.desired_state)
                    try:
                        current_state = self._current_state_queue.get(
                            block=True, timeout=sync_after
                        )
                    except queue.Empty:
                        pass

    def _synchronize(self, current_state: CurrentState) -> SynchronizeResponse:
        synchronize_request = SynchronizeRequest(
            worker_id=self._worker_id,
            instance_name_prefix="",
            platform=self._platform,
            current_state=current_state,
        )
        return self._operation_queue_stub.Synchronize(synchronize_request)

    def _synchronize_future(self, current_state: CurrentState) -> grpc.Future:
        synchronize_request = SynchronizeRequest(
            worker_id=self._worker_id,
            instance_name_prefix="",
            platform=self._platform,
            current_state=current_state,
        )
        return self._operation_queue_stub.Synchronize.future(
            synchronize_request
        )

    def graceful_shutdown(self):
        self._shutdown_notified.set()
        self._runner_thread.notify_stop()
        if self._sync_future is not None:
            self._sync_future.cancel()
