"""Check the system clock's NTP representation independently of wall time."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ntp import SystemTimeProvider, TimeProvider


class TimeProviderTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
