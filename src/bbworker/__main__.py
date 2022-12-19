import argparse
import signal
import sys

import grpc
from google.bytestream.bytestream_pb2_grpc import ByteStreamStub
from build.bazel.remote.execution.v2.remote_execution_pb2_grpc import (
    ContentAddressableStorageStub,
)
import pydantic
import yaml

from .cas import CASHelper
from .config import Config
from .directorybuilder import SharedTopLevelCachedDirectoryBuilder
from .filesystem import LocalHardlinkFilesystem
from .thread import WorkerThreadMain


MAX_MESSAGE_LENGTH = 16 * 1024 * 1024


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")
    return parser.parse_args()


def main():
    args = parse_args()

    with open(args.config_file, "r") as f:
        data = yaml.load(f.read(), Loader=yaml.Loader)
    try:
        config = Config.parse_obj(data)
    except pydantic.error_wrappers.ValidationError as e:
        sys.stderr.write(f"{e}\n")
        sys.exit(1)

    if config.sentry:
        import sentry_sdk

        sentry_sdk.init(
            config.sentry.address,
            traces_sample_rate=config.sentry.traces_sample_rate,
        )

    with (
        grpc.insecure_channel(
            config.buildbarn.scheduler_address,
            options=[
                ("grpc.max_send_message_length", MAX_MESSAGE_LENGTH),
                ("grpc.max_receive_message_length", MAX_MESSAGE_LENGTH),
            ],
        ) as channel,
        grpc.insecure_channel(
            config.buildbarn.cas_address,
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

        fsconfig = config.filesystem
        filesystem = LocalHardlinkFilesystem(
            fsconfig.cache_root,
            max_cache_size_bytes=fsconfig.max_cache_size_bytes,
            concurrency=fsconfig.concurrency,
            download_batch_size_bytes=fsconfig.download_batch_size_bytes,
        )
        filesystem.init()

        cas_stub = ContentAddressableStorageStub(cas_channel)
        cas_byte_stream_stub = ByteStreamStub(cas_channel)
        cas_helper = CASHelper(cas_stub, cas_byte_stream_stub)

        builder_config = config.build_directory_builder
        directory_builder = SharedTopLevelCachedDirectoryBuilder(
            builder_config.cache_root,
            cas_helper,
            filesystem,
            max_cache_size_bytes=builder_config.max_cache_size_bytes,
            concurrency=builder_config.concurrency,
        )
        directory_builder.init()
        for i in range(config.concurrency):
            thread_main = WorkerThreadMain(
                channel,
                cas_channel,
                config.platform,
                config.worker_id,
                filesystem,
                directory_builder,
                config.build_root,
                i,
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
