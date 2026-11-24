"""Serve basic unicast NTP/UDP using an injected local clock."""

import logging
import socket

from .packet import NTPPacket
from .time_provider import TimeProvider


LOGGER = logging.getLogger(__name__)


class NTPServer:
    """Answer NTPv3/v4 clients using a trusted local time provider.

    Providers are advertised as stratum 1 with leap indicator 0 and zero root
    delay and dispersion. This server does not assess clock synchronization.
    """

    def __init__(
        self, time_provider: TimeProvider, host: str = "127.0.0.1", port: int = 123
    ) -> None:
        self.time_provider = time_provider
        self.host = host
        self.port = port

    def create_response(self, request: NTPPacket, received: int) -> NTPPacket:
        """Build a reply to a validated request, sampling transmit time last.

        ``received`` must be the provider's NTP timestamp sampled on receipt.
        """
        response = NTPPacket()
        response.set_version(request.get_version())
        response.set_mode(4)
        response.set_leap_indicator(0)
        response.set_stratum(1)
        response.set_poll(request.get_poll())
        response.set_precision(self.time_provider.get_precision())
        response.set_reference_id(self.time_provider.get_reference_id())
        response.set_reference_timestamp(received)
        response.set_origin_timestamp(request.get_transmit_timestamp())
        response.set_receive_timestamp(received)
        response.set_transmit_timestamp(self.time_provider.get_timestamp())
        return response

    def serve(self) -> None:
        """Answer basic client requests until interrupted, closing the socket."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((self.host, self.port))
            LOGGER.info("Serving time on %s:%d/UDP", *sock.getsockname())

            while True:
                # Read the whole datagram so oversized packets are rejected.
                data, address = sock.recvfrom(65535)
                received = self.time_provider.get_timestamp()
                try:
                    request = NTPPacket.from_bytes(data)
                except ValueError:
                    LOGGER.debug("Ignoring invalid packet from %s", address)
                    continue

                if request.get_version() not in (3, 4) or request.get_mode() != 3:
                    LOGGER.debug("Ignoring unsupported request from %s", address)
                    continue

                response = self.create_response(request, received)
                try:
                    sock.sendto(response.to_bytes(), address)
                except OSError as error:
                    LOGGER.warning("Could not reply to %s: %s", address, error)
