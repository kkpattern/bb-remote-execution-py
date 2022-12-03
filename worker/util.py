import os.path
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
