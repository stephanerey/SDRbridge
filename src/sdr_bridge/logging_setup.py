from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import faulthandler
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import tempfile
import threading
import uuid
from typing import IO


LOG_FILE_NAME = "sdrbridge.log"
FAULT_FILE_NAME = "sdrbridge-fault.log"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5


def default_log_directory(instance_name: str | None = None) -> Path:
    override = os.environ.get("SDRBRIDGE_LOG_DIR")
    if override:
        return Path(override).expanduser()
    from .config import normalize_instance_name

    instance = normalize_instance_name(instance_name)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        root = Path(local_app_data) / "SDRbridge"
    else:
        state_root = os.environ.get("XDG_STATE_HOME")
        root = Path(state_root) / "SDRbridge" if state_root else Path.home() / ".local" / "state" / "SDRbridge"
    if instance != "default":
        root = root / "instances" / instance
    return root / "logs"


class JsonLogFormatter(logging.Formatter):
    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        item: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "component": record.name,
            "run_id": getattr(record, "run_id", self.run_id),
            "code": getattr(record, "code", "GENERAL"),
            "message": record.getMessage(),
            "process_id": record.process,
            "thread": record.threadName,
        }
        for name in ("source_id", "epoch"):
            value = getattr(record, name, None)
            if value is not None:
                item[name] = value
        details = getattr(record, "details", None)
        if isinstance(details, dict):
            item["details"] = details
        if record.exc_info:
            item["exception"] = self.formatException(record.exc_info)
        return json.dumps(item, ensure_ascii=False, separators=(",", ":"))


def _remove_owned_handlers(root: logging.Logger) -> None:
    for handler in list(root.handlers):
        if getattr(handler, "_sdrbridge_owned", False):
            root.removeHandler(handler)
            try:
                handler.flush()
            finally:
                handler.close()


@dataclass
class LoggingSession:
    run_id: str
    log_path: Path | None
    fault_path: Path | None
    handlers: list[logging.Handler] = field(default_factory=list)
    _fault_stream: IO[str] | None = None
    _enabled_fault_handler: bool = False
    _old_sys_hook: object | None = None
    _old_thread_hook: object | None = None
    _sys_hook: object | None = None
    _thread_hook: object | None = None
    _closed: bool = False

    def set_level(self, level: str | int) -> None:
        numeric = getattr(logging, level.upper()) if isinstance(level, str) else int(level)
        logging.getLogger().setLevel(numeric)
        for handler in self.handlers:
            handler.setLevel(numeric)

    def install_exception_hooks(self, *, chain: bool = True) -> None:
        logger = logging.getLogger("sdr_bridge.crash")
        self._old_sys_hook = sys.excepthook
        self._old_thread_hook = threading.excepthook

        def sys_hook(exc_type, exc_value, traceback) -> None:
            if exc_type is KeyboardInterrupt:
                if chain and callable(self._old_sys_hook):
                    self._old_sys_hook(exc_type, exc_value, traceback)
                return
            logger.critical(
                "unhandled exception on main thread",
                exc_info=(exc_type, exc_value, traceback),
                extra={"code": "UNHANDLED_MAIN_EXCEPTION"},
            )
            if chain and callable(self._old_sys_hook):
                self._old_sys_hook(exc_type, exc_value, traceback)

        def thread_hook(args: threading.ExceptHookArgs) -> None:
            logger.critical(
                "unhandled exception on worker thread",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
                extra={"code": "UNHANDLED_THREAD_EXCEPTION", "details": {"thread": args.thread.name if args.thread else None}},
            )
            if chain and callable(self._old_thread_hook):
                self._old_thread_hook(args)

        self._sys_hook = sys_hook
        self._thread_hook = thread_hook
        sys.excepthook = sys_hook
        threading.excepthook = thread_hook

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._sys_hook is not None and sys.excepthook is self._sys_hook and callable(self._old_sys_hook):
            sys.excepthook = self._old_sys_hook
        if self._thread_hook is not None and threading.excepthook is self._thread_hook and callable(self._old_thread_hook):
            threading.excepthook = self._old_thread_hook
        if self._enabled_fault_handler and faulthandler.is_enabled():
            faulthandler.disable()
        if self._fault_stream is not None:
            self._fault_stream.flush()
            self._fault_stream.close()
            self._fault_stream = None
        root = logging.getLogger()
        for handler in self.handlers:
            if handler in root.handlers:
                root.removeHandler(handler)
            try:
                handler.flush()
            finally:
                handler.close()
        self.handlers.clear()


def configure_logging(
    level: str | int = "INFO",
    log_dir: str | Path | None = None,
    *,
    run_id: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    enable_fault_handler: bool = True,
    stream: bool = True,
    chain_exception_hooks: bool = True,
    instance_name: str | None = None,
) -> LoggingSession:
    run_id = run_id or str(uuid.uuid4())
    formatter = JsonLogFormatter(run_id)
    root = logging.getLogger()
    _remove_owned_handlers(root)
    handlers: list[logging.Handler] = []
    selected_dir: Path | None = Path(log_dir).expanduser() if log_dir is not None else default_log_directory(instance_name)
    log_path: Path | None = None
    fault_path: Path | None = None
    directory_error: OSError | None = None
    try:
        selected_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        directory_error = exc
        selected_dir = Path(tempfile.gettempdir()) / "SDRbridge" / "logs"
        try:
            selected_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            selected_dir = None
    if selected_dir is not None:
        try:
            log_path = selected_dir / LOG_FILE_NAME
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=max(1, int(max_bytes)),
                backupCount=max(0, int(backup_count)),
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler._sdrbridge_owned = True  # type: ignore[attr-defined]
            root.addHandler(file_handler)
            handlers.append(file_handler)
        except OSError as exc:
            directory_error = directory_error or exc
            log_path = None
    if stream and getattr(sys.stderr, "write", None) is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        stream_handler._sdrbridge_owned = True  # type: ignore[attr-defined]
        root.addHandler(stream_handler)
        handlers.append(stream_handler)
    session = LoggingSession(run_id, log_path, fault_path, handlers)
    session.set_level(level)
    session.install_exception_hooks(chain=chain_exception_hooks)
    if enable_fault_handler and selected_dir is not None and not faulthandler.is_enabled():
        try:
            fault_path = selected_dir / FAULT_FILE_NAME
            session._fault_stream = fault_path.open("a", encoding="utf-8", buffering=1)
            faulthandler.enable(file=session._fault_stream, all_threads=True)
            session._enabled_fault_handler = True
            session.fault_path = fault_path
        except OSError:
            session._fault_stream = None
            session.fault_path = None
    logger = logging.getLogger("sdr_bridge.logging")
    logger.info(
        "persistent logging initialized",
        extra={
            "code": "LOGGING_READY",
            "details": {
                "log_path": str(log_path) if log_path else None,
                "fault_path": str(session.fault_path) if session.fault_path else None,
                "max_bytes": int(max_bytes),
                "backup_count": int(backup_count),
                "instance": instance_name or "default",
            },
        },
    )
    if directory_error is not None:
        logger.warning(
            "primary log directory was unavailable; fallback applied",
            extra={"code": "LOG_DIRECTORY_FALLBACK", "details": {"error": str(directory_error), "selected": str(selected_dir) if selected_dir else None}},
        )
    return session
