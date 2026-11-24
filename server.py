#!/usr/bin/env python3
"""Serve the local system clock over basic unicast NTP/UDP."""

import argparse
import logging
from ntp import NTPServer, SystemTimeProvider

LOGGER = logging.getLogger(__name__)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="IPv4 bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=123, help="UDP port (default: 123)")
    parser.add_argument("--timesrc",default="sys", help="Time reference source (sys/gps, default: sys)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.timesrc not in ["sys", "gps"]:
        parser.error("--timesrc must be either 'sys' or 'gps'")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        if (args.timesrc == "sys"):
            server = NTPServer(SystemTimeProvider(), host=args.host, port=args.port)
        if (args.timesrc == "gps"):
            server = NTPServer(SystemTimeProvider(), host=args.host, port=args.port)
            
        server.serve()
        
    except KeyboardInterrupt:
        LOGGER.info("Server stopped")
        
    except OSError as error:
        LOGGER.error("Server failed: %s", error)
        return 1
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
