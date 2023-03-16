from bbworker.config import parse_size_bytes


class TestParseSizeBytes:
    def test_pure_number(self):
        assert 1 == parse_size_bytes(1)
        assert 1024 == parse_size_bytes(1024)

    def test_pure_number_str(self):
        assert 1 == parse_size_bytes("1")
        assert 1024 == parse_size_bytes("1024")

    def test_number_with_unit(self):
        assert 1 == parse_size_bytes("1b")
        assert 1 == parse_size_bytes("1B")
        assert 1024 == parse_size_bytes("1K")
        assert 1024 == parse_size_bytes("1k")
        assert 1024 == parse_size_bytes("1kb")
        assert 1024 == parse_size_bytes("1KB")
        assert 1024 == parse_size_bytes("1Kb")
        assert 2 * 1024 == parse_size_bytes("2K")
        assert 2 * 1024 == parse_size_bytes("2k")
        assert 2 * 1024 == parse_size_bytes("2kb")
        assert 2 * 1024 == parse_size_bytes("2KB")
        assert 2 * 1024 == parse_size_bytes("2Kb")
        assert 2 * 1024 == parse_size_bytes("2kB")
        assert 3 * 1024 * 1024 == parse_size_bytes("3M")
        assert 3 * 1024 * 1024 == parse_size_bytes("3m")
        assert 3 * 1024 * 1024 == parse_size_bytes("3mb")
        assert 3 * 1024 * 1024 == parse_size_bytes("3MB")
        assert 3 * 1024 * 1024 == parse_size_bytes("3Mb")
        assert 3 * 1024 * 1024 == parse_size_bytes("3mB")
        assert 4 * 1024 * 1024 * 1024 == parse_size_bytes("4G")
        assert 4 * 1024 * 1024 * 1024 == parse_size_bytes("4g")
        assert 4 * 1024 * 1024 * 1024 == parse_size_bytes("4gb")
        assert 4 * 1024 * 1024 * 1024 == parse_size_bytes("4GB")
        assert 4 * 1024 * 1024 * 1024 == parse_size_bytes("4Gb")
        assert 4 * 1024 * 1024 * 1024 == parse_size_bytes("4gB")
