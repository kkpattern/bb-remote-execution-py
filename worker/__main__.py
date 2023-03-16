import signal

import grpc

from .filesystem import LocalHardlinkFilesystem
from .thread import WorkerThreadMain


MAX_MESSAGE_LENGTH = 16 * 1024 * 1024


def main():
    with grpc.insecure_channel("10.212.214.123:8983") as channel:
        with grpc.insecure_channel(
            "10.212.214.130:8980",
            options=[
                ("grpc.max_send_message_length", MAX_MESSAGE_LENGTH),
                ("grpc.max_receive_message_length", MAX_MESSAGE_LENGTH),
            ],
        ) as cas_channel:
            worker_threads = []

            def graceful_shutdown():
                print("Ready to gracefully shutdown")
                # TODO(gzzhangkai2014): prevent signal sent to subprocess.
                for t in worker_threads:
                    t.graceful_shutdown()

            signal.signal(signal.SIGINT, lambda s, f: graceful_shutdown())
            signal.signal(signal.SIGTERM, lambda s, f: graceful_shutdown())
            filesystem = LocalHardlinkFilesystem("tmp/cache")
            for i in range(5):
                thread_main = WorkerThreadMain(
                    channel, cas_channel, filesystem, i
                )
                thread_main.start()
                worker_threads.append(thread_main)
            for t in worker_threads:
                t.join()


if __name__ == "__main__":
    main()
