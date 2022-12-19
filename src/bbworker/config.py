import re
import typing

from pydantic import BaseModel
from pydantic import BaseSettings
from pydantic import validator


_KB = 1024
_MB = 1024 * 1024
_GB = 1024 * 1024 * 1024


def parse_size_bytes(raw: str | int) -> int:
    if isinstance(raw, str):
        m = re.match(r"^(?P<number>\d+)(?P<unit>[GgMmKk]?)[Bb]?$", raw)
        if m:
            number = m.group("number")
            unit_str = m.group("unit")
            match unit_str:
                case "G" | "g":
                    unit = _GB
                case "M" | "m":
                    unit = _MB
                case "K" | "k":
                    unit = _KB
                case _:
                    unit = 1
            result = int(number) * unit
        else:
            raise ValueError(f"{raw} is not a valid size bytes value.")
    else:
        result = raw
    return result


class BuildbarnConfig(BaseModel):
    cas_address: str
    scheduler_address: str


class FileSystemConfig(BaseModel):
    cache_root: str
    max_cache_size_bytes: int = 0
    concurrency: int = 10
    download_batch_size_bytes: int = 3 * 1024 * 1024

    _max_cache_size_bytes_validator = validator(
        "max_cache_size_bytes", pre=True, allow_reuse=True
    )(parse_size_bytes)

    _download_batch_size_bytes_validator = validator(
        "download_batch_size_bytes", pre=True, allow_reuse=True
    )(parse_size_bytes)


class BuildDirectoryBuilderConfig(BaseModel):
    cache_root: str
    max_cache_size_bytes: int = 0
    concurrency: int = 10

    _max_cache_size_bytes_validator = validator(
        "max_cache_size_bytes", pre=True, allow_reuse=True
    )(parse_size_bytes)


class Property(BaseModel):
    name: str
    value: str


class Platform(BaseModel):
    properties: typing.List[Property]


class Sentry(BaseModel):
    address: str
    traces_sample_rate: float = 0.1


class OpenTelemetry(BaseModel):
    http_host: str
    http_port: int


class Config(BaseSettings):
    buildbarn: BuildbarnConfig
    platform: Platform
    worker_id: typing.Dict[str, str]
    filesystem: FileSystemConfig
    build_directory_builder: BuildDirectoryBuilderConfig
    build_root: str
    concurrency: int = 1
    sentry: Sentry | None
    open_telemetry: OpenTelemetry | None
