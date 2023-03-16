import concurrent.futures
import time

from worker.lock import VariableLock


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
