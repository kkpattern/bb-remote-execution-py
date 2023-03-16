import typing
import hashlib

from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest

from worker.cas import CASCache


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

    def fetch_all(self, digests: typing.Iterable[Digest]):
        self._call_history.append(digests)
        for d in digests:
            yield d, 0, self._data_store[(d.hash, d.size_bytes)]

    def clear_call_history(self):
        self._call_history = []


def test_cas_cache():
    cas_helper = MockCASHelper()
    digest = cas_helper.append_digest_data(b"abced")
    cas_cache = CASCache(cas_helper)
    for d, offset, data in cas_cache.fetch_all([digest]):
        assert data == b"abced"
        assert offset == 0
        assert digest == d
    assert len(cas_helper.call_history) == 1
    cas_helper.clear_call_history()
    for d, offset, data in cas_cache.fetch_all([digest]):
        assert data == b"abced"
        assert offset == 0
        assert digest == d
    assert len(cas_helper.call_history) == 0
