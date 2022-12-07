from __future__ import annotations

import typing
import hashlib

from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest
from build.bazel.remote.execution.v2.remote_execution_pb2 import Directory
from build.bazel.remote.execution.v2.remote_execution_pb2 import DirectoryNode
from build.bazel.remote.execution.v2.remote_execution_pb2 import FileNode

import pytest


DirectoryData = typing.Dict[str, typing.Union[bytes, "DirectoryData"]]


class MockCASHelper(object):
    def __init__(self):
        self._data_store: typing.Dict[typing.Tuple[str, int], bytes] = {}
        self._call_history = []

    @property
    def call_history(self):
        return self._call_history

    def append_digest_data(self, data: bytes) -> Digest:
        size_bytes = len(data)
        hash_value = hashlib.sha256(data).hexdigest()
        digest = Digest(hash=hash_value, size_bytes=size_bytes)
        self._data_store[(digest.hash, digest.size_bytes)] = data
        return digest

    def append_file(self, name: str, data: bytes) -> FileNode:
        digest = self.append_digest_data(data)
        return FileNode(name=name, digest=digest)

    def append_directory(self, directory_data: DirectoryData) -> Digest:
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

    def fetch_all(self, digests: typing.Iterable[Digest]):
        self._call_history.append(digests)
        for d in digests:
            yield d, 0, self._data_store[(d.hash, d.size_bytes)]

    def clear_call_history(self):
        self._call_history = []


@pytest.fixture
def mock_cas_helper():
    return MockCASHelper()
