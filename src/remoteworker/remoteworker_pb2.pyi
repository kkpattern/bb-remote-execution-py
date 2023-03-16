from build.bazel.remote.execution.v2 import remote_execution_pb2 as _remote_execution_pb2
from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CurrentState(_message.Message):
    __slots__ = ["executing", "idle"]
    class Executing(_message.Message):
        __slots__ = ["action_digest", "completed", "fetching_inputs", "prefer_being_idle", "running", "started", "uploading_outputs"]
        ACTION_DIGEST_FIELD_NUMBER: _ClassVar[int]
        COMPLETED_FIELD_NUMBER: _ClassVar[int]
        FETCHING_INPUTS_FIELD_NUMBER: _ClassVar[int]
        PREFER_BEING_IDLE_FIELD_NUMBER: _ClassVar[int]
        RUNNING_FIELD_NUMBER: _ClassVar[int]
        STARTED_FIELD_NUMBER: _ClassVar[int]
        UPLOADING_OUTPUTS_FIELD_NUMBER: _ClassVar[int]
        action_digest: _remote_execution_pb2.Digest
        completed: _remote_execution_pb2.ExecuteResponse
        fetching_inputs: _empty_pb2.Empty
        prefer_being_idle: bool
        running: _empty_pb2.Empty
        started: _empty_pb2.Empty
        uploading_outputs: _empty_pb2.Empty
        def __init__(self, action_digest: _Optional[_Union[_remote_execution_pb2.Digest, _Mapping]] = ..., started: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ..., fetching_inputs: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ..., running: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ..., uploading_outputs: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ..., completed: _Optional[_Union[_remote_execution_pb2.ExecuteResponse, _Mapping]] = ..., prefer_being_idle: bool = ...) -> None: ...
    EXECUTING_FIELD_NUMBER: _ClassVar[int]
    IDLE_FIELD_NUMBER: _ClassVar[int]
    executing: CurrentState.Executing
    idle: _empty_pb2.Empty
    def __init__(self, idle: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ..., executing: _Optional[_Union[CurrentState.Executing, _Mapping]] = ...) -> None: ...

class DesiredState(_message.Message):
    __slots__ = ["executing", "idle"]
    class Executing(_message.Message):
        __slots__ = ["action", "action_digest", "auxiliary_metadata", "instance_name_suffix", "queued_timestamp", "w3c_trace_context"]
        class W3cTraceContextEntry(_message.Message):
            __slots__ = ["key", "value"]
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: str
            value: str
            def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
        ACTION_DIGEST_FIELD_NUMBER: _ClassVar[int]
        ACTION_FIELD_NUMBER: _ClassVar[int]
        AUXILIARY_METADATA_FIELD_NUMBER: _ClassVar[int]
        INSTANCE_NAME_SUFFIX_FIELD_NUMBER: _ClassVar[int]
        QUEUED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        W3C_TRACE_CONTEXT_FIELD_NUMBER: _ClassVar[int]
        action: _remote_execution_pb2.Action
        action_digest: _remote_execution_pb2.Digest
        auxiliary_metadata: _containers.RepeatedCompositeFieldContainer[_any_pb2.Any]
        instance_name_suffix: str
        queued_timestamp: _timestamp_pb2.Timestamp
        w3c_trace_context: _containers.ScalarMap[str, str]
        def __init__(self, action_digest: _Optional[_Union[_remote_execution_pb2.Digest, _Mapping]] = ..., action: _Optional[_Union[_remote_execution_pb2.Action, _Mapping]] = ..., queued_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., auxiliary_metadata: _Optional[_Iterable[_Union[_any_pb2.Any, _Mapping]]] = ..., instance_name_suffix: _Optional[str] = ..., w3c_trace_context: _Optional[_Mapping[str, str]] = ...) -> None: ...
    EXECUTING_FIELD_NUMBER: _ClassVar[int]
    IDLE_FIELD_NUMBER: _ClassVar[int]
    executing: DesiredState.Executing
    idle: _empty_pb2.Empty
    def __init__(self, idle: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ..., executing: _Optional[_Union[DesiredState.Executing, _Mapping]] = ...) -> None: ...

class SynchronizeRequest(_message.Message):
    __slots__ = ["current_state", "instance_name_prefix", "platform", "size_class", "worker_id"]
    class WorkerIdEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    CURRENT_STATE_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_NAME_PREFIX_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    SIZE_CLASS_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    current_state: CurrentState
    instance_name_prefix: str
    platform: _remote_execution_pb2.Platform
    size_class: int
    worker_id: _containers.ScalarMap[str, str]
    def __init__(self, worker_id: _Optional[_Mapping[str, str]] = ..., instance_name_prefix: _Optional[str] = ..., platform: _Optional[_Union[_remote_execution_pb2.Platform, _Mapping]] = ..., size_class: _Optional[int] = ..., current_state: _Optional[_Union[CurrentState, _Mapping]] = ...) -> None: ...

class SynchronizeResponse(_message.Message):
    __slots__ = ["desired_state", "next_synchronization_at"]
    DESIRED_STATE_FIELD_NUMBER: _ClassVar[int]
    NEXT_SYNCHRONIZATION_AT_FIELD_NUMBER: _ClassVar[int]
    desired_state: DesiredState
    next_synchronization_at: _timestamp_pb2.Timestamp
    def __init__(self, next_synchronization_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., desired_state: _Optional[_Union[DesiredState, _Mapping]] = ...) -> None: ...
