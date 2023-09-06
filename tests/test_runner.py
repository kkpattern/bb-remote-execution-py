import locale

from bbworker.runner import fix_showincludes
from bbworker.runner import reencoding_output


class TestFixShowIncludes:
    def test_fix_showincludes_en(self):
        output = (
            "Note: including file:    G:\\temp\\engine\\world.h\n"
            "Note: including file:    G:\\temp\\engine\\world2.h\n"
            "Note: including file:    C:\\Windows\\system.h\n"
            "Note: including file:    G:\\temp\\engine\\common\\common.h\n"
            "Note: including file:    C:\\Windows\\system2.h"
        ).encode("utf-8")
        fixed_output = fix_showincludes(output, "G:/temp")
        assert fixed_output == (
            b"Note: including file: engine\\world.h\n"
            b"Note: including file: engine\\world2.h\n"
            b"Note: including file:    C:\\Windows\\system.h\n"
            b"Note: including file: engine\\common\\common.h\n"
            b"Note: including file:    C:\\Windows\\system2.h"
        )

    def test_fix_showincludes_zh(self):
        output = (
            "注意: 包含文件:    G:\\temp\\engine\\world.h\n"
            "注意: 包含文件:    G:\\temp\\engine\\common\\common.h\n"
            "注意: 包含文件:    C:\\Windows\\system.h"
        ).encode("utf-8")
        fixed_output = fix_showincludes(output, "G:/temp")
        assert fixed_output == (
            b"\xe6\xb3\xa8\xe6\x84\x8f: \xe5\x8c\x85\xe5\x90\xab\xe6\x96\x87\xe4\xbb\xb6: engine\\world.h\n"
            b"\xe6\xb3\xa8\xe6\x84\x8f: \xe5\x8c\x85\xe5\x90\xab\xe6\x96\x87\xe4\xbb\xb6: engine\\common\\common.h\n"
            b"\xe6\xb3\xa8\xe6\x84\x8f: \xe5\x8c\x85\xe5\x90\xab\xe6\x96\x87\xe4\xbb\xb6:    C:\\Windows\\system.h"
        )

    def test_fix_showincludes_normalize_path(self):
        output = (
            "Note: including file:    G:\\temp\\engine\\world.h\n"
            "Note: including file:    G:\\temp/engine/common\\common.h\n"
            "Note: including file:    C:\\Windows\\system.h"
        ).encode("utf-8")
        fixed_output = fix_showincludes(output, "G:/temp")
        assert fixed_output == (
            b"Note: including file: engine\\world.h\n"
            b"Note: including file: engine\\common\\common.h\n"
            b"Note: including file:    C:\\Windows\\system.h"
        )

    def test_fix_showincludes_non_utf8(self):
        output = (
            "注意: 包含文件:    G:\\temp\\engine\\world.h\n"
            "注意: 包含文件:    G:\\temp/engine/common\\common.h\n"
            "注意: 包含文件:    C:\\Windows\\system.h"
        ).encode("cp936")
        fixed_output = fix_showincludes(output, "G:/temp")
        assert fixed_output == output


class TestReencodingOutput:
    def test_reencoding_output_local(self):
        local_encoding = locale.getpreferredencoding()
        output = "注意: 包含文件:    G:\\temp".encode(local_encoding)
        assert output.decode(local_encoding).encode(
            "utf-8"
        ) == reencoding_output(output)

    def test_reencoding_output_utf8(self):
        output = "注意: 包含文件:    G:\\temp".encode("utf-8")
        assert output == reencoding_output(output)

    def test_reencoding_output_other(self):
        output = "注意: 包含文件:    G:\\temp".encode("utf-16")
        assert output == reencoding_output(output)
