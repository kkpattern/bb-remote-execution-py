import collections
import concurrent.futures
import os
import os.path
import hashlib
import shutil
import stat
import sys
import typing

from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest
from build.bazel.remote.execution.v2.remote_execution_pb2 import Directory
from build.bazel.remote.execution.v2.remote_execution_pb2 import DirectoryNode
from build.bazel.remote.execution.v2.remote_execution_pb2 import FileNode

from .cacheinfo import FileCacheInfo
from .cacheinfo import DirectoryCacheInfo
from .cas import CASCache
from .cas import CASHelper
from .filesystem import LocalHardlinkFilesystem
from .util import digest_to_key
from .util import unlink_file
from .util import unlink_readonly_file
from .util import rmtree
from .util import rmtree_with_readonly_files
from .util import set_read_exec_only
from .util import create_dir_link
from .util import remove_dir_link


DigestKey = typing.Tuple[str, int]
OptionalDigestKey = typing.Optional[DigestKey]


class IDirectoryBuilder(object):
    @property
    def local_root(self):
        raise NotImplementedError(
            "This method should be implmented in subclass {0}.".format(
                self.__class__.__name__
            )
        )

    def build(self, input_root_digest: Digest, input_root: Directory) -> None:
        raise NotImplementedError(
            "This method should be implmented in subclass {0}.".format(
                self.__class__.__name__
            )
        )


class DiffBasedBuildDirectoryBuilder(IDirectoryBuilder):
    """A diff-based bazel action directory builder."""

    def __init__(
        self,
        root_local: str,
        cas_helper: CASHelper,
        filesystem: LocalHardlinkFilesystem,
    ):
        self._root_local = root_local
        self._cas_helper = cas_helper
        # 10MB directory blob cache.
        self._directory_blob_cache = CASCache(
            self._cas_helper, 10 * 1024 * 1024
        )
        self._filesystem = filesystem
        self._current_root_digest: typing.Optional[Digest] = None
        self._digest_to_directory: typing.Dict[
            OptionalDigestKey, typing.Optional[Directory]
        ] = {}

    @property
    def local_root(self):
        return self._root_local

    def clear(self):
        if os.path.exists(self._root_local):
            rmtree(self._root_local)

    def build(self, input_root_digest: Digest, input_root: Directory) -> None:
        if self._current_root_digest != input_root_digest:
            new_digest_to_directory = self._build_directory(
                self._digest_to_directory.get(
                    digest_to_key(self._current_root_digest), None
                ),
                input_root,
                self._root_local,
            )
            self._current_root_digest = input_root_digest
            self._digest_to_directory = new_digest_to_directory

    def _build_directory(
        self,
        old_input_root: typing.Optional[Directory],
        input_root: Directory,
        directory_local: str,
    ):
        digest_to_directory = {}
        if not os.path.exists(directory_local):
            os.makedirs(directory_local)
        if old_input_root is None:
            files = {}
            directories = {}
        else:
            files = {f.name: f for f in old_input_root.files}
            directories = {d.name: d for d in old_input_root.directories}
        new_files = {f.name: f for f in input_root.files}
        new_directories = {d.name: d for d in input_root.directories}
        file_to_fetch = []
        # clear unwanted files and directories.
        for name in os.listdir(directory_local):
            t = os.path.join(directory_local, name)
            if os.path.isfile(t) and name not in new_files:
                unlink_file(t)
            elif os.path.isdir(t) and name not in new_directories:
                rmtree(t)
        # Diff files.
        for name, f in new_files.items():
            if name not in files:
                file_to_fetch.append(f)
            elif name in files:
                if f.digest != files[name].digest:
                    unlink_file(os.path.join(directory_local, name))
                    file_to_fetch.append(f)
        if file_to_fetch:
            self._filesystem.fetch_to(
                self._cas_helper, file_to_fetch, directory_local
            )
        for f in input_root.files:
            if not os.path.exists(os.path.join(directory_local, f.name)):
                raise RuntimeError(f"missing file {f.name}")
        # Diff directories.
        directory_to_fetch = collections.defaultdict(list)
        for name, d in new_directories.items():
            if name not in directories:
                directory_to_fetch[digest_to_key(d.digest)].append(d)
            elif name in files:
                if d.digest != directories[name].digest:
                    directory_to_fetch[digest_to_key(d.digest)].append(d)
        digest_list = []
        for dlist in directory_to_fetch.values():
            for d in dlist:
                digest_list.append(d.digest)
        for digest, offset, data in self._directory_blob_cache.fetch_all(
            digest_list
        ):
            key = digest_to_key(digest)
            # TODO: missing.
            if key in directory_to_fetch:
                for directory_node in directory_to_fetch[key]:
                    subdirectory = Directory()
                    subdirectory.ParseFromString(data)
                    digest_to_directory[key] = subdirectory
                    digest_to_directory.update(
                        (
                            self._build_directory(
                                self._digest_to_directory.get(key, None),
                                subdirectory,
                                os.path.join(
                                    directory_local, directory_node.name
                                ),
                            )
                        )
                    )
            else:
                # TODO:
                print("Unknown digest")
        return digest_to_directory


class TopLevelCachedDirectoryBuilder(IDirectoryBuilder):
    def __init__(
        self,
        local_root: str,
        cache_root: str,
        cas_helper: CASHelper,
        filesystem: LocalHardlinkFilesystem,
        *,
        skip_cache: typing.Optional[typing.Iterable[str]] = None,
    ):
        self._local_root = local_root
        self._cache_root = cache_root
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
        self._cache_info: typing.Dict[str, DirectoryCacheInfo] = {}
        # in a file is not in cache dir. when we need to remove it, on
        # Windows we need to set it's mode to writable. However, this will
        # also change the source file's mode to writable. So on Windows
        # we decide to copy these files(there shouldn't be many files not
        # in cache dir).
        self._copy_file_not_in_cache_dir = sys.platform == "win32"

    @property
    def local_root(self):
        return self._local_root

    def clear(self):
        if os.path.exists(self._local_root):
            shutil.rmtree(self._local_root)

    def init(self):
        if not os.path.exists(self._cache_root):
            os.makedirs(self._cache_root)
        self._verify_existing_dirs()

    def build(self, input_root_digest: Digest, input_root: Directory) -> None:
        self._build_with_cache(
            input_root,
            self._local_root,
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
                copy_file=self._copy_file_not_in_cache_dir,
            )
        dir_digest_to_fetch: typing.Dict[DigestKey, Digest] = {}
        dir_digest_to_names: typing.Dict[
            DigestKey, typing.List[str]
        ] = collections.defaultdict(list)
        dn: DirectoryNode
        for dn in input_root.directories:
            digest = dn.digest
            name_in_cache = f"{digest.hash}_{digest.size_bytes}"
            path_in_cache = os.path.join(self._cache_root, name_in_cache)
            need_fetch = False
            if dn.name in large_directory or dn.name in skip_cache:
                need_fetch = True
            elif not os.path.exists(path_in_cache):
                need_fetch = True
            else:
                # TODO: move to single thread for corruption check.
                # corrupted = False
                # if name_in_cache not in self._cache_info:
                #     corrupted = True
                # else:
                #     corrupted = not self._verify_directory(
                #         path_in_cache, self._cache_info[name_in_cache]
                #     )
                corrupted = False
                if not corrupted:
                    create_dir_link(
                        path_in_cache, os.path.join(directory_local, dn.name)
                    )
                else:
                    rmtree(path_in_cache)
                    need_fetch = True
            if need_fetch:
                key = (digest.hash, digest.size_bytes)
                dir_digest_to_fetch[key] = digest
                dir_digest_to_names[key].append(dn.name)
        for digest, offset, data in self._directory_blob_cache.fetch_all(
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
                        self._build_native(
                            subdirectory,
                            dir_local_path,
                            readonly=False,
                            copy_file=self._copy_file_not_in_cache_dir,
                        )
                    else:
                        path_to_link.append(dir_local_path)
                if path_to_link:
                    path_in_cache = os.path.join(
                        self._cache_root, name_in_cache
                    )
                    dir_cache_info = self._build_native(
                        subdirectory, path_in_cache
                    )
                    self._cache_info[name_in_cache] = dir_cache_info
                    for dir_local_path in path_to_link:
                        create_dir_link(path_in_cache, dir_local_path)
            else:
                # TODO:
                print("Unknown digest")

    def _build_native(
        self,
        input_root: Directory,
        directory_local: str,
        readonly: bool = True,
        copy_file: bool = False,
    ) -> DirectoryCacheInfo:
        file_info: typing.Dict[str, FileCacheInfo] = {}
        dir_info: typing.Dict[str, DirectoryCacheInfo] = {}
        if not os.path.exists(directory_local):
            os.makedirs(directory_local)
        # files.
        self._filesystem.fetch_to(
            self._cas_helper,
            input_root.files,
            directory_local,
            copy_file=copy_file,
        )
        # TODO: better exception.
        for f in input_root.files:
            p = os.path.join(directory_local, f.name)
            if not os.path.exists(p):
                raise RuntimeError(f"missing file {f.name}")
            else:
                file_info[f.name] = FileCacheInfo(os.stat(p))
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
        for digest, offset, data in self._directory_blob_cache.fetch_all(
            dir_digest_to_fetch.values()
        ):
            key = (digest.hash, digest.size_bytes)
            if key in dir_digest_to_names:
                subdirectory = Directory()
                subdirectory.ParseFromString(data)
                for name in dir_digest_to_names[key]:
                    dir_info[name] = self._build_native(
                        subdirectory,
                        os.path.join(directory_local, name),
                        readonly=readonly,
                        copy_file=copy_file,
                    )
            else:
                # TODO:
                print("Unknown digest")
        # TODO: better exception.
        for d in input_root.directories:
            if not os.path.exists(os.path.join(directory_local, d.name)):
                raise RuntimeError(f"missing directory {d.name}")
        if readonly:
            set_read_exec_only(directory_local)
        return DirectoryCacheInfo(file_info, dir_info)

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

    def _verify_directory(
        self, target: str, target_cache_info: DirectoryCacheInfo
    ) -> bool:
        directory_to_check = [(target, target_cache_info)]
        while directory_to_check:
            dpath, cache_info = directory_to_check.pop(0)
            filenames = set()
            dirnames = set()
            try:
                for name in os.listdir(dpath):
                    # do NOT use isfile here. os.path.isfile is much slower
                    # than os.stat. just call os.stat, if file is missing we
                    # return False.
                    p = os.path.join(dpath, name)
                    if name in cache_info.file_info:
                        expect_info = cache_info.file_info[name]
                        if not expect_info.match(os.stat(p)):
                            return False
                        filenames.add(name)
                    elif name in cache_info.dir_info:
                        expect_dir_info = cache_info.dir_info[name]
                        directory_to_check.append((p, expect_dir_info))
                        dirnames.add(name)
                    else:
                        # unknown file or dir.
                        return False
            except FileNotFoundError:
                # if any required file or dir is missing, return False.
                return False
            for name in cache_info.file_info:
                if name not in filenames:
                    return False
            for name in cache_info.dir_info:
                if name not in dirnames:
                    return False
        return True

    def _verify_existing_dirs(self) -> None:
        print("INFO: verify directory start.")
        dir_to_verify: typing.List[str] = []
        for name in os.listdir(self._cache_root):
            p = os.path.join(self._cache_root, name)
            if os.path.isdir(p):
                dir_to_verify.append(name)
            elif os.path.isfile(p):
                unlink_file(p)
        if dir_to_verify:
            verify_thread_count = 10
            mapped_digests = [
                dir_to_verify[i::verify_thread_count]
                for i in range(verify_thread_count)
            ]
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=verify_thread_count,
                thread_name_prefix="verify_dir_thread_",
            ) as executor:
                future_list = []
                for part in mapped_digests:
                    future_list.append(
                        executor.submit(self._verify_thread, part)
                    )
                for f in future_list:
                    f.result()
        print("INFO: verify directory end.")

    def _verify_thread(self, directory_to_verify: typing.Iterable[str]):
        for name in directory_to_verify:
            p = os.path.join(self._cache_root, name)
            try:
                hash_, size_bytes_str = name.split("_")
                size_bytes = int(size_bytes_str)
                digest = self._calculate_dir_digest(p)
                if digest is None:
                    self._remove_cached_dir(p)
                elif digest.hash != hash_ or digest.size_bytes != size_bytes:
                    self._remove_cached_dir(p)
            except Exception:
                self._remove_cached_dir(p)

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

    def _remove_cached_dir(self, target: str):
        dir_mode = stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR
        file_mode = stat.S_IWUSR | stat.S_IRUSR
        for dir_, dirnames, filenames in os.walk(target):
            for n in filenames:
                os.chmod(os.path.join(dir_, n), file_mode)
            for n in dirnames:
                os.chmod(os.path.join(dir_, n), dir_mode)
        os.chmod(target, dir_mode)
        shutil.rmtree(target)
