# Variable Length Quantity Varint

Encodes and decodes non-negative integers as unsigned LEB128 byte sequences, for compact serialization of small integers.

```python
from variable_length_quantity_varint import encode, decode

encoded = encode(300)        # b'\xac\x02'
value, consumed = decode(encoded)   # (300, 2)
```

`encode(value)` returns `bytes`. `decode(data, offset=0)` returns a `(value, bytes_consumed)` tuple so you can parse several values out of one buffer by advancing the offset. Aliases `encode_unsigned` / `decode_unsigned` are provided if you want the signedness explicit at the call site.

## Why this exists

Small integers dominate most serialized data — lengths, field tags, enum ordinals. A fixed-width 64-bit encoding wastes seven bytes for a value like `3`. LEB128 uses one byte per seven payload bits, so `3` is `b'\x03'` and `300` is `b'\xac\x02'`. The trade-off is decode cost (a byte-at-a-time loop) and variable width, which makes random access into a stream impossible without an index. For length-prefixed and sequential formats that trade is almost always worth it.

## Edge cases worth knowing

- **Non-negative only.** If you need signed support, apply zig-zag yourself (`(n << 1) ^ (n >> 63)` for 64-bit) before calling `encode`. Mixing the two would inflate the API and invite conflicting interpretations, so it is deliberately out of scope.
- **Non-minimal encodings are rejected.** `0` has exactly one canonical form, `b'\x00'`; `b'\x80\x00'` raises `DecodeError`. If you need to accept redundant encodings from another producer, pre-normalize before calling `decode`.
- **`bool` is rejected by `encode`** even though it is a subclass of `int` in Python, because silently writing `True` as `b'\x01'` is almost always a caller bug.
- **A 10-byte ceiling is enforced** on decode. A 10-byte LEB128 stream carries 70 bits, which covers every unsigned 64-bit integer; anything longer is truncated or hostile and raises `DecodeError`.
