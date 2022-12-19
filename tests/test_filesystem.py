import concurrent.futures
import os
import os.path
import random
import stat
import tempfile
import threading
import time
import uuid

import pytest

from bbworker.filesystem import LocalHardlinkFilesystem
from bbworker.filesystem import MaxSizeReached
from bbworker.util import set_read_only
from bbworker.util import unlink_readonly_file


class FakeIOError(Exception):
    pass


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
            mock_cas_helper.set_seconds_per_byte(0.001)
            test_data_list = []

            for i in range(500):
                test_data_list.append(
                    (f"file_{i}", (f"abcd{i}" * (i % 20 + 1)).encode())
                )

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
                part_n = 1000
                parts = [shuffled_list[i::part_n] for i in range(part_n)]
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

    def test_download_within_max_cache_size(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"x" * 100),
                ("file_2", b"y" * 200),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(
                filesystem_root, max_cache_size_bytes=300
            )
            filesystem.init()
            filesystem.fetch_to(
                mock_cas_helper, [i[0] for i in test_file_list], target_root
            )
            for fnode, data in test_file_list:
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert os.path.isfile(path_in_cache)
                with open(path_in_cache, "rb") as f:
                    assert f.read() == data

    def test_single_file_larger_than_max_cache_size(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"x" * 100),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(
                filesystem_root, max_cache_size_bytes=30
            )
            filesystem.init()
            with pytest.raises(MaxSizeReached):
                filesystem.fetch_to(
                    mock_cas_helper,
                    [i[0] for i in test_file_list],
                    target_root,
                )

    def test_multiple_files_larger_than_max_cache_size(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"x" * 100),
                ("file_2", b"y" * 100),
                ("file_3", b"z" * 50),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(
                filesystem_root,
                max_cache_size_bytes=249,
            )
            filesystem.init()
            with pytest.raises(MaxSizeReached):
                filesystem.fetch_to(
                    mock_cas_helper,
                    [i[0] for i in test_file_list],
                    target_root,
                )

    def test_multiple_files_with_same_content(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"x" * 100),
                ("file_2", b"x" * 100),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(
                filesystem_root,
                max_cache_size_bytes=100,
            )
            filesystem.init()
            filesystem.fetch_to(
                mock_cas_helper,
                [i[0] for i in test_file_list],
                target_root,
            )
            for fnode, data in test_file_list:
                p = os.path.join(target_root, fnode.name)
                assert os.path.isfile(p)
                with open(p, "rb") as f:
                    assert f.read() == data

    def test_evict_file(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"x" * 100),
                ("file_2", b"y" * 100),
                ("file_3", b"z" * 100),
                ("file_4", b"a" * 100),
                ("file_5", b"b" * 100),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(
                filesystem_root,
                max_cache_size_bytes=300,
            )
            filesystem.init()
            for i in [0, 1, 2]:
                filesystem.fetch_to(
                    mock_cas_helper,
                    [test_file_list[i][0]],
                    target_root,
                )
            for i in [0, 3, 4]:
                filesystem.fetch_to(
                    mock_cas_helper,
                    [test_file_list[i][0]],
                    target_root,
                )
            # all files exist in target dir.
            for i in [0, 1, 2, 3, 4]:
                fnode, data = test_file_list[i]
                p = os.path.join(target_root, fnode.name)
                assert os.path.isfile(p)
                with open(p, "rb") as f:
                    assert f.read() == data
            for i in [0, 3, 4]:
                fnode, data = test_file_list[i]
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert os.path.isfile(path_in_cache)
                with open(path_in_cache, "rb") as f:
                    assert f.read() == data
            for i in [1, 2]:
                fnode, data = test_file_list[i]
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert not os.path.exists(path_in_cache)

    def test_evict_multiple_files(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"a" * 210),
                ("file_2", b"b" * 200),
                ("file_3", b"c" * 140),
                ("file_4", b"d" * 130),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(
                filesystem_root,
                max_cache_size_bytes=420,
            )
            filesystem.init()
            for i in [[0, 1], [2, 3]]:
                filesystem.fetch_to(
                    mock_cas_helper,
                    [test_file_list[j][0] for j in i],
                    target_root,
                )
            # all files exist in target dir.
            for i in [0, 1, 2, 3]:
                fnode, data = test_file_list[i]
                p = os.path.join(target_root, fnode.name)
                assert os.path.isfile(p)
                with open(p, "rb") as f:
                    assert f.read() == data
            # only file 2 and 3 should exist in cache dir.
            for i in [2, 3]:
                fnode, data = test_file_list[i]
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert os.path.isfile(path_in_cache)
                with open(path_in_cache, "rb") as f:
                    assert f.read() == data
            # file 0, 1 should not exist in cache dir.
            for i in [0, 1]:
                fnode, data = test_file_list[i]
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert not os.path.exists(path_in_cache)

    def test_fetch_evicted_files_again(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"a" * 20),
                ("file_2", b"b" * 25),
                ("file_3", b"c" * 30),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(
                filesystem_root,
                max_cache_size_bytes=30,
            )
            filesystem.init()

            for k in range(5):
                for i in test_file_list:
                    filesystem.fetch_to(mock_cas_helper, [i[0]], target_root)
            for i in [2]:
                fnode, data = test_file_list[i]
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert os.path.isfile(path_in_cache)
                with open(path_in_cache, "rb") as f:
                    assert f.read() == data

    def test_shrink_max_cache_size_after_restart(self, mock_cas_helper):
        for i in range(5):
            with (
                tempfile.TemporaryDirectory() as filesystem_root,
                tempfile.TemporaryDirectory() as target_root,
            ):
                test_file_list = []
                for name, data in [
                    ("file_1", b"a" * 100),
                    ("file_2", b"b" * 100),
                    ("file_3", b"c" * 100),
                    ("file_4", b"d" * 100),
                    ("file_5", b"e" * 100),
                    ("file_6", b"f" * 100),
                    ("file_7", b"g" * 100),
                    ("file_8", b"h" * 100),
                ]:
                    test_file_list.append(
                        (mock_cas_helper.append_file(name, data), data)
                    )
                filesystem = LocalHardlinkFilesystem(
                    filesystem_root,
                    max_cache_size_bytes=800,
                )
                filesystem.init()
                filesystem.fetch_to(
                    mock_cas_helper,
                    [i[0] for i in test_file_list],
                    target_root,
                )
                for name in [
                    "file_2",
                    "file_1",
                    "file_3",
                    "file_4",
                    "file_7",
                    "file_6",
                    "file_8",
                    "file_5",
                ]:
                    time.sleep(0.1)  # make sure atime different.
                    os.utime(os.path.join(target_root, name))
                filesystem = LocalHardlinkFilesystem(
                    filesystem_root, max_cache_size_bytes=300
                )
                filesystem.init()
                for i in [1, 0, 2, 3, 6]:
                    fnode, data = test_file_list[i]
                    digest = fnode.digest
                    path_in_cache = os.path.join(
                        filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                    )
                    assert not os.path.exists(path_in_cache)
                for i in [5, 7, 4]:
                    fnode, data = test_file_list[i]
                    digest = fnode.digest
                    path_in_cache = os.path.join(
                        filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                    )
                    assert os.path.isfile(path_in_cache)
                    with open(path_in_cache, "rb") as f:
                        assert f.read() == data

    def test_reach_max_size_because_of_pending_files(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"a" * 100),
                ("file_2", b"b" * 100),
                ("file_3", b"c" * 100),
                ("file_4", b"d" * 100),
                ("file_5", b"e" * 100),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(
                filesystem_root,
                max_cache_size_bytes=300,
            )
            filesystem.init()
            mock_cas_helper.set_seconds_per_byte(0.002)

            def _fetch_in_another_thread():
                try:
                    filesystem.fetch_to(
                        mock_cas_helper,
                        [i[0] for i in test_file_list[:3]],
                        target_root,
                    )
                except Exception:
                    pass

            other_thread = threading.Thread(target=_fetch_in_another_thread)
            other_thread.start()

            time.sleep(0.1)

            try:
                with pytest.raises(MaxSizeReached):
                    filesystem.fetch_to(
                        mock_cas_helper,
                        [i[0] for i in test_file_list[3:5]],
                        target_root,
                    )
            finally:
                other_thread.join()

    def test_current_size_bytes(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"a" * 10),
                ("file_2", b"b" * 25),
                ("file_3", b"c" * 30),
                ("file_4", b"d" * 45),
                ("file_5", b"e" * 20),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(
                filesystem_root,
                max_cache_size_bytes=300,
            )
            filesystem.init()

            filesystem.fetch_to(
                mock_cas_helper,
                [i[0] for i in test_file_list],
                target_root,
            )
            total_size = 0
            for f in os.listdir(filesystem_root):
                total_size += os.stat(os.path.join(filesystem_root, f)).st_size
            assert total_size == filesystem.current_size_bytes

    def test_current_size_bytes_after_evict(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"a" * 10),
                ("file_2", b"b" * 25),
                ("file_3", b"c" * 30),
                ("file_4", b"d" * 45),
                ("file_5", b"e" * 20),
                ("file_6", b"f" * 20),
                ("file_7", b"g" * 2),
                ("file_8", b"h" * 30),
                # intentionally download twich.
                ("file_1", b"a" * 10),
                ("file_2", b"b" * 25),
                ("file_3", b"c" * 30),
                ("file_4", b"d" * 45),
                ("file_5", b"e" * 20),
                ("file_6", b"f" * 20),
                ("file_7", b"g" * 2),
                ("file_8", b"h" * 30),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(
                filesystem_root,
                max_cache_size_bytes=45,
            )
            filesystem.init()

            for i in test_file_list:
                filesystem.fetch_to(
                    mock_cas_helper,
                    [i[0]],
                    target_root,
                )
                total_size = 0
                for f in os.listdir(filesystem_root):
                    total_size += os.stat(
                        os.path.join(filesystem_root, f)
                    ).st_size
                assert total_size == filesystem.current_size_bytes

    def test_current_size_bytes_after_error(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            error_data = b"x" * 1
            for name, data in [
                ("file_1", b"a" * 10),
                ("file_2", b"b" * 25),
                ("file_3", b"c" * 30),
                ("file_4", b"d" * 45),
                ("file_5", b"e" * 20),
                ("file_6", b"f" * 20),
                ("file_7", b"g" * 2),
                ("file_8", b"h" * 30),
                # intentionally download twich.
                ("file_1", b"a" * 10),
                ("file_2", b"b" * 25),
                ("file_3", b"c" * 30),
                ("file_4", b"d" * 45),
                ("file_5", error_data),
                ("file_6", b"f" * 20),
                ("file_7", b"g" * 2),
                ("file_8", b"h" * 30),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            mock_cas_helper.set_data_exception(error_data, FakeIOError())
            filesystem = LocalHardlinkFilesystem(
                filesystem_root,
                max_cache_size_bytes=45,
            )
            filesystem.init()

            for i in test_file_list:
                try:
                    filesystem.fetch_to(
                        mock_cas_helper,
                        [i[0]],
                        target_root,
                    )
                except FakeIOError:
                    pass
                total_size = 0
                for f in os.listdir(filesystem_root):
                    total_size += os.stat(
                        os.path.join(filesystem_root, f)
                    ).st_size
                assert total_size == filesystem.current_size_bytes

    def test_file_missing(self, mock_cas_helper):
        with (
            tempfile.TemporaryDirectory() as filesystem_root,
            tempfile.TemporaryDirectory() as target_root,
        ):
            test_file_list = []
            for name, data in [
                ("file_1", b"x" * 100),
                ("file_2", b"y" * 200),
            ]:
                test_file_list.append(
                    (mock_cas_helper.append_file(name, data), data)
                )
            filesystem = LocalHardlinkFilesystem(
                filesystem_root, max_cache_size_bytes=300
            )
            filesystem.init()
            filesystem.fetch_to(
                mock_cas_helper, [i[0] for i in test_file_list], target_root
            )
            for fnode, data in test_file_list:
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert os.path.isfile(path_in_cache)
                with open(path_in_cache, "rb") as f:
                    assert f.read() == data
            for f in os.listdir(filesystem_root):
                unlink_readonly_file(os.path.join(filesystem_root, f))
            filesystem.fetch_to(
                mock_cas_helper, [i[0] for i in test_file_list], target_root
            )
            for fnode, data in test_file_list:
                digest = fnode.digest
                path_in_cache = os.path.join(
                    filesystem_root, f"{digest.hash}_{digest.size_bytes}"
                )
                assert os.path.isfile(path_in_cache)
                with open(path_in_cache, "rb") as f:
                    assert f.read() == data

    # TODO: disk IO error.
