"""Check packet encoding against independently specified wire bytes."""

import unittest

from ntp import NTPPacket


class NTPPacketTests(unittest.TestCase):
    WIRE = bytes.fromhex(
        "e4 02 fa ec"  # LI=3, version=4, mode=4, stratum=2, poll=-6, precision=-20
        "ffff8000"  # Root delay: -0.5 seconds
        "00004000"  # Root dispersion: 0.25 seconds
        "47505300"  # Reference ID: GPS\0
        "0102030400000001"
        "1112131480000000"
        "21222324ffffffff"
        "3132333400000000"
    )
    FIELDS = (
        ("leap_indicator", 3, 0, 3),
        ("version", 4, 0, 7),
        ("mode", 4, 0, 7),
        ("stratum", 2, 0, 255),
        ("poll", -6, -128, 127),
        ("precision", -20, -128, 127),
        ("root_delay", -32768, -(2**31), 2**31 - 1),
        ("root_dispersion", 16384, 0, 2**32 - 1),
        ("reference_id", 0x47505300, 0, 2**32 - 1),
        ("reference_timestamp", 0x0102030400000001, 0, 2**64 - 1),
        ("origin_timestamp", 0x1112131480000000, 0, 2**64 - 1),
        ("receive_timestamp", 0x21222324FFFFFFFF, 0, 2**64 - 1),
        ("transmit_timestamp", 0x3132333400000000, 0, 2**64 - 1),
    )

    def test_default_packet(self):
        self.assertEqual(NTPPacket().to_bytes(), b"\x23" + bytes(47))

    def test_parse_known_wire_packet(self):
        packet = NTPPacket.from_bytes(self.WIRE)
        for field, expected, _, _ in self.FIELDS:
            with self.subTest(field=field):
                self.assertEqual(getattr(packet, f"get_{field}")(), expected)
        self.assertEqual(packet.to_bytes(), self.WIRE)

    def test_build_known_wire_packet(self):
        packet = NTPPacket()
        for field, value, _, _ in self.FIELDS:
            getattr(packet, f"set_{field}")(value)
        self.assertEqual(packet.to_bytes(), self.WIRE)

    def test_bit_fields_preserve_neighboring_bits(self):
        for field, value, expected in (
            ("leap_indicator", 0, 0x24),
            ("version", 0, 0xC4),
            ("mode", 0, 0xE0),
        ):
            with self.subTest(field=field):
                packet = NTPPacket.from_bytes(self.WIRE)
                getattr(packet, f"set_{field}")(value)
                self.assertEqual(packet.to_bytes(), bytes([expected]) + self.WIRE[1:])

    def test_field_boundaries_round_trip(self):
        for field, _, minimum, maximum in self.FIELDS:
            for value in (minimum, maximum):
                with self.subTest(field=field, value=value):
                    packet = NTPPacket()
                    getattr(packet, f"set_{field}")(value)
                    decoded = NTPPacket.from_bytes(packet.to_bytes())
                    self.assertEqual(getattr(decoded, f"get_{field}")(), value)

    def test_invalid_values_leave_packet_unchanged(self):
        for field, _, minimum, maximum in self.FIELDS:
            for value in (minimum - 1, maximum + 1, 1.5, "1", None, True):
                with self.subTest(field=field, value=value):
                    packet = NTPPacket.from_bytes(self.WIRE)
                    error = ValueError if type(value) is int else TypeError
                    with self.assertRaises(error):
                        getattr(packet, f"set_{field}")(value)
                    self.assertEqual(packet.to_bytes(), self.WIRE)

    def test_invalid_packet_lengths(self):
        for size in (0, 1, 47, 49, 68):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    NTPPacket.from_bytes(bytes(size))

    def test_non_bytes_input(self):
        for data in (48, "x" * 48, [0] * 48, None):
            with self.subTest(data=data):
                with self.assertRaises(TypeError):
                    NTPPacket.from_bytes(data)

    def test_packets_and_serialized_snapshots_are_independent(self):
        first = NTPPacket.from_bytes(self.WIRE)
        second = NTPPacket.from_bytes(self.WIRE)
        snapshot = first.to_bytes()
        first.set_stratum(5)
        self.assertEqual(second.to_bytes(), self.WIRE)
        self.assertEqual(snapshot, self.WIRE)


if __name__ == "__main__":
    unittest.main()
