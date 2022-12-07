import collections
import concurrent.futures
import hashlib
import io
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
from .util import set_read_only
from .util import set_read_exec_only
from .util import link_file
from .util import unlink_readonly_file


def digest_to_cache_name(digest: Digest):
    """Convert digest to "{hash}_{size}"."""
    return "{0}_{1}".format(digest.hash, digest.size_bytes)


class LocalHardlinkFilesystem(object):
    """基于hardlink的本地缓存文件系统."""

    def __init__(self, cache_root_dir: str):
        self._cache_root_dir = cache_root_dir
        self._global_lock = threading.Lock()
        self._download_lock = threading.Lock()
        self._file_lock = VariableLock()
        self._file_cache_info: typing.Dict[str, FileCacheInfo] = {}

    def init(self):
        if not os.path.exists(self._cache_root_dir):
            os.makedirs(self._cache_root_dir)
        self._verify_existing_files()

    def _verify_existing_files(self) -> None:
        self._file_cache_info.clear()
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
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=verify_thread_count,
                thread_name_prefix="verify_thread_",
            ) as executor:
                future_list = []
                for part in mapped_digests:
                    future_list.append(
                        executor.submit(self._verify_thread, part)
                    )
                for f in future_list:
                    self._file_cache_info.update(f.result())
            for name in os.listdir(self._cache_root_dir):
                if name not in self._file_cache_info:
                    raise RuntimeError("Unverified file in cache root.")

    def _verify_thread(self, file_to_verify: typing.Iterable[str]):
        file_cache_info: typing.Dict[str, FileCacheInfo] = {}
        for name in file_to_verify:
            p = os.path.join(self._cache_root_dir, name)
            try:
                hash_, size_bytes_str = name.split("_")
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
                            file_cache_info[name] = FileCacheInfo(os.stat(p))
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
        for fnode in fnode_list:
            name_in_cache = digest_to_cache_name(fnode.digest)
            path_in_cache = os.path.join(self._cache_root_dir, name_in_cache)
            with self._file_lock.lock(path_in_cache):
                if os.path.exists(path_in_cache):
                    if name_in_cache not in self._file_cache_info:
                        corrupted = True
                    elif not self._file_cache_info[name_in_cache].match(
                        os.stat(path_in_cache)
                    ):
                        del self._file_cache_info[name_in_cache]
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
                        unlink_readonly_file(path_in_cache)
                        missing_files.append(fnode)
                else:
                    missing_files.append(fnode)
        return missing_files

    def fetch_to(
        self,
        backend,
        files: typing.Iterable[FileNode],
        target_dir: str,
        *,
        copy_file: bool = False,
    ):
        """Fetch files into the target directory."""
        missing_files = self._link_existing_files(
            files, target_dir, copy_file=copy_file
        )
        with self._download_lock:
            real_download_list = self._link_existing_files(
                missing_files, target_dir, copy_file=copy_file
            )
            self._batch_download(
                backend, real_download_list, target_dir, copy_file=copy_file
            )
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
        *,
        copy_file: bool = False,
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
        file_sha256: typing.Dict[str, hashlib._Hash] = {}
        try:
            for digest, offset, data in backend.fetch_all(
                digest_to_fetch.values()
            ):
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
        for name_in_cache, files in cache_name_to_files.items():
            executable = False
            for f in files:
                if f.is_executable:
                    executable = True
                    break
            path_in_cache = os.path.join(self._cache_root_dir, name_in_cache)
            path_in_temp = path_in_cache + ".tmp"
            with self._file_lock.lock(path_in_cache):
                if os.path.exists(path_in_cache):
                    raise RuntimeError(f"{path_in_cache} shouldn't exist")
                os.rename(path_in_temp, path_in_cache)
                if executable:
                    set_read_exec_only(path_in_cache)
                else:
                    set_read_only(path_in_cache)
                self._file_cache_info[name_in_cache] = FileCacheInfo(
                    os.stat(path_in_cache)
                )
        missing_files = self._link_existing_files(
            files_to_download, link_target_dir, copy_file=copy_file
        )
        assert not missing_files
