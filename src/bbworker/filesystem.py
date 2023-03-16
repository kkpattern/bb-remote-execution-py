import collections
import concurrent.futures
import hashlib
import io
import logging
import os
import os.path
import typing
import shutil
import stat
import threading

from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest
from build.bazel.remote.execution.v2.remote_execution_pb2 import FileNode

from .cacheinfo import FileCacheInfo
from .lock import VariableLock
from .metrics import MeterBase
from .util import set_read_only
from .util import set_read_exec_only
from .util import link_file
from .util import unlink_readonly_file


DownloadFuture = concurrent.futures.Future[None]


def digest_to_cache_name(digest: Digest):
    """Convert digest to "{hash}_{size}"."""
    return "{0}_{1}".format(digest.hash, digest.size_bytes)


class FilesystemError(Exception):
    pass


class MaxSizeReached(FilesystemError):
    """But max cache size reached and we cannot make space either because a
    single file is large then whole cache size or there are too many pending
    files downloading.
    """

    pass


class InvalidDigest(FilesystemError):
    pass


class DigestAndFileNodes(object):
    def __init__(self, digest: Digest, file_nodes: typing.List[FileNode]):
        self.digest = digest
        self.file_nodes = file_nodes

    def append_file_node(self, file_node: FileNode):
        self.file_nodes.append(file_node)


class DownloadBatch(object):
    def __init__(
        self,
        batch: typing.Optional[typing.Iterable[DigestAndFileNodes]] = None,
    ) -> None:
        self._digest_and_file_nodes: typing.List[DigestAndFileNodes] = []
        self._total_size_bytes = 0
        self._future: DownloadFuture = concurrent.futures.Future()
        if batch:
            for d in batch:
                self._digest_and_file_nodes.append(d)
                self._total_size_bytes += d.digest.size_bytes

    def __iter__(self):
        for digest_and_file_nodes in self._digest_and_file_nodes:
            yield digest_and_file_nodes

    @property
    def future(self):
        return self._future

    @property
    def digests(self):
        return [i.digest for i in self._digest_and_file_nodes]

    @property
    def total_size_bytes(self):
        return self._total_size_bytes

    def append_digest_and_file_nodes(
        self, digest_and_file_nodes: DigestAndFileNodes
    ):
        self._digest_and_file_nodes.append(digest_and_file_nodes)
        self._total_size_bytes += digest_and_file_nodes.digest.size_bytes


class LocalHardlinkFilesystem(object):
    """基于hardlink的本地缓存文件系统."""

    def __init__(
        self,
        cache_root_dir: str,
        meter: MeterBase,
        *,
        max_cache_size_bytes: int = 0,
        concurrency: int = 10,
        download_batch_size_bytes: int = 3 * 1024 * 1024,
    ):
        self._cache_root_dir = cache_root_dir
        self._file_lock = VariableLock()
        self._current_size_bytes = 0
        self._max_cache_size_bytes = max_cache_size_bytes
        self._download_batch_size_bytes = download_batch_size_bytes
        self._cached_files: typing.Dict[
            str, FileCacheInfo
        ] = collections.OrderedDict()
        self._pending_files: typing.Dict[str, DownloadFuture] = {}
        self._global_lock = threading.Lock()
        self._executor = concurrent.futures.ThreadPoolExecutor(
            concurrency, thread_name_prefix="filesystem_"
        )
        self._meter = meter

    @property
    def current_size_bytes(self):
        return self._current_size_bytes

    def init(self):
        if not os.path.exists(self._cache_root_dir):
            os.makedirs(self._cache_root_dir)
        self._verify_existing_files()

    def _verify_existing_files(self) -> None:
        logging.info("validate cached files start.")
        self._cached_files.clear()
        self._current_size_bytes = 0
        file_to_verify: typing.List[str] = []
        for name in os.listdir(self._cache_root_dir):
            p = os.path.join(self._cache_root_dir, name)
            if os.path.isfile(p):
                file_to_verify.append(name)
            elif os.path.isdir(p):
                shutil.rmtree(p)
        if file_to_verify:
            verify_thread_count = 20
            mapped_digests = [
                file_to_verify[i::verify_thread_count]
                for i in range(verify_thread_count)
            ]
            cached_files = {}
            future_list = []
            for part in mapped_digests:
                future_list.append(
                    self._executor.submit(self._verify_thread, part)
                )
            for f in future_list:
                cached_files.update(f.result())
            files_to_evict: typing.List[str] = []
            for name_in_cache in sorted(
                cached_files,
                key=lambda k: cached_files[k].st_atime,
                reverse=True,
            ):
                cache_info = cached_files[name_in_cache]
                new_size_bytes = cache_info.st_size + self._current_size_bytes
                if new_size_bytes > self._max_cache_size_bytes > 0:
                    files_to_evict.append(name_in_cache)
                else:
                    self._cached_files[name_in_cache] = cache_info
                    self._current_size_bytes = new_size_bytes
            for name_in_cache in files_to_evict:
                path_in_cache = os.path.join(
                    self._cache_root_dir, name_in_cache
                )
                unlink_readonly_file(path_in_cache)
        logging.info("validate cached files end.")

    def _verify_thread(self, file_to_verify: typing.Iterable[str]):
        file_cache_info: typing.Dict[str, FileCacheInfo] = {}
        for name in file_to_verify:
            p = os.path.join(self._cache_root_dir, name)
            try:
                hash_, size_bytes_str = name.split("_")
                # we need get cache info first so we don't change the atime.
                cache_info = FileCacheInfo(os.stat(p))
                if os.stat(p).st_mode & stat.S_IWUSR:
                    unlink_readonly_file(p)
                else:
                    size_bytes = int(size_bytes_str)
                    if os.path.getsize(p) == size_bytes:
                        sha256 = hashlib.sha256()
                        corrupted = False
                        with open(p, "rb") as f:
                            while True:
                                sha256.update(f.read(1024 * 1024))
                                if f.tell() == size_bytes:
                                    test_hash = sha256.hexdigest()
                                    if test_hash != hash_:
                                        corrupted = True
                                    break
                        if corrupted:
                            unlink_readonly_file(p)
                        else:
                            file_cache_info[name] = cache_info
                    else:
                        unlink_readonly_file(p)
            except Exception:
                unlink_readonly_file(p)
        return file_cache_info

    def _link_existing_files(
        self,
        fnode_list: typing.Iterable[FileNode],
        target_dir: str,
        *,
        copy_file: bool = False,
    ) -> typing.List[FileNode]:
        """Link existing files into target directory.
        Return files not exists.
        """
        missing_files = []
        cached_files = {}
        with self._global_lock:
            # copies cache info into cached_files so we don't need to lock
            # the whole self._cached_files during linking.
            for fnode in fnode_list:
                name_in_cache = digest_to_cache_name(fnode.digest)
                try:
                    cached_files[name_in_cache] = self._cached_files[
                        name_in_cache
                    ]
                except KeyError:
                    pass
        corrupted_files: typing.List[FileNode] = []
        for fnode in fnode_list:
            name_in_cache = digest_to_cache_name(fnode.digest)
            path_in_cache = os.path.join(self._cache_root_dir, name_in_cache)
            with self._file_lock.lock(path_in_cache):
                if os.path.exists(path_in_cache):
                    if name_in_cache not in cached_files:
                        corrupted = True
                    elif not cached_files[name_in_cache].match(
                        os.stat(path_in_cache)
                    ):
                        del cached_files[name_in_cache]
                        corrupted = True
                    else:
                        corrupted = False
                    if not corrupted:
                        target_path = os.path.join(target_dir, fnode.name)
                        if os.path.exists(target_path):
                            unlink_readonly_file(target_path)
                        if not copy_file:
                            link_file(path_in_cache, target_path)
                        else:
                            shutil.copy2(path_in_cache, target_path)
                    else:
                        corrupted_files.append(fnode)
                else:
                    if name_in_cache in cached_files:
                        corrupted_files.append(fnode)
                    missing_files.append(fnode)
        with self._global_lock:
            for fn in corrupted_files:
                name_in_cache = digest_to_cache_name(fn.digest)
                path_in_cache = os.path.join(
                    self._cache_root_dir, name_in_cache
                )
                if os.path.exists(path_in_cache):
                    unlink_readonly_file(path_in_cache)
                del self._cached_files[name_in_cache]
                self._current_size_bytes -= fn.digest.size_bytes
                missing_files.append(fn)
        return missing_files

    def _download_missing_files(
        self, backend, files: typing.Iterable[FileNode]
    ) -> typing.Iterable[DownloadFuture]:
        batch_size = self._download_batch_size_bytes
        size_limited = self._max_cache_size_bytes > 0
        max_cache_size_bytes = self._max_cache_size_bytes
        download_futures: typing.Set[concurrent.futures.Future] = set()
        # merge the files that have the same content.
        merged_files: typing.Dict[str, DigestAndFileNodes] = {}
        for fn in files:
            name_in_cache = digest_to_cache_name(fn.digest)
            if name_in_cache in merged_files:
                merged_files[name_in_cache].append_file_node(fn)
            else:
                merged_files[name_in_cache] = DigestAndFileNodes(
                    fn.digest, [fn]
                )
        with self._global_lock:
            # calculate which files we need to download. which files we need
            # to remove to make space.
            required_size = 0
            available_cache_size_bytes = (
                self._max_cache_size_bytes - self._current_size_bytes
            )
            missing_files: typing.List[DigestAndFileNodes] = []
            names_need_to_evict: typing.List[str] = []
            cached_names: typing.List[str] = []
            for name_in_cache, digest_and_file_nodes in merged_files.items():
                if name_in_cache in self._cached_files:
                    cached_names.append(name_in_cache)
                    continue
                elif name_in_cache in self._pending_files:
                    download_futures.add(self._pending_files[name_in_cache])
                    continue
                else:
                    missing_files.append(digest_and_file_nodes)
                    size_bytes = digest_and_file_nodes.digest.size_bytes
                    if size_bytes > max_cache_size_bytes > 0:
                        raise MaxSizeReached
                    required_size += size_bytes
            if size_limited and required_size > available_cache_size_bytes:
                for name_in_cache in self._cached_files:
                    names_need_to_evict.append(name_in_cache)
                    cache_info = self._cached_files[name_in_cache]
                    required_size -= cache_info.st_size
                    if required_size <= available_cache_size_bytes:
                        break
                if required_size > available_cache_size_bytes:
                    raise MaxSizeReached
            for name in cached_names:
                self._cached_files[name] = self._cached_files.pop(name)
            for name in names_need_to_evict:
                cache_info = self._cached_files.pop(name)
                self._current_size_bytes -= cache_info.st_size
            # split missing files to batches to download.
            batch = DownloadBatch()
            batch_list: typing.List[DownloadBatch] = [batch]
            for digest_and_file_nodes in missing_files:
                size_bytes = digest_and_file_nodes.digest.size_bytes
                if size_bytes > batch_size:
                    batch_for_digest = DownloadBatch([digest_and_file_nodes])
                    batch_list.append(batch_for_digest)
                elif size_bytes + batch.total_size_bytes > batch_size:
                    batch = DownloadBatch([digest_and_file_nodes])
                    batch_for_digest = batch
                    batch_list.append(batch)
                else:
                    batch_for_digest = batch
                    batch.append_digest_and_file_nodes(digest_and_file_nodes)
                name_in_cache = digest_to_cache_name(
                    digest_and_file_nodes.digest
                )
                future = batch_for_digest.future
                self._pending_files[name_in_cache] = future
                download_futures.add(future)
                self._current_size_bytes += (
                    digest_and_file_nodes.digest.size_bytes
                )
        # remove evicted files first so we have enough space to download new
        # files.
        for name_in_cache in names_need_to_evict:
            self._meter.count("evict_cached_file")
            path_in_cache = os.path.join(self._cache_root_dir, name_in_cache)
            with self._file_lock.lock(path_in_cache):
                if os.path.exists(path_in_cache):
                    unlink_readonly_file(path_in_cache)
        for batch in batch_list:
            if batch.digests:
                self._executor.submit(self._download_thread, backend, batch)
        return download_futures

    def _download_thread(self, backend, batch: DownloadBatch):
        try:
            self._download_thread_inner(backend, batch)
        except Exception as e:
            with self._global_lock:
                for digest_and_file_nodes in batch:
                    digest = digest_and_file_nodes.digest
                    name_in_cache = digest_to_cache_name(digest)
                    path_in_cache = os.path.join(
                        self._cache_root_dir, name_in_cache
                    )
                    if os.path.exists(path_in_cache):
                        unlink_readonly_file(path_in_cache)
                    self._current_size_bytes -= digest.size_bytes
                    del self._pending_files[name_in_cache]
            batch.future.set_exception(e)
        else:
            try:
                with self._global_lock:
                    for digest_and_file_nodes in batch:
                        digest = digest_and_file_nodes.digest
                        name_in_cache = digest_to_cache_name(digest)
                        path_in_cache = os.path.join(
                            self._cache_root_dir, name_in_cache
                        )
                        if os.path.exists(path_in_cache):
                            path_in_cache = os.path.join(
                                self._cache_root_dir, name_in_cache
                            )
                            file_stat = os.stat(path_in_cache)
                            self._cached_files[name_in_cache] = FileCacheInfo(
                                file_stat
                            )
                        else:
                            # download failed. return the reserved size bytes.
                            self._current_size_bytes -= digest.size_bytes
                        del self._pending_files[name_in_cache]
                batch.future.set_result(None)
            except Exception as e:
                batch.future.set_exception(e)

    def _download_thread_inner(self, backend, batch: DownloadBatch):
        file_opened: typing.Dict[str, io.BufferedWriter] = {}
        file_sha256: typing.Dict[str, hashlib._Hash] = {}
        try:
            for digest, offset, data in backend.fetch_all_block(batch.digests):
                name_in_cache = digest_to_cache_name(digest)
                # We need to download into a temp path. Only the file is
                # downloaded and verify then we can move it to cache root.
                # TODO: create test for it.
                path_in_temp = os.path.join(
                    self._cache_root_dir, name_in_cache + ".tmp"
                )
                if path_in_temp in file_opened:
                    f = file_opened[path_in_temp]
                    sha256 = file_sha256[path_in_temp]
                else:
                    if os.path.exists(path_in_temp):
                        raise RuntimeError(f"{path_in_temp} shouldn't exist")
                    f = open(path_in_temp, "wb")
                    sha256 = hashlib.sha256()
                    file_opened[path_in_temp] = f
                    file_sha256[path_in_temp] = sha256
                f.write(data)
                sha256.update(data)
                if offset + len(data) >= digest.size_bytes:
                    assert offset + len(data) == digest.size_bytes
                    f.close()
                    del file_opened[path_in_temp]
                    del file_sha256[path_in_temp]
                    if (
                        os.path.getsize(path_in_temp) != digest.size_bytes
                        or sha256.hexdigest() != digest.hash
                    ):
                        os.unlink(path_in_temp)
                        # TODO: better exception.
                        raise Exception("???:{0}".format(path_in_temp))
        finally:
            file_sha256.clear()
            for file in file_opened.values():
                file.close()
            file_opened.clear()
        # set mode.
        for digest_and_file_nodes in batch:
            name_in_cache = digest_to_cache_name(digest_and_file_nodes.digest)
            executable = False
            for fn in digest_and_file_nodes.file_nodes:
                if fn.is_executable:
                    executable = True
                    break
            path_in_cache = os.path.join(self._cache_root_dir, name_in_cache)
            path_in_temp = path_in_cache + ".tmp"
            with self._file_lock.lock(path_in_cache):
                if os.path.exists(path_in_cache):
                    # TODO: unlink instead?
                    raise RuntimeError(f"{path_in_cache} shouldn't exist")
                os.rename(path_in_temp, path_in_cache)
                if executable:
                    set_read_exec_only(path_in_cache)
                else:
                    set_read_only(path_in_cache)

    def fetch_to(
        self,
        backend,
        files: typing.Iterable[FileNode],
        target_dir: str,
        *,
        copy_file: bool = False,
    ):
        """Fetch files into the target directory."""
        # TODO: add generator test.
        # convert to list. we will iterate multiple times.
        files = list(files)
        while files:
            download_futures = self._download_missing_files(backend, files)
            for f in concurrent.futures.as_completed(download_futures):
                f.result()
            files = self._link_existing_files(
                files, target_dir, copy_file=copy_file
            )
