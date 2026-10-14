from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import hmac
import json
import socket
import socketserver
import threading
import time
import uuid
from typing import Any, Callable

from .bridge import SDRBridge
from .udp import UDPDestination

API_VERSION = 1
MAX_LINE_BYTES = 65_536
HEARTBEAT_INTERVAL_S = 5
LEASE_TIMEOUT_S = 15


class ProtocolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("BAD_REQUEST", "duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ProtocolError("BAD_REQUEST", "non-finite JSON number")


def _depth(value: Any, level: int = 0) -> int:
    if level > 16:
        return level
    if isinstance(value, dict):
        return max([level] + [_depth(item, level + 1) for item in value.values()])
    if isinstance(value, list):
        return max([level] + [_depth(item, level + 1) for item in value])
    return level


def strict_json_loads(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates, parse_constant=_reject_constant)
    except ProtocolError:
        raise
    except Exception as exc:
        raise ProtocolError("BAD_REQUEST", "malformed JSON") from exc
    if not isinstance(value, dict) or _depth(value) > 16:
        raise ProtocolError("BAD_REQUEST", "JSON object/depth invalid")
    return value


@dataclass(slots=True)
class Subscription:
    subscription_id: str
    wire_stream_id: int
    source_id: str
    profile_id: str
    profile_revision: int
    pipeline_token: str
    destination: UDPDestination


@dataclass(slots=True)
class Session:
    client_id: str
    client_name: str
    client_version: str
    peer_host: str
    last_seen: float
    subscriptions: dict[str, Subscription] = field(default_factory=dict)
    released: set[str] = field(default_factory=set)
    requests: deque[float] = field(default_factory=deque)


class NativeControlManager:
    def __init__(self, bridge: SDRBridge, *, token: str | None = None, clock: Callable[[], float] = time.monotonic):
        if token is not None and len(token.encode("utf-8")) < 32:
            raise ValueError("LAN token must contain at least 32 bytes")
        self.bridge = bridge
        self.token = token
        self.clock = clock
        self.run_id = str(uuid.uuid4())
        self.bridge.run_id = self.run_id
        self._lock = threading.RLock()
        self._sessions: dict[str, Session] = {}
        self._next_stream_id = 1

    def _new_stream_id(self) -> int:
        with self._lock:
            if self._next_stream_id > 0xFFFFFFFF:
                raise ProtocolError("RESOURCE_LIMIT", "wire stream identity exhausted")
            value = self._next_stream_id
            self._next_stream_id += 1
            return value

    def _rate_limit(self, session: Session) -> None:
        now = self.clock()
        while session.requests and session.requests[0] <= now - 1.0:
            session.requests.popleft()
        if len(session.requests) >= 40:
            raise ProtocolError("RESOURCE_LIMIT", "request rate exceeded")
        session.requests.append(now)

    @staticmethod
    def _exact(params: dict, allowed: set[str], required: set[str] = frozenset()) -> None:
        if set(params) - allowed or not required.issubset(params):
            raise ProtocolError("BAD_REQUEST", "unknown or missing parameter")

    def hello(self, params: dict, peer_host: str) -> tuple[Session, dict]:
        self._exact(params, {"client_name", "client_version", "token"}, {"client_name", "client_version"})
        name, version = params["client_name"], params["client_version"]
        if not isinstance(name, str) or not 1 <= len(name) <= 128 or not isinstance(version, str) or not 1 <= len(version) <= 64:
            raise ProtocolError("BAD_REQUEST", "invalid client identity")
        supplied = params.get("token")
        if self.token is not None and (not isinstance(supplied, str) or not hmac.compare_digest(supplied, self.token)):
            raise ProtocolError("UNAUTHORIZED", "invalid read token")
        client_id = uuid.uuid4().hex
        session = Session(client_id, name, version, peer_host, self.clock())
        with self._lock:
            self._sessions[client_id] = session
        return session, {
            "client_id": client_id,
            "run_id": self.run_id,
            "role": "read",
            "heartbeat_interval_s": HEARTBEAT_INTERVAL_S,
            "lease_timeout_s": LEASE_TIMEOUT_S,
        }

    def _source_result(self) -> dict:
        status = self.bridge.status()
        return {
            "source_id": self.bridge.source_id,
            "state": status["state"],
            "epoch": str(self.bridge.epoch),
            "effective": {
                "sample_rate_sps": self.bridge.config.sample_rate_sps,
                "sample_format": self.bridge.config.sample_format.value,
                "center_frequency_hz": str(self.bridge.config.center_frequency_hz),
                "config_revision": self.bridge.config.revision,
            },
        }

    def dispatch(self, session: Session, method: str, params: dict) -> tuple[dict, bool]:
        self._rate_limit(session)
        session.last_seen = self.clock()
        if method == "list_sources":
            self._exact(params, set())
            return {"items": [self._source_result()]}, False
        if method == "list_profiles":
            self._exact(params, set())
            return {"items": [profile.to_dict() for profile in self.bridge.profiles.items()]}, False
        if method == "get_status":
            self._exact(params, set())
            return {
                "source": self._source_result(),
                "subscriptions": [self._subscription_result(item) for item in session.subscriptions.values()],
                "counters": {
                    "blocks_received": self.bridge.blocks_received,
                    "source_queue_drops": self.bridge.source_queue_drops,
                },
            }, False
        if method == "heartbeat":
            self._exact(params, {"telemetry"})
            telemetry = params.get("telemetry", {})
            if not isinstance(telemetry, dict) or len(telemetry) > 16:
                raise ProtocolError("BAD_REQUEST", "telemetry is too large")
            for value in telemetry.values():
                if isinstance(value, (dict, list)) or (isinstance(value, str) and len(value) > 128):
                    raise ProtocolError("BAD_REQUEST", "telemetry must contain bounded scalars")
            return {"state": self.bridge.state.value}, False
        if method == "subscribe":
            return self._subscribe(session, params), False
        if method == "unsubscribe":
            self._exact(params, {"subscription_id"}, {"subscription_id"})
            subscription_id = params["subscription_id"]
            if not isinstance(subscription_id, str):
                raise ProtocolError("BAD_REQUEST", "invalid subscription_id")
            if subscription_id in session.released:
                return {"subscription_id": subscription_id, "already_closed": True}, False
            subscription = session.subscriptions.pop(subscription_id, None)
            if subscription is None:
                raise ProtocolError("DESTINATION_DENIED", "subscription does not belong to this session")
            self._release_subscription(subscription)
            session.released.add(subscription_id)
            return {"subscription_id": subscription_id, "already_closed": False}, False
        if method == "goodbye":
            self._exact(params, set())
            self.release_session(session.client_id)
            return {"closed": True}, True
        raise ProtocolError("BAD_REQUEST", "unknown method")

    def _subscribe(self, session: Session, params: dict) -> dict:
        self._exact(params, {"source_id", "profile_id", "profile_revision", "transport", "port"}, {"source_id", "profile_id", "profile_revision", "transport", "port"})
        if params["source_id"] != self.bridge.source_id:
            raise ProtocolError("UNKNOWN_SOURCE", "unknown source")
        if not self.bridge.running:
            raise ProtocolError("SOURCE_NOT_RUNNING", "source is not running")
        if params["transport"] != "udp_unicast":
            raise ProtocolError("UNSUPPORTED_PROFILE", "client subscriptions support udp_unicast only")
        port = params["port"]
        if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
            raise ProtocolError("DESTINATION_DENIED", "invalid UDP port")
        try:
            profile = self.bridge.profiles.get(str(params["profile_id"]), int(params["profile_revision"]))
        except (KeyError, ValueError):
            raise ProtocolError("UNKNOWN_PROFILE", "unknown profile")
        if profile.protocol != "sdbu_v2":
            raise ProtocolError("UNSUPPORTED_PROFILE", "profile is not native SDBU v2")
        stream_id = self._new_stream_id()
        destination = UDPDestination((session.peer_host, port), wire_stream_id=stream_id)
        destination.start()
        try:
            pipeline_token, _ = self.bridge.subscribe_profile(profile.profile_id, profile.profile_revision, destination.enqueue)
        except Exception as exc:
            destination.stop()
            raise ProtocolError("UNSUPPORTED_PROFILE", "profile cannot be activated") from exc
        subscription_id = uuid.uuid4().hex
        subscription = Subscription(subscription_id, stream_id, self.bridge.source_id, profile.profile_id, profile.profile_revision, pipeline_token, destination)
        session.subscriptions[subscription_id] = subscription
        return self._subscription_result(subscription)

    def _subscription_result(self, item: Subscription) -> dict:
        profile = self.bridge.profiles.get(item.profile_id, item.profile_revision)
        return {
            "subscription_id": item.subscription_id,
            "wire_stream_id": item.wire_stream_id,
            "epoch": str(self.bridge.epoch),
            "profile_id": item.profile_id,
            "profile_revision": item.profile_revision,
            "endpoint": {"host": item.destination.destination[0], "port": item.destination.destination[1]},
            "effective": {
                "sample_rate_sps": profile.output_rate_sps,
                "sample_format": profile.sample_format.value,
                "center_frequency_hz": str(self.bridge.config.center_frequency_hz),
                "config_revision": self.bridge.config.revision,
            },
        }

    def _release_subscription(self, item: Subscription) -> None:
        self.bridge.unsubscribe_profile(item.pipeline_token)
        item.destination.stop()

    def release_session(self, client_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(client_id, None)
        if session:
            for subscription in list(session.subscriptions.values()):
                self._release_subscription(subscription)
            session.subscriptions.clear()

    def expire_sessions(self) -> list[str]:
        now = self.clock()
        with self._lock:
            expired = [key for key, value in self._sessions.items() if now - value.last_seen >= LEASE_TIMEOUT_S]
        for client_id in expired:
            self.release_session(client_id)
        return expired

    def close(self) -> None:
        with self._lock:
            clients = list(self._sessions)
        for client_id in clients:
            self.release_session(client_id)


class _NativeHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        manager: NativeControlManager = self.server.manager  # type: ignore[attr-defined]
        session: Session | None = None
        self.connection.settimeout(1.0)
        close_after = False
        buffered = b""
        try:
            while not close_after:
                while b"\n" not in buffered:
                    try:
                        chunk = self.connection.recv(4096)
                    except socket.timeout:
                        if session and manager.clock() - session.last_seen >= LEASE_TIMEOUT_S:
                            close_after = True
                            break
                        continue
                    if not chunk:
                        close_after = True
                        break
                    buffered += chunk
                    if len(buffered) > MAX_LINE_BYTES:
                        close_after = True
                        break
                if close_after:
                    break
                raw, buffered = buffered.split(b"\n", 1)
                raw += b"\n"
                if not raw:
                    break
                if len(raw) > MAX_LINE_BYTES or not raw.endswith(b"\n"):
                    break
                request_id = None
                try:
                    request = strict_json_loads(raw)
                    if set(request) != {"api_version", "request_id", "method", "params"}:
                        raise ProtocolError("BAD_REQUEST", "invalid request envelope")
                    request_id = request["request_id"]
                    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 64:
                        raise ProtocolError("BAD_REQUEST", "invalid request_id")
                    if request["api_version"] != API_VERSION:
                        raise ProtocolError("UNSUPPORTED_VERSION", "unsupported API version")
                    method, params = request["method"], request["params"]
                    if not isinstance(method, str) or not isinstance(params, dict):
                        raise ProtocolError("BAD_REQUEST", "invalid method or params")
                    if method == "hello":
                        if session is not None:
                            raise ProtocolError("BAD_REQUEST", "hello already completed")
                        session, result = manager.hello(params, self.client_address[0])
                    else:
                        if session is None:
                            raise ProtocolError("NOT_REGISTERED", "hello is required")
                        result, close_after = manager.dispatch(session, method, params)
                    response = {"request_id": request_id, "ok": True, "result": result}
                except ProtocolError as exc:
                    response = {"request_id": request_id, "ok": False, "error": {"code": exc.code, "message": exc.message}}
                    if request_id is None:
                        close_after = True
                except Exception:
                    response = {"request_id": request_id, "ok": False, "error": {"code": "INTERNAL_ERROR", "message": "internal server error"}}
                self.wfile.write(json.dumps(response, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n")
                self.wfile.flush()
        finally:
            if session:
                manager.release_session(session.client_id)


class _ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class NativeControlServer:
    def __init__(
        self,
        bridge: SDRBridge,
        host: str = "127.0.0.1",
        port: int = 47632,
        *,
        token: str | None = None,
        allow_lan: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ):
        loopback = host in {"127.0.0.1", "localhost", "::1"}
        if not loopback and (not allow_lan or token is None):
            raise ValueError("non-loopback native control requires explicit LAN enablement and token")
        self.manager = NativeControlManager(bridge, token=token, clock=clock)
        self._server = _ThreadingServer((host, port), _NativeHandler)
        self._server.manager = self.manager  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None
        self._watchdog_stop = threading.Event()
        self._watchdog_thread: threading.Thread | None = None
        self._started = False

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address
        return str(host), int(port)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.serve_forever, name="native-control", daemon=True)
        self._thread.start()
        self._watchdog_stop.clear()
        self._watchdog_thread = threading.Thread(target=self._watchdog, name="native-leases", daemon=True)
        self._watchdog_thread.start()
        self._started = True

    def _watchdog(self) -> None:
        while not self._watchdog_stop.wait(.5):
            self.manager.expire_sessions()

    def close(self) -> None:
        self._watchdog_stop.set()
        if self._started:
            self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=2)
        self.manager.close()
        self._started = False
