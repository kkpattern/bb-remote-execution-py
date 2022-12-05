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
            signal.signal(signal.SIGBREAK, lambda s, f: graceful_shutdown())
            filesystem = LocalHardlinkFilesystem("tmp/cache")
            filesystem.init()
            for i in range(1):
                thread_main = WorkerThreadMain(
                    channel, cas_channel, filesystem, i
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
