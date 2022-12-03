from google.api import annotations_pb2 as _annotations_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class QueryWriteStatusRequest(_message.Message):
    __slots__ = ["resource_name"]
    RESOURCE_NAME_FIELD_NUMBER: _ClassVar[int]
    resource_name: str
    def __init__(self, resource_name: _Optional[str] = ...) -> None: ...

class QueryWriteStatusResponse(_message.Message):
    __slots__ = ["committed_size", "complete"]
    COMMITTED_SIZE_FIELD_NUMBER: _ClassVar[int]
    COMPLETE_FIELD_NUMBER: _ClassVar[int]
    committed_size: int
    complete: bool
    def __init__(self, committed_size: _Optional[int] = ..., complete: bool = ...) -> None: ...

class ReadRequest(_message.Message):
    __slots__ = ["read_limit", "read_offset", "resource_name"]
    READ_LIMIT_FIELD_NUMBER: _ClassVar[int]
    READ_OFFSET_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_NAME_FIELD_NUMBER: _ClassVar[int]
    read_limit: int
    read_offset: int
    resource_name: str
    def __init__(self, resource_name: _Optional[str] = ..., read_offset: _Optional[int] = ..., read_limit: _Optional[int] = ...) -> None: ...

class ReadResponse(_message.Message):
    __slots__ = ["data"]
    DATA_FIELD_NUMBER: _ClassVar[int]
    data: bytes
    def __init__(self, data: _Optional[bytes] = ...) -> None: ...

class WriteRequest(_message.Message):
    __slots__ = ["data", "finish_write", "resource_name", "write_offset"]
    DATA_FIELD_NUMBER: _ClassVar[int]
    FINISH_WRITE_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_NAME_FIELD_NUMBER: _ClassVar[int]
    WRITE_OFFSET_FIELD_NUMBER: _ClassVar[int]
    data: bytes
    finish_write: bool
    resource_name: str
    write_offset: int
    def __init__(self, resource_name: _Optional[str] = ..., write_offset: _Optional[int] = ..., finish_write: bool = ..., data: _Optional[bytes] = ...) -> None: ...

class WriteResponse(_message.Message):
    __slots__ = ["committed_size"]
    COMMITTED_SIZE_FIELD_NUMBER: _ClassVar[int]
    committed_size: int
    def __init__(self, committed_size: _Optional[int] = ...) -> None: ...
