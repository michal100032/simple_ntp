"""The basic NTP header defined in RFC 5905, section 7.3."""


class NTPPacket:
    """A mutable 48-byte NTP packet with explicit field getters and setters.

    Fields use integers in their wire representation. Root delay is signed
    16.16 fixed point; root dispersion is unsigned 16.16 fixed point. Divide
    either by 2**16 to get seconds. Timestamps are unsigned 32.32 fixed point
    NTP timestamps, not Unix timestamps. Reference ID is an unsigned integer.

    Setters validate storage ranges, not protocol policy (such as supported
    versions or valid server strata). Extensions and authentication are not
    supported. A new packet defaults to version 4, client mode, and zero for
    every other field.
    """

    SIZE = 48

    def __init__(self) -> None:
        self._data = bytearray(self.SIZE)
        self.set_version(4)
        self.set_mode(3)

    @classmethod
    def from_bytes(cls, data: bytes) -> "NTPPacket":
        """Parse exactly 48 bytes, rejecting truncated or extended packets."""
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        if len(data) != cls.SIZE:
            raise ValueError(f"an NTP packet must be exactly {cls.SIZE} bytes")
        packet = cls()
        packet._data[:] = data
        return packet

    def to_bytes(self) -> bytes:
        """Return an immutable snapshot of the packet in network byte order."""
        return bytes(self._data)

    @staticmethod
    def _validate(value: int, bits: int, signed: bool = False) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("field value must be an integer")
        minimum = -(1 << (bits - 1)) if signed else 0
        maximum = (1 << (bits - int(signed))) - 1
        if not minimum <= value <= maximum:
            raise ValueError(f"field value must be between {minimum} and {maximum}")

    def _get_integer(self, offset: int, size: int, signed: bool = False) -> int:
        return int.from_bytes(self._data[offset:offset + size], "big", signed=signed)

    def _set_integer(
        self, offset: int, size: int, value: int, signed: bool = False
    ) -> None:
        self._validate(value, size * 8, signed)
        self._data[offset:offset + size] = value.to_bytes(size, "big", signed=signed)

    def _set_bits(self, value: int, shift: int, bits: int) -> None:
        self._validate(value, bits)
        mask = ((1 << bits) - 1) << shift
        self._data[0] = (self._data[0] & ~mask) | (value << shift)

    def get_leap_indicator(self) -> int:
        """Return the two-bit leap indicator."""
        return self._data[0] >> 6

    def set_leap_indicator(self, value: int) -> None:
        self._set_bits(value, 6, 2)

    def get_version(self) -> int:
        """Return the three-bit version number."""
        return (self._data[0] >> 3) & 7

    def set_version(self, value: int) -> None:
        self._set_bits(value, 3, 3)

    def get_mode(self) -> int:
        """Return the three-bit association mode (3: client, 4: server)."""
        return self._data[0] & 7

    def set_mode(self, value: int) -> None:
        self._set_bits(value, 0, 3)

    def get_stratum(self) -> int:
        return self._get_integer(1, 1)

    def set_stratum(self, value: int) -> None:
        self._set_integer(1, 1, value)

    def get_poll(self) -> int:
        """Return the signed poll interval exponent in log2 seconds."""
        return self._get_integer(2, 1, signed=True)

    def set_poll(self, value: int) -> None:
        self._set_integer(2, 1, value, signed=True)

    def get_precision(self) -> int:
        """Return the signed clock precision exponent in log2 seconds."""
        return self._get_integer(3, 1, signed=True)

    def set_precision(self, value: int) -> None:
        self._set_integer(3, 1, value, signed=True)

    def get_root_delay(self) -> int:
        """Return the raw signed 16.16 root delay."""
        return self._get_integer(4, 4, signed=True)

    def set_root_delay(self, value: int) -> None:
        self._set_integer(4, 4, value, signed=True)

    def get_root_dispersion(self) -> int:
        """Return the raw unsigned 16.16 root dispersion."""
        return self._get_integer(8, 4)

    def set_root_dispersion(self, value: int) -> None:
        self._set_integer(8, 4, value)

    def get_reference_id(self) -> int:
        """Return the raw 32-bit reference identifier."""
        return self._get_integer(12, 4)

    def set_reference_id(self, value: int) -> None:
        self._set_integer(12, 4, value)

    def get_reference_timestamp(self) -> int:
        """Return the raw 64-bit reference timestamp."""
        return self._get_integer(16, 8)

    def set_reference_timestamp(self, value: int) -> None:
        self._set_integer(16, 8, value)

    def get_origin_timestamp(self) -> int:
        """Return the raw 64-bit origin timestamp."""
        return self._get_integer(24, 8)

    def set_origin_timestamp(self, value: int) -> None:
        self._set_integer(24, 8, value)

    def get_receive_timestamp(self) -> int:
        """Return the raw 64-bit receive timestamp."""
        return self._get_integer(32, 8)

    def set_receive_timestamp(self, value: int) -> None:
        self._set_integer(32, 8, value)

    def get_transmit_timestamp(self) -> int:
        """Return the raw 64-bit transmit timestamp."""
        return self._get_integer(40, 8)

    def set_transmit_timestamp(self, value: int) -> None:
        self._set_integer(40, 8, value)
