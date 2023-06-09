from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class MetricRule(_message.Message):
    __slots__ = ["metric_costs", "selector"]
    class MetricCostsEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    METRIC_COSTS_FIELD_NUMBER: _ClassVar[int]
    SELECTOR_FIELD_NUMBER: _ClassVar[int]
    metric_costs: _containers.ScalarMap[str, int]
    selector: str
    def __init__(self, selector: _Optional[str] = ..., metric_costs: _Optional[_Mapping[str, int]] = ...) -> None: ...

class Quota(_message.Message):
    __slots__ = ["limits", "metric_rules"]
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    METRIC_RULES_FIELD_NUMBER: _ClassVar[int]
    limits: _containers.RepeatedCompositeFieldContainer[QuotaLimit]
    metric_rules: _containers.RepeatedCompositeFieldContainer[MetricRule]
    def __init__(self, limits: _Optional[_Iterable[_Union[QuotaLimit, _Mapping]]] = ..., metric_rules: _Optional[_Iterable[_Union[MetricRule, _Mapping]]] = ...) -> None: ...

class QuotaLimit(_message.Message):
    __slots__ = ["default_limit", "description", "display_name", "duration", "free_tier", "max_limit", "metric", "name", "unit", "values"]
    class ValuesEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    DEFAULT_LIMIT_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    FREE_TIER_FIELD_NUMBER: _ClassVar[int]
    MAX_LIMIT_FIELD_NUMBER: _ClassVar[int]
    METRIC_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    UNIT_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    default_limit: int
    description: str
    display_name: str
    duration: str
    free_tier: int
    max_limit: int
    metric: str
    name: str
    unit: str
    values: _containers.ScalarMap[str, int]
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., default_limit: _Optional[int] = ..., max_limit: _Optional[int] = ..., free_tier: _Optional[int] = ..., duration: _Optional[str] = ..., metric: _Optional[str] = ..., unit: _Optional[str] = ..., values: _Optional[_Mapping[str, int]] = ..., display_name: _Optional[str] = ...) -> None: ...
