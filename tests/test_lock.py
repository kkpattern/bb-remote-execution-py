import concurrent.futures
import random
import time

from bbworker.lock import VariableLock


class _Expected(Exception):
    pass


class TestVariableLock(object):
    def test_lock(self):
        lock = VariableLock()
        test_dict = {"a": {}, "b": {}, 1: {}}

        def _test_lock(var):
            with lock.lock(var):
                assert not test_dict[var]
                start_at = time.time()
                i = 0
                while True:
                    test_dict[var][i] = True
                    i += 1
                    if (time.time() - start_at) > 0.1:
                        break
                assert len(test_dict[var]) == i
                test_dict[var].clear()

        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            futures = []
            for i in range(10):
                futures.append(executor.submit(_test_lock, "a"))
                futures.append(executor.submit(_test_lock, "b"))
                futures.append(executor.submit(_test_lock, 1))
            for f in futures:
                f.result()

    def test_lock_with_exception(self):
        lock = VariableLock()
        test_dict = {"a": {}, "b": {}, 1: {}}

        def _test_lock(var):
            try:
                with lock.lock(var):
                    try:
                        assert not test_dict[var]
                        start_at = time.time()
                        i = 0
                        while True:
                            test_dict[var][i] = True
                            i += 1
                            if (time.time() - start_at) > 0.1:
                                # do NOT block main thread.
                                if random.random() < 0.5:
                                    raise _Expected("Unlucky")
                                break
                        assert len(test_dict[var]) == i
                    finally:
                        test_dict[var].clear()
            except Exception:
                pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            futures = []
            for i in range(10):
                futures.append(executor.submit(_test_lock, "a"))
                futures.append(executor.submit(_test_lock, "b"))
                futures.append(executor.submit(_test_lock, 1))
            start_at = time.time()
            while True:
                all_done = True
                for f in futures:
                    if not f.done():
                        all_done = False
                        break
                if all_done:
                    break
                elif (time.time() - start_at) > 5:
                    all_done = False
                    break
            assert all_done
