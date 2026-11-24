"""Check the system clock's NTP representation independently of wall time."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch
import struct

from ntp import SystemTimeProvider, TimeProvider, PPSTimeProvider

class SystemTimeProviderTests(unittest.TestCase):
    def test_provider_requires_an_implementation(self):
        with self.assertRaises(TypeError):
            TimeProvider()

    def test_system_timestamp_conversion(self):
        for unix_ns, expected in (
            (0, 2_208_988_800 << 32),
            (1_500_000_000, (2_208_988_801 << 32) | 0x80000000),
            (-500_000_000, (2_208_988_799 << 32) | 0x80000000),
            (2_085_978_496_000_000_000, 0),  # First NTP era rollover.
            (2_085_978_496_250_000_000, 0x40000000),
        ):
            with self.subTest(unix_ns=unix_ns):
                with patch("ntp.time_provider.time.time_ns", return_value=unix_ns):
                    self.assertEqual(SystemTimeProvider().get_timestamp(), expected)

    def test_system_precision_rounds_up_and_fits_signed_byte(self):
        for resolution, expected in (
            (1e-9, -29),
            (2**-20, -20),
            (2**-200, -128),
            (2**200, 127),
        ):
            with self.subTest(resolution=resolution):
                with patch(
                    "ntp.time_provider.time.get_clock_info",
                    return_value=SimpleNamespace(resolution=resolution),
                ) as clock_info:
                    self.assertEqual(SystemTimeProvider().get_precision(), expected)
                    clock_info.assert_called_once_with("time")

    def test_system_reference_id(self):
        self.assertEqual(SystemTimeProvider().get_reference_id(), 0x58535953)

class PPSTimeProviderTests(unittest.TestCase):
    NTP_EPOCH_OFFSET = 2_208_988_800

    def setUp(self):
        self.shm = SimpleNamespace(read=self._read_shm)

        self.provider_patcher = patch(
            "ntp.time_provider.sysv_ipc.SharedMemory",
            return_value=self.shm,
        )
        self.shared_memory = self.provider_patcher.start()
        self.addCleanup(self.provider_patcher.stop)

        self.provider = PPSTimeProvider()

    def _read_shm(
        self,
        size,
        *,
        count=2,
        clock_sec=1_500_000_000,
        clock_nsec=500_000_000,
        precision=-20,
        valid=1,
    ):
        return struct.pack(
            self.provider.SHM_FORMAT,
            1,                  # mode
            count,
            clock_sec,
            clock_nsec // 1000,
            clock_sec,
            clock_nsec // 1000,
            0,                  # leap
            precision,
            1,                  # nsamples
            valid,
            clock_nsec,
            clock_nsec,
            *([0] * 8),
        )

    def test_shared_memory_initialization(self):
        self.shared_memory.assert_called_once_with(
            self.provider.NTP2,
            flags=0,
            mode=0o600,
            size=struct.calcsize(self.provider.SHM_FORMAT),
        )

    def test_timestamp_conversion(self):
        test_cases = (
            (0, 0, (2_208_988_800 << 32)),
            (1_500_000_000, 0,
             (3_708_988_800 << 32)),
            (1_500_000_000, 500_000_000,
             (3_708_988_800 << 32) | 0x80000000),
            (1_500_000_000, 250_000_000,
             (3_708_988_800 << 32) | 0x40000000),
        )

        for sec, nsec, expected in test_cases:
            with self.subTest(sec=sec, nsec=nsec):
                self.shm.read = lambda size: self._read_shm(
                    clock_sec=sec,
                    clock_nsec=nsec,
                )

                self.provider.last_count = None
                self.provider.timestamp = None

                self.assertEqual(
                    self.provider.get_timestamp(),
                    expected,
                )

    def test_precision(self):
        self.assertEqual(self.provider.get_precision(), -20)

    def test_invalid_sample_is_rejected(self):
        self.shm.read = lambda size: self._read_shm(valid=0)

        with self.assertRaises(RuntimeError):
            self.provider.get_timestamp()

    def test_duplicate_sample_is_ignored(self):
        self.provider.get_timestamp()

        original_timestamp = self.provider.timestamp

        self.shm.read = lambda size: self._read_shm(
            count=2,
            clock_sec=1_600_000_000,
        )

        self.provider.get_timestamp()

        self.assertEqual(
            self.provider.timestamp,
            original_timestamp,
        )

    def test_invalid_sample_does_not_overwrite_previous_timestamp(self):
        self.provider.get_timestamp()
        original_timestamp = self.provider.timestamp

        self.shm.read = lambda size: self._read_shm(valid=0)

        self.provider._PPSTimeProvider__update_state()

        self.assertEqual(
            self.provider.timestamp,
            original_timestamp,
        )

    def test_odd_counter_is_rejected(self):
        self.shm.read = lambda size: self._read_shm(count=3)

        with self.assertRaises(RuntimeError):
            self.provider.get_timestamp()

if __name__ == "__main__":
    unittest.main()
