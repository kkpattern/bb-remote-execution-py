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


def test_cas_cache_without_limit():
    cas_helper = MockCASHelper()
    data_list = [
        b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        b"bbbbbbbbbbbbbbbb",
        b"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        b"c" * (10 * 1024 * 1024),
        b"e" * (10 * 1024 * 1024),
        b"f" * (20 * 1024 * 1024),
    ]
    digest_list = []
    for data in data_list:
        digest_list.append(cas_helper.append_digest_data(data))
    cas_cache = CASCache(cas_helper)
    for i, each_digest in enumerate(digest_list):
        for d, offset, data in cas_cache.fetch_all([each_digest]):
            assert data == data_list[i]
            assert offset == 0
            assert d.hash == each_digest.hash
            assert d.size_bytes == each_digest.size_bytes
    assert len(cas_helper.call_history) == len(data_list)
    cas_helper.clear_call_history()
    # all data should be in cache.
    for i, each_digest in enumerate(digest_list):
        for d, offset, data in cas_cache.fetch_all([each_digest]):
            assert data == data_list[i]
            assert offset == 0
            assert d.hash == each_digest.hash
    assert len(cas_helper.call_history) == 0


def test_cas_cache_cannot_fit_in():
    cas_helper = MockCASHelper()
    data_list = [
        b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        b"bbbbbbbbbbbbbbbb",
        b"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        b"c" * (10 * 1024 * 1024),
        b"e" * (10 * 1024 * 1024),
        b"f" * (20 * 1024 * 1024),
    ]
    digest_list = []
    for data in data_list:
        digest_list.append(cas_helper.append_digest_data(data))
    cas_cache = CASCache(cas_helper, max_size_bytes=1)
    for i, each_digest in enumerate(digest_list):
        for d, offset, data in cas_cache.fetch_all([each_digest]):
            assert data == data_list[i]
            assert offset == 0
            assert d.hash == each_digest.hash
            assert d.size_bytes == each_digest.size_bytes
    assert len(cas_helper.call_history) == len(data_list)
    cas_helper.clear_call_history()
    # all data should not be in cache.
    for i, each_digest in enumerate(digest_list):
        for d, offset, data in cas_cache.fetch_all([each_digest]):
            assert data == data_list[i]
            assert offset == 0
            assert d.hash == each_digest.hash
    assert len(cas_helper.call_history) == len(data_list)


def test_cas_cache_lru():
    cas_helper = MockCASHelper()
    data_list = [
        b"a" * 5,
        b"b" * 3,
        b"c" * 4,
    ]
    digest_list = []
    for data in data_list:
        digest_list.append(cas_helper.append_digest_data(data))
    cas_cache = CASCache(cas_helper, max_size_bytes=10)

    def try_fetch(index: int):
        try_digest, try_data = digest_list[index], data_list[index]
        for d, offset, data in cas_cache.fetch_all([try_digest]):
            assert data == try_data
            assert offset == 0
            assert d.hash == try_digest.hash
            assert d.size_bytes == try_digest.size_bytes

    try_fetch(0)
    try_fetch(1)
    try_fetch(0)
    try_fetch(2)
    # Now data 0, 2 should be in cache and 1 should not.
    cas_helper.clear_call_history()
    try_fetch(0)
    assert len(cas_helper.call_history) == 0
    try_fetch(2)
    assert len(cas_helper.call_history) == 0
    try_fetch(1)
    assert len(cas_helper.call_history) == 1
