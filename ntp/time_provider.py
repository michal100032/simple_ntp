"""Time sources for the simple trusted-local-reference NTP server."""

from abc import ABC, abstractmethod
import math
import time


NTP_EPOCH_OFFSET = 2_208_988_800
NANOSECONDS_PER_SECOND = 1_000_000_000


class TimeProvider(ABC):
    """A trusted local clock and the metadata advertised for it."""

    @abstractmethod
    def get_timestamp(self) -> int:
        """Read the clock as an unsigned 64-bit NTP 32.32 timestamp."""

    @abstractmethod
    def get_precision(self) -> int:
        """Return the clock's log2-second precision, in the range -128..127."""

    @abstractmethod
    def get_reference_id(self) -> int:
        """Return the local clock's unsigned 32-bit NTP reference identifier."""


class SystemTimeProvider(TimeProvider):
    """Use the system wall clock without changing or synchronizing it."""

    def get_timestamp(self) -> int:
        seconds, nanoseconds = divmod(time.time_ns(), NANOSECONDS_PER_SECOND)
        seconds = (seconds + NTP_EPOCH_OFFSET) & 0xFFFFFFFF
        fraction = (nanoseconds << 32) // NANOSECONDS_PER_SECOND
        return (seconds << 32) | fraction

    def get_precision(self) -> int:
        precision = math.ceil(math.log2(time.get_clock_info("time").resolution))
        return max(-128, min(127, precision))

    def get_reference_id(self) -> int:
        # X-prefixed identifiers are reserved for experimental local references.
        return int.from_bytes(b"XSYS", "big")
