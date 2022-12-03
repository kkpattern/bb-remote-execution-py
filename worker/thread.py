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
from .state import ThreadWorkerState
from .runner import RunnerThread
from .directorybuilder import DiffBasedBuildDirectoryBuilder


class WorkerThreadMain(threading.Thread):
    def __init__(
        self,
        operation_queue_channel,
        cas_channel,
        filesystem,
        worker_iid: int,
    ):
        super().__init__()
        self._operation_queue_channel = operation_queue_channel
        self._cas_channel = cas_channel
        self._current_state = ThreadWorkerState[CurrentState](
            CurrentState(idle={})
        )
        self._desired_state = ThreadWorkerState[DesiredState](
            DesiredState(idle={})
        )
        self._worker_id = {"id": "test", "thread": str(worker_iid)}

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
            DiffBasedBuildDirectoryBuilder(
                "tmp/{0}".format(worker_iid),
                cas_helper,
                filesystem,
            ),
            self._current_state,
            self._desired_state,
        )
        self._sync_future: typing.Optional[grpc.Future] = None
        self._shutdown_notified = threading.Event()

    def run(self):
        self._runner_thread.start()
        sync_after = None
        while True:
            if self._shutdown_notified.is_set():
                # Wait runner thread to finish.
                self._runner_thread.join()
                break
            else:
                current_state = self._current_state.get_state(sync_after)
                self._sync_future = self._synchronize_future(current_state)
                try:
                    response = self._sync_future.result()
                except grpc.FutureCancelledError:
                    sync_after = None
                else:
                    sync_after = (
                        response.next_synchronization_at.seconds - time.time()
                    )
                    self._desired_state.set_state(response.desired_state)
                finally:
                    self._sync_future = None

    def _synchronize(self, current_state: CurrentState) -> SynchronizeResponse:
        synchronize_request = SynchronizeRequest(
            worker_id=self._worker_id,
            instance_name_prefix="",
            platform={"properties": [{"name": "os", "value": "macos"}]},
            current_state=current_state,
        )
        return self._operation_queue_stub.Synchronize(synchronize_request)

    def _synchronize_future(self, current_state: CurrentState) -> grpc.Future:
        synchronize_request = SynchronizeRequest(
            worker_id=self._worker_id,
            instance_name_prefix="",
            platform={"properties": [{"name": "os", "value": "macos"}]},
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
