import collections
import io
import os
import os.path
import sys
import typing
import threading

from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest
from build.bazel.remote.execution.v2.remote_execution_pb2 import FileNode


def digest_to_cache_name(digest: Digest):
    """Convert digest to "{hash}_{size}"."""
    return "{0}_{1}".format(digest.hash, digest.size_bytes)


class LocalHardlinkFilesystem(object):
    """基于hardlink的本地缓存文件系统."""

    def __init__(self, cache_root_dir: str):
        self._cache_root_dir = cache_root_dir
        self._global_lock = threading.Lock()
        self._download_lock = threading.Lock()
        self._file_locks: typing.Dict[str, threading.Lock] = {}

    def init(self):
        if not os.path.exists(self._cache_root_dir):
            os.makedirs(self._cache_root_dir)

    def _link_existing_files(
        self, fnode_list: typing.List[FileNode], target_dir: str
    ) -> typing.List[FileNode]:
        """Link existing files into target directory.
        Return files not exists.
        """
        missing_files = []
        for fnode in fnode_list:
            path_in_cache = os.path.join(
                self._cache_root_dir, digest_to_cache_name(fnode.digest)
            )
            lock = self._acquire_file_lock(path_in_cache)
            try:
                if os.path.exists(path_in_cache):
                    target_path = os.path.join(target_dir, fnode.name)
                    if os.path.exists(target_path):
                        if sys.platform == "win32":
                            os.chmod(target_path, 0o700)
                        os.unlink(target_path)
                    os.link(path_in_cache, target_path)
                else:
                    missing_files.append(fnode)
            finally:
                lock.release()
        return missing_files

    def fetch_to(self, backend, files: typing.List[FileNode], target_dir: str):
        """Fetch files into the target directory."""
        missing_files = self._link_existing_files(files, target_dir)
        with self._download_lock:
            real_download_list = self._link_existing_files(
                missing_files, target_dir
            )
            self._batch_download(backend, real_download_list, target_dir)
        # check all files exist.
        for f in files:
            if not os.path.exists(os.path.join(target_dir, f.name)):
                raise RuntimeError(
                    "{0} doesn't exist.".format(
                        os.path.join(target_dir, f.name)
                    )
                )

    def _batch_download(
        self,
        backend,
        files_to_download: typing.List[FileNode],
        link_target_dir: str,
    ):
        """Batch download files and link them into link_target_dir."""
        # NOTE: 注意一个相同的digest可能对应多个文件. 需要去重.
        digest_to_fetch = {}
        cache_name_to_files = collections.defaultdict(list)
        for fn in files_to_download:
            name_in_cache = digest_to_cache_name(fn.digest)
            cache_name_to_files[name_in_cache].append(fn)
            digest_to_fetch[name_in_cache] = fn.digest
        file_opened: typing.Dict[str, io.BufferedWriter] = {}
        try:
            for digest, offset, data in backend.fetch_all(
                digest_to_fetch.values()
            ):
                name_in_cache = digest_to_cache_name(digest)
                path_in_cache = os.path.join(
                    self._cache_root_dir, name_in_cache
                )
                if path_in_cache in file_opened:
                    f = file_opened[path_in_cache]
                else:
                    if os.path.exists(path_in_cache):
                        raise RuntimeError(f"{path_in_cache} shouldn't exist")
                    f = open(path_in_cache, "wb")
                    file_opened[path_in_cache] = f
                f.write(data)
                if offset + len(data) >= digest.size_bytes:
                    assert offset + len(data) == digest.size_bytes
                    f.close()
                    del file_opened[path_in_cache]
                    if os.path.getsize(path_in_cache) != digest.size_bytes:
                        os.unlink(path_in_cache)
                        # TODO: better exception.
                        raise Exception("???:{0}".format(path_in_cache))
        except Exception:
            for file in file_opened.values():
                file.close()
            file_opened.clear()
            raise
        # set mode.
        for cache_name, files in cache_name_to_files.items():
            mode = 0o0400
            for f in files:
                if f.is_executable:
                    mode = 0o0500
                    break
            path_in_cache = os.path.join(self._cache_root_dir, cache_name)
            os.chmod(path_in_cache, mode)
        missing_files = self._link_existing_files(
            files_to_download, link_target_dir
        )
        assert not missing_files

    def _acquire_file_lock(self, name_in_cache: str) -> threading.Lock:
        """Acquire a file lock. If no lock exists a new lock will be created.
        return the acquired lock so caller can release it.
        """
        while True:
            if name_in_cache in self._file_locks:
                lock = self._file_locks[name_in_cache]
                lock.acquire()
                if self._file_locks.get(name_in_cache, None) is not lock:
                    # 持有的锁被别的线程删除了, 释放他然后重新来.
                    lock.release()
                    continue
                else:
                    # 成功持有锁.
                    break
            else:
                with self._global_lock:
                    if name_in_cache not in self._file_locks:
                        # 第一个创建锁.
                        lock = threading.Lock()
                        lock.acquire()
                        self._file_locks[name_in_cache] = lock
                        break
                    else:
                        # 同时有其他人创建锁成功了, 重新走流程申请这个锁.
                        continue
        return lock

    def _remove_file_lock(
        self, name_in_cache: str, lock_to_remove: threading.Lock
    ):
        # 先获取到锁本身.
        lock_to_remove.acquire()
        try:
            with self._global_lock:
                if self._file_locks.get(name_in_cache, None) is lock_to_remove:
                    del self._file_locks[name_in_cache]
        finally:
            lock_to_remove.release()
