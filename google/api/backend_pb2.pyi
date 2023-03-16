from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Backend(_message.Message):
    __slots__ = ["rules"]
    RULES_FIELD_NUMBER: _ClassVar[int]
    rules: _containers.RepeatedCompositeFieldContainer[BackendRule]
    def __init__(self, rules: _Optional[_Iterable[_Union[BackendRule, _Mapping]]] = ...) -> None: ...

class BackendRule(_message.Message):
    __slots__ = ["address", "deadline", "disable_auth", "jwt_audience", "min_deadline", "operation_deadline", "path_translation", "protocol", "selector"]
    class PathTranslation(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    APPEND_PATH_TO_ADDRESS: BackendRule.PathTranslation
    CONSTANT_ADDRESS: BackendRule.PathTranslation
    DEADLINE_FIELD_NUMBER: _ClassVar[int]
    DISABLE_AUTH_FIELD_NUMBER: _ClassVar[int]
    JWT_AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    MIN_DEADLINE_FIELD_NUMBER: _ClassVar[int]
    OPERATION_DEADLINE_FIELD_NUMBER: _ClassVar[int]
    PATH_TRANSLATION_FIELD_NUMBER: _ClassVar[int]
    PATH_TRANSLATION_UNSPECIFIED: BackendRule.PathTranslation
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    SELECTOR_FIELD_NUMBER: _ClassVar[int]
    address: str
    deadline: float
    disable_auth: bool
    jwt_audience: str
    min_deadline: float
    operation_deadline: float
    path_translation: BackendRule.PathTranslation
    protocol: str
    selector: str
    def __init__(self, selector: _Optional[str] = ..., address: _Optional[str] = ..., deadline: _Optional[float] = ..., min_deadline: _Optional[float] = ..., operation_deadline: _Optional[float] = ..., path_translation: _Optional[_Union[BackendRule.PathTranslation, str]] = ..., jwt_audience: _Optional[str] = ..., disable_auth: bool = ..., protocol: _Optional[str] = ...) -> None: ...
