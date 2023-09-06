import argparse
import os
import urllib.request
import subprocess
import sys
import time


CONFIG_TEMPLATE = """
buildbarn:
  cas_address: "{cas_address}"
  scheduler_address: "{scheduler_address}"
platform:
  properties:
    - name: "host_os"
      value: "windows"
worker_id:
  node: "{node_name}"
filesystem:
  cache_root: "tmp/file_cache"
  max_cache_size_bytes: "{max_file_cache_size_bytes}"
build_directory_builder:
  cache_root: "tmp/dir_cache"
  max_cache_size_bytes: "{max_dir_cache_size_bytes}"
build_root: "tmp/build"
concurrency: {concurrency}
sentry:
  address: "{sentry_address}"
  traces_sample_rate: 0.1
"""


CAS_ADDRESS = "10.212.214.49:8980"
SCHEDULER_ADDRESS = "10.212.214.131:8983"
SENTRY_ADDRESS = (
    "http://ebf11e59bd7a420d80aab9377c6c7d52@42.186.242.93:9000/20"
)


DOWNLOAD_URL = "https://gzdev2-echoes-assets.s3dev-gz.nie.netease.com/bbworker_service-{0}"

REQUIRED_TMP = "C:\\temp"
MSVC_PATH = "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Tools\\MSVC\\14.29.30133"


BBWORKER_EXE_NAME = "bbworker_service.exe"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("version", nargs="?", default="latest")
    parser.add_argument("--name", default=os.getlogin())
    parser.add_argument("--concurrency", default=3)
    parser.add_argument("--max-file-cache-size-bytes", default="3G")
    parser.add_argument("--max-dir-cache-size-bytes", default="3G")
    return parser.parse_args()


def write_config(
    node_name, concurrency, max_file_cache_size_bytes, max_dir_cache_size_bytes
):
    with open("bbworker_service.yaml", "w") as f:
        f.write(
            CONFIG_TEMPLATE.format(
                cas_address=CAS_ADDRESS,
                scheduler_address=SCHEDULER_ADDRESS,
                node_name=node_name,
                concurrency=concurrency,
                max_file_cache_size_bytes=max_file_cache_size_bytes,
                max_dir_cache_size_bytes=max_dir_cache_size_bytes,
                sentry_address=SENTRY_ADDRESS,
            ).lstrip()
        )


def main():
    args = parse_args()
    if not os.path.isdir(REQUIRED_TMP):
        print(f"请先创建{REQUIRED_TMP}目录")
        sys.exit(1)
    if not os.path.isdir(MSVC_PATH):
        print(f"未找到依赖的MSVC目录: {MSVC_PATH}")
        sys.exit(2)
    download_url = DOWNLOAD_URL.format(args.version)
    tmp_bbworker_exe = "bbworker_service.exe.tmp"
    if os.path.exists(BBWORKER_EXE_NAME):
        subprocess.call([BBWORKER_EXE_NAME, "stop"])
        subprocess.call([BBWORKER_EXE_NAME, "remove"])
        service_name = subprocess.check_output(
            [BBWORKER_EXE_NAME, "name"]
        ).strip()
        max_wait = 60
        for i in range(max_wait):
            try:
                service_info = subprocess.check_output(
                    ["sc.exe", "queryex", service_name]
                )
            except subprocess.CalledProcessError as e:
                if int(e.returncode) == 1060:
                    pass
                else:
                    raise
            else:
                pid = 0
                for line in service_info.splitlines():
                    if b"PID" in line:
                        pid = int(line.split(b":")[-1])
                if pid != 0:
                    if i < max_wait - 1:
                        print("Wait bbworker process to exit.")
                        time.sleep(2)
                    else:
                        print("Force kill bbworker process:", pid)
                        subprocess.call(["taskkill", "/PID", str(pid), "/F"])
    try:
        with open(tmp_bbworker_exe, "wb") as f:
            response = urllib.request.urlopen(download_url)
            f.write(response.read())
        if os.path.exists(BBWORKER_EXE_NAME):
            os.unlink(BBWORKER_EXE_NAME)
        os.rename(tmp_bbworker_exe, BBWORKER_EXE_NAME)
    finally:
        if os.path.exists(tmp_bbworker_exe):
            os.unlink(tmp_bbworker_exe)
    write_config(
        args.name,
        args.concurrency,
        args.max_file_cache_size_bytes,
        args.max_dir_cache_size_bytes,
    )
    subprocess.check_call([BBWORKER_EXE_NAME, "--startup", "auto", "install"])
    subprocess.check_call([BBWORKER_EXE_NAME, "start"])


if __name__ == "__main__":
    main()
