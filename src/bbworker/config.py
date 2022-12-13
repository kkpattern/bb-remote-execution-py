import typing

from pydantic import BaseModel
from pydantic import BaseSettings


class BuildbarnConfig(BaseModel):
    cas_address: str
    scheduler_address: str


class FileSystemConfig(BaseModel):
    cache_root: str
    max_cache_size_bytes: int = 0
    concurrency: int = 10
    download_batch_size_bytes: int = 3 * 1024 * 1024


class BuildDirectoryBuilderConfig(BaseModel):
    cache_root: str


class Property(BaseModel):
    name: str
    value: str


class Platform(BaseModel):
    properties: typing.List[Property]


class Config(BaseSettings):
    buildbarn: BuildbarnConfig
    platform: Platform
    worker_id: typing.Dict[str, str]
    filesystem: FileSystemConfig
    build_directory_builder: BuildDirectoryBuilderConfig
    build_root: str
    concurrency: int = 1
