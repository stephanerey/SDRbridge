from __future__ import annotations

import argparse
import json
import socket
import time

from .ring import RingReader, SharedIQRing


class LocalIQClient:
    def __init__(self, name: str, host: str = "127.0.0.1", port: int = 47631):
        self._sock = socket.create_connection((host, port), timeout=3)
        self._file = self._sock.makefile("rwb")
        response = self._request({"action": "register", "name": name})
        desc = response["ring"]
        self.client_id = response["client_id"]
        self.ring = SharedIQRing.attach(desc)
        self.reader = RingReader(self.ring)
        self.samples = 0
        self._last_heartbeat = 0.0

    def _request(self, payload: dict) -> dict:
        self._file.write(json.dumps(payload).encode("utf-8") + b"\n")
        self._file.flush()
        response = json.loads(self._file.readline().decode("utf-8"))
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "bridge request failed"))
        return response

    def read(self, timeout: float = 1.0):
        block = self.reader.read(timeout)
        if block:
            self.samples += block.sample_count
            now = time.monotonic()
            if now - self._last_heartbeat >= 1.0:
                self._request({"action": "heartbeat", "client_id": self.client_id, "sequence": block.sequence, "samples": self.samples, "dropped": self.reader.dropped_blocks})
                self._last_heartbeat = now
        return block

    def close(self) -> None:
        self.ring.close()
        self._file.close()
        self._sock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SDR_Bridge local diagnostic client")
    parser.add_argument("--name", default="diagnostic-client")
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--port", type=int, default=47631)
    args = parser.parse_args()
    client = LocalIQClient(args.name, port=args.port)
    start = time.monotonic(); blocks = samples = 0
    try:
        while time.monotonic() - start < args.seconds:
            block = client.read(1)
            if block:
                blocks += 1; samples += block.sample_count
        elapsed = time.monotonic() - start
        print(json.dumps({"blocks": blocks, "samples": samples, "samples_per_second": samples / elapsed, "dropped": client.reader.dropped_blocks}, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()

