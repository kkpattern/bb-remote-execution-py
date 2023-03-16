import collections
import hashlib
import os.path
import typing
import uuid

import grpc
import grpc.aio
from google.bytestream.bytestream_pb2 import ReadRequest
from google.bytestream.bytestream_pb2 import WriteRequest
from google.bytestream.bytestream_pb2_grpc import ByteStreamStub
from build.bazel.remote.execution.v2.remote_execution_pb2 import (
    BatchReadBlobsRequest,
)
from build.bazel.remote.execution.v2.remote_execution_pb2 import (
    BatchUpdateBlobsRequest,
)
from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest
from build.bazel.remote.execution.v2.remote_execution_pb2_grpc import (
    ContentAddressableStorageStub,
)


class IProvider:
    @property
    def size_bytes(self) -> int:
        raise NotImplementedError(
            f"This method should be implmented in {self.__class__.__name__}"
        )

    @property
    def hash_(self) -> str:
        raise NotImplementedError(
            f"This method should be implmented in {self.__class__.__name__}"
        )

    def read(
        self, segment_size: typing.Optional[int] = None
    ) -> typing.Iterator[bytes]:
        raise NotImplementedError(
            f"This method should be implmented in {self.__class__.__name__}"
        )

    def read_all(self) -> bytes:
        raise NotImplementedError(
            f"This method should be implmented in {self.__class__.__name__}"
        )


class FileProvider(IProvider):
    def __init__(self, filepath: str):
        self._filepath = filepath
        self._size_bytes: typing.Optional[int] = None
        self._digest: typing.Optional[str] = None

    @property
    def size_bytes(self) -> int:
        if self._size_bytes is None:
            self._size_bytes = os.path.getsize(self._filepath)
        return self._size_bytes

    @property
    def hash_(self) -> str:
        if self._digest is None:
            sha256 = hashlib.sha256()
            for data in self.read(3 * 1024 * 1024):
                sha256.update(data)
            self._digest = sha256.hexdigest()
        return self._digest

    def read(
        self, segment_size: typing.Optional[int] = None
    ) -> typing.Iterator[bytes]:
        if segment_size is None:
            with open(self._filepath, "rb") as f:
                data = f.read()
            return data
        else:
            with open(self._filepath, "rb") as f:
                while True:
                    data = f.read(segment_size)
                    if data:
                        yield data
                    else:
                        break

    def read_all(self) -> bytes:
        with open(self._filepath, "rb") as f:
            data = f.read()
        return data


class BytesProvider(IProvider):
    def __init__(self, data: bytes):
        self._data = data
        self._size_bytes = len(self._data)
        self._digest: typing.Optional[str] = None

    @property
    def size_bytes(self) -> int:
        return self._size_bytes

    @property
    def hash_(self) -> str:
        if self._digest is None:
            self._digest = hashlib.sha256(self._data).hexdigest()
        return self._digest

    def read(
        self, segment_size: typing.Optional[int] = None
    ) -> typing.Iterator[bytes]:
        if segment_size is None:
            return self._data
        else:
            start = 0
            end = segment_size
            while True:
                yield self._data[start:end]
                start += segment_size
                end += segment_size
                if start >= self._size_bytes:
                    break

    def read_all(self) -> bytes:
        return self._data


class FetchBatch(object):
    def __init__(self) -> None:
        self._digests: typing.List[Digest] = []
        self._total_size_bytes = 0

    @property
    def digests(self):
        return self._digests

    @property
    def total_size_bytes(self):
        return self._total_size_bytes

    def append_digest(self, digest: Digest):
        self._digests.append(digest)
        self._total_size_bytes += digest.size_bytes


class UpdateBatch(object):
    def __init__(self) -> None:
        self._providers: typing.List[IProvider] = []
        self._total_size_bytes = 0

    @property
    def providers(self) -> typing.List[IProvider]:
        return self._providers

    @property
    def total_size_bytes(self):
        return self._total_size_bytes

    def append_provider(self, provider):
        self._providers.append(provider)
        self._total_size_bytes += provider.size_bytes


class CASHelper(object):
    """ContentAddressableStorage helper class."""

    def __init__(
        self,
        cas_stub: ContentAddressableStorageStub,
        cas_byte_stream_stub: ByteStreamStub,
        msg_size_bytes_limit: int = 3 * 1024 * 1024,
    ):
        self._cas_stub = cas_stub
        self._byte_steam_stub = cas_byte_stream_stub
        self._msg_size_bytes_limit = msg_size_bytes_limit

    def fetch_all(
        self, digests: typing.Iterable[Digest]
    ) -> typing.Iterator[typing.Tuple[Digest, bytes]]:
        batch = FetchBatch()
        batch_list = [batch]
        bytes_limit = self._msg_size_bytes_limit
        large_blob = {}
        for each_digest in digests:
            size_bytes = each_digest.size_bytes
            if size_bytes >= bytes_limit:
                large_blob[
                    (each_digest.hash, each_digest.size_bytes)
                ] = each_digest
            elif batch.total_size_bytes + size_bytes < bytes_limit:
                batch.append_digest(each_digest)
            else:
                batch = FetchBatch()
                batch.append_digest(each_digest)
                batch_list.append(batch)
        for i, batch in enumerate(batch_list):
            if batch.digests:
                request = BatchReadBlobsRequest(digests=batch.digests)
                response = self._cas_stub.BatchReadBlobs(request)
                for each in response.responses:
                    if each.status.code != grpc.StatusCode.OK.value[0]:
                        print(each.status.message)
                        continue
                    yield each.digest, each.data

        for each_digest in large_blob.values():
            bytes_stream = self._read_bytes_from_stream(each_digest)
            tmp = bytearray()
            for offset, data in bytes_stream:
                tmp.extend(data)
            yield each_digest, bytes(tmp)

    def fetch_all_block(
        self, digests: typing.Iterable[Digest]
    ) -> typing.Iterator[typing.Tuple[Digest, int, bytes]]:
        batch = FetchBatch()
        batch_list = [batch]
        bytes_limit = self._msg_size_bytes_limit
        large_blob = {}
        for each_digest in digests:
            size_bytes = each_digest.size_bytes
            if size_bytes >= bytes_limit:
                large_blob[
                    (each_digest.hash, each_digest.size_bytes)
                ] = each_digest
            elif batch.total_size_bytes + size_bytes < bytes_limit:
                batch.append_digest(each_digest)
            else:
                batch = FetchBatch()
                batch.append_digest(each_digest)
                batch_list.append(batch)
        for i, batch in enumerate(batch_list):
            if batch.digests:
                request = BatchReadBlobsRequest(digests=batch.digests)
                response = self._cas_stub.BatchReadBlobs(request)
                for each in response.responses:
                    if each.status.code != grpc.StatusCode.OK.value[0]:
                        print(each.status.message)
                        continue
                    yield each.digest, 0, each.data

        for each_digest in large_blob.values():
            bytes_stream = self._read_bytes_from_stream(each_digest)
            for offset, data in bytes_stream:
                yield each_digest, offset, data

    def _read_bytes_from_stream(self, digest: Digest):
        resource_name = "blobs/{hash_}/{size}".format(
            hash_=digest.hash, size=digest.size_bytes
        )
        request = ReadRequest(
            resource_name=resource_name, read_offset=0, read_limit=0
        )
        offset = 0
        for response in self._byte_steam_stub.Read(request):
            if not response.data:
                continue
            yield offset, response.data
            received_bytes = len(response.data)
            offset += received_bytes
            if offset >= digest.size_bytes:
                assert offset == digest.size_bytes
                break

    def update_all(self, provider_list: typing.Iterable[IProvider]):
        batch = UpdateBatch()
        batch_list = [batch]
        bytes_limit = self._msg_size_bytes_limit
        for provider in provider_list:
            size_bytes = provider.size_bytes
            if size_bytes >= bytes_limit:
                self._write_bytes_to_steam(provider)
            elif batch.total_size_bytes + size_bytes < bytes_limit:
                batch.append_provider(provider)
            else:
                batch = UpdateBatch()
                batch.append_provider(provider)
                batch_list.append(batch)
        for batch in batch_list:
            requests: typing.List[BatchUpdateBlobsRequest.Request] = []
            for provider in batch.providers:
                data = provider.read_all()
                requests.append(
                    BatchUpdateBlobsRequest.Request(
                        digest={
                            "hash": provider.hash_,
                            "size_bytes": provider.size_bytes,
                        },
                        data=data,
                    )
                )
            update_request = BatchUpdateBlobsRequest(requests=requests)
            response = self._cas_stub.BatchUpdateBlobs(update_request)
            for each in response.responses:
                if each.status.code != grpc.StatusCode.OK.value[0]:
                    # TODO:
                    print(each.status.message)

    def _write_bytes_to_steam(self, provider: IProvider):
        self._byte_steam_stub.Write(self._write_requests(provider))

    def _write_requests(self, provider: IProvider):
        hash_ = provider.hash_
        total_size_bytes = provider.size_bytes
        resource_name = "uploads/{uuid_}/blobs/{hash_}/{size}".format(
            uuid_=uuid.uuid4(), hash_=hash_, size=total_size_bytes
        )
        offset = 0
        for data in provider.read(segment_size=self._msg_size_bytes_limit):
            data_size = len(data)
            if data_size + offset >= total_size_bytes:
                assert data_size + offset == total_size_bytes
                finish_write = True
            else:
                finish_write = False
            yield WriteRequest(
                resource_name=resource_name,
                write_offset=offset,
                finish_write=finish_write,
                data=data,
            )
            offset += data_size


DigestKey = typing.Tuple[str, int]
CacheInternalResult = typing.Tuple[Digest, bytes]
CacheResult = typing.Tuple[Digest, int, bytes]


class CASCache(object):
    """A CAS cache.

    NOTE: If a blob is larger than max_size_bytes it won't be cached.
    """

    def __init__(self, backend: CASHelper, max_size_bytes: int = 0):
        self._backend = backend
        self._max_size_bytes = max_size_bytes
        self._total_size_bytes = 0
        self._cache: typing.Dict[
            typing.Tuple[str, int], bytes
        ] = collections.OrderedDict()

    def _fetch_all_in_cache(
        self, digests: typing.Iterable[Digest]
    ) -> typing.Tuple[typing.List[CacheInternalResult], typing.List[Digest]]:
        """Fetch a blob in cache. If missing returns None."""
        result_list = []
        missing_list = []
        for each in digests:
            key = (each.hash, each.size_bytes)
            if key in self._cache:
                # use OrderedDict as a LRU cache dict.
                r = self._cache.pop(key)
                self._cache[key] = r
                result_list.append((each, r))
            else:
                missing_list.append(each)
        return (result_list, missing_list)

    def fetch_all(
        self, digests: typing.Iterable[Digest]
    ) -> typing.Iterator[typing.Tuple[Digest, bytes]]:
        result_list, missing_list = self._fetch_all_in_cache(digests)
        if missing_list:
            for d, data in self._backend.fetch_all(missing_list):
                # Small enough to cache.
                if not (d.size_bytes > self._max_size_bytes > 0):
                    self._add_to_cache(d, data)
                yield d, data
        for d, data in result_list:
            yield d, data

    def fetch_all_block(
        self, digests: typing.Iterable[Digest]
    ) -> typing.Iterator[typing.Tuple[Digest, int, bytes]]:
        result_list, missing_list = self._fetch_all_in_cache(digests)
        if missing_list:
            for d, offset, data in self._backend.fetch_all_block(missing_list):
                # Small enough to cache.
                if d.size_bytes == len(data):
                    self._add_to_cache(d, data)
                yield d, offset, data
        for d, data in result_list:
            yield d, 0, data

    def _add_to_cache(self, d: Digest, data: bytes):
        self._cache[(d.hash, d.size_bytes)] = data
        self._total_size_bytes += d.size_bytes
        while self._total_size_bytes > self._max_size_bytes > 0:
            for key in self._cache:
                self._cache.pop(key)
                self._total_size_bytes -= key[1]
                break
