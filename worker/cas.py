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
    def __init__(self):
        self._providers = []
        self._total_size_bytes = 0

    @property
    def providers(self):
        return self._providers

    @property
    def total_size_bytes(self):
        return self._total_size_bytes

    def append_provider(self, provider):
        self._providers.append(provider)
        self._total_size_bytes += provider.size_bytes


class FileProvider(object):
    def __init__(self, filepath: str):
        self._filepath = filepath
        self._size_bytes: typing.Optional[int] = None
        self._digest: typing.Optional[str] = None

    @property
    def size_bytes(self):
        if self._size_bytes is None:
            self._size_bytes = os.path.getsize(self._filepath)
        return self._size_bytes

    @property
    def digest(self):
        if self._digest is None:
            sha256 = hashlib.sha256()
            for data in self.read(10 * 1024 * 1024):
                sha256.update(data)
            self._digest = sha256.hexdigest()
        return self._digest

    def read(self, segment_size: typing.Optional[int] = None):
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

    def read_all(self):
        with open(self._filepath, "rb") as f:
            data = f.read()
        return data


class CASHelper(object):
    """ContentAddressableStorage helper class."""

    def __init__(
        self,
        cas_stub: ContentAddressableStorageStub,
        cas_byte_stream_stub: ByteStreamStub,
        msg_size_bytes_limit: int = 10 * 1024 * 1024,
    ):
        self._cas_stub = cas_stub
        self._byte_steam_stub = cas_byte_stream_stub
        self._msg_size_bytes_limit = msg_size_bytes_limit

    def fetch_all(self, digests: typing.Iterable[Digest]):
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
                received_blob_count = 0
                for each in response.responses:
                    if each.status.code != grpc.StatusCode.OK.value[0]:
                        print(each.status.message)
                        continue
                    yield each.digest, 0, each.data
                    received_blob_count += 1
                if received_blob_count != len(batch.digests):
                    raise RuntimeError(
                        "Not much {0} {1}".format(
                            received_blob_count, len(batch.digests)
                        )
                    )

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
        sha256 = hashlib.sha256()
        for response in self._byte_steam_stub.Read(request):
            if not response.data:
                continue
            sha256.update(response.data)
            yield offset, response.data
            received_bytes = len(response.data)
            offset += received_bytes
            if offset >= digest.size_bytes:
                assert offset == digest.size_bytes
                break
        if sha256.hexdigest() != digest.hash:
            raise ValueError("Hash not match")

    def update_all(self, provider_list: typing.Iterable[FileProvider]):
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
                batch_list.append(batch)
        for batch in batch_list:
            requests: typing.List[BatchUpdateBlobsRequest.Request] = []
            for provider in batch.providers:
                digest = provider.digest
                data = provider.read_all()
                requests.append(
                    BatchUpdateBlobsRequest.Request(
                        digest={
                            "hash": digest,
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

    def _write_bytes_to_steam(self, provider):
        self._byte_steam_stub.Write(self._write_requests(provider))

    def _write_requests(self, provider):
        digest = provider.digest
        total_size_bytes = provider.size_bytes
        resource_name = "uploads/{uuid_}/blobs/{hash_}/{size}".format(
            uuid_=uuid.uuid4(), hash_=digest, size=total_size_bytes
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
    """A CAS cache. If a blob is larger than message size it won't be
    cached.
    """

    def __init__(self, backend: CASHelper):
        self._backend = backend
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

    def fetch_all(self, digests: typing.Iterable[Digest]):
        result_list, missing_list = self._fetch_all_in_cache(digests)
        if missing_list:
            for d, offset, data in self._backend.fetch_all(missing_list):
                # Small enough to cache.
                if d.size_bytes == len(data):
                    self._cache[(d.hash, d.size_bytes)] = data
                yield d, offset, data
        for d, data in result_list:
            yield d, 0, data
