# Simple Python NTP

A standard-library module for reading and writing the basic 48-byte NTP packet
header described in [RFC 5905, section 7.3](https://www.rfc-editor.org/rfc/rfc5905.html#section-7.3).
The `server.py` script uses `NTPServer` with a `SystemTimeProvider` to serve the
system clock over UDP. `NTPPacket` parses requests and builds responses.

Requirements:
```bash
# become root
sudo su

# create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# install sysv_ipc
python3 -m pip install sys_ipc
```

Start the server as root from the repository root and from inside the venv:

```sh
python server.py --host 127.0.0.1
```

The default address is `127.0.0.1` and the default port is `123`. Binding UDP
port 123 may require elevated privileges, depending on the operating system.
Use `--host 0.0.0.0` to listen on all IPv4 interfaces. Stop with Ctrl+C.

The server can also be used directly:

```python
from ntp import NTPServer, SystemTimeProvider

server = NTPServer(SystemTimeProvider(), host="127.0.0.1", port=8123)
server.serve()  # Ctrl+C closes the socket and raises KeyboardInterrupt.
```

To supply another trusted local clock, subclass `ntp.TimeProvider` and implement
`get_timestamp()`, `get_precision()`, and `get_reference_id()`. Timestamps must
use unsigned 64-bit NTP 32.32 encoding. Precision is an integer log2-second
exponent between -128 and 127, and the reference identifier is an unsigned
32-bit integer. Pass the provider to `NTPServer` in place of `SystemTimeProvider`.
All providers use the same stratum-1, leap-indicator-0 local-reference policy
described below; they do not supply upstream synchronization state.

The server accepts basic 48-byte NTPv3/v4 client requests (mode 3) and returns
server replies (mode 4). It copies the client's transmit timestamp into the
response's origin timestamp, samples the system clock immediately after receipt,
and samples it again immediately before sending. Conversion uses integer
nanoseconds and wraps the seconds field at NTP era boundaries.

This simple implementation treats the system clock as a trusted local reference:
it advertises stratum 1, leap indicator 0, experimental reference ID `XSYS`, and
zero root delay and dispersion. The reference timestamp is the local clock
sample taken on receipt. It does not determine the host's synchronization state,
leap-second status, or accuracy; reported precision reflects the clock's nominal
resolution. It neither synchronizes nor changes the system clock. Malformed
packets, unsupported versions/modes, extensions, and authentication are ignored.

Run this example from the repository root:

```python
from ntp import NTPPacket

packet = NTPPacket()  # Version 4, client mode; other fields start at zero.
packet.set_mode(4)  # Server mode.
packet.set_stratum(2)
packet.set_poll(6)  # 2**6 seconds.
packet.set_precision(-20)  # 2**-20 seconds.
packet.set_root_delay(1 << 15)  # 0.5 seconds in 16.16 fixed point.
packet.set_reference_id(int.from_bytes(b"GPS\0", "big"))
packet.set_transmit_timestamp((3_900_000_000 << 32) | (1 << 31))

data = packet.to_bytes()
parsed = NTPPacket.from_bytes(data)
assert parsed.get_stratum() == 2
assert parsed.get_transmit_timestamp() == packet.get_transmit_timestamp()
```

Every header field has `get_<field>()` and `set_<field>(value)` methods:
`leap_indicator`, `version`, `mode`, `stratum`, `poll`, `precision`, `root_delay`,
`root_dispersion`, `reference_id`, `reference_timestamp`, `origin_timestamp`,
`receive_timestamp`, and `transmit_timestamp`.

All field values are integers. Root delay is signed 16.16 fixed point and root
dispersion is unsigned 16.16 fixed point: divide by `2**16` to obtain seconds.
Timestamps retain the exact unsigned 64-bit NTP encoding: the high 32 bits hold
seconds within an NTP era and the low 32 bits hold fractional seconds. They are
not Unix timestamps; epoch conversion and era selection are left to the caller.

Setters raise `TypeError` for non-integers (including booleans) and `ValueError`
for values outside the field's storage range. Protocol policy, such as which
versions and modes a server accepts, is left to the caller. Parsing requires
exactly 48 bytes; extensions and authentication fields are unsupported.

Run the tests from the repository root:

```sh
python -m unittest discover -s tests -v
```
