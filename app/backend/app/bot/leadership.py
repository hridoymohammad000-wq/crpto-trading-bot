from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO


class RuntimeLeadershipError(RuntimeError):
    """Raised when another process already owns trading execution leadership."""


class RuntimeLeadership:
    """Cross-process singleton guard for the trading runtime.

    The lock is held for the lifetime of the running bot. It intentionally uses
    a small OS file lock rather than in-memory state so separate Uvicorn worker
    processes cannot both become execution leaders on the same machine.
    """

    def __init__(self, lock_path: str | Path) -> None:
        self.lock_path = Path(lock_path)
        self._handle: BinaryIO | None = None
        self._owner_pid: int | None = None
        self._acquired_at: datetime | None = None

    @property
    def is_owner(self) -> bool:
        return self._handle is not None

    @property
    def owner_pid(self) -> int | None:
        return self._owner_pid if self.is_owner else None

    @property
    def acquired_at(self) -> datetime | None:
        return self._acquired_at if self.is_owner else None

    def acquire(self) -> bool:
        if self.is_owner:
            return True

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.lock_path, "a+b", buffering=0)
        try:
            self._lock_nonblocking(handle)
        except OSError:
            handle.close()
            return False

        now = datetime.now(timezone.utc)
        metadata = {
            "pid": os.getpid(),
            "acquired_at": now.isoformat(),
        }
        payload = json.dumps(metadata, separators=(",", ":")).encode("utf-8")
        handle.seek(0)
        handle.truncate(0)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())

        self._handle = handle
        self._owner_pid = os.getpid()
        self._acquired_at = now
        return True

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return

        try:
            self._unlock(handle)
        finally:
            handle.close()
            self._handle = None
            self._owner_pid = None
            self._acquired_at = None

    def owner_metadata(self) -> dict[str, object] | None:
        try:
            raw = self.lock_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _lock_nonblocking(handle: BinaryIO) -> None:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            # msvcrt locks a byte range and requires that the range exists.
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(handle: BinaryIO) -> None:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
