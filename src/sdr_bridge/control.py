from __future__ import annotations

import json
import socketserver
import threading

from .bridge import SDRBridge


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        bridge: SDRBridge = self.server.bridge  # type: ignore[attr-defined]
        client_id: str | None = None
        try:
            for raw in self.rfile:
                if len(raw) > 65_536:
                    break
                try:
                    request = json.loads(raw.decode("utf-8"))
                    action = request.get("action")
                    if action == "status":
                        response = {"ok": True, "status": bridge.status()}
                    elif action == "register":
                        if client_id:
                            raise ValueError("connection already registered")
                        profile_id = request.get("profile_id")
                        profile_revision = int(request.get("profile_revision", 1))
                        client_id, _ = bridge.register_client(str(request.get("name", "client")), profile_id, profile_revision)
                        response = {"ok": True, "client_id": client_id, "ring": bridge.ring_descriptor_for_client(client_id), "config": bridge.config.to_dict()}
                    elif action == "heartbeat":
                        if not client_id or request.get("client_id") != client_id:
                            raise PermissionError("invalid client session")
                        bridge.record_read(client_id, int(request.get("sequence", -1)), int(request.get("samples", 0)), int(request.get("dropped", 0)))
                        response = {"ok": True}
                    elif action == "set_config":
                        # Control endpoint is local-only, but changes still require the
                        # server GUI token. Client adapters never receive this token.
                        if request.get("token") != self.server.control_token:  # type: ignore[attr-defined]
                            raise PermissionError("server control token required")
                        allowed = {"center_frequency_hz", "sample_rate_sps", "bandwidth_hz", "gain_reduction_db", "agc_enabled"}
                        changes = {k: v for k, v in request.get("changes", {}).items() if k in allowed}
                        expected = int(request.get("expected_config_revision", bridge.config.revision))
                        response = {"ok": True, "config": bridge.apply_config(expected, changes).to_dict()}
                    else:
                        raise ValueError("unknown action")
                except Exception as exc:
                    response = {"ok": False, "error": str(exc), "code": getattr(exc, "code", "BAD_REQUEST")}
                self.wfile.write(json.dumps(response, separators=(",", ":")).encode("utf-8") + b"\n")
                self.wfile.flush()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            if client_id:
                bridge.unregister_client(client_id)


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ControlServer:
    def __init__(self, bridge: SDRBridge, host: str = "127.0.0.1", port: int = 47631, control_token: str = "local-gui"):
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("MVP control server must bind to loopback only")
        self._server = _Server((host, port), _Handler)
        self._server.bridge = bridge  # type: ignore[attr-defined]
        self._server.control_token = control_token  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None
        self._started = False

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address
        return str(host), int(port)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.serve_forever, name="control-server", daemon=True)
        self._thread.start()
        self._started = True

    def close(self) -> None:
        if self._started:
            self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)
        self._started = False

