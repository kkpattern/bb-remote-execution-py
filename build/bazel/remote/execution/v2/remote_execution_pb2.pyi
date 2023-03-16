from build.bazel.semver import semver_pb2 as _semver_pb2
from google.api import annotations_pb2 as _annotations_pb2
from google.longrunning import operations_pb2 as _operations_pb2
from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.rpc import status_pb2 as _status_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Action(_message.Message):
    __slots__ = ["command_digest", "do_not_cache", "input_root_digest", "platform", "salt", "timeout"]
    COMMAND_DIGEST_FIELD_NUMBER: _ClassVar[int]
    DO_NOT_CACHE_FIELD_NUMBER: _ClassVar[int]
    INPUT_ROOT_DIGEST_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    SALT_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    command_digest: Digest
    do_not_cache: bool
    input_root_digest: Digest
    platform: Platform
    salt: bytes
    timeout: _duration_pb2.Duration
    def __init__(self, command_digest: _Optional[_Union[Digest, _Mapping]] = ..., input_root_digest: _Optional[_Union[Digest, _Mapping]] = ..., timeout: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., do_not_cache: bool = ..., salt: _Optional[bytes] = ..., platform: _Optional[_Union[Platform, _Mapping]] = ...) -> None: ...

class ActionCacheUpdateCapabilities(_message.Message):
    __slots__ = ["update_enabled"]
    UPDATE_ENABLED_FIELD_NUMBER: _ClassVar[int]
    update_enabled: bool
    def __init__(self, update_enabled: bool = ...) -> None: ...

class ActionResult(_message.Message):
    __slots__ = ["execution_metadata", "exit_code", "output_directories", "output_directory_symlinks", "output_file_symlinks", "output_files", "output_symlinks", "stderr_digest", "stderr_raw", "stdout_digest", "stdout_raw"]
    EXECUTION_METADATA_FIELD_NUMBER: _ClassVar[int]
    EXIT_CODE_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_DIRECTORIES_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_DIRECTORY_SYMLINKS_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FILES_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FILE_SYMLINKS_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_SYMLINKS_FIELD_NUMBER: _ClassVar[int]
    STDERR_DIGEST_FIELD_NUMBER: _ClassVar[int]
    STDERR_RAW_FIELD_NUMBER: _ClassVar[int]
    STDOUT_DIGEST_FIELD_NUMBER: _ClassVar[int]
    STDOUT_RAW_FIELD_NUMBER: _ClassVar[int]
    execution_metadata: ExecutedActionMetadata
    exit_code: int
    output_directories: _containers.RepeatedCompositeFieldContainer[OutputDirectory]
    output_directory_symlinks: _containers.RepeatedCompositeFieldContainer[OutputSymlink]
    output_file_symlinks: _containers.RepeatedCompositeFieldContainer[OutputSymlink]
    output_files: _containers.RepeatedCompositeFieldContainer[OutputFile]
    output_symlinks: _containers.RepeatedCompositeFieldContainer[OutputSymlink]
    stderr_digest: Digest
    stderr_raw: bytes
    stdout_digest: Digest
    stdout_raw: bytes
    def __init__(self, output_files: _Optional[_Iterable[_Union[OutputFile, _Mapping]]] = ..., output_file_symlinks: _Optional[_Iterable[_Union[OutputSymlink, _Mapping]]] = ..., output_symlinks: _Optional[_Iterable[_Union[OutputSymlink, _Mapping]]] = ..., output_directories: _Optional[_Iterable[_Union[OutputDirectory, _Mapping]]] = ..., output_directory_symlinks: _Optional[_Iterable[_Union[OutputSymlink, _Mapping]]] = ..., exit_code: _Optional[int] = ..., stdout_raw: _Optional[bytes] = ..., stdout_digest: _Optional[_Union[Digest, _Mapping]] = ..., stderr_raw: _Optional[bytes] = ..., stderr_digest: _Optional[_Union[Digest, _Mapping]] = ..., execution_metadata: _Optional[_Union[ExecutedActionMetadata, _Mapping]] = ...) -> None: ...

class BatchReadBlobsRequest(_message.Message):
    __slots__ = ["acceptable_compressors", "digests", "instance_name"]
    ACCEPTABLE_COMPRESSORS_FIELD_NUMBER: _ClassVar[int]
    DIGESTS_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_NAME_FIELD_NUMBER: _ClassVar[int]
    acceptable_compressors: _containers.RepeatedScalarFieldContainer[Compressor.Value]
    digests: _containers.RepeatedCompositeFieldContainer[Digest]
    instance_name: str
    def __init__(self, instance_name: _Optional[str] = ..., digests: _Optional[_Iterable[_Union[Digest, _Mapping]]] = ..., acceptable_compressors: _Optional[_Iterable[_Union[Compressor.Value, str]]] = ...) -> None: ...

class BatchReadBlobsResponse(_message.Message):
    __slots__ = ["responses"]
    class Response(_message.Message):
        __slots__ = ["compressor", "data", "digest", "status"]
        COMPRESSOR_FIELD_NUMBER: _ClassVar[int]
        DATA_FIELD_NUMBER: _ClassVar[int]
        DIGEST_FIELD_NUMBER: _ClassVar[int]
        STATUS_FIELD_NUMBER: _ClassVar[int]
        compressor: Compressor.Value
        data: bytes
        digest: Digest
        status: _status_pb2.Status
        def __init__(self, digest: _Optional[_Union[Digest, _Mapping]] = ..., data: _Optional[bytes] = ..., compressor: _Optional[_Union[Compressor.Value, str]] = ..., status: _Optional[_Union[_status_pb2.Status, _Mapping]] = ...) -> None: ...
    RESPONSES_FIELD_NUMBER: _ClassVar[int]
    responses: _containers.RepeatedCompositeFieldContainer[BatchReadBlobsResponse.Response]
    def __init__(self, responses: _Optional[_Iterable[_Union[BatchReadBlobsResponse.Response, _Mapping]]] = ...) -> None: ...

class BatchUpdateBlobsRequest(_message.Message):
    __slots__ = ["instance_name", "requests"]
    class Request(_message.Message):
        __slots__ = ["compressor", "data", "digest"]
        COMPRESSOR_FIELD_NUMBER: _ClassVar[int]
        DATA_FIELD_NUMBER: _ClassVar[int]
        DIGEST_FIELD_NUMBER: _ClassVar[int]
        compressor: Compressor.Value
        data: bytes
        digest: Digest
        def __init__(self, digest: _Optional[_Union[Digest, _Mapping]] = ..., data: _Optional[bytes] = ..., compressor: _Optional[_Union[Compressor.Value, str]] = ...) -> None: ...
    INSTANCE_NAME_FIELD_NUMBER: _ClassVar[int]
    REQUESTS_FIELD_NUMBER: _ClassVar[int]
    instance_name: str
    requests: _containers.RepeatedCompositeFieldContainer[BatchUpdateBlobsRequest.Request]
    def __init__(self, instance_name: _Optional[str] = ..., requests: _Optional[_Iterable[_Union[BatchUpdateBlobsRequest.Request, _Mapping]]] = ...) -> None: ...

class BatchUpdateBlobsResponse(_message.Message):
    __slots__ = ["responses"]
    class Response(_message.Message):
        __slots__ = ["digest", "status"]
        DIGEST_FIELD_NUMBER: _ClassVar[int]
        STATUS_FIELD_NUMBER: _ClassVar[int]
        digest: Digest
        status: _status_pb2.Status
        def __init__(self, digest: _Optional[_Union[Digest, _Mapping]] = ..., status: _Optional[_Union[_status_pb2.Status, _Mapping]] = ...) -> None: ...
    RESPONSES_FIELD_NUMBER: _ClassVar[int]
    responses: _containers.RepeatedCompositeFieldContainer[BatchUpdateBlobsResponse.Response]
    def __init__(self, responses: _Optional[_Iterable[_Union[BatchUpdateBlobsResponse.Response, _Mapping]]] = ...) -> None: ...

class CacheCapabilities(_message.Message):
    __slots__ = ["action_cache_update_capabilities", "cache_priority_capabilities", "digest_functions", "max_batch_total_size_bytes", "supported_batch_update_compressors", "supported_compressors", "symlink_absolute_path_strategy"]
    ACTION_CACHE_UPDATE_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    CACHE_PRIORITY_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    DIGEST_FUNCTIONS_FIELD_NUMBER: _ClassVar[int]
    MAX_BATCH_TOTAL_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    SUPPORTED_BATCH_UPDATE_COMPRESSORS_FIELD_NUMBER: _ClassVar[int]
    SUPPORTED_COMPRESSORS_FIELD_NUMBER: _ClassVar[int]
    SYMLINK_ABSOLUTE_PATH_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    action_cache_update_capabilities: ActionCacheUpdateCapabilities
    cache_priority_capabilities: PriorityCapabilities
    digest_functions: _containers.RepeatedScalarFieldContainer[DigestFunction.Value]
    max_batch_total_size_bytes: int
    supported_batch_update_compressors: _containers.RepeatedScalarFieldContainer[Compressor.Value]
    supported_compressors: _containers.RepeatedScalarFieldContainer[Compressor.Value]
    symlink_absolute_path_strategy: SymlinkAbsolutePathStrategy.Value
    def __init__(self, digest_functions: _Optional[_Iterable[_Union[DigestFunction.Value, str]]] = ..., action_cache_update_capabilities: _Optional[_Union[ActionCacheUpdateCapabilities, _Mapping]] = ..., cache_priority_capabilities: _Optional[_Union[PriorityCapabilities, _Mapping]] = ..., max_batch_total_size_bytes: _Optional[int] = ..., symlink_absolute_path_strategy: _Optional[_Union[SymlinkAbsolutePathStrategy.Value, str]] = ..., supported_compressors: _Optional[_Iterable[_Union[Compressor.Value, str]]] = ..., supported_batch_update_compressors: _Optional[_Iterable[_Union[Compressor.Value, str]]] = ...) -> None: ...

class Command(_message.Message):
    __slots__ = ["arguments", "environment_variables", "output_directories", "output_files", "output_node_properties", "output_paths", "platform", "working_directory"]
    class EnvironmentVariable(_message.Message):
        __slots__ = ["name", "value"]
        NAME_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        name: str
        value: str
        def __init__(self, name: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    ARGUMENTS_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_VARIABLES_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_DIRECTORIES_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FILES_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_NODE_PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_PATHS_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    WORKING_DIRECTORY_FIELD_NUMBER: _ClassVar[int]
    arguments: _containers.RepeatedScalarFieldContainer[str]
    environment_variables: _containers.RepeatedCompositeFieldContainer[Command.EnvironmentVariable]
    output_directories: _containers.RepeatedScalarFieldContainer[str]
    output_files: _containers.RepeatedScalarFieldContainer[str]
    output_node_properties: _containers.RepeatedScalarFieldContainer[str]
    output_paths: _containers.RepeatedScalarFieldContainer[str]
    platform: Platform
    working_directory: str
    def __init__(self, arguments: _Optional[_Iterable[str]] = ..., environment_variables: _Optional[_Iterable[_Union[Command.EnvironmentVariable, _Mapping]]] = ..., output_files: _Optional[_Iterable[str]] = ..., output_directories: _Optional[_Iterable[str]] = ..., output_paths: _Optional[_Iterable[str]] = ..., platform: _Optional[_Union[Platform, _Mapping]] = ..., working_directory: _Optional[str] = ..., output_node_properties: _Optional[_Iterable[str]] = ...) -> None: ...

class Compressor(_message.Message):
    __slots__ = []
    class Value(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
    DEFLATE: Compressor.Value
    IDENTITY: Compressor.Value
    ZSTD: Compressor.Value
    def __init__(self) -> None: ...

class Digest(_message.Message):
    __slots__ = ["hash", "size_bytes"]
    HASH_FIELD_NUMBER: _ClassVar[int]
    SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    hash: str
    size_bytes: int
    def __init__(self, hash: _Optional[str] = ..., size_bytes: _Optional[int] = ...) -> None: ...

class DigestFunction(_message.Message):
    __slots__ = []
    class Value(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
    MD5: DigestFunction.Value
    MURMUR3: DigestFunction.Value
    SHA1: DigestFunction.Value
    SHA256: DigestFunction.Value
    SHA384: DigestFunction.Value
    SHA512: DigestFunction.Value
    UNKNOWN: DigestFunction.Value
    VSO: DigestFunction.Value
    def __init__(self) -> None: ...

class Directory(_message.Message):
    __slots__ = ["directories", "files", "node_properties", "symlinks"]
    DIRECTORIES_FIELD_NUMBER: _ClassVar[int]
    FILES_FIELD_NUMBER: _ClassVar[int]
    NODE_PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    SYMLINKS_FIELD_NUMBER: _ClassVar[int]
    directories: _containers.RepeatedCompositeFieldContainer[DirectoryNode]
    files: _containers.RepeatedCompositeFieldContainer[FileNode]
    node_properties: NodeProperties
    symlinks: _containers.RepeatedCompositeFieldContainer[SymlinkNode]
    def __init__(self, files: _Optional[_Iterable[_Union[FileNode, _Mapping]]] = ..., directories: _Optional[_Iterable[_Union[DirectoryNode, _Mapping]]] = ..., symlinks: _Optional[_Iterable[_Union[SymlinkNode, _Mapping]]] = ..., node_properties: _Optional[_Union[NodeProperties, _Mapping]] = ...) -> None: ...

class DirectoryNode(_message.Message):
    __slots__ = ["digest", "name"]
    DIGEST_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    digest: Digest
    name: str
    def __init__(self, name: _Optional[str] = ..., digest: _Optional[_Union[Digest, _Mapping]] = ...) -> None: ...

class ExecuteOperationMetadata(_message.Message):
    __slots__ = ["action_digest", "stage", "stderr_stream_name", "stdout_stream_name"]
    ACTION_DIGEST_FIELD_NUMBER: _ClassVar[int]
    STAGE_FIELD_NUMBER: _ClassVar[int]
    STDERR_STREAM_NAME_FIELD_NUMBER: _ClassVar[int]
    STDOUT_STREAM_NAME_FIELD_NUMBER: _ClassVar[int]
    action_digest: Digest
    stage: ExecutionStage.Value
    stderr_stream_name: str
    stdout_stream_name: str
    def __init__(self, stage: _Optional[_Union[ExecutionStage.Value, str]] = ..., action_digest: _Optional[_Union[Digest, _Mapping]] = ..., stdout_stream_name: _Optional[str] = ..., stderr_stream_name: _Optional[str] = ...) -> None: ...

class ExecuteRequest(_message.Message):
    __slots__ = ["action_digest", "execution_policy", "instance_name", "results_cache_policy", "skip_cache_lookup"]
    ACTION_DIGEST_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_POLICY_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_NAME_FIELD_NUMBER: _ClassVar[int]
    RESULTS_CACHE_POLICY_FIELD_NUMBER: _ClassVar[int]
    SKIP_CACHE_LOOKUP_FIELD_NUMBER: _ClassVar[int]
    action_digest: Digest
    execution_policy: ExecutionPolicy
    instance_name: str
    results_cache_policy: ResultsCachePolicy
    skip_cache_lookup: bool
    def __init__(self, instance_name: _Optional[str] = ..., skip_cache_lookup: bool = ..., action_digest: _Optional[_Union[Digest, _Mapping]] = ..., execution_policy: _Optional[_Union[ExecutionPolicy, _Mapping]] = ..., results_cache_policy: _Optional[_Union[ResultsCachePolicy, _Mapping]] = ...) -> None: ...

class ExecuteResponse(_message.Message):
    __slots__ = ["cached_result", "message", "result", "server_logs", "status"]
    class ServerLogsEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: LogFile
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[LogFile, _Mapping]] = ...) -> None: ...
    CACHED_RESULT_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    SERVER_LOGS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    cached_result: bool
    message: str
    result: ActionResult
    server_logs: _containers.MessageMap[str, LogFile]
    status: _status_pb2.Status
    def __init__(self, result: _Optional[_Union[ActionResult, _Mapping]] = ..., cached_result: bool = ..., status: _Optional[_Union[_status_pb2.Status, _Mapping]] = ..., server_logs: _Optional[_Mapping[str, LogFile]] = ..., message: _Optional[str] = ...) -> None: ...

class ExecutedActionMetadata(_message.Message):
    __slots__ = ["auxiliary_metadata", "execution_completed_timestamp", "execution_start_timestamp", "input_fetch_completed_timestamp", "input_fetch_start_timestamp", "output_upload_completed_timestamp", "output_upload_start_timestamp", "queued_timestamp", "virtual_execution_duration", "worker", "worker_completed_timestamp", "worker_start_timestamp"]
    AUXILIARY_METADATA_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_COMPLETED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_START_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    INPUT_FETCH_COMPLETED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    INPUT_FETCH_START_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_UPLOAD_COMPLETED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_UPLOAD_START_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    QUEUED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    VIRTUAL_EXECUTION_DURATION_FIELD_NUMBER: _ClassVar[int]
    WORKER_COMPLETED_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    WORKER_FIELD_NUMBER: _ClassVar[int]
    WORKER_START_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    auxiliary_metadata: _containers.RepeatedCompositeFieldContainer[_any_pb2.Any]
    execution_completed_timestamp: _timestamp_pb2.Timestamp
    execution_start_timestamp: _timestamp_pb2.Timestamp
    input_fetch_completed_timestamp: _timestamp_pb2.Timestamp
    input_fetch_start_timestamp: _timestamp_pb2.Timestamp
    output_upload_completed_timestamp: _timestamp_pb2.Timestamp
    output_upload_start_timestamp: _timestamp_pb2.Timestamp
    queued_timestamp: _timestamp_pb2.Timestamp
    virtual_execution_duration: _duration_pb2.Duration
    worker: str
    worker_completed_timestamp: _timestamp_pb2.Timestamp
    worker_start_timestamp: _timestamp_pb2.Timestamp
    def __init__(self, worker: _Optional[str] = ..., queued_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., worker_start_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., worker_completed_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., input_fetch_start_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., input_fetch_completed_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., execution_start_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., execution_completed_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., virtual_execution_duration: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., output_upload_start_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., output_upload_completed_timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., auxiliary_metadata: _Optional[_Iterable[_Union[_any_pb2.Any, _Mapping]]] = ...) -> None: ...

class ExecutionCapabilities(_message.Message):
    __slots__ = ["digest_function", "exec_enabled", "execution_priority_capabilities", "supported_node_properties"]
    DIGEST_FUNCTION_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_PRIORITY_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    EXEC_ENABLED_FIELD_NUMBER: _ClassVar[int]
    SUPPORTED_NODE_PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    digest_function: DigestFunction.Value
    exec_enabled: bool
    execution_priority_capabilities: PriorityCapabilities
    supported_node_properties: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, digest_function: _Optional[_Union[DigestFunction.Value, str]] = ..., exec_enabled: bool = ..., execution_priority_capabilities: _Optional[_Union[PriorityCapabilities, _Mapping]] = ..., supported_node_properties: _Optional[_Iterable[str]] = ...) -> None: ...

class ExecutionPolicy(_message.Message):
    __slots__ = ["priority"]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    priority: int
    def __init__(self, priority: _Optional[int] = ...) -> None: ...

class ExecutionStage(_message.Message):
    __slots__ = []
    class Value(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
    CACHE_CHECK: ExecutionStage.Value
    COMPLETED: ExecutionStage.Value
    EXECUTING: ExecutionStage.Value
    QUEUED: ExecutionStage.Value
    UNKNOWN: ExecutionStage.Value
    def __init__(self) -> None: ...

class FileNode(_message.Message):
    __slots__ = ["digest", "is_executable", "name", "node_properties"]
    DIGEST_FIELD_NUMBER: _ClassVar[int]
    IS_EXECUTABLE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    NODE_PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    digest: Digest
    is_executable: bool
    name: str
    node_properties: NodeProperties
    def __init__(self, name: _Optional[str] = ..., digest: _Optional[_Union[Digest, _Mapping]] = ..., is_executable: bool = ..., node_properties: _Optional[_Union[NodeProperties, _Mapping]] = ...) -> None: ...

class FindMissingBlobsRequest(_message.Message):
    __slots__ = ["blob_digests", "instance_name"]
    BLOB_DIGESTS_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_NAME_FIELD_NUMBER: _ClassVar[int]
    blob_digests: _containers.RepeatedCompositeFieldContainer[Digest]
    instance_name: str
    def __init__(self, instance_name: _Optional[str] = ..., blob_digests: _Optional[_Iterable[_Union[Digest, _Mapping]]] = ...) -> None: ...

class FindMissingBlobsResponse(_message.Message):
    __slots__ = ["missing_blob_digests"]
    MISSING_BLOB_DIGESTS_FIELD_NUMBER: _ClassVar[int]
    missing_blob_digests: _containers.RepeatedCompositeFieldContainer[Digest]
    def __init__(self, missing_blob_digests: _Optional[_Iterable[_Union[Digest, _Mapping]]] = ...) -> None: ...

class GetActionResultRequest(_message.Message):
    __slots__ = ["action_digest", "inline_output_files", "inline_stderr", "inline_stdout", "instance_name"]
    ACTION_DIGEST_FIELD_NUMBER: _ClassVar[int]
    INLINE_OUTPUT_FILES_FIELD_NUMBER: _ClassVar[int]
    INLINE_STDERR_FIELD_NUMBER: _ClassVar[int]
    INLINE_STDOUT_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_NAME_FIELD_NUMBER: _ClassVar[int]
    action_digest: Digest
    inline_output_files: _containers.RepeatedScalarFieldContainer[str]
    inline_stderr: bool
    inline_stdout: bool
    instance_name: str
    def __init__(self, instance_name: _Optional[str] = ..., action_digest: _Optional[_Union[Digest, _Mapping]] = ..., inline_stdout: bool = ..., inline_stderr: bool = ..., inline_output_files: _Optional[_Iterable[str]] = ...) -> None: ...

class GetCapabilitiesRequest(_message.Message):
    __slots__ = ["instance_name"]
    INSTANCE_NAME_FIELD_NUMBER: _ClassVar[int]
    instance_name: str
    def __init__(self, instance_name: _Optional[str] = ...) -> None: ...

class GetTreeRequest(_message.Message):
    __slots__ = ["instance_name", "page_size", "page_token", "root_digest"]
    INSTANCE_NAME_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ROOT_DIGEST_FIELD_NUMBER: _ClassVar[int]
    instance_name: str
    page_size: int
    page_token: str
    root_digest: Digest
    def __init__(self, instance_name: _Optional[str] = ..., root_digest: _Optional[_Union[Digest, _Mapping]] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class GetTreeResponse(_message.Message):
    __slots__ = ["directories", "next_page_token"]
    DIRECTORIES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    directories: _containers.RepeatedCompositeFieldContainer[Directory]
    next_page_token: str
    def __init__(self, directories: _Optional[_Iterable[_Union[Directory, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class LogFile(_message.Message):
    __slots__ = ["digest", "human_readable"]
    DIGEST_FIELD_NUMBER: _ClassVar[int]
    HUMAN_READABLE_FIELD_NUMBER: _ClassVar[int]
    digest: Digest
    human_readable: bool
    def __init__(self, digest: _Optional[_Union[Digest, _Mapping]] = ..., human_readable: bool = ...) -> None: ...

class NodeProperties(_message.Message):
    __slots__ = ["mtime", "properties", "unix_mode"]
    MTIME_FIELD_NUMBER: _ClassVar[int]
    PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    UNIX_MODE_FIELD_NUMBER: _ClassVar[int]
    mtime: _timestamp_pb2.Timestamp
    properties: _containers.RepeatedCompositeFieldContainer[NodeProperty]
    unix_mode: _wrappers_pb2.UInt32Value
    def __init__(self, properties: _Optional[_Iterable[_Union[NodeProperty, _Mapping]]] = ..., mtime: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., unix_mode: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ...) -> None: ...

class NodeProperty(_message.Message):
    __slots__ = ["name", "value"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: str
    def __init__(self, name: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class OutputDirectory(_message.Message):
    __slots__ = ["is_topologically_sorted", "path", "tree_digest"]
    IS_TOPOLOGICALLY_SORTED_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    TREE_DIGEST_FIELD_NUMBER: _ClassVar[int]
    is_topologically_sorted: bool
    path: str
    tree_digest: Digest
    def __init__(self, path: _Optional[str] = ..., tree_digest: _Optional[_Union[Digest, _Mapping]] = ..., is_topologically_sorted: bool = ...) -> None: ...

class OutputFile(_message.Message):
    __slots__ = ["contents", "digest", "is_executable", "node_properties", "path"]
    CONTENTS_FIELD_NUMBER: _ClassVar[int]
    DIGEST_FIELD_NUMBER: _ClassVar[int]
    IS_EXECUTABLE_FIELD_NUMBER: _ClassVar[int]
    NODE_PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    contents: bytes
    digest: Digest
    is_executable: bool
    node_properties: NodeProperties
    path: str
    def __init__(self, path: _Optional[str] = ..., digest: _Optional[_Union[Digest, _Mapping]] = ..., is_executable: bool = ..., contents: _Optional[bytes] = ..., node_properties: _Optional[_Union[NodeProperties, _Mapping]] = ...) -> None: ...

class OutputSymlink(_message.Message):
    __slots__ = ["node_properties", "path", "target"]
    NODE_PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    node_properties: NodeProperties
    path: str
    target: str
    def __init__(self, path: _Optional[str] = ..., target: _Optional[str] = ..., node_properties: _Optional[_Union[NodeProperties, _Mapping]] = ...) -> None: ...

class Platform(_message.Message):
    __slots__ = ["properties"]
    class Property(_message.Message):
        __slots__ = ["name", "value"]
        NAME_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        name: str
        value: str
        def __init__(self, name: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    properties: _containers.RepeatedCompositeFieldContainer[Platform.Property]
    def __init__(self, properties: _Optional[_Iterable[_Union[Platform.Property, _Mapping]]] = ...) -> None: ...

class PriorityCapabilities(_message.Message):
    __slots__ = ["priorities"]
    class PriorityRange(_message.Message):
        __slots__ = ["max_priority", "min_priority"]
        MAX_PRIORITY_FIELD_NUMBER: _ClassVar[int]
        MIN_PRIORITY_FIELD_NUMBER: _ClassVar[int]
        max_priority: int
        min_priority: int
        def __init__(self, min_priority: _Optional[int] = ..., max_priority: _Optional[int] = ...) -> None: ...
    PRIORITIES_FIELD_NUMBER: _ClassVar[int]
    priorities: _containers.RepeatedCompositeFieldContainer[PriorityCapabilities.PriorityRange]
    def __init__(self, priorities: _Optional[_Iterable[_Union[PriorityCapabilities.PriorityRange, _Mapping]]] = ...) -> None: ...

class RequestMetadata(_message.Message):
    __slots__ = ["action_id", "action_mnemonic", "configuration_id", "correlated_invocations_id", "target_id", "tool_details", "tool_invocation_id"]
    ACTION_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_MNEMONIC_FIELD_NUMBER: _ClassVar[int]
    CONFIGURATION_ID_FIELD_NUMBER: _ClassVar[int]
    CORRELATED_INVOCATIONS_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ID_FIELD_NUMBER: _ClassVar[int]
    TOOL_DETAILS_FIELD_NUMBER: _ClassVar[int]
    TOOL_INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    action_id: str
    action_mnemonic: str
    configuration_id: str
    correlated_invocations_id: str
    target_id: str
    tool_details: ToolDetails
    tool_invocation_id: str
    def __init__(self, tool_details: _Optional[_Union[ToolDetails, _Mapping]] = ..., action_id: _Optional[str] = ..., tool_invocation_id: _Optional[str] = ..., correlated_invocations_id: _Optional[str] = ..., action_mnemonic: _Optional[str] = ..., target_id: _Optional[str] = ..., configuration_id: _Optional[str] = ...) -> None: ...

class ResultsCachePolicy(_message.Message):
    __slots__ = ["priority"]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    priority: int
    def __init__(self, priority: _Optional[int] = ...) -> None: ...

class ServerCapabilities(_message.Message):
    __slots__ = ["cache_capabilities", "deprecated_api_version", "execution_capabilities", "high_api_version", "low_api_version"]
    CACHE_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    DEPRECATED_API_VERSION_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    HIGH_API_VERSION_FIELD_NUMBER: _ClassVar[int]
    LOW_API_VERSION_FIELD_NUMBER: _ClassVar[int]
    cache_capabilities: CacheCapabilities
    deprecated_api_version: _semver_pb2.SemVer
    execution_capabilities: ExecutionCapabilities
    high_api_version: _semver_pb2.SemVer
    low_api_version: _semver_pb2.SemVer
    def __init__(self, cache_capabilities: _Optional[_Union[CacheCapabilities, _Mapping]] = ..., execution_capabilities: _Optional[_Union[ExecutionCapabilities, _Mapping]] = ..., deprecated_api_version: _Optional[_Union[_semver_pb2.SemVer, _Mapping]] = ..., low_api_version: _Optional[_Union[_semver_pb2.SemVer, _Mapping]] = ..., high_api_version: _Optional[_Union[_semver_pb2.SemVer, _Mapping]] = ...) -> None: ...

class SymlinkAbsolutePathStrategy(_message.Message):
    __slots__ = []
    class Value(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
    ALLOWED: SymlinkAbsolutePathStrategy.Value
    DISALLOWED: SymlinkAbsolutePathStrategy.Value
    UNKNOWN: SymlinkAbsolutePathStrategy.Value
    def __init__(self) -> None: ...

class SymlinkNode(_message.Message):
    __slots__ = ["name", "node_properties", "target"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    NODE_PROPERTIES_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    name: str
    node_properties: NodeProperties
    target: str
    def __init__(self, name: _Optional[str] = ..., target: _Optional[str] = ..., node_properties: _Optional[_Union[NodeProperties, _Mapping]] = ...) -> None: ...

class ToolDetails(_message.Message):
    __slots__ = ["tool_name", "tool_version"]
    TOOL_NAME_FIELD_NUMBER: _ClassVar[int]
    TOOL_VERSION_FIELD_NUMBER: _ClassVar[int]
    tool_name: str
    tool_version: str
    def __init__(self, tool_name: _Optional[str] = ..., tool_version: _Optional[str] = ...) -> None: ...

class Tree(_message.Message):
    __slots__ = ["children", "root"]
    CHILDREN_FIELD_NUMBER: _ClassVar[int]
    ROOT_FIELD_NUMBER: _ClassVar[int]
    children: _containers.RepeatedCompositeFieldContainer[Directory]
    root: Directory
    def __init__(self, root: _Optional[_Union[Directory, _Mapping]] = ..., children: _Optional[_Iterable[_Union[Directory, _Mapping]]] = ...) -> None: ...

class UpdateActionResultRequest(_message.Message):
    __slots__ = ["action_digest", "action_result", "instance_name", "results_cache_policy"]
    ACTION_DIGEST_FIELD_NUMBER: _ClassVar[int]
    ACTION_RESULT_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_NAME_FIELD_NUMBER: _ClassVar[int]
    RESULTS_CACHE_POLICY_FIELD_NUMBER: _ClassVar[int]
    action_digest: Digest
    action_result: ActionResult
    instance_name: str
    results_cache_policy: ResultsCachePolicy
    def __init__(self, instance_name: _Optional[str] = ..., action_digest: _Optional[_Union[Digest, _Mapping]] = ..., action_result: _Optional[_Union[ActionResult, _Mapping]] = ..., results_cache_policy: _Optional[_Union[ResultsCachePolicy, _Mapping]] = ...) -> None: ...

class WaitExecutionRequest(_message.Message):
    __slots__ = ["name"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...
