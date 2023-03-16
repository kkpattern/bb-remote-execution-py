from __future__ import annotations

import collections
import concurrent.futures
import functools
import os
import os.path
import hashlib
import shutil
import stat
import sys
import typing
import threading

from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest
from build.bazel.remote.execution.v2.remote_execution_pb2 import Directory
from build.bazel.remote.execution.v2.remote_execution_pb2 import DirectoryNode
from build.bazel.remote.execution.v2.remote_execution_pb2 import FileNode

from .cas import CASHelper
from .filesystem import LocalHardlinkFilesystem
from .lock import VariableRLock
from .util import unlink_file
from .util import unlink_readonly_file
from .util import rmtree
from .util import rmtree_with_readonly_files
from .util import set_dir_readonly_recursive
from .util import create_dir_link
from .util import remove_dir_link


DigestKey = typing.Tuple[str, int]
OptionalDigestKey = typing.Optional[DigestKey]

FutureDigest = concurrent.futures.Future[Digest]


def digest_to_key(digest: Digest):
    return f"{digest.hash}_{digest.size_bytes}"


class DirectoryBuilderError(Exception):
    pass


class MaxSizeReached(DirectoryBuilderError):
    """But max cache size reached and we cannot make enough space."""

    pass


class IDirectoryBuilder(object):
    def build(
        self, input_root_digest: Digest, input_root: Directory, local_root: str
    ) -> None:
        raise NotImplementedError(
            "This method should be implmented in subclass {0}.".format(
                self.__class__.__name__
            )
        )


class FileData:
    def __init__(self, digest: Digest, is_executable: bool):
        self._digest = digest
        self._is_executable = is_executable
        self._name_in_cache = f"{self._digest.hash}_{self._digest.size_bytes}"

    @property
    def name_in_cache(self):
        return self._name_in_cache

    @property
    def digest(self):
        return self._digest

    @property
    def is_executable(self):
        return self._is_executable

    def to_file_node(self, name: str):
        return FileNode(
            name=name, digest=self._digest, is_executable=self._is_executable
        )


class DirectoryData:
    def __init__(
        self,
        checksum_digest: Digest,
        files: typing.Dict[str, FileData],
        directories: typing.Dict[str, DirectoryData],
    ):
        self._checksum_digest = checksum_digest
        self._name_in_cache = (
            f"{self._checksum_digest.hash}_{self._checksum_digest.size_bytes}"
        )
        self._files: typing.Dict[str, FileData] = {}
        self._files.update(files)
        self._directories: typing.Dict[str, DirectoryData] = {}
        self._directories.update(directories)
        self._copy_size_bytes = 0
        for fd in self._files.values():
            self._copy_size_bytes += fd.digest.size_bytes
        for dir_data in self._directories.values():
            self._copy_size_bytes += dir_data.copy_size_bytes

    @property
    def checksum_digest(self):
        return self._checksum_digest

    @property
    def name_in_cache(self):
        return self._name_in_cache

    @property
    def file_count(self):
        return len(self._files)

    def files(self) -> typing.Iterator[typing.Tuple[str, FileData]]:
        for name, fd in self._files.items():
            yield name, fd

    def directories(self) -> typing.Iterator[typing.Tuple[str, DirectoryData]]:
        for name, data in self._directories.items():
            yield name, data

    @property
    def copy_size_bytes(self):
        return self._copy_size_bytes


class DirectoryDataCache:
    def __init__(self, cas_helper: CASHelper, max_cached: int = 5000):
        self._cas_helper = cas_helper
        self._max_cached = max_cached
        self._global_lock = threading.Lock()
        self._cache: typing.Dict[
            str, DirectoryData
        ] = collections.OrderedDict()

    def fetch_directory_data(
        self, digest: Digest, directory: Directory, with_cache: bool
    ) -> DirectoryData:
        result = None
        key = f"{digest.hash}_{digest.size_bytes}"
        if with_cache:
            with self._global_lock:
                if key in self._cache:
                    result = self._cache.pop(key)
                    self._cache[key] = result
        if result is None:
            result = self._fetch_directory_data(digest, directory, with_cache)
            with self._global_lock:
                self._cache[key] = result
                while len(self._cache) > self._max_cached:
                    for key_to_evict in self._cache:
                        self._cache.pop(key_to_evict)
                        break
        return result

    def _fetch_directory_data(
        self, digest: Digest, directory: Directory, with_cache: bool
    ) -> DirectoryData:
        checksum_message = Directory()
        files = {}
        for f in sorted(directory.files, key=lambda fn: fn.name):
            fd = FileData(f.digest, f.is_executable)
            files[f.name] = fd
            checksum_message.files.append(fd.to_file_node(f.name))

        subdirs: typing.Dict[str, DirectoryData] = {}

        dir_digest_to_fetch: typing.Dict[DigestKey, Digest] = {}
        dir_digest_to_names: typing.Dict[
            DigestKey, typing.List[str]
        ] = collections.defaultdict(list)
        dn: DirectoryNode
        for dn in directory.directories:
            subdir_digest = dn.digest
            key = (subdir_digest.hash, subdir_digest.size_bytes)
            dir_digest_to_fetch[key] = subdir_digest
            dir_digest_to_names[key].append(dn.name)

        for subdir_digest, data in self._cas_helper.fetch_all(
            dir_digest_to_fetch.values()
        ):
            key = (subdir_digest.hash, subdir_digest.size_bytes)
            if key in dir_digest_to_names:
                subdirectory = Directory()
                subdirectory.ParseFromString(data)
                for name in dir_digest_to_names[key]:
                    subdirs[name] = self.fetch_directory_data(
                        subdir_digest, subdirectory, with_cache
                    )
        for n in sorted(subdirs):
            d = subdirs[n]
            checksum_message.directories.append(
                DirectoryNode(name=n, digest=d.checksum_digest)
            )
        checksum_data = checksum_message.SerializeToString(deterministic=True)
        return DirectoryData(
            Digest(
                hash=hashlib.sha256(checksum_data).hexdigest(),
                size_bytes=len(checksum_data),
            ),
            files,
            subdirs,
        )


class SharedTopLevelCachedDirectoryBuilder(IDirectoryBuilder):
    def __init__(
        self,
        cache_root: str,
        cas_helper: CASHelper,
        filesystem: LocalHardlinkFilesystem,
        *,
        skip_cache: typing.Optional[typing.Iterable[str]] = None,
        max_cache_size_bytes: int = 0,
        concurrency: int = 10,
        copy_file: bool = False,
    ):
        self._cache_dir_root = cache_root
        self._cas_helper = cas_helper
        self._directory_data_cache = DirectoryDataCache(self._cas_helper, 5000)
        self._filesystem = filesystem
        self._large_directory = set(["engine", "external"])
        if skip_cache is None:
            # by default we do not cache bazel-out, because output files
            # need to be created in it.
            self._skip_cache = set(["bazel-out"])
        else:
            self._skip_cache = set(skip_cache)
        self._dir_lock = VariableRLock()
        self._download_lock = threading.RLock()
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="directory_builder_"
        )
        self._pending_cached_dir: typing.Dict[str, FutureDigest] = {}
        self._cached_dir: typing.Dict[
            str, DirectoryData
        ] = collections.OrderedDict()
        self._max_cache_size_bytes = max_cache_size_bytes
        self._current_size_bytes = 0
        # on Windows platform, we cannot unlink a readonly hardlink. so we
        # use copy instead of hardlink on Windows.
        if sys.platform == "win32" and not copy_file:
            print("WARNING: only copy file is supported on Windows platform")
            self._copy_from_filesystem = True
        else:
            self._copy_from_filesystem = copy_file
        self._file_count: typing.Dict[str, int] | None
        if self._copy_from_filesystem:
            self._file_count = None
        else:
            self._file_count = {}

    @property
    def cache_dir_root(self):
        return self._cache_dir_root

    @property
    def current_size_bytes(self):
        return self._current_size_bytes

    def init(self):
        if not os.path.exists(self._cache_dir_root):
            os.makedirs(self._cache_dir_root)
        self._cached_dir.clear()
        self._pending_cached_dir.clear()
        self._current_size_bytes = 0
        # TODO: shrink size.
        self._verify_existing_dirs()

    def build(
        self, input_root_digest: Digest, input_root: Directory, target_dir: str
    ) -> None:
        dir_data = self._directory_data_cache.fetch_directory_data(
            input_root_digest, input_root, True
        )
        self._build_toplevel(
            dir_data,
            target_dir,
            self._large_directory,
            self._skip_cache,
        )

    def _build_toplevel(
        self,
        dir_data: DirectoryData,
        directory_local: str,
        large_directory: typing.Set[str],
        skip_cache: typing.Set[str],
    ) -> None:
        if not os.path.exists(directory_local):
            os.makedirs(directory_local)
        for name in os.listdir(directory_local):
            p = os.path.join(directory_local, name)
            if os.path.isfile(p):
                unlink_readonly_file(p)
            elif os.path.islink(p):
                remove_dir_link(p)
            elif os.path.isdir(p):
                if name in large_directory:
                    self._remove_large_directory(p)
                elif name in skip_cache:
                    rmtree_with_readonly_files(p)
                else:
                    remove_dir_link(p)
            else:
                remove_dir_link(p)
        if dir_data.file_count:
            self._filesystem.fetch_to(
                self._cas_helper,
                [fd.to_file_node(name) for name, fd in dir_data.files()],
                directory_local,
                copy_file=self._copy_from_filesystem,
            )
        self._build_toplevel_dirs(
            dir_data.directories(),
            directory_local,
            large_directory,
            skip_cache,
        )

    def _build_toplevel_dirs(
        self,
        missing_dirs: typing.Iterable[typing.Tuple[str, DirectoryData]],
        directory_local: str,
        large_directory: typing.Set[str],
        skip_cache: typing.Set[str],
    ):
        large_dir_to_build: typing.Dict[str, DirectoryData] = {}
        skip_cache_dir_to_build: typing.Dict[str, DirectoryData] = {}
        cached_dir_to_build: typing.Dict[str, DirectoryData] = {}
        for name, each_dir in missing_dirs:
            if name in large_directory:
                large_dir_to_build[name] = each_dir
            elif name in skip_cache:
                skip_cache_dir_to_build[name] = each_dir
            else:
                cached_dir_to_build[name] = each_dir

        build_native_futures: typing.List[FutureDigest] = []
        delayed_link: typing.Dict[
            str, typing.List[str]
        ] = collections.defaultdict(list)
        dir_need_to_evict = []
        with self._download_lock:
            required_size_bytes = 0
            cached_names: typing.List[str] = []
            dirs_to_download: typing.Dict[str, DirectoryData] = {}
            file_count = self._file_count
            for name, subdir in cached_dir_to_build.items():
                name_in_cache = subdir.name_in_cache
                dir_local_path = os.path.join(directory_local, name)
                if name_in_cache in self._cached_dir:
                    # other thread may downloaded the same directory at the
                    # same time.
                    cached_names.append(name_in_cache)
                elif name_in_cache in self._pending_cached_dir:
                    # other thread is downloading the same directory.
                    f = self._pending_cached_dir[name_in_cache]
                    build_native_futures.append(f)
                else:
                    size_bytes, file_count = self._calculate_required_size(
                        subdir, file_count
                    )
                    required_size_bytes += size_bytes
                    dirs_to_download[name] = subdir
                delayed_link[name_in_cache].append(dir_local_path)
            available_size_bytes = (
                self._max_cache_size_bytes
                - self._current_size_bytes
                - required_size_bytes
            )
            if self._max_cache_size_bytes > 0 > available_size_bytes:
                released_size = 0
                for name_in_cache in self._cached_dir:
                    dir_need_to_evict.append(name_in_cache)
                    size_bytes, file_count = self._calculate_released_size(
                        self._cached_dir[name_in_cache], file_count
                    )
                    released_size += size_bytes
                    if available_size_bytes + released_size >= 0:
                        break
                if available_size_bytes + released_size < 0:
                    raise MaxSizeReached
                self._current_size_bytes -= released_size
                for name in dir_need_to_evict:
                    del self._cached_dir[name]
            for name in cached_names:
                self._cached_dir[name] = self._cached_dir.pop(name)
            self._current_size_bytes += required_size_bytes
            self._file_count = file_count
            for name, subdirectory in dirs_to_download.items():
                f = self._build_cached_directory_in_thread(
                    subdirectory, self._copy_from_filesystem
                )
                build_native_futures.append(f)
        for name, subdirectory in large_dir_to_build.items():
            dir_local_path = os.path.join(directory_local, name)
            self._build_toplevel(subdirectory, dir_local_path, set(), set())
        for name, subdirectory in skip_cache_dir_to_build.items():
            dir_local_path = os.path.join(directory_local, name)
            f = self._build_native_in_thread(
                subdirectory,
                dir_local_path,
                copy_file=self._copy_from_filesystem,
            )
            build_native_futures.append(f)

        # TODO: do in thread.
        for name in dir_need_to_evict:
            print("evict dir:", name)
            self._remove_cached_dir(name)

        for f in concurrent.futures.as_completed(build_native_futures):
            f.result()

        for name_in_cache, link_targets in delayed_link.items():
            path_in_cache = os.path.join(self._cache_dir_root, name_in_cache)
            with self._dir_lock.lock(path_in_cache):
                for dir_local_path in link_targets:
                    create_dir_link(path_in_cache, dir_local_path)
        for name, dir_ in missing_dirs:
            p = os.path.join(directory_local, name)
            if not os.path.isdir(p):
                raise RuntimeError(f"missing directory {p}")

    def _build_cached_directory_in_thread(
        self,
        directory: DirectoryData,
        copy_file: bool = False,
    ) -> FutureDigest:
        """Build a cached directory in thread. This method MUST be called with
        _download_lock.
        """
        name_in_cache = directory.name_in_cache

        future: FutureDigest
        if name_in_cache in self._pending_cached_dir:
            future = self._pending_cached_dir[name_in_cache]
        else:
            future = concurrent.futures.Future()
            path_in_cache = os.path.join(self._cache_dir_root, name_in_cache)
            tmp_in_cache = path_in_cache + ".tmp"

            inner_future = self._build_native_in_thread(
                directory, tmp_in_cache, copy_file=copy_file
            )

            def _inner_finish(inner_future):
                try:
                    checksum = inner_future.result()
                    with self._download_lock:
                        assert (
                            self._pending_cached_dir.get(name_in_cache, None)
                            is future
                        )
                        assert os.path.isdir(tmp_in_cache)
                        del self._pending_cached_dir[name_in_cache]
                        with self._dir_lock.lock(path_in_cache):
                            # dir being evict but haven't been removed yet.
                            # just remove it.
                            if os.path.exists(path_in_cache):
                                self._remove_cached_dir(name_in_cache)
                            shutil.move(tmp_in_cache, path_in_cache)
                            set_dir_readonly_recursive(path_in_cache)
                        self._cached_dir[name_in_cache] = directory
                except Exception as e:
                    with self._download_lock:
                        size_bytes, file_count = self._calculate_released_size(
                            directory, self._file_count
                        )
                        self._current_size_bytes -= size_bytes
                        self._file_count = file_count
                    future.set_exception(e)
                else:
                    future.set_result(checksum)
                finally:
                    if os.path.exists(tmp_in_cache):
                        self._remove_cached_dir(name_in_cache)

            self._pending_cached_dir[name_in_cache] = future
            inner_future.add_done_callback(_inner_finish)
        return future

    def _build_native_in_thread(
        self,
        directory: DirectoryData,
        directory_local: str,
        copy_file: bool = False,
    ) -> FutureDigest:
        future: FutureDigest = concurrent.futures.Future()

        def _chain_exception(inner_future):
            try:
                inner_future.result()
            except Exception as e:
                future.set_exception(e)

        inner_future = self._executor.submit(
            self._build_native,
            future,
            directory,
            directory_local,
            copy_file=copy_file,
        )
        inner_future.add_done_callback(_chain_exception)
        return future

    def _build_native(
        self,
        future: FutureDigest,
        directory: DirectoryData,
        directory_local: str,
        copy_file: bool = False,
    ):
        dir_message = Directory()
        if not os.path.exists(directory_local):
            os.makedirs(directory_local)
        # files.
        if directory.file_count:
            sorted_files = sorted(
                [fd.to_file_node(n) for n, fd in directory.files()],
                key=lambda fn: fn.name,
            )
            self._filesystem.fetch_to(
                self._cas_helper,
                sorted_files,
                directory_local,
                copy_file=copy_file,
            )
            for fnode in sorted_files:
                dir_message.files.append(fnode)
            # TODO: better exception and set_exception.
            for n, fd in directory.files():
                p = os.path.join(directory_local, n)
                if not os.path.exists(p):
                    raise RuntimeError(f"missing file {n}")
        # directories.
        subdir_check: typing.Dict[str, None | DirectoryNode] = {}
        subdir_check_lock = threading.Lock()

        def _set_result():
            dir_data = dir_message.SerializeToString(deterministic=True)
            future.set_result(
                Digest(
                    hash=hashlib.sha256(dir_data).hexdigest(),
                    size_bytes=len(dir_data),
                )
            )

        def _subdir_build_callback(name: str, fut: FutureDigest):
            try:
                digest = fut.result()
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
            else:
                with subdir_check_lock:
                    subdir_check[name] = DirectoryNode(
                        name=name, digest=digest
                    )

                    if all(subdir_check.values()):
                        for name in sorted(subdir_check):
                            n = subdir_check[name]
                            assert n
                            dir_message.directories.append(n)
                        # TODO: better exception and set_exception.
                        for d in directory.directories():
                            if not os.path.exists(
                                os.path.join(directory_local, name)
                            ):
                                raise RuntimeError(f"missing directory {name}")
                        _set_result()

        for each_name, subdirectory in directory.directories():
            subdir_check[each_name] = None
            sub_future = self._build_native_in_thread(
                subdirectory,
                os.path.join(directory_local, each_name),
                copy_file=copy_file,
            )
            sub_future.add_done_callback(
                functools.partial(_subdir_build_callback, each_name)
            )
        with subdir_check_lock:
            if not subdir_check:
                _set_result()

    def _remove_large_directory(self, target: str):
        for name in os.listdir(target):
            p = os.path.join(target, name)
            # remove links first so we can quick remove a large directory.
            if os.path.isdir(p):
                # XXX: directory in large directory should always be a link.
                remove_dir_link(p)
            elif os.path.isfile(p):
                unlink_readonly_file(p)
        rmtree(target)

    def _verify_existing_dirs(self) -> None:
        print("INFO: verify directory start.")
        dir_to_verify: typing.List[typing.Tuple[str, Digest]] = []
        for name in os.listdir(self._cache_dir_root):
            try:
                hash_, size_bytes_str = name.split("_")
                size_bytes = int(size_bytes_str)
            except Exception:
                p = os.path.join(self._cache_dir_root, name)
                if os.path.isfile(p):
                    os.unlink(p)
                elif os.path.isdir(p):
                    self._remove_cached_dir(name)
            else:
                dir_to_verify.append(
                    (name, Digest(hash=hash_, size_bytes=size_bytes))
                )
        if dir_to_verify:
            verify_thread_count = 10
            mapped_digests = [
                dir_to_verify[i::verify_thread_count]
                for i in range(verify_thread_count)
            ]
            future_list = []
            for part in mapped_digests:
                future_list.append(
                    self._executor.submit(self._verify_thread, part)
                )
            for future in future_list:
                future.result()
        for dir_data in self._cached_dir.values():
            # TODO: link size
            self._current_size_bytes += dir_data.copy_size_bytes
        print("INFO: verify directory end.")

    def _verify_thread(
        self, directory_to_verify: typing.Iterable[typing.Tuple[str, Digest]]
    ):
        for name, check_digest in directory_to_verify:
            p = os.path.join(self._cache_dir_root, name)
            try:
                dir_data = self._calculate_dir_digest(p)
                if dir_data is None:
                    self._remove_cached_dir(name)
                elif dir_data.checksum_digest != check_digest:
                    self._remove_cached_dir(name)
                else:
                    self._cached_dir[name] = dir_data
            except Exception:
                self._remove_cached_dir(name)

    def _calculate_dir_digest(
        self, dir_path: str
    ) -> typing.Optional[DirectoryData]:
        if os.stat(dir_path).st_mode & stat.S_IWUSR:
            return None
        checksum_message = Directory()
        files: typing.Dict[str, FileData] = {}
        subdirs: typing.Dict[str, DirectoryData] = {}
        for name in sorted(os.listdir(dir_path)):
            p = os.path.join(dir_path, name)
            if os.stat(p).st_mode & stat.S_IWUSR:
                return None
            if os.path.isfile(p):
                size_bytes = os.path.getsize(p)
                sha256 = hashlib.sha256()
                with open(p, "rb") as f:
                    while True:
                        sha256.update(f.read(1024 * 1024))
                        if f.tell() == size_bytes:
                            break
                d = Digest(hash=sha256.hexdigest(), size_bytes=size_bytes)
                is_executable = bool(os.stat(p).st_mode & stat.S_IXUSR)
                fd = FileData(d, is_executable)
                files[name] = fd
                checksum_message.files.append(fd.to_file_node(name))
            elif os.path.isdir(p):
                subdir_data = self._calculate_dir_digest(p)
                if subdir_data is None:
                    return None
                subdirs[name] = subdir_data
                checksum_message.directories.append(
                    DirectoryNode(
                        name=name, digest=subdir_data.checksum_digest
                    )
                )
            else:
                return None
        checksum_data = checksum_message.SerializeToString(deterministic=True)
        checksum_digest = Digest(
            hash=hashlib.sha256(checksum_data).hexdigest(),
            size_bytes=len(checksum_data),
        )
        return DirectoryData(checksum_digest, files, subdirs)

    def _remove_cached_dir(self, name_in_cache: str):
        path_in_cache = os.path.join(self._cache_dir_root, name_in_cache)
        print("remove cached directory:", path_in_cache)
        with self._dir_lock.lock(path_in_cache):
            if os.path.exists(path_in_cache):
                if self._copy_from_filesystem:
                    dir_mode = stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR
                    file_mode = stat.S_IWUSR | stat.S_IRUSR
                    for dir_, dirnames, filenames in os.walk(path_in_cache):
                        for n in filenames:
                            os.chmod(os.path.join(dir_, n), file_mode)
                        for n in dirnames:
                            os.chmod(os.path.join(dir_, n), dir_mode)
                    os.chmod(path_in_cache, dir_mode)
                else:
                    dir_mode = stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR
                    for dir_, dirnames, filenames in os.walk(path_in_cache):
                        os.chmod(dir_, dir_mode)
                        for n in filenames:
                            unlink_file(os.path.join(dir_, n))
                shutil.rmtree(path_in_cache)

    def _calculate_required_size(
        self,
        dir_data: DirectoryData,
        file_count: typing.Dict[str, int] | None = None,
    ) -> typing.Tuple[int, typing.Dict[str, int] | None]:
        new_file_count: typing.Dict[str, int] | None
        if file_count is None:
            new_file_count = None
            result = dir_data.copy_size_bytes
        else:
            result = 0
            new_file_count = {}
            new_file_count.update(file_count)
            for n, fd in dir_data.files():
                if fd.name_in_cache not in new_file_count:
                    new_file_count[fd.name_in_cache] = 1
                    result += fd.digest.size_bytes
                else:
                    new_file_count[fd.name_in_cache] += 1
            for n, subdir_data in dir_data.directories():
                subdir_result, new_file_count = self._calculate_required_size(
                    subdir_data, new_file_count
                )
                result += subdir_result
        return result, new_file_count

    def _calculate_released_size(
        self,
        dir_data: DirectoryData,
        file_count: typing.Dict[str, int] | None = None,
    ) -> typing.Tuple[int, typing.Dict[str, int] | None]:
        new_file_count: typing.Dict[str, int] | None
        if file_count is None:
            new_file_count = None
            result = dir_data.copy_size_bytes
        else:
            result = 0
            new_file_count = {}
            new_file_count.update(file_count)
            for n, fd in dir_data.files():
                new_file_count[fd.name_in_cache] -= 1
                if new_file_count[fd.name_in_cache] == 0:
                    result += fd.digest.size_bytes
                    del new_file_count[fd.name_in_cache]
            for n, subdir_data in dir_data.directories():
                subdir_result, new_file_count = self._calculate_released_size(
                    subdir_data, new_file_count
                )
                result += subdir_result
        return result, new_file_count
