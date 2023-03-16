import os
import os.path
import stat
import shutil
import sys
import tempfile
import typing

from build.bazel.remote.execution.v2.remote_execution_pb2 import Digest


def digest_to_key(digest: typing.Optional[Digest]):
    if digest:
        key = (digest.hash, digest.size_bytes)
    else:
        key = None
    return key


def setup_xcode_env(env: typing.Dict[str, str]):
    if "XCODE_VERSION_OVERRIDE" in env:
        xcode_version = env["XCODE_VERSION_OVERRIDE"].rsplit(".", 1)[0]
        developer_dir = (
            "/Applications/Xcode-{0}.app/Contents/Developer/"
        ).format(xcode_version)
        if os.path.isdir(developer_dir):
            env["DEVELOPER_DIR"] = developer_dir
            if "APPLE_SDK_PLATFORM" in env:
                apple_sdk_version_override = env.get(
                    "APPLE_SDK_VERSION_OVERRIDE", ""
                )
                sdk_root = "{developer_dir}Platforms/{apple_sdk_platform}.platform/Developer/SDKs/{apple_sdk_platform}{apple_sdk_version_override}.sdk".format(  # noqa: E501
                    developer_dir=developer_dir,
                    apple_sdk_platform=env["APPLE_SDK_PLATFORM"],
                    apple_sdk_version_override=apple_sdk_version_override,
                )
                env["SDKROOT"] = sdk_root


def set_read_only(target: str):
    os.chmod(target, stat.S_IRUSR)


def set_read_exec_only(target: str):
    os.chmod(target, stat.S_IRUSR | stat.S_IXUSR)


if sys.platform == "win32":
    import _winapi

    def link_file(source: str, target: str):
        try:
            os.link(source, target)
        except OSError as e:
            if e.winerror == 1142:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_p = os.path.join(tmp_dir, os.path.basename(source))
                    shutil.copy2(source, tmp_p)
                    unlink_file(source)
                    shutil.copy2(tmp_p, source)
                    os.link(source, target)

    def unlink_file(target: str):
        os.unlink(target)

    def unlink_readonly_file(target: str):
        # need to set IWUSR before remove.
        os.chmod(target, stat.S_IWUSR)
        os.unlink(target)

    def rmtree(target: str):
        shutil.rmtree(target)

    def rmtree_with_readonly_files(target: str):
        for dir_, dirnames, filenames in os.walk(target):
            for n in filenames:
                os.chmod(os.path.join(dir_, n), stat.S_IWUSR)
        shutil.rmtree(target)

    def create_dir_link(source: str, target: str):
        _winapi.CreateJunction(source, target)

    def remove_dir_link(target: str):
        os.remove(target)

else:

    def link_file(source: str, target: str):
        os.link(source, target)

    def unlink_file(target: str):
        os.unlink(target)

    def unlink_readonly_file(target: str):
        os.unlink(target)

    def rmtree(target: str):
        shutil.rmtree(target)

    def rmtree_with_readonly_files(target: str):
        shutil.rmtree(target)

    def create_dir_link(source: str, target: str):
        os.symlink(os.path.abspath(source), os.path.abspath(target))

    def remove_dir_link(target: str):
        os.unlink(target)
