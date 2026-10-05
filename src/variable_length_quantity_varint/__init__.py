"""Variable Length Quantity Varint — LEB128 encoding for non-negative integers."""

from .core import encode, decode, encode_unsigned, decode_unsigned, EncodeError, DecodeError

__all__ = [
    "encode",
    "decode",
    "encode_unsigned",
    "decode_unsigned",
    "EncodeError",
    "DecodeError",
]
