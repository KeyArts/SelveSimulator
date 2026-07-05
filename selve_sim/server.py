"""
Serial port simulator server.

Reads XML messages from the serial port (or virtual port pair) and
writes back responses + events.

Message framing: The Selve gateway sends/receives one complete XML document
per transaction, terminated by a newline (\\n).  The XML header line
<?xml version="1.0" encoding="UTF-8"?> is always present.

Usage:
    python -m selve_sim.server --port /dev/ttyUSB1
    python -m selve_sim.server --port COM5         # Windows
    python -m selve_sim.server --port LOOPBACK     # internal test mode (no real serial)
"""

import argparse
import asyncio
import logging
import sys
import time
from typing import Optional

import serial  # pyserial

from .dispatcher import dispatch
from .protocol import SelveRequest
from .state import GatewayState

log = logging.getLogger("selve.server")

BAUD_RATE = 115200
READ_TIMEOUT = 0.1   # seconds


class SelveSimulator:
    """Wraps a serial.Serial port and handles the request/response loop."""

    def __init__(self, port: str, state: Optional[GatewayState] = None):
        self.port_name = port
        self.state = state or GatewayState()
        self.state.add_default_devices()
        self._ser: Optional[serial.Serial] = None
        self._running = False
        self._buf = ""

    # ── Connection ──────────────────────────────────────────────────────────

    def open(self):
        log.info("Opening serial port %s @ %d baud", self.port_name, BAUD_RATE)
        self._ser = serial.Serial(
            port=self.port_name,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=READ_TIMEOUT,
        )
        self._running = True
        log.info("Serial port opened. Simulator ready.")

    def close(self):
        self._running = False
        if self._ser and self._ser.is_open:
            self._ser.close()
            log.info("Serial port closed.")

    # ── Main loop ───────────────────────────────────────────────────────────

    def run(self):
        """Blocking run loop. Call from main thread."""
        self.open()
        try:
            while self._running:
                self._tick()
        except KeyboardInterrupt:
            log.info("Interrupted by user.")
        finally:
            self.close()

    def _tick(self):
        """Read available bytes, try to parse complete XML messages."""
        if not self._ser or not self._ser.is_open:
            return
        try:
            data = self._ser.read(self._ser.in_waiting or 1)
        except serial.SerialException as e:
            log.error("Serial read error: %s", e)
            self._running = False
            return

        if data:
            self._buf += data.decode("utf-8", errors="replace")
            self._process_buffer()

    def _process_buffer(self):
        """Extract and handle complete XML documents from the receive buffer."""
        while True:
            # A complete Selve message ends after the root closing tag.
            # We look for </methodCall> or </methodResponse> as message end.
            end_call = self._buf.find("</methodCall>")
            end_resp = self._buf.find("</methodResponse>")

            if end_call == -1 and end_resp == -1:
                break  # no complete message yet

            if end_call != -1 and (end_resp == -1 or end_call < end_resp):
                end = end_call + len("</methodCall>")
            else:
                end = end_resp + len("</methodResponse>")

            raw = self._buf[:end].strip()
            self._buf = self._buf[end:]

            # Strip XML declaration prefix if present to find the start tag
            start = raw.find("<methodCall")
            if start == -1:
                start = raw.find("<methodResponse")
            if start == -1:
                log.debug("Discarding non-method data: %r", raw[:80])
                continue

            xml_msg = raw[start:]
            log.debug("RX: %s", xml_msg[:200])
            self._handle_message(xml_msg)

    def _handle_message(self, xml_str: str):
        """Parse, dispatch and respond to a single XML message."""
        try:
            request = SelveRequest.parse(xml_str)
        except Exception as exc:
            log.warning("XML parse error: %s\nInput: %r", exc, xml_str[:200])
            self._send('<?xml version="1.0" encoding="UTF-8"?>\n'
                       '<methodResponse><fault><array>'
                       '<string>XML parse error</string><int>1</int>'
                       '</array></fault></methodResponse>\n')
            return

        log.info("→ %s %s", request.method, request.params)
        response, events = dispatch(self.state, request)

        resp_xml = response.to_xml()
        log.info("← %s", resp_xml[:200])
        self._send(resp_xml)

        for event in events:
            ev_xml = event.to_xml()
            log.debug("! event: %s", ev_xml[:200])
            self._send(ev_xml)

    def _send(self, xml_str: str):
        if self._ser and self._ser.is_open:
            self._ser.write(xml_str.encode("utf-8"))
            self._ser.flush()


# ── Internal loopback for unit testing ─────────────────────────────────────

class LoopbackSimulator(SelveSimulator):
    """
    In-process simulator: instead of a real serial port, exposes
    send_raw(xml) -> [response_xml, ...event_xmls] for testing.
    """

    def __init__(self, state: Optional[GatewayState] = None):
        super().__init__("LOOPBACK", state)
        self._responses: list = []

    def open(self):
        self._running = True
        log.info("LoopbackSimulator ready (no serial port).")

    def close(self):
        self._running = False

    def _send(self, xml_str: str):
        self._responses.append(xml_str)

    def send_raw(self, xml_str: str) -> list:
        """Send an XML request, return list of response + event XML strings."""
        self._responses.clear()
        self._buf += xml_str
        self._process_buffer()
        return list(self._responses)

    def run(self):
        raise NotImplementedError("Use send_raw() for loopback mode")


# ── CLI entry point ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Selve USB-RF Gateway Simulator"
    )
    parser.add_argument(
        "--port", required=True,
        help="Serial port to bind (e.g. /dev/ttyUSB1, COM5)"
    )
    parser.add_argument(
        "--loglevel", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.loglevel),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    sim = SelveSimulator(port=args.port)
    sim.run()


if __name__ == "__main__":
    main()
