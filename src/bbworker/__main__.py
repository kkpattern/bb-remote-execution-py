import argparse
import signal
import sys

from .main import WorkerMain


MAX_MESSAGE_LENGTH = 16 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    worker_main = WorkerMain(args.config_file)
    signal.signal(signal.SIGINT, lambda s, f: worker_main.graceful_shutdown())
    signal.signal(signal.SIGTERM, lambda s, f: worker_main.graceful_shutdown())
    if sys.platform == "win32":
        signal.signal(
            signal.SIGBREAK, lambda s, f: worker_main.graceful_shutdown()
        )
    worker_main.run()


if __name__ == "__main__":
    main()
