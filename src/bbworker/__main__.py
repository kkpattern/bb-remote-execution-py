import signal
import sys

import grpc
from google.bytestream.bytestream_pb2_grpc import ByteStreamStub
from build.bazel.remote.execution.v2.remote_execution_pb2_grpc import (
    ContentAddressableStorageStub,
)

from .cas import CASHelper
from .directorybuilder import SharedTopLevelCachedDirectoryBuilder
from .filesystem import LocalHardlinkFilesystem
from .thread import WorkerThreadMain


MAX_MESSAGE_LENGTH = 16 * 1024 * 1024


def main():
    with (
        grpc.insecure_channel(
            "10.212.214.123:8983",
            options=[
                ("grpc.max_send_message_length", MAX_MESSAGE_LENGTH),
                ("grpc.max_receive_message_length", MAX_MESSAGE_LENGTH),
            ],
        ) as channel,
        grpc.insecure_channel(
            "10.212.214.130:8980",
            options=[
                ("grpc.max_send_message_length", MAX_MESSAGE_LENGTH),
                ("grpc.max_receive_message_length", MAX_MESSAGE_LENGTH),
            ],
        ) as cas_channel,
    ):
        worker_threads = []

        def graceful_shutdown():
            print("Ready to gracefully shutdown")
            # TODO(gzzhangkai2014): prevent signal sent to subprocess.
            for t in worker_threads:
                t.graceful_shutdown()

        signal.signal(signal.SIGINT, lambda s, f: graceful_shutdown())
        signal.signal(signal.SIGTERM, lambda s, f: graceful_shutdown())
        if sys.platform == "win32":
            signal.signal(signal.SIGBREAK, lambda s, f: graceful_shutdown())

        filesystem = LocalHardlinkFilesystem("tmp/file_cache")
        filesystem.init()

        cas_stub = ContentAddressableStorageStub(cas_channel)
        cas_byte_stream_stub = ByteStreamStub(cas_channel)
        cas_helper = CASHelper(cas_stub, cas_byte_stream_stub)

        directory_builder = SharedTopLevelCachedDirectoryBuilder(
            "tmp/dir_cache",
            cas_helper,
            filesystem,
        )
        directory_builder.init()
        for i in range(10):
            thread_main = WorkerThreadMain(
                channel, cas_channel, filesystem, directory_builder, i
            )
            thread_main.start()
            worker_threads.append(thread_main)
        # On Windows platform, join will total block main thread. We need
        # signal handler to worker so we use timeout here.
        while True:
            for t in worker_threads:
                t.join(timeout=1)
            any_alived = False
            for t in worker_threads:
                if t.is_alive():
                    any_alived = True
                    break
            if not any_alived:
                break


if __name__ == "__main__":
    main()
