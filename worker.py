import hashlib
import typing

import grpc
from build.bazel.remote.execution.v2.remote_execution_pb2 import BatchReadBlobsRequest  # noqa: E501
from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest
from build.bazel.remote.execution.v2.remote_execution_pb2 import Command
from build.bazel.remote.execution.v2.remote_execution_pb2 import Directory
from build.bazel.remote.execution.v2.remote_execution_pb2_grpc import ContentAddressableStorageStub  # noqa: E501
from remoteworker.remoteworker_pb2 import CurrentState
from remoteworker.remoteworker_pb2 import SynchronizeRequest
from remoteworker.remoteworker_pb2_grpc import OperationQueueStub


# next_synchronization_at {
#   seconds: 1669576210
#   nanos: 349240116
# }
# desired_state {
#   executing {
#     action_digest {
#       hash: "53d2e05cc9539b31b81c62f594f2d88cad7dc9f5ef73072c05df17de5a10ec80"
#       size_bytes: 157
#     }
#     action {
#       command_digest {
#         hash: "b3fdbe8d896db374588a04a07a38548aaf3439b12ec45bfd6329e8c506c9ec47"
#         size_bytes: 3895
#       }
#       input_root_digest {
#         hash: "e52f977a4c7c2939270c02f379ac5668936c67a2309bdcc6abb29c3abcf64067"
#         size_bytes: 341
#       }
#       timeout {
#         seconds: 1800
#       }
#       platform {
#         properties {
#           name: "os"
#           value: "macos"
#         }
#       }
#     }
#     queued_timestamp {
#       seconds: 1669576192
#       nanos: 145637129
#     }
#     auxiliary_metadata {
#       type_url: "type.googleapis.com/build.bazel.remote.execution.v2.RequestMetadata"
#       value: "\n\016\n\005bazel\022\0055.3.1\022@53d2e05cc9539b31b81c62f594f2d88cad7dc9f5ef73072c05df17de5a10ec80\032$c08f36b6-8b42-4e4e-8139-38d8e6ee8e9c\"$f11561c2-733c-4ab4-bfef-f9af08cba511*\nCppCompile2\024//common:common_objc:@4a3a4d3920563e20973ad707e077eafe1702b62b5d9976b6a60f8154eb1949aa"
#     }
#   }
# }


def get_action_detail(
    command_digest: Digest,
    input_root_digest: Digest,
) -> typing.Tuple[typing.Optional[Command], typing.Optional[Directory]]:
    request = BatchReadBlobsRequest(
        digests=[command_digest, input_root_digest],
        acceptable_compressors=[0])
    response = cas_stub.BatchReadBlobs(request)
    command = None
    input_root = None
    for each in response.responses:
        # TODO: check status
        if each.digest == command_digest:
            command = Command()
            command.ParseFromString(each.data)
            check_command_data = command.SerializeToString()
            sha256 = hashlib.sha256()
            sha256.update(check_command_data)
            print(sha256.hexdigest())
            print(len(check_command_data))
            print(each.digest)
        elif each.digest == input_root_digest:
            input_root = Directory()
            input_root.ParseFromString(each.data)
    return (command, input_root)


def get_command(cas_stub: ContentAddressableStorageStub,
                digest: Digest) -> typing.Optional[Command]:
    response = cas_stub.BatchReadBlobs(
        BatchReadBlobsRequest(digests=[digest], acceptable_compressors=[0]))
    if len(response.responses) == 1:
        r = response.responses[0]
        # TODO: check r.status
        command = Command()
        command.ParseFromString(r.data)
    else:
        command = None
    return command


def prepare_input_root(cas_stub: ContentAddressableStorageStub,
                       input_root: Directory):
    pass


def execute_command(common: Command):
    pass


with grpc.insecure_channel("10.212.214.123:8983") as channel:
    with grpc.insecure_channel('10.212.214.130:8980') as cas_channel:
        cas_stub = ContentAddressableStorageStub(cas_channel)
        operation_queue_stub = OperationQueueStub(channel)
        current_state = CurrentState(idle={})

        synchronize_request = SynchronizeRequest(
            worker_id={"id": "test", "b": "2"},
            instance_name_prefix="",
            platform={"properties": [{"name": "os", "value": "macos"}]},
            current_state=current_state)
        response = operation_queue_stub.Synchronize(synchronize_request)
        if hasattr(response.desired_state, "executing"):
            should_executing = response.desired_state.executing
            action = should_executing.action
            command, input_root = get_action_detail(action.command_digest,
                                                    action.input_root_digest)
            if command and input_root:
                pass
