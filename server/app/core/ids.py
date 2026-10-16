"""Unique identifier generation utilities.

Provides RFC 9562 compliant UUIDv7 identifiers for index locality and temporal ordering.
"""

from __future__ import annotations

import os
import time
import uuid


def generate_uuid7() -> uuid.UUID:
    """Generate an RFC 9562 compliant UUIDv7.

    UUIDv7 structure (128 bits):
    - 48 bits: Unix timestamp in milliseconds (big-endian)
    - 4 bits: Version 7 (0b0111)
    - 12 bits: rand_a pseudo-random bits
    - 2 bits: Variant 2 (0b10, RFC 4122/9562)
    - 62 bits: rand_b pseudo-random bits

    Provides monotonicity and excellent B-Tree index locality in PostgreSQL.
    """
    nanoseconds = time.time_ns()
    milliseconds = nanoseconds // 1_000_000

    # 48-bit timestamp (6 bytes)
    time_ms_bytes = milliseconds.to_bytes(6, byteorder="big")

    # 10 random bytes for rand_a (12 bits) and rand_b (62 bits)
    rand_bytes = bytearray(os.urandom(10))

    # Set version to 7: top 4 bits of byte 6 (rand_bytes[0])
    rand_bytes[0] = (rand_bytes[0] & 0x0F) | 0x70

    # Set variant to 10xx (RFC 4122): top 2 bits of byte 8 (rand_bytes[2])
    rand_bytes[2] = (rand_bytes[2] & 0x3F) | 0x80

    uuid_bytes = bytes(time_ms_bytes) + bytes(rand_bytes)
    return uuid.UUID(bytes=uuid_bytes)


def is_valid_uuid(val: str | uuid.UUID) -> bool:
    """Check if a string or UUID object is a valid UUID."""
    if isinstance(val, uuid.UUID):
        return True
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError, TypeError):
        return False
