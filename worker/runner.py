import hashlib
import os
import os.path
import subprocess
import sys
import threading
import typing

import grpc
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

from .cas import CASHelper
from .cas import FileProvider

from .state import ThreadWorkerState
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
    build_directory_builder: IDirectoryBuilder,
    cas_helper: CASHelper,
    command: Command,
    input_root_digest: Digest,
    input_root: Directory,
) -> ActionResult:
    build_directory_builder.build(input_root_digest, input_root)
    prepare_output_dirs(command, build_directory_builder.local_root)
    if command.working_directory:
        working_directory = os.path.join(
            build_directory_builder.local_root, command.working_directory
        )
    else:
        working_directory = build_directory_builder.local_root
    env = {}
    for each_env in command.environment_variables:
        env[each_env.name] = each_env.value

    if sys.platform == "darwin":
        setup_xcode_env(env)
    elif sys.platform == "win32":
        env["SystemRoot"] = "c:\\Windows"
    result = subprocess.run(
        command.arguments,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=working_directory,
    )
    if result.returncode == 0:
        # Check outputs.
        if command.output_paths:
            output_paths = command.output_paths
        else:
            output_paths = list(command.output_files)
            output_paths.extend(command.output_directories)
        # First check all file exists.
        for each in output_paths:
            local_path = os.path.join(build_directory_builder.local_root, each)
            if not os.path.exists(local_path):
                # TODO:
                raise Exception(f"{each} not generated.")
            elif os.path.isdir(local_path):
                raise NotImplementedError(
                    "Output directory is not implemented yet."
                )
        # Then generate ActionResult.
        update_provider_list = []
        output_files = []
        for each in output_paths:
            local_path = os.path.join(build_directory_builder.local_root, each)
            if os.path.isfile(local_path):
                provider = FileProvider(local_path)
                update_provider_list.append(provider)
                # TODO: is_executable
                output_files.append(
                    OutputFile(
                        path=each,
                        digest={
                            "hash": provider.digest,
                            "size_bytes": provider.size_bytes,
                        },
                    )
                )
            # TODO: Directory.
        cas_helper.update_all(update_provider_list)
    else:
        output_files = []
    # Upload action result.
    stdout_raw = result.stdout if result.stdout else b""
    stdout_hash = hashlib.sha256(stdout_raw).hexdigest()
    stderr_raw = result.stderr if result.stderr else b""
    stderr_hash = hashlib.sha256(stderr_raw).hexdigest()
    action_result = ActionResult(
        output_files=output_files,
        exit_code=result.returncode,
        stdout_raw=stdout_raw,
        stdout_digest={"hash": stdout_hash, "size_bytes": len(stdout_raw)},
        stderr_raw=stderr_raw,
        stderr_digest={"hash": stderr_hash, "size_bytes": len(stderr_raw)},
    )
    return action_result


class RunnerThread(threading.Thread):
    def __init__(
        self,
        cas_stub: ContentAddressableStorageStub,
        cas_helper: CASHelper,
        action_cache_stub,
        build_directory_builder: IDirectoryBuilder,
        current_state: ThreadWorkerState[CurrentState],
        desired_state: ThreadWorkerState[DesiredState],
    ):
        super().__init__()
        self._cas_stub = cas_stub
        self._cas_helper = cas_helper
        self._action_cache_stub = action_cache_stub
        self._build_directory_builder = build_directory_builder
        self._current_state = current_state
        self._desired_state = desired_state
        self._stop_event = threading.Event()

    def notify_stop(self):
        self._stop_event.set()
        self._desired_state.set_state(DesiredState(idle={}))

    def run(self):
        while True:
            if self._stop_event.is_set():
                break
            desired_state = self._desired_state.get_state()
            # NOTE: ALWAYS set back at least one new current_state after get a
            # new state.
            if desired_state.WhichOneof("worker_state") == "executing":
                action_digest = desired_state.executing.action_digest
                print(f"Action {action_digest.hash} started")
                should_executing = desired_state.executing
                self._current_state.set_state(
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
                    self._current_state.set_state(
                        CurrentState(
                            executing={
                                "action_digest": action_digest,
                                "running": {},
                            }
                        )
                    )
                    action_result = execute_command(
                        self._build_directory_builder,
                        self._cas_helper,
                        command,
                        action.input_root_digest,
                        input_root,
                    )
                    if action_result.exit_code == 0:
                        self._action_cache_stub.UpdateActionResult(
                            UpdateActionResultRequest(
                                action_digest=action_digest,
                                action_result=action_result,
                            )
                        )
                    response = ExecuteResponse(
                        result=action_result,
                        cached_result=False,
                        status={"code": grpc.StatusCode.OK.value[0]},
                    )
                    self._current_state.set_state(
                        CurrentState(
                            executing={
                                "action_digest": action_digest,
                                "completed": response,
                            }
                        )
                    )
                else:
                    # TODO: report error?
                    self._current_state.set_state(CurrentState(idle={}))
                print(f"Action {action_digest.hash} finished")
            else:
                self._current_state.set_state(CurrentState(idle={}))
