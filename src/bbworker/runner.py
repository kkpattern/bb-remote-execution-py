import os
import os.path
import queue
import subprocess
import sys
import threading
import typing

import grpc
from google.protobuf.any_pb2 import Any
from google.rpc.error_details_pb2 import PreconditionFailure
from google.rpc.status_pb2 import Status
from build.bazel.remote.execution.v2.remote_execution_pb2 import ActionResult
from build.bazel.remote.execution.v2.remote_execution_pb2 import (
    BatchReadBlobsRequest,
)
from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest
from build.bazel.remote.execution.v2.remote_execution_pb2 import Command
from build.bazel.remote.execution.v2.remote_execution_pb2 import Directory
from build.bazel.remote.execution.v2.remote_execution_pb2 import (
    ExecuteResponse,
)
from build.bazel.remote.execution.v2.remote_execution_pb2 import OutputFile
from build.bazel.remote.execution.v2.remote_execution_pb2 import (
    UpdateActionResultRequest,
)
from build.bazel.remote.execution.v2.remote_execution_pb2_grpc import (
    ContentAddressableStorageStub,
)
from remoteworker.remoteworker_pb2 import CurrentState
from remoteworker.remoteworker_pb2 import DesiredState

from .cas import IProvider
from .cas import BytesProvider
from .cas import CASHelper
from .cas import FileProvider
from .cas import BatchReadBlobsError

from .directorybuilder import IDirectoryBuilder
from .util import setup_xcode_env


def get_action_detail(
    cas_stub: ContentAddressableStorageStub,
    command_digest: Digest,
    input_root_digest: Digest,
) -> typing.Tuple[typing.Optional[Command], typing.Optional[Directory]]:
    request = BatchReadBlobsRequest(
        digests=[command_digest, input_root_digest],
    )
    response = cas_stub.BatchReadBlobs(request)
    command = None
    input_root = None
    for each in response.responses:
        if each.status.code != grpc.StatusCode.OK.value[0]:
            print(each.status.message)
            continue
        if each.digest == command_digest:
            command = Command()
            command.ParseFromString(each.data)
        elif each.digest == input_root_digest:
            input_root = Directory()
            input_root.ParseFromString(each.data)
        else:
            # TODO: Exception?
            pass
    return (command, input_root)


def prepare_output_dirs(command: Command, root: str) -> None:
    if command.output_paths:
        for each in command.output_paths:
            dir_ = os.path.dirname(os.path.join(root, each))
            if not os.path.isdir(dir_):
                os.makedirs(dir_)
    else:
        for each in list(command.output_files) + list(
            command.output_directories
        ):
            dir_ = os.path.dirname(os.path.join(root, each))
            if not os.path.isdir(dir_):
                os.makedirs(dir_)


def execute_command(
    state_queue: queue.Queue,
    build_directory_builder: IDirectoryBuilder,
    build_directory: str,
    cas_helper: CASHelper,
    action_digest: Digest,
    command: Command,
    input_root_digest: Digest,
    input_root: Directory,
):
    state_queue.put(
        CurrentState(
            executing={
                "action_digest": action_digest,
                "fetching_inputs": {},
            }
        )
    )
    try:
        build_directory_builder.build(
            input_root_digest, input_root, build_directory
        )
    except BatchReadBlobsError as e:
        status = Status(code=grpc.StatusCode.FAILED_PRECONDITION.value[0])
        if e.digests:
            violations = []
            for each in e.digests:
                violations.append(
                    {
                        "type": "MISSING",
                        "subject": f"blobs/{each.hash}/{each.size_bytes}",
                    }
                )
            detail_any = Any()
            detail_any.Pack(PreconditionFailure(violations=violations))
            status.details.append(detail_any)
        response = ExecuteResponse(status=status)
    else:
        prepare_output_dirs(command, build_directory)
        if command.working_directory:
            working_directory = os.path.join(
                build_directory, command.working_directory
            )
        else:
            working_directory = build_directory
        env = {}
        for each_env in command.environment_variables:
            env[each_env.name] = each_env.value

        if sys.platform == "darwin":
            setup_xcode_env(env)
        elif sys.platform == "win32":
            env["SystemRoot"] = "c:\\Windows"

        state_queue.put(
            CurrentState(
                executing={
                    "action_digest": action_digest,
                    "running": {},
                }
            )
        )
        result = subprocess.run(
            command.arguments,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working_directory,
        )

        update_provider_list: typing.List[IProvider] = []

        stdout_digest = None
        stderr_digest = None
        if result.stdout:
            stdout_provider = BytesProvider(result.stdout)
            stdout_digest = Digest(
                hash=stdout_provider.hash_,
                size_bytes=stdout_provider.size_bytes,
            )
            update_provider_list.append(stdout_provider)

        if result.stderr:
            stderr_provider = BytesProvider(result.stderr)
            stderr_digest = Digest(
                hash=stderr_provider.hash_,
                size_bytes=stderr_provider.size_bytes,
            )
            update_provider_list.append(stderr_provider)
        if result.returncode == 0:
            # Check outputs.
            if command.output_paths:
                output_paths: typing.Iterable[str] = command.output_paths
            else:
                output_paths = list(command.output_files)
                output_paths.extend(command.output_directories)
            # First check all file exists.
            for each in output_paths:
                local_path = os.path.join(build_directory, each)
                if not os.path.exists(local_path):
                    # TODO:
                    raise Exception(f"{each} not generated.")
                elif os.path.isdir(local_path):
                    raise NotImplementedError(
                        "Output directory is not implemented yet."
                    )
            # Then generate ActionResult.
            output_files = []

            for each in output_paths:
                local_path = os.path.join(build_directory, each)
                if os.path.isfile(local_path):
                    provider = FileProvider(local_path)
                    update_provider_list.append(provider)
                    # TODO: is_executable
                    output_files.append(
                        OutputFile(
                            path=each,
                            digest={
                                "hash": provider.hash_,
                                "size_bytes": provider.size_bytes,
                            },
                        )
                    )
                # TODO: Directory.
        else:
            output_files = []

        cas_helper.update_all(update_provider_list)

        state_queue.put(
            CurrentState(
                executing={
                    "action_digest": action_digest,
                    "uploading_outputs": {},
                }
            )
        )
        # Upload action result.
        action_result = ActionResult(
            output_files=output_files,
            exit_code=result.returncode,
            stdout_digest=stdout_digest,
            stdout_raw=result.stdout,
            stderr_digest=stderr_digest,
            stderr_raw=result.stderr,
        )
        response = ExecuteResponse(
            result=action_result,
            cached_result=False,
            status={"code": grpc.StatusCode.OK.value[0]},
        )
    return response


class RunnerThread(threading.Thread):
    def __init__(
        self,
        cas_stub: ContentAddressableStorageStub,
        cas_helper: CASHelper,
        action_cache_stub,
        build_directory_builder: IDirectoryBuilder,
        build_directory: str,
        current_state_queue: "queue.Queue[CurrentState]",
        desired_state_queue: "queue.Queue[DesiredState]",
    ):
        super().__init__()
        self._cas_stub = cas_stub
        self._cas_helper = cas_helper
        self._action_cache_stub = action_cache_stub
        self._build_directory_builder = build_directory_builder
        self._build_directory = build_directory
        self._current_state_queue = current_state_queue
        self._desired_state_queue = desired_state_queue
        self._stop_event = threading.Event()

    def notify_stop(self):
        self._stop_event.set()
        self._desired_state_queue.put(DesiredState(idle={}))

    def run(self):
        self._current_state_queue.put(CurrentState(idle={}))
        while True:
            if self._stop_event.is_set():
                break
            desired_state = self._desired_state_queue.get(block=True)
            # we only handle the newest desired state.
            while True:
                try:
                    desired_state = self._desired_state_queue.get_nowait()
                except queue.Empty:
                    break
            # NOTE: ALWAYS set back at least one new current_state after get a
            # new state.
            if desired_state.WhichOneof("worker_state") == "executing":
                action_digest = desired_state.executing.action_digest
                # print(f"Action {action_digest.hash} started")
                should_executing = desired_state.executing
                self._current_state_queue.put(
                    CurrentState(
                        executing={
                            "action_digest": action_digest,
                            "started": {},
                        }
                    )
                )
                action = should_executing.action
                command, input_root = get_action_detail(
                    self._cas_stub,
                    action.command_digest,
                    action.input_root_digest,
                )
                if command and input_root:
                    response = execute_command(
                        self._current_state_queue,
                        self._build_directory_builder,
                        self._build_directory,
                        self._cas_helper,
                        action_digest,
                        command,
                        action.input_root_digest,
                        input_root,
                    )
                    self._current_state_queue.put(
                        CurrentState(
                            executing={
                                "action_digest": action_digest,
                                "completed": response,
                            }
                        )
                    )
                    if response.result and response.result.exit_code == 0:
                        self._action_cache_stub.UpdateActionResult(
                            UpdateActionResultRequest(
                                action_digest=action_digest,
                                action_result=response.result,
                            )
                        )
                # print(f"Action {action_digest.hash} finished")
            else:
                self._current_state_queue.put(CurrentState(idle={}))
