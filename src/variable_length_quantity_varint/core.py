"""LEB128 unsigned varint encoding and decoding.

This module implements unsigned LEB128 (Little-Endian Base 128), the same
scheme used by Protobuf, DWARF, and WebAssembly. Each byte carries seven
payload bits in its low bits and a continuation flag in the high bit. The
least-significant group comes first, hence "little-endian".

Design choices, stated plainly so the tests cannot drift away from them:

- Non-negative integers only. A caller who needs signed support must zig-zag
  themselves before calling here. Mixing the two would inflate the API and
  invite conflicting ordering rules, so it is deliberately out of scope.
- ``encode`` accepts ``int`` (and any value that quacks like one via
  ``__index__``) and returns ``bytes``. It rejects negative integers and
  non-integers explicitly rather than producing a silently wrong stream.
- ``decode`` accepts ``bytes`` or ``bytearray`` and returns ``(int, int)`` —
  the value and the number of bytes consumed. Returning both lets a caller
  resume parsing from the right offset without re-scanning. A stream-style
  API that mutated a cursor would be more convenient but would force a stateful
  object; this keeps the functions pure.
- Decoding rejects leading zero groups (the canonical non-minimal encoding)
  and enforces a 10-byte ceiling so a truncated or hostile stream cannot make
  the decoder allocate an unbounded number of bytes. 10 bytes can hold every
  64-bit value with room to spare; anything longer has no legitimate use.
"""

from __future__ import annotations

from typing import Tuple


_MAX_BYTES = 10
# A 10-byte LEB128 stream can carry 70 payload bits, which covers every
# unsigned 64-bit integer (and even a few beyond). Enforcing this bound turns
# a hostile or truncated stream into a clean error instead of an allocation
# spiral.


class EncodeError(ValueError):
    """Raised when ``encode`` is given a value it cannot represent."""


class DecodeError(ValueError):
    """Raised when ``decode`` sees a malformed or non-minimal LEB128 stream."""


def encode_unsigned(value: int) -> bytes:
    """Encode ``value`` as unsigned LEB128 bytes.

    Raises
    ------
    EncodeError
        If ``value`` is negative, not an integer, or larger than
        ``(1 << 70) - 1`` (the most 10 LEB128 bytes can carry).
    """
    if isinstance(value, bool):
        # ``bool`` is a subclass of ``int`` in Python, so ``isinstance(True, int)``
        # is True. Accepting it would mean ``encode(True)`` silently produces
        # ``b'\x01'``, which is a bug magnet at call sites that meant a real
        # integer. Require callers to be explicit.
        raise EncodeError("bool is not accepted; pass an int")

    if isinstance(value, int):
        n = value
    else:
        try:
            n = value.__index__()
        except AttributeError:
            raise EncodeError(f"expected an int, got {type(value).__name__}") from None
        if isinstance(n, bool):  # rare but possible for odd __index__ impls
            raise EncodeError("__index__ returned bool; pass an int")

    if n < 0:
        raise EncodeError("value must be non-negative")
    if n.bit_length() > 70:
        # More than 70 payload bits cannot fit in 10 bytes. This mirrors the
        # decoder's ceiling so a round-trip can never silently lose data.
        raise EncodeError("value exceeds the 70-bit LEB128 ceiling")

    if n == 0:
        # LEB128 encodes zero as a single 0x00 byte. Handling it explicitly
        # avoids an empty output from the loop below.
        return b"\x00"

    out = bytearray()
    while n > 0:
        group = n & 0x7F
        n >>= 7
        if n:
            out.append(group | 0x80)
        else:
            out.append(group)
    return bytes(out)


def decode_unsigned(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """Decode one unsigned LEB128 value starting at ``offset``.

    Returns ``(value, length_consumed)``. ``length_consumed`` is the number of
    bytes read, so the caller can advance ``offset + length_consumed`` to parse
    the next value from the same buffer.

    Raises
    ------
    DecodeError
        If the stream runs out of bytes before a terminating byte, if it runs
        longer than ``_MAX_BYTES`` bytes, or if the encoding is non-minimal (a
        leading zero group that lets the same value be written two ways).
    """
    if isinstance(data, (bytes, bytearray)):
        buf = data
    else:
        raise DecodeError(f"expected bytes or bytearray, got {type(data).__name__}")

    if not isinstance(offset, int) or isinstance(offset, bool):
        raise DecodeError("offset must be an int")
    if offset < 0:
        raise DecodeError("offset must be non-negative")
    if offset > len(buf):
        raise DecodeError("offset is past end of input")

    result = 0
    shift = 0
    consumed = 0
    prev_group: int = -1

    for i in range(offset, len(buf)):
        byte = buf[i]
        group = byte & 0x7F

        result |= group << shift
        shift += 7
        consumed += 1

        if not (byte & 0x80):
            # Final byte reached.
            if consumed > 1 and group == 0:
                # A non-minimal encoding has an extra trailing zero group that
                # carries no information, e.g. ``b'\x80\x00'`` for value 0
                # instead of ``b'\x00'``, or ``b'\xff\x00'`` for value 127
                # instead of ``b'\x7f'``. The tell-tale sign is a final group
                # of zero after at least one continuation byte: the previous
                # group already held the complete value in its 7 payload bits,
                # so the continuation bit on it was pure padding. Some decoders
                # accept these, but accepting them makes equality checks on
                # the serialized form ambiguous. Reject so the canonical form
                # is the only form.
                raise DecodeError("non-minimal LEB128: trailing zero group")
            return result, consumed

        if consumed >= _MAX_BYTES:
            # No terminating byte within the ceiling. A longer stream cannot
            # add any representable value, so this is malformed or hostile.
            raise DecodeError("LEB128 sequence exceeds 10 bytes without terminating")

        prev_group = group

    raise DecodeError("truncated LEB128: no terminating byte before end of input")


# Friendly aliases. ``encode`` / ``decode`` are the names callers reach for
# first; the ``_unsigned`` spellings exist to make it obvious that a signed
# variant is intentionally absent.
encode = encode_unsigned
decode = decode_unsigned
