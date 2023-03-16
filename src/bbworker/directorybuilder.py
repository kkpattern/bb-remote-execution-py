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

from .cas import CASCache
from .cas import CASHelper
from .filesystem import LocalHardlinkFilesystem
from .lock import VariableLock
from .util import unlink_file
from .util import unlink_readonly_file
from .util import rmtree
from .util import rmtree_with_readonly_files
from .util import set_read_exec_only
from .util import set_read_exec_write
from .util import create_dir_link
from .util import remove_dir_link


DigestKey = typing.Tuple[str, int]
OptionalDigestKey = typing.Optional[DigestKey]

FutureDigest = concurrent.futures.Future[Digest]


def digest_to_key(digest: Digest):
    return f"{digest.hash}_{digest.size_bytes}"


class IDirectoryBuilder(object):
    def build(
        self, input_root_digest: Digest, input_root: Directory, local_root: str
    ) -> None:
        raise NotImplementedError(
            "This method should be implmented in subclass {0}.".format(
                self.__class__.__name__
            )
        )


class SharedTopLevelCachedDirectoryBuilder(IDirectoryBuilder):
    def __init__(
        self,
        cache_root: str,
        cas_helper: CASHelper,
        filesystem: LocalHardlinkFilesystem,
        *,
        skip_cache: typing.Optional[typing.Iterable[str]] = None,
        concurrency: int = 10,
    ):
        self._cache_dir_root = os.path.join(cache_root, "dir")
        self._cache_digest_root = os.path.join(cache_root, "digest")
        self._cas_helper = cas_helper
        # 10MB directory blob cache.
        self._directory_blob_cache = CASCache(
            self._cas_helper, 10 * 1024 * 1024
        )
        self._filesystem = filesystem
        self._large_directory = set(["engine", "external"])
        if skip_cache is None:
            # by default we do not cache bazel-out, because output files
            # need to be created in it.
            self._skip_cache = set(["bazel-out"])
        else:
            self._skip_cache = set(skip_cache)
        self._dir_lock = VariableLock()
        self._download_lock = threading.RLock()
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="directory_builder_"
        )
        # on Windows platform, we cannot unlink a readonly hardlink. so we
        # use copy instead of hardlink on Windows.
        self._copy_from_filesystem = sys.platform == "win32"

    @property
    def cache_dir_root(self):
        return self._cache_dir_root

    @property
    def cache_digest_root(self):
        return self._cache_digest_root

    def init(self):
        if not os.path.exists(self._cache_dir_root):
            os.makedirs(self._cache_dir_root)
        if not os.path.exists(self._cache_digest_root):
            os.makedirs(self._cache_digest_root)
        self._verify_existing_dirs()

    def build(
        self, input_root_digest: Digest, input_root: Directory, target_dir: str
    ) -> None:
        self._build_with_cache(
            input_root,
            target_dir,
            self._large_directory,
            self._skip_cache,
        )

    def _build_with_cache(
        self,
        input_root: Directory,
        directory_local: str,
        large_directory: typing.Optional[typing.Set[str]] = None,
        skip_cache: typing.Optional[typing.Set[str]] = None,
    ) -> None:
        if large_directory is None:
            large_directory = set()
        if skip_cache is None:
            skip_cache = set()
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
        if input_root.files:
            self._filesystem.fetch_to(
                self._cas_helper,
                input_root.files,
                directory_local,
                copy_file=self._copy_from_filesystem,
            )
        missing_dirs = self._link_existing_dirs(
            input_root.directories,
            directory_local,
            large_directory,
            skip_cache,
        )
        with self._download_lock:
            missing_dirs = self._link_existing_dirs(
                missing_dirs, directory_local, large_directory, skip_cache
            )
            if missing_dirs:
                self._build_dirs(
                    missing_dirs, directory_local, large_directory, skip_cache
                )

    def _link_existing_dirs(
        self,
        dirs: typing.Iterable[DirectoryNode],
        directory_local: str,
        large_directory: typing.Set[str],
        skip_cache: typing.Set[str],
    ) -> typing.Iterable[DirectoryNode]:
        missing_dirs = []
        for dnode in dirs:
            dname = dnode.name
            if dname in large_directory or dname in skip_cache:
                missing_dirs.append(dnode)
            else:
                name_in_cache = digest_to_key(dnode.digest)
                path_in_cache = os.path.join(
                    self._cache_dir_root, name_in_cache
                )
                with self._dir_lock.lock(path_in_cache):
                    if os.path.exists(path_in_cache):
                        create_dir_link(
                            path_in_cache,
                            os.path.join(directory_local, dname),
                        )
                    else:
                        missing_dirs.append(dnode)
        return missing_dirs

    def _build_dirs(
        self,
        missing_dirs: typing.Iterable[DirectoryNode],
        directory_local: str,
        large_directory: typing.Optional[typing.Set[str]] = None,
        skip_cache: typing.Optional[typing.Set[str]] = None,
    ):
        if large_directory is None:
            large_directory = set()
        if skip_cache is None:
            skip_cache = set()
        dir_digest_to_fetch: typing.Dict[DigestKey, Digest] = {}
        dir_digest_to_names: typing.Dict[
            DigestKey, typing.List[str]
        ] = collections.defaultdict(list)
        dn: DirectoryNode
        for dn in missing_dirs:
            digest = dn.digest
            key = (digest.hash, digest.size_bytes)
            dir_digest_to_fetch[key] = digest
            dir_digest_to_names[key].append(dn.name)

        build_native_futures: typing.List[FutureDigest] = []
        delayed_link = {}
        for digest, data in self._directory_blob_cache.fetch_all(
            dir_digest_to_fetch.values()
        ):
            key = (digest.hash, digest.size_bytes)
            if key in dir_digest_to_names:
                subdirectory = Directory()
                subdirectory.ParseFromString(data)
                name_in_cache = f"{digest.hash}_{digest.size_bytes}"
                path_to_link = []
                for name in dir_digest_to_names[key]:
                    dir_local_path = os.path.join(directory_local, name)
                    if name in large_directory:
                        self._build_with_cache(subdirectory, dir_local_path)
                    elif name in skip_cache:
                        f = self._build_native_in_thread(
                            subdirectory,
                            dir_local_path,
                            readonly=False,
                            copy_file=self._copy_from_filesystem,
                        )
                        build_native_futures.append(f)
                    else:
                        path_to_link.append(dir_local_path)
                if path_to_link:
                    path_in_cache = os.path.join(
                        self._cache_dir_root, name_in_cache
                    )
                    tmp_in_cache = path_in_cache + ".tmp"
                    f = self._build_native_in_thread(
                        subdirectory,
                        tmp_in_cache,
                        copy_file=self._copy_from_filesystem,
                    )
                    delayed_link[f] = (name_in_cache, path_to_link)
                    build_native_futures.append(f)
            else:
                # TODO:
                print("Unknown digest")

        for fut in concurrent.futures.as_completed(build_native_futures):
            if fut in delayed_link:
                cdigest = fut.result()
                name_in_cache, path_to_link = delayed_link[fut]
                path_in_cache = os.path.join(
                    self._cache_dir_root, name_in_cache
                )
                tmp_in_cache = path_in_cache + ".tmp"
                with self._dir_lock.lock(path_in_cache):
                    set_read_exec_write(tmp_in_cache)
                    shutil.move(tmp_in_cache, path_in_cache)
                    set_read_exec_only(path_in_cache)

                    checksum_path = os.path.join(
                        self._cache_digest_root, name_in_cache
                    )
                    with open(checksum_path, "w") as check_f:
                        check_f.write(f"{cdigest.hash}_{cdigest.size_bytes}\n")
                    for dir_local_path in path_to_link:
                        create_dir_link(path_in_cache, dir_local_path)

    def _build_native_in_thread(
        self,
        input_root: Directory,
        directory_local: str,
        readonly: bool = True,
        copy_file: bool = False,
    ) -> FutureDigest:
        future: FutureDigest = concurrent.futures.Future()
        self._executor.submit(
            self._build_native,
            future,
            input_root,
            directory_local,
            readonly=readonly,
            copy_file=copy_file,
        )
        return future

    def _build_native(
        self,
        future: FutureDigest,
        input_root: Directory,
        directory_local: str,
        readonly: bool = True,
        copy_file: bool = False,
    ):
        dir_message = Directory()
        if not os.path.exists(directory_local):
            os.makedirs(directory_local)
        # files.
        if input_root.files:
            self._filesystem.fetch_to(
                self._cas_helper,
                input_root.files,
                directory_local,
                copy_file=copy_file,
            )
        for fnode in sorted(input_root.files, key=lambda fn: fn.name):
            dir_message.files.append(
                FileNode(name=fnode.name, digest=fnode.digest)
            )
        # TODO: better exception.
        for f in input_root.files:
            p = os.path.join(directory_local, f.name)
            if not os.path.exists(p):
                raise RuntimeError(f"missing file {f.name}")
        # directories.
        dir_digest_to_fetch: typing.Dict[DigestKey, Digest] = {}
        dir_digest_to_names: typing.Dict[
            DigestKey, typing.List[str]
        ] = collections.defaultdict(list)
        for dir_node in input_root.directories:
            dir_digest = dir_node.digest
            key = (dir_digest.hash, dir_digest.size_bytes)
            dir_digest_to_fetch[key] = dir_digest
            dir_digest_to_names[key].append(dir_node.name)
        subdir_check: typing.Dict[str, None | DirectoryNode] = {}
        subdir_check_lock = threading.Lock()

        def _set_result():
            if readonly:
                set_read_exec_only(directory_local)
            dir_data = dir_message.SerializeToString(deterministic=True)
            future.set_result(
                Digest(
                    hash=hashlib.sha256(dir_data).hexdigest(),
                    size_bytes=len(dir_data),
                )
            )

        def _subdir_build_callback(name: str, fut: FutureDigest):
            digest = fut.result()
            with subdir_check_lock:
                subdir_check[name] = DirectoryNode(name=name, digest=digest)

                if all(subdir_check.values()):
                    for name in sorted(subdir_check):
                        n = subdir_check[name]
                        assert n
                        dir_message.directories.append(n)
                    # TODO: better exception.
                    for d in input_root.directories:
                        if not os.path.exists(
                            os.path.join(directory_local, d.name)
                        ):
                            raise RuntimeError(f"missing directory {d.name}")
                    _set_result()

        for digest, data in self._directory_blob_cache.fetch_all(
            dir_digest_to_fetch.values()
        ):
            key = (digest.hash, digest.size_bytes)
            try:
                names = dir_digest_to_names[key]
            except KeyError:
                pass
            else:
                subdirectory = Directory()
                subdirectory.ParseFromString(data)
                for each_name in names:
                    subdir_check[each_name] = None
                    sub_future = self._build_native_in_thread(
                        subdirectory,
                        os.path.join(directory_local, each_name),
                        readonly=readonly,
                        copy_file=copy_file,
                    )
                    sub_future.add_done_callback(
                        functools.partial(_subdir_build_callback, each_name)
                    )
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
        for name in os.listdir(self._cache_digest_root):
            p = os.path.join(self._cache_digest_root, name)
            if os.path.isdir(p):
                rmtree(p)
            elif os.path.isfile(p):
                with open(p, "r") as f:
                    check_digest_str = f.read().strip()
                try:
                    hash_, size_bytes_str = check_digest_str.split("_")
                    size_bytes = int(size_bytes_str)
                except Exception:
                    unlink_file(p)
                else:
                    dir_to_verify.append(
                        (name, Digest(hash=hash_, size_bytes=size_bytes))
                    )
        valid_names = set([i[0] for i in dir_to_verify])
        for name in os.listdir(self._cache_dir_root):
            if name not in valid_names:
                p = os.path.join(self._cache_dir_root, name)
                if os.path.isfile(p):
                    os.unlink(p)
                elif os.path.isdir(p):
                    rmtree(p)
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
        print("INFO: verify directory end.")

    def _verify_thread(
        self, directory_to_verify: typing.Iterable[typing.Tuple[str, Digest]]
    ):
        for name, check_digest in directory_to_verify:
            p = os.path.join(self._cache_dir_root, name)
            try:
                digest = self._calculate_dir_digest(p)
                if digest is None:
                    self._remove_cached_dir(name)
                elif (
                    digest.hash != check_digest.hash
                    or digest.size_bytes != check_digest.size_bytes
                ):
                    self._remove_cached_dir(name)
            except Exception:
                self._remove_cached_dir(name)

    def _calculate_dir_digest(self, dir_path: str) -> typing.Optional[Digest]:
        if os.stat(dir_path).st_mode & stat.S_IWUSR:
            return None
        dir_message = Directory()
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
                dir_message.files.append(
                    FileNode(
                        name=name,
                        digest=Digest(
                            hash=sha256.hexdigest(), size_bytes=size_bytes
                        ),
                    )
                )
            elif os.path.isdir(p):
                subdir_digest = self._calculate_dir_digest(p)
                if subdir_digest is None:
                    return None
                dir_message.directories.append(
                    DirectoryNode(name=name, digest=subdir_digest)
                )
            else:
                return None
        dir_data = dir_message.SerializeToString(deterministic=True)
        return Digest(
            hash=hashlib.sha256(dir_data).hexdigest(), size_bytes=len(dir_data)
        )

    def _remove_cached_dir(self, name: str):
        print("remove corrupted cached directory:", name)
        target = os.path.join(self._cache_dir_root, name)
        if self._copy_from_filesystem:
            dir_mode = stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR
            file_mode = stat.S_IWUSR | stat.S_IRUSR
            for dir_, dirnames, filenames in os.walk(target):
                for n in filenames:
                    os.chmod(os.path.join(dir_, n), file_mode)
                for n in dirnames:
                    os.chmod(os.path.join(dir_, n), dir_mode)
            os.chmod(target, dir_mode)
        else:
            dir_mode = stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR
            for dir_, dirnames, filenames in os.walk(target):
                os.chmod(dir_, dir_mode)
                for n in filenames:
                    unlink_file(os.path.join(dir_, n))
        shutil.rmtree(target)
        os.unlink(os.path.join(self._cache_digest_root, name))
