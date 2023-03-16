import concurrent.futures
import os
import os.path
import random
import stat
import tempfile
import threading
import uuid

import pytest

from worker.filesystem import LocalHardlinkFilesystem
from worker.util import set_read_only


class TestLocalHardlinkFilesystem(object):
    def test_verify_file(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"acdeftest"),
                ("file_2", b"mxxi"),
                ("xx_file", b"xxxier"),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            filesystem.fetch_to(
                mock_cas_helper, [i[0] for i in test_file_list], target_root
            )
            # simulate process restart.
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            for fnode, data in test_file_list:
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert os.path.isfile(path_in_cache)
                with open(path_in_cache, "rb") as f:
                    assert f.read() == data

    def test_verify_file_remove_mode_change(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"acdeftest"),
                ("file_2", b"mxxi"),
                ("xx_file", b"xxxier"),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            filesystem.fetch_to(
                mock_cas_helper, [i[0] for i in test_file_list], target_root
            )
            path_in_target = os.path.join(target_root, "file_1")
            os.chmod(path_in_target, stat.S_IWRITE)
            # simulate process restart.
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            removed_fnode, _ = test_file_list.pop(0)
            removed_digest = removed_fnode.digest
            for fnode, data in test_file_list:
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert os.path.isfile(path_in_cache)
                with open(path_in_cache, "rb") as f:
                    assert f.read() == data
            assert not os.path.exists(
                os.path.join(
                    filesystem_root,
                    f"{removed_digest.hash}_{removed_digest.size_bytes}",
                )
            )

    def test_verify_file_remove_content_change(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"acdeftest"),
                ("file_2", b"mxxi"),
                ("xx_file", b"xxxier"),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            filesystem.fetch_to(
                mock_cas_helper, [i[0] for i in test_file_list], target_root
            )
            path_in_target = os.path.join(target_root, "file_1")
            os.chmod(path_in_target, stat.S_IWRITE)
            with open(path_in_target, "wb") as f:
                f.write(b"changeddata")
            set_read_only(path_in_target)
            # simulate process restart.
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            removed_fnode, _ = test_file_list.pop(0)
            removed_digest = removed_fnode.digest
            for fnode, data in test_file_list:
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert os.path.isfile(path_in_cache)
                with open(path_in_cache, "rb") as f:
                    assert f.read() == data
            assert not os.path.exists(
                os.path.join(
                    filesystem_root,
                    f"{removed_digest.hash}_{removed_digest.size_bytes}",
                )
            )

    def test_verify_file_remove_content_change_without_size_change(
        self, mock_cas_helper
    ):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"acdeftest"),
                ("file_2", b"mxxi"),
                ("xx_file", b"xxxier"),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            filesystem.fetch_to(
                mock_cas_helper, [i[0] for i in test_file_list], target_root
            )
            path_in_target = os.path.join(target_root, "file_1")
            os.chmod(path_in_target, stat.S_IWRITE)
            with open(path_in_target, "wb") as f:
                f.write(b"testacdef")
            set_read_only(path_in_target)
            # simulate process restart.
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            removed_fnode, _ = test_file_list.pop(0)
            removed_digest = removed_fnode.digest
            for fnode, data in test_file_list:
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert os.path.isfile(path_in_cache)
                with open(path_in_cache, "rb") as f:
                    assert f.read() == data
            assert not os.path.exists(
                os.path.join(
                    filesystem_root,
                    f"{removed_digest.hash}_{removed_digest.size_bytes}",
                )
            )

    def test_verify_large_file_content_change_without_size_change(
        self, mock_cas_helper
    ):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"x" * 10 * 1024 * 1024),
                ("file_2", b"mxxi"),
                ("xx_file", b"xxxier"),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            filesystem.fetch_to(
                mock_cas_helper, [i[0] for i in test_file_list], target_root
            )
            # make file_1 corrupt.
            path_in_target = os.path.join(target_root, "file_1")
            os.chmod(path_in_target, stat.S_IWRITE)
            with open(path_in_target, "wb") as f:
                f.write(b"y" * 10 * 1024 * 1024)
            set_read_only(path_in_target)
            # simulate process restart.
            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()
            removed_fnode, _ = test_file_list.pop(0)
            removed_digest = removed_fnode.digest
            for fnode, data in test_file_list:
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert os.path.isfile(path_in_cache)
                with open(path_in_cache, "rb") as f:
                    assert f.read() == data
            assert not os.path.exists(
                os.path.join(
                    filesystem_root,
                    f"{removed_digest.hash}_{removed_digest.size_bytes}",
                )
            )

    @pytest.mark.only_in_full_test
    def test_multithread(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_data_list = []
            for i in range(5000):
                test_data_list.append((f"file_{i}", b"abcd" * (i % 20 + 1)))

            test_file_list = []
            for name, data in test_data_list:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )

            filesystem = LocalHardlinkFilesystem(filesystem_root)
            filesystem.init()

            def _thread_run():
                thread_root = os.path.join(target_root, str(uuid.uuid4()))
                os.makedirs(thread_root)
                shuffled_list = list(test_file_list)
                random.shuffle(shuffled_list)
                part_size = 5
                parts = [shuffled_list[i::part_size] for i in range(part_size)]
                for p in parts:
                    filesystem.fetch_to(
                        mock_cas_helper,
                        [i[0] for i in p],
                        thread_root,
                    )
                    for fnode, data in p:
                        p = os.path.join(thread_root, fnode.name)
                        assert os.path.isfile(p)
                        assert not os.stat(p).st_mode & stat.S_IWUSR
                        with open(p, "rb") as f:
                            assert f.read() == data

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=10
            ) as executor:
                futures = []
                for i in range(10):
                    futures.append(executor.submit(_thread_run))
                for f in futures:
                    f.result()
