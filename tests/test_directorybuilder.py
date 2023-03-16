import os
import os.path
import stat
import sys
import tempfile

import pytest

from worker.directorybuilder import TopLevelCachedDirectoryBuilder
from worker.filesystem import LocalHardlinkFilesystem

from worker.util import unlink_readonly_file


def _assert_directory(dir_data, dir_path: str):
    assert sorted(os.listdir(dir_path)) == sorted(dir_data)
    for k, v in dir_data.items():
        if isinstance(v, bytes):
            p = os.path.join(dir_path, k)
            assert os.path.isfile(p)
            with open(p, "rb") as f:
                assert f.read() == v
        elif isinstance(v, dict):
            _assert_directory(v, os.path.join(dir_path, k))


class TestTopLevelCachedDirectoryBuilder(object):
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
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)

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
            builder = TopLevelCachedDirectoryBuilder(
                local_root,
                cache_root,
                mock_cas_helper,
                filesystem,
                skip_cache=["dir_2", "dir_3"],
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)
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
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory)
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
                builder = TopLevelCachedDirectoryBuilder(
                    local_root, cache_root, mock_cas_helper, filesystem
                )
                builder.init()
                builder.build(input_root_digest, input_root_directory)
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
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            for i, d in enumerate(input_root_digest_list):
                builder.build(d, input_root_directory_list[i])
                _assert_directory(input_root_data_list[i], local_root)
            cached_dirs = sorted(os.listdir(cache_root))
            # simulate process restart.
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
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
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            for i, d in enumerate(input_root_digest_list):
                builder.build(d, input_root_directory_list[i])
                _assert_directory(input_root_data_list[i], local_root)
            for name in os.listdir(filesystem_root):
                p = os.path.join(filesystem_root, name)
                assert not os.stat(p).st_mode & stat.S_IWUSR

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
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)
            # Test dir mode changed.
            for name in os.listdir(cache_root):
                p = os.path.join(cache_root, name)
                if os.path.isdir(p):
                    os.chmod(p, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
            # simulate process restart.
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert not sorted(os.listdir(cache_root))
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)
            # Test file mode changed.
            for dir_, dirnames, filenames in os.walk(cache_root):
                for name in filenames:
                    p = os.path.join(dir_, name)
                    os.chmod(p, stat.S_IWUSR | stat.S_IRUSR)
            # simulate process restart.
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert not sorted(os.listdir(cache_root))
            builder.build(input_root_digest, input_root_directory)
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
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)
            for name in os.listdir(cache_root):
                p = os.path.join(cache_root, name)
                if os.path.isdir(p):
                    os.chmod(p, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
                    with open(os.path.join(p, "new.txt"), "wb") as f:
                        f.write(b"testdata")
                    os.chmod(p, stat.S_IRUSR | stat.S_IXUSR)
            # simulate process restart.
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert not sorted(os.listdir(cache_root))
            builder.build(input_root_digest, input_root_directory)
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
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)
            for dir_, dirnames, filenames in os.walk(cache_root):
                for name in filenames:
                    p = os.path.join(dir_, name)
                    origin_mode = os.stat(p).st_mode
                    os.chmod(p, origin_mode | stat.S_IWUSR)
                    with open(p, "wb") as f:
                        f.write(b"testoverride")
                    os.chmod(p, origin_mode)
            # simulate process restart.
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert not sorted(os.listdir(cache_root))
            builder.build(input_root_digest, input_root_directory)
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
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)
            cached_dirs = sorted(os.listdir(cache_root))
            # simulate process restart.
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
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
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)
            for dir_, dirnames, filenames in os.walk(cache_root):
                for name in filenames:
                    p = os.path.join(dir_, name)
                    os.chmod(dir_, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
                    unlink_readonly_file(p)
                    os.chmod(dir_, stat.S_IRUSR | stat.S_IXUSR)
            # simulate process restart.
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.init()
            assert not sorted(os.listdir(cache_root))
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)

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
            builder_1 = TopLevelCachedDirectoryBuilder(
                local_root_1, cache_root_1, mock_cas_helper, filesystem
            )
            builder_2 = TopLevelCachedDirectoryBuilder(
                local_root_2, cache_root_2, mock_cas_helper, filesystem
            )
            builder_1.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root_1)

            builder_2.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root_2)

            def should_not_call(*args, **kargs):
                assert (
                    False
                ), "should not call filesystem.fetch_to when dir is cached."

            filesystem.fetch_to = should_not_call
            builder_1.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root_1)
            builder_2.build(input_root_digest, input_root_directory)
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
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)

    def test_build_clear(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as local_root,
            tempfile.TemporaryDirectory() as cache_root,
        ):
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )

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
                builder.build(input_root_digest, input_root_directory)
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
            builder = TopLevelCachedDirectoryBuilder(
                local_root, cache_root, mock_cas_helper, filesystem
            )
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)
            # create a output directory.
            os.makedirs(os.path.join(local_root, "bazel-out"))
            # build directory again.
            builder.build(input_root_digest, input_root_directory)
            _assert_directory(input_root_data, local_root)
