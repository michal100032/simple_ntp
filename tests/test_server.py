"""Exercise injected clocks and the server loop without network access."""

import socket
import unittest
from unittest.mock import patch

from ntp import NTPPacket, NTPServer, TimeProvider
import server as cli


class FixedTimeProvider(TimeProvider):
    def __init__(self, *timestamps: int) -> None:
        self.timestamps = iter(timestamps)

    def get_timestamp(self) -> int:
        return next(self.timestamps)

    def get_precision(self) -> int:
        return -20

    def get_reference_id(self) -> int:
        return 0x58545354  # XTST


class NTPServerTests(unittest.TestCase):
    def test_response_uses_provider_and_request_timestamps(self):
        request = NTPPacket()
        request.set_poll(-6)
        request.set_transmit_timestamp(0x1112131480000000)
        server = NTPServer(FixedTimeProvider(0x3132333400000000))

        response = server.create_response(request, 0x21222324FFFFFFFF)

        self.assertEqual(response.to_bytes(), bytes.fromhex(
            "24 01 fa ec"  # LI=0, version=4, server mode, stratum=1.
            "00000000 00000000 58545354"
            "21222324ffffffff"  # Reference: clock at receipt.
            "1112131480000000"  # Origin: client's transmit timestamp.
            "21222324ffffffff"  # Receive: clock at receipt.
            "3132333400000000"  # Transmit: next provider sample.
        ))

    def test_loop_rejects_bad_requests_and_continues_after_send_error(self):
        address = ("127.0.0.1", 9000)
        old_version = NTPPacket()
        old_version.set_version(2)
        server_mode = NTPPacket()
        server_mode.set_mode(4)
        v3 = NTPPacket()
        v3.set_version(3)
        v3.set_transmit_timestamp(42)
        v4 = NTPPacket()
        v4.set_transmit_timestamp(43)
        datagrams = (
            b"short", bytes(49), old_version.to_bytes(), server_mode.to_bytes(),
            v3.to_bytes(), v4.to_bytes(),
        )
        server = NTPServer(FixedTimeProvider(*range(100, 108)), "127.0.0.1", 8123)

        with patch("ntp.server.socket.socket") as socket_factory:
            sock = socket_factory.return_value.__enter__.return_value
            sock.getsockname.return_value = ("127.0.0.1", 8123)
            sock.recvfrom.side_effect = [
                *((data, address) for data in datagrams), KeyboardInterrupt(),
            ]
            sock.sendto.side_effect = [OSError("send failed"), None]
            with self.assertLogs("ntp.server", level="WARNING") as logs:
                with self.assertRaises(KeyboardInterrupt):
                    server.serve()

            socket_factory.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind.assert_called_once_with(("127.0.0.1", 8123))
            self.assertEqual(sock.sendto.call_count, 2)
            for call, version, origin, received, transmitted in zip(
                sock.sendto.call_args_list, (3, 4), (42, 43), (104, 106), (105, 107)
            ):
                data, destination = call.args
                reply = NTPPacket.from_bytes(data)
                self.assertEqual(destination, address)
                self.assertEqual(reply.get_version(), version)
                self.assertEqual(reply.get_origin_timestamp(), origin)
                self.assertEqual(reply.get_receive_timestamp(), received)
                self.assertEqual(reply.get_transmit_timestamp(), transmitted)
            self.assertIn("send failed", logs.output[0])
            socket_factory.return_value.__exit__.assert_called_once()

    def test_cli_constructs_server_with_system_provider(self):
        with patch("sys.argv", ["server.py", "--host", "0.0.0.0", "--port", "8123"]):
            with patch("server.NTPServer") as server_class:
                with patch("server.SystemTimeProvider") as provider_class:
                    self.assertEqual(cli.main(), 0)
                    server_class.assert_called_once_with(
                        provider_class.return_value, host="0.0.0.0", port=8123
                    )
                    server_class.return_value.serve.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
