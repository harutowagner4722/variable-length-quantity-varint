import unittest

from variable_length_quantity_varint import (
    encode,
    decode,
    encode_unsigned,
    decode_unsigned,
    EncodeError,
    DecodeError,
)


class TestEncode(unittest.TestCase):
    def test_zero_is_single_byte(self):
        self.assertEqual(encode(0), b"\x00")

    def test_single_byte_boundary(self):
        # 127 is the largest value that fits in one byte (0x7F, no continuation).
        self.assertEqual(encode(127), b"\x7f")

    def test_two_byte_transition(self):
        # 128 is the smallest value requiring two bytes.
        self.assertEqual(encode(128), b"\x80\x01")

    def test_known_values(self):
        cases = {
            300: b"\xac\x02",
            16384: b"\x80\x80\x01",
            624373: b"\xf5\x8d\x26",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(encode(value), expected)

    def test_max_64bit_round_trips(self):
        n = (1 << 64) - 1
        encoded = encode(n)
        # 64 bits / 7 bits-per-byte rounds up to 10 bytes.
        self.assertEqual(len(encoded), 10)
        self.assertEqual(decode(encoded)[0], n)

    def test_70_bit_ceiling_accepted(self):
        n = (1 << 70) - 1
        encoded = encode(n)
        self.assertEqual(decode(encoded)[0], n)

    def test_71_bit_rejected(self):
        with self.assertRaises(EncodeError):
            encode(1 << 70)

    def test_negative_rejected(self):
        with self.assertRaises(EncodeError):
            encode(-1)

    def test_bool_rejected(self):
        # bool is a subclass of int but is treated as a likely caller bug.
        with self.assertRaises(EncodeError):
            encode(True)

    def test_non_integer_rejected(self):
        with self.assertRaises(EncodeError):
            encode("128")
        with self.assertRaises(EncodeError):
            encode(1.5)

    def test_index_protocol_accepted(self):
        class FancyInt:
            def __init__(self, n):
                self._n = n
            def __index__(self):
                return self._n
        self.assertEqual(encode(FancyInt(300)), b"\xac\x02")


class TestDecode(unittest.TestCase):
    def test_round_trip_assorted(self):
        values = [0, 1, 127, 128, 300, 16383, 16384, 2**32, 2**63, (1 << 64) - 1]
        for v in values:
            encoded = encode(v)
            with self.subTest(value=v, encoded=encoded):
                decoded, consumed = decode(encoded)
                self.assertEqual(decoded, v)
                self.assertEqual(consumed, len(encoded))

    def test_decode_returns_int_value_and_int_length(self):
        value, length = decode(b"\xac\x02")
        self.assertIsInstance(value, int)
        self.assertIsInstance(length, int)
        self.assertEqual(value, 300)
        self.assertEqual(length, 2)

    def test_offset_skips_prefix(self):
        buf = b"\xff" + encode(300)
        value, consumed = decode(buf, offset=1)
        self.assertEqual(value, 300)
        self.assertEqual(consumed, 2)

    def test_offset_at_end_raises(self):
        with self.assertRaises(DecodeError):
            decode(b"\x80", offset=1)

    def test_truncated_raises(self):
        # 300 encodes as b'\xac\x02'; dropping the terminator leaves it dangling.
        with self.assertRaises(DecodeError):
            decode(b"\xac")

    def test_non_minimal_zero_raises(self):
        # 0 has the canonical encoding b'\x00'; b'\x80\x00' is a padded alias.
        with self.assertRaises(DecodeError):
            decode(b"\x80\x00")

    def test_non_minimal_leading_zero_raises(self):
        # 127 canonical is b'\x7f'; b'\xff\x00' pads it with a leading zero group.
        with self.assertRaises(DecodeError):
            decode(b"\xff\x00")

    def test_overlong_stream_raises(self):
        # 11 continuation bytes with no terminator: a hostile/truncated stream.
        with self.assertRaises(DecodeError):
            decode(b"\x80" * 11)

    def test_bytearray_accepted(self):
        value, _ = decode(bytearray(b"\xac\x02"))
        self.assertEqual(value, 300)

    def test_non_bytes_rejected(self):
        with self.assertRaises(DecodeError):
            decode("ac02")

    def test_negative_offset_rejected(self):
        with self.assertRaises(DecodeError):
            decode(b"\x00", offset=-1)

    def test_decodes_concatenated_stream_in_two_calls(self):
        # Two values packed back-to-back; decode should report exactly the
        # bytes it consumed so the caller can advance.
        stream = encode(300) + encode(0)
        v1, n1 = decode(stream, offset=0)
        v2, n2 = decode(stream, offset=n1)
        self.assertEqual((v1, v2), (300, 0))
        self.assertEqual(n1 + n2, len(stream))


class TestAliases(unittest.TestCase):
    def test_encode_alias_matches_encode_unsigned(self):
        self.assertIs(encode, encode_unsigned)

    def test_decode_alias_matches_decode_unsigned(self):
        self.assertIs(decode, decode_unsigned)


if __name__ == "__main__":
    unittest.main()
