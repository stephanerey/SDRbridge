from __future__ import annotations

import argparse
import json
import socket
import time
import uuid

from .udp import NativeDatagram, parse_datagram


class NativeIQClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 47632, *, token: str | None = None, profile_id: str = "native-cs16-192k"):
        self._control = socket.create_connection((host, port), timeout=3)
        self._file = self._control.makefile("rwb")
        self._udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp.bind(("127.0.0.1", 0))
        self._udp.settimeout(1.0)
        self._request("hello", {"client_name": "SDRbridge reference client", "client_version": "0.3.0", **({"token": token} if token else {})})
        source = self._request("list_sources", {})["items"][0]
        self.subscription = self._request("subscribe", {
            "source_id": source["source_id"],
            "profile_id": profile_id,
            "profile_revision": 1,
            "transport": "udp_unicast",
            "port": self._udp.getsockname()[1],
        })

    def _request(self, method: str, params: dict) -> dict:
        request_id = uuid.uuid4().hex
        request = {"api_version": 1, "request_id": request_id, "method": method, "params": params}
        self._file.write(json.dumps(request, separators=(",", ":")).encode("utf-8") + b"\n")
        self._file.flush()
        response = json.loads(self._file.readline())
        if response.get("request_id") != request_id:
            raise RuntimeError("native control request_id mismatch")
        if not response.get("ok"):
            error = response.get("error", {})
            raise RuntimeError(f"{error.get('code')}: {error.get('message')}")
        return response["result"]

    def receive(self, timeout: float = 1.0) -> NativeDatagram:
        self._udp.settimeout(timeout)
        data, _ = self._udp.recvfrom(65_535)
        packet = parse_datagram(data)
        if packet.wire_stream_id != self.subscription["wire_stream_id"]:
            raise RuntimeError("unexpected wire stream")
        return packet

    def heartbeat(self) -> dict:
        return self._request("heartbeat", {})

    def close(self) -> None:
        try:
            if getattr(self, "subscription", None):
                self._request("unsubscribe", {"subscription_id": self.subscription["subscription_id"]})
            self._request("goodbye", {})
        except Exception:
            pass
        self._file.close()
        self._control.close()
        self._udp.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Client de référence SDRbridge SDBU v2")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=47632)
    parser.add_argument("--token")
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()
    client = NativeIQClient(args.host, args.port, token=args.token)
    packets = samples = 0
    started = time.monotonic()
    try:
        while time.monotonic() - started < args.seconds:
            packet = client.receive(1.0)
            packets += 1
            samples += packet.sample_count
        print(json.dumps({"packets": packets, "samples": samples, "elapsed_s": time.monotonic() - started}, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
