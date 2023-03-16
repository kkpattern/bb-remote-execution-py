import concurrent.futures
import os
import os.path
import random
import stat
import sys
import tempfile
import typing
import uuid

import pytest

from bbworker.directorybuilder import SharedTopLevelCachedDirectoryBuilder
from bbworker.filesystem import LocalHardlinkFilesystem

from bbworker.util import unlink_readonly_file
from bbworker.util import set_read_exec_write


class FakeIOError(Exception):
    pass


def _assert_directory(
    dir_data,
    dir_path: str,
    skip_cache: typing.Optional[typing.Iterable[str]] = None,
):
    if skip_cache is None:
        skip_cache = set()
    assert sorted(os.listdir(dir_path)) == sorted(dir_data)
    for k, v in dir_data.items():
        p = os.path.join(dir_path, k)
        if k not in skip_cache:
            assert not (
                os.stat(p).st_mode & stat.S_IWUSR
            ), f"{p} should be readony"
        if isinstance(v, bytes):
            assert os.path.isfile(p)
            with open(p, "rb") as f:
                assert f.read() == v
        elif isinstance(v, dict):
            if k in skip_cache:
                sub_skip_cache = os.listdir(p)
            else:
                sub_skip_cache = None
            _assert_directory(v, p, skip_cache=sub_skip_cache)


def _get_directory_size_inode(target: str) -> int:
    total_size_bytes = 0
    inode_set = set()
    for dir_, dirnames, filenames in os.walk(target):
        for n in filenames:
            p = os.path.join(dir_, n)
            inode = os.stat(p).st_ino
            if inode not in inode_set:
                inode_set.add(inode)
                total_size_bytes += os.path.getsize(p)
    return total_size_bytes


class TestSharedTopLevelCachedDirectoryBuilder(object):
    def test_basic_build(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data = {
                "file_1": b"a" * 100,
                "file_2": b"b" * 20,
                "dir_1": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                },
            }
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)

    def test_basic_build_executable(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data = {
                "file_1": b"a" * 100,
                "file_2": b"b" * 20,
                "dir_1": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                },
            }
            mock_cas_helper.set_data_executable(b"a" * 100, True)
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)
            assert (
                os.stat(os.path.join(local_root, "file_1")).st_mode
                & stat.S_IXUSR
            )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="chmod cannot make directory real readonly on Windows.",
    )
    def test_basic_build_dir_readonly(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data = {
                "file_1": b"a" * 100,
                "file_2": b"b" * 20,
                "dir_1": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                    "dir_1_1": {},
                    "dir_1_2": {
                        "dir_1_1_1": {
                            "file_1_1_1_1": b"x" * 10,
                        },
                    },
                },
                "dir_2": {},
                "dir_3": {
                    "file_3_1": b"c" * 10,
                },
            }
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            skip_cache = ["dir_2", "dir_3"]
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root,
                mock_cas_helper,
                filesystem,
                skip_cache=skip_cache,
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(
                input_root_data, local_root, skip_cache=skip_cache
            )
            for test_dir in [
                os.path.join(local_root, "dir_1"),
                os.path.join(local_root, "dir_1", "dir_1_1"),
                os.path.join(local_root, "dir_1", "dir_1_2", "dir_1_1_1"),
            ]:
                with pytest.raises(PermissionError):
                    with open(os.path.join(test_dir, "test.txt"), "wb") as f:
                        f.write(b"test")
            for test_dir in [
                os.path.join(local_root, "dir_2"),
                os.path.join(local_root, "dir_3"),
            ]:
                p = os.path.join(test_dir, "test.txt")
                with open(p, "wb") as f:
                    f.write(b"test")
                assert os.path.isfile(p)

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="chmod cannot make directory real readonly on Windows.",
    )
    def test_basic_build_dir_readonly_no_skip_cache(self, mock_cas_helper):
        """when build directory for skip cache dir, should not make it
        readonly.
        """
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data = {
                "file_1": b"a" * 100,
                "file_2": b"b" * 20,
                "dir_1": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                    "dir_1_1": {},
                    "dir_1_2": {
                        "dir_1_1_1": {
                            "file_1_1_1_1": b"x" * 10,
                        },
                    },
                },
            }
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)
            for test_dir in [
                os.path.join(local_root, "dir_1"),
                os.path.join(local_root, "dir_1", "dir_1_1"),
                os.path.join(local_root, "dir_1", "dir_1_2", "dir_1_1_1"),
            ]:
                with pytest.raises(PermissionError):
                    with open(os.path.join(test_dir, "test.txt"), "wb") as f:
                        f.write(b"test")

    def test_basic_build_relative_path(self, mock_cas_helper):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as test_root:
            os.chdir(test_root)
            try:
                filesystem_root = "filesystem_root"
                local_root = "local_root"
                cache_root = "cache_root"
                input_root_data = {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"d" * 15,
                    },
                }
                input_root_digest = mock_cas_helper.append_directory(
                    input_root_data
                )
                input_root_directory = mock_cas_helper.get_directory_by_digest(
                    input_root_digest
                )
                filesystem = LocalHardlinkFilesystem(filesystem_root)
                filesystem.init()
                builder = SharedTopLevelCachedDirectoryBuilder(
                    cache_root, mock_cas_helper, filesystem
                )
                builder.init()
                builder.build(
                    input_root_digest, input_root_directory, local_root
                )
                _assert_directory(input_root_data, local_root)
            finally:
                os.chdir(cwd)

    def test_build_verify_dirs(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data_list = [
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {
                            "dir_1_1_1": {
                                "file_1_1_1_1": b"x" * 10,
                            },
                        },
                    },
                },
                {
                    "file_1": b"a" * 200,
                    "file_2": b"x" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "dir_1_1": {},
                        "dir_1_2": {
                            "dir_1_1_1": {
                                "file_1_1_1_1": b"x" * 10,
                            },
                        },
                    },
                    "dir_2": {
                        "file_2_1": b"x" * 104,
                    },
                },
                {
                    "file_1": b"a" * 200,
                    "file_2": b"x" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "dir_1_1": {},
                        "dir_1_2": {
                            "dir_1_1_1": {
                                "file_1_1_1_1": b"x" * 10,
                            },
                        },
                    },
                    "dir_2": {
                        "file_2": b"abced",
                        "file_2_1": b"x" * 104,
                    },
                },
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {
                            "dir_1_1_1": {
                                "file_1_1_1_1": b"x" * 10,
                            },
                        },
                    },
                },
            ]
            input_root_digest_list = []
            input_root_directory_list = []
            for input_root_data in input_root_data_list:
                digest = mock_cas_helper.append_directory(input_root_data)
                input_root_digest_list.append(digest)
                input_root_directory_list.append(
                    mock_cas_helper.get_directory_by_digest(digest)
                )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            for i, d in enumerate(input_root_digest_list):
                builder.build(d, input_root_directory_list[i], local_root)
                _assert_directory(input_root_data_list[i], local_root)
            cached_dirs = sorted(os.listdir(cache_root))
            # simulate process restart.
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert cached_dirs == sorted(os.listdir(cache_root))
            _assert_directory(input_root_data_list[-1], local_root)

    def test_keep_file_readonly(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data_list = [
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {
                            "dir_1_1_1": {
                                "file_1_1_1_1": b"x" * 10,
                            },
                        },
                    },
                },
                {
                    "file_1": b"a" * 200,
                    "file_2": b"x" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "dir_1_1": {},
                        "dir_1_2": {
                            "dir_1_1_1": {
                                "file_1_1_1_1": b"x" * 10,
                            },
                        },
                    },
                    "dir_2": {
                        "file_2_1": b"x" * 104,
                    },
                },
                {
                    "file_1": b"a" * 200,
                    "file_2": b"x" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "dir_1_1": {},
                        "dir_1_2": {
                            "dir_1_1_1": {
                                "file_1_1_1_1": b"x" * 10,
                            },
                        },
                    },
                    "dir_2": {
                        "file_2": b"abced",
                        "file_2_1": b"x" * 104,
                    },
                },
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {
                            "dir_1_1_1": {
                                "file_1_1_1_1": b"x" * 10,
                            },
                        },
                    },
                },
            ]
            input_root_digest_list = []
            input_root_directory_list = []
            for input_root_data in input_root_data_list:
                digest = mock_cas_helper.append_directory(input_root_data)
                input_root_digest_list.append(digest)
                input_root_directory_list.append(
                    mock_cas_helper.get_directory_by_digest(digest)
                )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            for i, d in enumerate(input_root_digest_list):
                builder.build(d, input_root_directory_list[i], local_root)
                _assert_directory(input_root_data_list[i], local_root)
            for name in os.listdir(filesystem_root):
                p = os.path.join(filesystem_root, name)
                assert not os.stat(p).st_mode & stat.S_IWUSR

    def test_validation_keep_file_readonly(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data_list = [
                {
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                    },
                },
                {
                    "dir_2": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"d" * 15,
                    },
                },
            ]
            input_root_digest_list = []
            input_root_directory_list = []
            for input_root_data in input_root_data_list:
                digest = mock_cas_helper.append_directory(input_root_data)
                input_root_digest_list.append(digest)
                input_root_directory_list.append(
                    mock_cas_helper.get_directory_by_digest(digest)
                )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            for i, d in enumerate(input_root_digest_list):
                builder.build(d, input_root_directory_list[i], local_root)
                _assert_directory(input_root_data_list[i], local_root)
            # corrupt the seconds directory.
            set_read_exec_write(os.path.join(local_root, "dir_2"))
            with open(os.path.join(local_root, "dir_2", "test"), "wb") as f:
                f.write(b"xx")
            builder.init()
            # all files in filesystem keeps readonly.
            for name in os.listdir(filesystem_root):
                p = os.path.join(filesystem_root, name)
                assert not os.stat(p).st_mode & stat.S_IWUSR

            def _no_fetch_to(*args, **kargs):
                assert False, "fetch_to should not be called."

            filesystem.fetch_to = _no_fetch_to
            # the first directory should still in the same.
            builder.build(
                input_root_digest_list[0],
                input_root_directory_list[0],
                local_root,
            )
            _assert_directory(input_root_data_list[0], local_root)

    def test_build_verify_mode_changed(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data = {
                "file_1": b"a" * 100,
                "file_2": b"b" * 20,
                "dir_1": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                    "dir_1_1": {},
                    "dir_1_2": {
                        "dir_1_1_1": {
                            "file_1_1_1_1": b"x" * 10,
                        },
                    },
                },
            }
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)
            # Test dir mode changed.
            cache_dir_root = builder.cache_dir_root
            for name in os.listdir(cache_dir_root):
                p = os.path.join(cache_dir_root, name)
                if os.path.isdir(p):
                    os.chmod(p, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
            # simulate process restart.
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert not sorted(os.listdir(cache_dir_root))
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)
            # Test file mode changed.
            for dir_, dirnames, filenames in os.walk(cache_root):
                for name in filenames:
                    p = os.path.join(dir_, name)
                    os.chmod(p, stat.S_IWUSR | stat.S_IRUSR)
            # simulate process restart.
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert not sorted(os.listdir(cache_dir_root))
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)

    def test_build_verify_add_file(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data = {
                "file_1": b"a" * 100,
                "file_2": b"b" * 20,
                "dir_1": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                    "dir_1_1": {},
                    "dir_1_2": {
                        "dir_1_1_1": {
                            "file_1_1_1_1": b"x" * 10,
                        },
                    },
                },
            }
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)
            cache_dir_root = builder.cache_dir_root
            for name in os.listdir(cache_dir_root):
                p = os.path.join(cache_dir_root, name)
                if os.path.isdir(p):
                    os.chmod(p, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
                    with open(os.path.join(p, "new.txt"), "wb") as f:
                        f.write(b"testdata")
                    os.chmod(p, stat.S_IRUSR | stat.S_IXUSR)
            # simulate process restart.
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert not sorted(os.listdir(cache_dir_root))
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)

    def test_build_verify_file_content_change(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data = {
                "file_1": b"a" * 100,
                "file_2": b"b" * 20,
                "dir_1": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                    "dir_1_1": {},
                    "dir_1_2": {
                        "dir_1_1_1": {
                            "file_1_1_1_1": b"x" * 10,
                        },
                    },
                },
            }
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)
            cache_dir_root = builder.cache_dir_root
            for dir_, dirnames, filenames in os.walk(cache_dir_root):
                for name in filenames:
                    p = os.path.join(dir_, name)
                    origin_mode = os.stat(p).st_mode
                    os.chmod(p, origin_mode | stat.S_IWUSR)
                    with open(p, "wb") as f:
                        f.write(b"testoverride")
                    os.chmod(p, origin_mode)
            # simulate process restart.
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert not sorted(os.listdir(cache_dir_root))
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)

    def test_build_verify_large_file(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data = {
                "file_1": b"a" * (10 * 1024 * 1024),
                "file_2": b"b" * 20,
                "dir_1": {
                    "file_1_1": b"c" * (10 * 1024 * 1024),
                    "file_1_2": b"d" * 15,
                    "dir_1_1": {},
                    "dir_1_2": {
                        "dir_1_1_1": {
                            "file_1_1_1_1": b"x" * 10,
                        },
                    },
                },
            }
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)
            cached_dirs = sorted(os.listdir(cache_root))
            # simulate process restart.
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert cached_dirs == sorted(os.listdir(cache_root))
            _assert_directory(input_root_data, local_root)

    def test_build_verify_remove_file(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data = {
                "file_1": b"a" * 100,
                "file_2": b"b" * 20,
                "dir_1": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                    "dir_1_1": {},
                    "dir_1_2": {
                        "dir_1_1_1": {
                            "file_1_1_1_1": b"x" * 10,
                        },
                    },
                },
            }
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)
            cache_dir_root = builder.cache_dir_root
            for dir_, dirnames, filenames in os.walk(cache_dir_root):
                for name in filenames:
                    p = os.path.join(dir_, name)
                    os.chmod(dir_, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
                    unlink_readonly_file(p)
                    os.chmod(dir_, stat.S_IRUSR | stat.S_IXUSR)
            # simulate process restart.
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert not sorted(os.listdir(cache_dir_root))
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)

    def test_in_cache_after_validation(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data_list = [
                {
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                    },
                },
                {
                    "dir_2": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"d" * 15,
                    },
                },
            ]
            input_root_digest_list = []
            input_root_directory_list = []
            for input_root_data in input_root_data_list:
                digest = mock_cas_helper.append_directory(input_root_data)
                input_root_digest_list.append(digest)
                input_root_directory_list.append(
                    mock_cas_helper.get_directory_by_digest(digest)
                )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            for i, d in enumerate(input_root_digest_list):
                builder.build(d, input_root_directory_list[i], local_root)
                _assert_directory(input_root_data_list[i], local_root)
            # remove file content remove cas. we should still be able to build
            # the directory because we still have cache.
            for f in os.listdir(filesystem_root):
                unlink_readonly_file(os.path.join(filesystem_root, f))
            mock_cas_helper.set_data_exception(
                b"c" * 5, FakeIOError("not found")
            )
            mock_cas_helper.set_data_exception(
                b"d" * 15, FakeIOError("not found")
            )
            # simulate restart
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            for i, d in enumerate(input_root_digest_list):
                builder.build(d, input_root_directory_list[i], local_root)
                _assert_directory(input_root_data_list[i], local_root)

    def test_basic_build_with_cache(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root_1,
            tempfile.TemporaryDirectory() as cache_root_1,
            tempfile.TemporaryDirectory() as local_root_2,
            tempfile.TemporaryDirectory() as cache_root_2,
        ):
            input_root_data = {
                "dir_1": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                },
            }
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            builder_1 = SharedTopLevelCachedDirectoryBuilder(
                cache_root_1, mock_cas_helper, filesystem
            )
            builder_1.init()
            builder_2 = SharedTopLevelCachedDirectoryBuilder(
                cache_root_2, mock_cas_helper, filesystem
            )
            builder_2.init()
            builder_1.build(
                input_root_digest, input_root_directory, local_root_1
            )
            _assert_directory(input_root_data, local_root_1)

            builder_2.build(
                input_root_digest, input_root_directory, local_root_2
            )
            _assert_directory(input_root_data, local_root_2)

            def should_not_call(*args, **kargs):
                assert (
                    False
                ), "should not call filesystem.fetch_to when dir is cached."

            filesystem.fetch_to = should_not_call
            builder_1.build(
                input_root_digest, input_root_directory, local_root_1
            )
            _assert_directory(input_root_data, local_root_1)
            builder_2.build(
                input_root_digest, input_root_directory, local_root_2
            )
            _assert_directory(input_root_data, local_root_2)

    def test_build_files_with_same_data(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data = {
                "file_1": b"a" * 100,
                "file_2": b"a" * 100,
                "file_3": b"a" * 100,
                "dir_1": {
                    "file_1": b"c" * 5,
                    "file_2": b"d" * 15,
                },
                "dir_2": {
                    "file_1": b"c" * 5,
                    "file_2": b"d" * 15,
                },
            }
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)

    def test_build_clear(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()

            input_root_data_1 = {
                "file_1": b"a" * 100,
                "file_2": b"b" * 20,
                "dir_1": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                },
            }
            input_root_data_2 = {
                "file_1": b"acef" * 100,
                "dir_2": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                },
            }
            input_root_data_3 = {
                "dir_2": {
                    "file_1_2": b"d" * 15,
                    "dir_2_1": {
                        "file_2_1_1": b"abcefg",
                        "dir_2_1_1": {
                            "file_2_1_1_1": b"z" * 100,
                        },
                    },
                },
            }
            for data in [
                input_root_data_1,
                input_root_data_2,
                input_root_data_1,
                input_root_data_3,
                input_root_data_2,
            ]:
                input_root_digest = mock_cas_helper.append_directory(data)
                input_root_directory = mock_cas_helper.get_directory_by_digest(
                    input_root_digest
                )
                builder.build(
                    input_root_digest, input_root_directory, local_root
                )
                _assert_directory(data, local_root)

    # def test_corrupt_check_during_running(self, mock_cas_helper):
    #     with (
    #         tempfile.TemporaryDirectory() as filesystem_root,
    #         tempfile.TemporaryDirectory() as local_root,
    #         tempfile.TemporaryDirectory() as cache_root,
    #     ):
    #         input_root_data = {
    #             "file_1": b"a" * 100,
    #             "file_2": b"b" * 20,
    #             "dir_1": {
    #                 "file_1_1": b"c" * 5,
    #                 "file_1_2": b"d" * 15,
    #             },
    #         }
    #         input_root_digest = mock_cas_helper.append_directory(
    #             input_root_data
    #         )
    #         input_root_directory = mock_cas_helper.get_directory_by_digest(
    #             input_root_digest
    #         )
    #         filesystem = LocalHardlinkFilesystem(filesystem_root)
    #         builder = TopLevelCachedDirectoryBuilder(
    #             local_root, cache_root, mock_cas_helper, filesystem
    #         )
    #         builder.build(input_root_digest, input_root_directory)
    #         _assert_directory(input_root_data, local_root)
    #         # make files corrupt.
    #         for dir_, dirnames, filenames in os.walk(cache_root):
    #             for n in filenames:
    #                 p = os.path.join(dir_, n)
    #                 os.chmod(p, stat.S_IWUSR)
    #                 with open(p, "wb") as f:
    #                     f.write(b"xxx")
    #         builder.build(input_root_digest, input_root_directory)
    #         _assert_directory(input_root_data, local_root)

    # def test_file_added(self, mock_cas_helper):
    #     with (
    #         tempfile.TemporaryDirectory() as filesystem_root,
    #         tempfile.TemporaryDirectory() as local_root,
    #         tempfile.TemporaryDirectory() as cache_root,
    #     ):
    #         input_root_data = {
    #             "file_1": b"a" * 100,
    #             "file_2": b"b" * 20,
    #             "dir_1": {
    #                 "file_1_1": b"c" * 5,
    #                 "file_1_2": b"d" * 15,
    #             },
    #         }
    #         input_root_digest = mock_cas_helper.append_directory(
    #             input_root_data
    #         )
    #         input_root_directory = mock_cas_helper.get_directory_by_digest(
    #             input_root_digest
    #         )
    #         filesystem = LocalHardlinkFilesystem(filesystem_root)
    #         builder = TopLevelCachedDirectoryBuilder(
    #             local_root, cache_root, mock_cas_helper, filesystem
    #         )
    #         builder.build(input_root_digest, input_root_directory)
    #         _assert_directory(input_root_data, local_root)
    #         # add new files in directory.
    #         for dir_, dirnames, filenames in os.walk(cache_root):
    #             for n in dirnames:
    #                 with open(os.path.join(dir_, n, "new"), "wb") as f:
    #                     f.write(b"XX")
    #         builder.build(input_root_digest, input_root_directory)
    #         _assert_directory(input_root_data, local_root)

    # def test_file_removed(self, mock_cas_helper):
    #     with (
    #         tempfile.TemporaryDirectory() as filesystem_root,
    #         tempfile.TemporaryDirectory() as local_root,
    #         tempfile.TemporaryDirectory() as cache_root,
    #     ):
    #         input_root_data = {
    #             "file_1": b"a" * 100,
    #             "file_2": b"b" * 20,
    #             "dir_1": {
    #                 "file_1_1": b"c" * 5,
    #                 "file_1_2": b"d" * 15,
    #             },
    #         }
    #         input_root_digest = mock_cas_helper.append_directory(
    #             input_root_data
    #         )
    #         input_root_directory = mock_cas_helper.get_directory_by_digest(
    #             input_root_digest
    #         )
    #         filesystem = LocalHardlinkFilesystem(filesystem_root)
    #         builder = TopLevelCachedDirectoryBuilder(
    #             local_root, cache_root, mock_cas_helper, filesystem
    #         )
    #         builder.build(input_root_digest, input_root_directory)
    #         _assert_directory(input_root_data, local_root)
    #         # make files in directory corrupt.
    #         for name in os.listdir(cache_root):
    #             p = os.path.join(cache_root, name)
    #             if os.path.isdir(p):
    #                 for dir_, dirnames, filenames in os.walk(p):
    #                     for n in filenames:
    #                         unlink_file(os.path.join(dir_, n))
    #         builder.build(input_root_digest, input_root_directory)
    #         _assert_directory(input_root_data, local_root)

    # def test_file_added_after_restart(self, mock_cas_helper):
    #     with (
    #         tempfile.TemporaryDirectory() as filesystem_root,
    #         tempfile.TemporaryDirectory() as local_root,
    #         tempfile.TemporaryDirectory() as cache_root,
    #     ):
    #         input_root_data = {
    #             "file_1": b"a" * 100,
    #             "file_2": b"b" * 20,
    #             "dir_1": {
    #                 "file_1_1": b"c" * 5,
    #                 "file_1_2": b"d" * 15,
    #             },
    #         }
    #         input_root_digest = mock_cas_helper.append_directory(
    #             input_root_data
    #         )
    #         input_root_directory = mock_cas_helper.get_directory_by_digest(
    #             input_root_digest
    #         )
    #         filesystem = LocalHardlinkFilesystem(filesystem_root)
    #         builder = TopLevelCachedDirectoryBuilder(
    #             local_root, cache_root, mock_cas_helper, filesystem
    #         )
    #         builder.build(input_root_digest, input_root_directory)
    #         _assert_directory(input_root_data, local_root)
    #         # add new files in directory.
    #         for dir_, dirnames, filenames in os.walk(cache_root):
    #             for n in dirnames:
    #                 with open(os.path.join(dir_, n, "new"), "wb") as f:
    #                     f.write(b"XX")
    #         # simulate restart process.
    #         builder = TopLevelCachedDirectoryBuilder(
    #             local_root, cache_root, mock_cas_helper, filesystem
    #         )
    #         builder.build(input_root_digest, input_root_directory)
    #         _assert_directory(input_root_data, local_root)

    # def test_file_removed_after_restart(self, mock_cas_helper):
    #     with (
    #         tempfile.TemporaryDirectory() as filesystem_root,
    #         tempfile.TemporaryDirectory() as local_root,
    #         tempfile.TemporaryDirectory() as cache_root,
    #     ):
    #         input_root_data = {
    #             "file_1": b"a" * 100,
    #             "file_2": b"b" * 20,
    #             "dir_1": {
    #                 "file_1_1": b"c" * 5,
    #                 "file_1_2": b"d" * 15,
    #             },
    #         }
    #         input_root_digest = mock_cas_helper.append_directory(
    #             input_root_data
    #         )
    #         input_root_directory = mock_cas_helper.get_directory_by_digest(
    #             input_root_digest
    #         )
    #         filesystem = LocalHardlinkFilesystem(filesystem_root)
    #         builder = TopLevelCachedDirectoryBuilder(
    #             local_root, cache_root, mock_cas_helper, filesystem
    #         )
    #         builder.build(input_root_digest, input_root_directory)
    #         _assert_directory(input_root_data, local_root)
    #         # make files in directory corrupt.
    #         for name in os.listdir(cache_root):
    #             p = os.path.join(cache_root, name)
    #             if os.path.isdir(p):
    #                 for dir_, dirnames, filenames in os.walk(p):
    #                     for n in filenames:
    #                         unlink_file(os.path.join(dir_, n))
    #         # simulate restart process.
    #         builder = TopLevelCachedDirectoryBuilder(
    #             local_root, cache_root, mock_cas_helper, filesystem
    #         )
    #         builder.build(input_root_digest, input_root_directory)
    #         _assert_directory(input_root_data, local_root)

    def test_remove_output_directory(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            input_root_data = {
                "file_1": b"a" * 100,
                "file_2": b"b" * 20,
                "dir_1": {
                    "file_1_1": b"c" * 5,
                    "file_1_2": b"d" * 15,
                },
            }
            input_root_digest = mock_cas_helper.append_directory(
                input_root_data
            )
            input_root_directory = mock_cas_helper.get_directory_by_digest(
                input_root_digest
            )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)
            # create a output directory.
            os.makedirs(os.path.join(local_root, "bazel-out"))
            # build directory again.
            builder.build(input_root_digest, input_root_directory, local_root)
            _assert_directory(input_root_data, local_root)

    @pytest.mark.only_in_full_test
    def test_multithread(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            mock_cas_helper.set_seconds_per_byte(0.00001)
            input_root_data_list = [
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"d" * 15,
                    },
                },
                {
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"x" * 15,
                        "file_1_2": b"y" * 15,
                    },
                },
                {
                    "file_2": b"b" * 20,
                    "dir_2": {
                        "file_2_1": b"x" * 1024 * 1024,
                        "file_2_2": b"y" * 15,
                    },
                },
                {
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"d" * 15,
                    },
                    "dir_2": {
                        "file_2_1": b"x" * 1024 * 1024,
                        "file_2_2": b"y" * 15,
                    },
                    "bazel-out": {
                        "dir_1": {
                            "file_1_1": b"abcd",
                        },
                    },
                },
                {
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"d" * 15,
                        "dir_1_1": {
                            "file_1_1": b"x" * 10,
                        },
                    },
                    "dir_2": {
                        "file_2_1": b"x" * 1024 * 1024,
                        "file_2_2": b"y" * 15,
                    },
                    "bazel-out": {
                        "file_1": b"abcd",
                    },
                    "external": {"engine": {"file_x": b"x"}},
                },
            ]
            for i in range(10):
                input_root_data_list.append(
                    {f"dir_{i}": {"file_1": b"d" * (i % 10 + 1)}}
                )
            for i in range(10):
                input_root_data_list.append(
                    {
                        "bazel-out": {f"file_{i}": b"d" * 10},
                        f"dir_{i}": {"file_1": b"d" * (i % 10 + 1)},
                    }
                )
            for i in range(20):
                dir_data = {}
                for j in range(5):
                    dir_data[f"dir_{i}_{j}"] = {
                        f"file_{i}_{j}_x": b"xxx" * (i + j)
                    }
                input_root_data_list.append(dir_data)
            input_root_digest_list = [
                mock_cas_helper.append_directory(d)
                for d in input_root_data_list
            ]
            input_root_directory_list = [
                mock_cas_helper.get_directory_by_digest(d)
                for d in input_root_digest_list
            ]
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            skip_cache = ["bazel-out", "external", "engine"]
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root,
                mock_cas_helper,
                filesystem,
                skip_cache=skip_cache,
            )
            builder.init()

            def _thread_run():
                thread_root = os.path.join(local_root, str(uuid.uuid4()))
                index_list = list(range(len(input_root_data_list)))
                random.shuffle(index_list)
                for i in index_list:
                    builder.build(
                        input_root_digest_list[i],
                        input_root_directory_list[i],
                        thread_root,
                    )
                    _assert_directory(
                        input_root_data_list[i],
                        thread_root,
                        skip_cache=skip_cache,
                    )

            futures = []
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=10
            ) as executor:
                for i in range(20):
                    futures.append(executor.submit(_thread_run))
            for f in futures:
                f.result()

    # def test_same_directory_with_skip_cache_name


class TestCacheSizeLimitWithCopy:
    def test_current_size_bytes(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            test_data_list = [
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,  # test same file content.
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},  # test same dir.
                    },
                },
                {
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},  # test same dir.
                    },
                },
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,  # test same file content.
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
                {
                    "dir_2": {
                        "file_1_1": b"x" * 105,
                        "file_1_2": b"c" * 51,  # test same file content.
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {
                            "dir_1_1_1": {
                                "filex": b"x" * 200,
                            },
                        },
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
            ]
            input_list = []
            for data in test_data_list:
                digest = mock_cas_helper.append_directory(data)
                dir_ = mock_cas_helper.get_directory_by_digest(digest)
                input_list.append((digest, dir_))
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem, copy_file=True
            )
            builder.init()
            for digest, dir_ in input_list:
                builder.build(digest, dir_, local_root)
                total_size_bytes = 0
                for dir_, dirnames, filenames in os.walk(cache_root):
                    for n in filenames:
                        p = os.path.join(dir_, n)
                        total_size_bytes += os.path.getsize(p)
                assert total_size_bytes == builder.current_size_bytes

    def test_current_size_bytes_after_error(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            error_data = b"x" * 105
            test_data_list = [
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
                {
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
                {
                    "dir_2": {
                        "file_1_1": error_data,
                        "file_1_2": b"c" * 51,
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {
                            "dir_1_1_1": {
                                "filex": b"x" * 200,
                            },
                        },
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
            ]
            input_list = []
            for data in test_data_list:
                digest = mock_cas_helper.append_directory(data)
                dir_ = mock_cas_helper.get_directory_by_digest(digest)
                input_list.append((digest, dir_))
            mock_cas_helper.set_data_exception(error_data, FakeIOError())
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem, copy_file=True
            )
            builder.init()
            for digest, dir_ in input_list:
                try:
                    builder.build(digest, dir_, local_root)
                except FakeIOError:
                    pass
                total_size_bytes = 0
                for dir_, dirnames, filenames in os.walk(cache_root):
                    for n in filenames:
                        p = os.path.join(dir_, n)
                        total_size_bytes += os.path.getsize(p)
                assert total_size_bytes == builder.current_size_bytes

    def test_current_size_bytes_after_evict(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            test_data_list = [
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"x" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_3": b"x" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "dir_x": {
                        "dir_1_1": {"file_1_1_1": b"o" * 15},
                        "dir_1_2": {"file_1_2_1": b"z" * 5},
                    },
                },  # size_bytes: 20
            ]
            input_list = []
            for data in test_data_list:
                digest = mock_cas_helper.append_directory(data)
                dir_ = mock_cas_helper.get_directory_by_digest(digest)
                input_list.append((digest, dir_))
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root,
                mock_cas_helper,
                filesystem,
                copy_file=True,
                max_cache_size_bytes=60,
            )
            builder.init()
            for i in [0, 1, 2, 3, 4, 3, 2, 1, 2, 3, 0, 4, 4, 0, 1, 2]:
                digest, dir_ = input_list[i]
                builder.build(digest, dir_, local_root)
                total_size_bytes = 0
                for dir_, dirnames, filenames in os.walk(cache_root):
                    for n in filenames:
                        p = os.path.join(dir_, n)
                        total_size_bytes += os.path.getsize(p)
                assert total_size_bytes == builder.current_size_bytes

    def test_evict_directory(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            test_data_list = [
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"x" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_3": b"x" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "dir_x": {
                        "dir_1_1": {"file_1_1_1": b"o" * 15},
                        "dir_1_2": {"file_1_2_1": b"z" * 5},
                    },
                },  # size_bytes: 20
            ]
            input_list = []
            for data in test_data_list:
                digest = mock_cas_helper.append_directory(data)
                dir_ = mock_cas_helper.get_directory_by_digest(digest)
                input_list.append((digest, dir_))
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root,
                mock_cas_helper,
                filesystem,
                copy_file=True,
                max_cache_size_bytes=60,
            )
            builder.init()
            for i in [0, 1, 2]:
                digest, dir_ = input_list[i]
                builder.build(digest, dir_, local_root)
            for i in [0, 3, 4]:
                digest, dir_ = input_list[i]
                builder.build(digest, dir_, local_root)

            total_size_bytes = 0
            for dir_, dirnames, filenames in os.walk(cache_root):
                for n in filenames:
                    p = os.path.join(dir_, n)
                    total_size_bytes += os.path.getsize(p)
            assert total_size_bytes == builder.current_size_bytes
            assert builder.current_size_bytes == 60
            for i in [1, 2]:
                digest = input_list[i][1].directories[0].digest
                p = os.path.join(
                    cache_root, "dir", f"{digest.hash}_{digest.size_bytes}"
                )
                assert not os.path.exists(p)

    # TODO: download error remain broken directory.
    # TODO: test direcotry data cache.


class TestCacheSizeLimitWithHardlink:
    def test_current_size_bytes(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            test_data_list = [
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,  # test same file content.
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},  # test same dir.
                    },
                },
                {
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},  # test same dir.
                    },
                },
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,  # test same file content.
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
                {
                    "dir_2": {
                        "file_1_1": b"x" * 105,
                        "file_1_2": b"c" * 51,  # test same file content.
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {
                            "dir_1_1_1": {
                                "filex": b"x" * 200,
                            },
                        },
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
            ]
            input_list = []
            for data in test_data_list:
                digest = mock_cas_helper.append_directory(data)
                dir_ = mock_cas_helper.get_directory_by_digest(digest)
                input_list.append((digest, dir_))
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem, copy_file=False
            )
            builder.init()
            for digest, dir_ in input_list:
                builder.build(digest, dir_, local_root)
                total_size_bytes = _get_directory_size_inode(cache_root)
                assert total_size_bytes == builder.current_size_bytes

    def test_current_size_bytes_after_error(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            error_data = b"x" * 105
            test_data_list = [
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
                {
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
                {
                    "dir_2": {
                        "file_1_1": error_data,
                        "file_1_2": b"c" * 51,
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {
                            "dir_1_1_1": {
                                "filex": b"x" * 200,
                            },
                        },
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },
            ]
            input_list = []
            for data in test_data_list:
                digest = mock_cas_helper.append_directory(data)
                dir_ = mock_cas_helper.get_directory_by_digest(digest)
                input_list.append((digest, dir_))
            mock_cas_helper.set_data_exception(error_data, FakeIOError())
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root, mock_cas_helper, filesystem, copy_file=False
            )
            builder.init()
            for digest, dir_ in input_list:
                try:
                    builder.build(digest, dir_, local_root)
                except FakeIOError:
                    pass
                total_size_bytes = _get_directory_size_inode(cache_root)
                assert total_size_bytes == builder.current_size_bytes

    def test_current_size_bytes_after_evict(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            test_data_list = [
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"x" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_3": b"x" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "dir_x": {
                        "dir_1_1": {"file_1_1_1": b"o" * 15},
                        "dir_1_2": {"file_1_2_1": b"z" * 5},
                    },
                },  # size_bytes: 20
            ]
            input_list = []
            for data in test_data_list:
                digest = mock_cas_helper.append_directory(data)
                dir_ = mock_cas_helper.get_directory_by_digest(digest)
                input_list.append((digest, dir_))
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root,
                mock_cas_helper,
                filesystem,
                copy_file=False,
                max_cache_size_bytes=60,
            )
            builder.init()
            for i in [0, 1, 2, 3, 4, 3, 2, 1, 2, 3, 0, 4, 4, 0, 1, 2]:
                digest, dir_ = input_list[i]
                builder.build(digest, dir_, local_root)
                total_size_bytes = _get_directory_size_inode(cache_root)
                assert total_size_bytes == builder.current_size_bytes

    def test_evict_directory(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            test_data_list = [
                {
                    "file_1": b"a" * 100,
                    "file_2": b"b" * 20,
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"c" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "dir_1": {
                        "file_1_1": b"c" * 5,
                        "file_1_2": b"x" * 5,
                        "dir_1_1": {"file_1_1_1": b"x" * 5},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_3": b"d" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "file_1": b"a" * 100,
                    "dir_1": {
                        "file_1_3": b"x" * 15,
                        "dir_1_1": {},
                        "dir_1_2": {"file_1_1_1": b"x" * 5},
                    },
                },  # size_bytes: 20
                {
                    "dir_x": {
                        "dir_1_1": {"file_1_1_1": b"o" * 15},
                        "dir_1_2": {"file_1_2_1": b"z" * 5},
                    },
                },  # size_bytes: 20
            ]
            input_list = []
            for data in test_data_list:
                digest = mock_cas_helper.append_directory(data)
                dir_ = mock_cas_helper.get_directory_by_digest(digest)
                input_list.append((digest, dir_))
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            builder = SharedTopLevelCachedDirectoryBuilder(
                cache_root,
                mock_cas_helper,
                filesystem,
                copy_file=False,
                max_cache_size_bytes=60,
            )
            builder.init()
            for i in [0, 1, 2]:
                digest, dir_ = input_list[i]
                builder.build(digest, dir_, local_root)
            for i in [0, 3, 4]:
                digest, dir_ = input_list[i]
                builder.build(digest, dir_, local_root)

            total_size_bytes = _get_directory_size_inode(cache_root)
            assert total_size_bytes == builder.current_size_bytes
            assert builder.current_size_bytes == 60
            for i in [1, 2]:
                digest = input_list[i][1].directories[0].digest
                p = os.path.join(
                    cache_root, "dir", f"{digest.hash}_{digest.size_bytes}"
                )
                assert not os.path.exists(p)
