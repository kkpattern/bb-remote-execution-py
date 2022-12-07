import os.path
import sys
import tempfile

from worker.util import link_file


if sys.platform == "win32":

    def test_link_file_more_than_1024_limit():
        with tempfile.TemporaryDirectory() as dir_:
            source_file = os.path.join(dir_, "source")
            with open(source_file, "wb") as f:
                f.write(b"abcd")
            for i in range(3000):
                link_file(source_file, os.path.join(dir_, f"target_{i}"))
