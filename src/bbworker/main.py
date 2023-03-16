import sys
import typing

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
from .metrics import MeterBase
from .filesystem import LocalHardlinkFilesystem
from .thread import WorkerThreadMain


MAX_MESSAGE_LENGTH = 16 * 1024 * 1024


class WorkerMain:
    def __init__(self, config_path: str):
        self._config_path = config_path
        self._worker_threads: typing.List[WorkerThreadMain] = []

    def run(self) -> None:
        self._worker_threads = []

        with open(self._config_path, "r") as f:
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

        meter: MeterBase
        if config.open_telemetry:
            from prometheus_client import start_http_server
            from .metrics import create_meter

            start_http_server(
                addr=config.open_telemetry.http_host,
                port=config.open_telemetry.http_port,
            )

            meter = create_meter()
        else:
            from .metrics import create_dummy_meter

            meter = create_dummy_meter()
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
            fsconfig = config.filesystem
            filesystem = LocalHardlinkFilesystem(
                fsconfig.cache_root,
                meter,
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
                meter,
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
                    meter,
                )
                thread_main.start()
                self._worker_threads.append(thread_main)
            # On Windows platform, join will total block main thread. We need
            # signal handler to worker so we use timeout here.
            while True:
                for t in self._worker_threads:
                    t.join(timeout=1)
                any_alived = False
                for t in self._worker_threads:
                    if t.is_alive():
                        any_alived = True
                        break
                if not any_alived:
                    break

    def graceful_shutdown(self):
        print("Ready to gracefully shutdown")
        # TODO(gzzhangkai2014): prevent signal sent to subprocess.
        for t in self._worker_threads:
            t.graceful_shutdown()
