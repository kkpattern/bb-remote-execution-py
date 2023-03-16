from __future__ import annotations

import os
import sys
import typing


if sys.platform == "win32":

    class FileCacheInfo(object):
        """Some hand selected attributes for testing if a file is changed."""

        def __init__(self, file_stat: os.stat_result):
            # TODO: st_mode will change on windows?
            # self.st_mode = file_stat.st_mode
            self.st_mtime = file_stat.st_mtime
            self.st_ctime = file_stat.st_ctime
            self.st_uid = file_stat.st_uid
            self.st_gid = file_stat.st_gid
            self.st_size = file_stat.st_size

        def match(self, file_stat):
            return (
                self.st_mtime == file_stat.st_mtime
                and self.st_ctime == file_stat.st_ctime
                and self.st_uid == file_stat.st_uid
                and self.st_gid == file_stat.st_gid
                and self.st_size == file_stat.st_size
            )

else:

    class FileCacheInfo(object):
        """Some hand selected attributes for testing if a file is changed."""

        def __init__(self, file_stat: os.stat_result):
            self.st_mode = file_stat.st_mode
            self.st_mtime = file_stat.st_mtime
            self.st_uid = file_stat.st_uid
            self.st_gid = file_stat.st_gid
            self.st_size = file_stat.st_size

        def match(self, file_stat):
            return (
                self.st_mode == file_stat.st_mode
                and self.st_mtime == file_stat.st_mtime
                and self.st_mode == file_stat.st_mode
                and self.st_uid == file_stat.st_uid
                and self.st_gid == file_stat.st_gid
                and self.st_size == file_stat.st_size
            )


class DirectoryCacheInfo(object):
    def __init__(
        self,
        file_info: typing.Dict[str, FileCacheInfo],
        dir_info: typing.Dict[str, DirectoryCacheInfo],
    ):
        self.file_info = file_info
        self.dir_info = dir_info
