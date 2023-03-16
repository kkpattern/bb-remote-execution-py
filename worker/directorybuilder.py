import collections
import os
import os.path
import shutil
import typing

from build.bazel.remote.execution.v2.remote_execution_pb2 import Directory
from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest

from .cas import CASHelper
from .util import digest_to_key
from .filesystem import LocalHardlinkFilesystem


DIGEST_KEY = typing.Optional[typing.Tuple[str, int]]


class DiffBasedBuildDirectoryBuilder(object):
    """A diff-based bazel action directory builder."""

    def __init__(
        self,
        root_local: str,
        cas_helper: CASHelper,
        filesystem: LocalHardlinkFilesystem,
    ):
        self._root_local = root_local
        self._cas_helper = cas_helper
        self._filesystem = filesystem
        self._current_root_digest: typing.Optional[Digest] = None
        self._digest_to_directory: typing.Dict[
            DIGEST_KEY, typing.Optional[Directory]
        ] = {}

    @property
    def local_root(self):
        return self._root_local

    def clear(self):
        if os.path.exists(self._root_local):
            shutil.rmtree(self._root_local)

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
        # Diff files.
        for name, f in files.items():
            if name not in new_files:
                os.unlink(os.path.join(directory_local, name))
        for name, f in new_files.items():
            if name not in files:
                file_to_fetch.append(f)
            elif name in files:
                if f.digest != files[name].digest:
                    os.unlink(os.path.join(directory_local, name))
                    file_to_fetch.append(f)
        self._filesystem.fetch_to(
            self._cas_helper, file_to_fetch, directory_local
        )
        for f in input_root.files:
            if not os.path.exists(os.path.join(directory_local, f.name)):
                raise RuntimeError(f"missing file {f.name}")
        # Diff directories.
        directory_to_fetch = collections.defaultdict(list)
        for name, d in directories.items():
            if name not in new_directories:
                shutil.rmtree(os.path.join(directory_local, name))
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
        for digest, offset, data in self._cas_helper.fetch_all(digest_list):
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
