import argparse
import logging
import os.path
import signal
import sys

from .main import WorkerMain


MAX_MESSAGE_LENGTH = 16 * 1024 * 1024


def _handle_exception(exc_type, exc_value, exc_traceback):
    logging.critical(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")
    parser.add_argument("--log-file", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    log_foramt = "%(asctime)s:%(levelname)s:%(message)s"
    if args.log_file:
        logging.basicConfig(
            filename=os.path.abspath(args.log_file),
            level=logging.INFO,
            format=log_foramt,
        )
    else:
        logging.basicConfig(level=logging.INFO, format=log_foramt)

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
