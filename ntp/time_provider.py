"""Time sources for the simple trusted-local-reference NTP server."""

from abc import ABC, abstractmethod
import math
import time
import sysv_ipc
import struct
import logging

LOGGER = logging.getLogger(__name__)

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

class PPSTimeProvider(TimeProvider):
    """Use the GNSS PPS signal from gpsd SHM as a reference"""
    
    NTPD_BASE = 0x4E545030  # the base offset of the gpsd SHM area
    NTP2 = NTPD_BASE + 2    # the address of the PPS timesource in memory

    # Shared Memory segment layout, using the native Linux ABI.
    # Raspberry Pi 4: aarch64, little-endian.
    SHM_FORMAT = "@iiq i q i i i i i I I 8i"
    SHM_SIZE = struct.calcsize(SHM_FORMAT)

    def __init__(self):
        self.shm = sysv_ipc.SharedMemory(
            self.NTP2,
            flags=0,
            mode=0o600,
            size=self.SHM_SIZE
        )

        self.last_count = None
        self.timestamp = None
        self.precision = None

    def __update_state(self) -> None:
        data = self.shm.read(self.SHM_SIZE)
        fields = struct.unpack(self.SHM_FORMAT, data)

        (
            mode, count,
            clock_sec, clock_usec,
            receive_sec, receive_usec,
            leap, precision, nsamples, valid,
            clock_nsec, receive_nsec,
            *dummy
        ) = fields

        # Reject invalid or already processed samples.
        if not valid or count == self.last_count:
            return

        # Reject samples with an inconsistent snapshot.
        # The SHM writer uses an odd/even counter protocol.
        if count & 1:
            return

        ntp_seconds = (clock_sec + NTP_EPOCH_OFFSET) & 0xFFFFFFFF
        ntp_fraction = (clock_nsec << 32) // NANOSECONDS_PER_SECOND

        self.timestamp = (ntp_seconds << 32) | ntp_fraction
        self.precision = precision
        self.last_count = count

    def get_timestamp(self) -> int:
        self.__update_state()

        if self.timestamp is None:
            LOGGER.error("No valid PPS timestamp available")

        return self.timestamp

    def get_precision(self) -> int:
        self.__update_state()

        if self.precision is None:
            LOGGER.error("No valid PPS precision available")

        return self.precision


    def get_reference_id(self) -> int:
        # X-prefixed identifiers are reserved for experimental local references.
        return int.from_bytes(b"XPPS", "big")