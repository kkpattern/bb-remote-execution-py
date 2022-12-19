from __future__ import annotations

import time
import typing
import hashlib

from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest
from build.bazel.remote.execution.v2.remote_execution_pb2 import Directory
from build.bazel.remote.execution.v2.remote_execution_pb2 import DirectoryNode
from build.bazel.remote.execution.v2.remote_execution_pb2 import FileNode

import pytest

from bbworker.directorybuilder import DirectoryData
from bbworker.directorybuilder import FileData


DirectoryDict = typing.Dict[str, typing.Union[bytes, "DirectoryDict"]]
DigestKey = typing.Tuple[str, int]


class MockCASHelper(object):
    def __init__(self):
        self._data_store: typing.Dict[DigestKey, bytes] = {}
        self._exceptions: typing.Dict[DigestKey, Exception] = {}
        self._executable: typing.Dict[DigestKey, bool] = {}
        self._call_history = []
        self._seconds_per_byte: typing.Union[int, float] = 0

    @property
    def call_history(self):
        return self._call_history

    def set_seconds_per_byte(self, v: typing.Union[int, float]):
        self._seconds_per_byte = v

    def append_digest_data(self, data: bytes) -> Digest:
        digest = self._data_to_digest(data)
        self._data_store[(digest.hash, digest.size_bytes)] = data
        return digest

    def append_file(self, name: str, data: bytes) -> FileNode:
        digest = self.append_digest_data(data)
        is_executable = self._executable.get(
            (digest.hash, digest.size_bytes), False
        )
        return FileNode(name=name, digest=digest, is_executable=is_executable)

    def append_directory(self, directory_data: DirectoryDict) -> Digest:
        directory = Directory()
        for key in sorted(directory_data):
            value = directory_data[key]
            if isinstance(value, bytes):
                directory.files.append(self.append_file(key, value))
            elif isinstance(value, dict):
                directory_digest = self.append_directory(value)
                directory.directories.append(
                    DirectoryNode(name=key, digest=directory_digest)
                )
        return self.append_digest_data(directory.SerializeToString(True))

    def get_directory_by_digest(self, digest: Digest) -> Directory:
        data = self._data_store[(digest.hash, digest.size_bytes)]
        d = Directory()
        d.ParseFromString(data)
        return d

    def get_directory_data_by_digest(self, digest: Digest) -> DirectoryData:
        data = self._data_store[(digest.hash, digest.size_bytes)]
        d = Directory()
        d.ParseFromString(data)
        files = {}
        for fnode in d.files:
            files[fnode.name] = FileData(
                fnode.digest,
                self._executable.get(
                    (fnode.digest.hash, fnode.digest.size_bytes), False
                ),
            )
        subdirs = {}
        for fnode in d.directories:
            subdirs[fnode.name] = self.get_directory_data_by_digest(
                fnode.digest
            )
        return DirectoryData(digest, files, subdirs)

    def fetch_all(self, digests: typing.Iterable[Digest]):
        self._call_history.append(digests)
        if self._seconds_per_byte > 0:
            total_size = sum([d.size_bytes for d in digests])
            time.sleep(total_size * self._seconds_per_byte)
        for d in digests:
            key = (d.hash, d.size_bytes)
            if key in self._exceptions:
                raise self._exceptions[key]
            yield d, self._data_store[key]

    def fetch_all_block(self, digests: typing.Iterable[Digest]):
        self._call_history.append(digests)
        if self._seconds_per_byte > 0:
            total_size = sum([d.size_bytes for d in digests])
            time.sleep(total_size * self._seconds_per_byte)
        for d in digests:
            key = (d.hash, d.size_bytes)
            if key in self._exceptions:
                raise self._exceptions[key]
            yield d, 0, self._data_store[(d.hash, d.size_bytes)]

    def set_data_exception(self, data: bytes, exception: Exception):
        digest = self._data_to_digest(data)
        self._exceptions[(digest.hash, digest.size_bytes)] = exception

    def set_data_executable(self, data: bytes, executable: bool):
        digest = self._data_to_digest(data)
        self._executable[(digest.hash, digest.size_bytes)] = executable

    def clear_call_history(self):
        self._call_history = []

    def _data_to_digest(self, data: bytes) -> Digest:
        size_bytes = len(data)
        hash_value = hashlib.sha256(data).hexdigest()
        return Digest(hash=hash_value, size_bytes=size_bytes)


@pytest.fixture
def mock_cas_helper():
    return MockCASHelper()


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "only_in_full_test: skip this test unless --full is provided",
    )


def pytest_addoption(parser):
    parser.addoption(
        "--full", action="store_true", help="run full test. will be slow"
    )


def pytest_runtest_setup(item):
    if "only_in_full_test" in item.keywords and not item.config.getoption(
        "--full"
    ):
        pytest.skip("this test will only run in full mode")
