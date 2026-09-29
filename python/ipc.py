"""Latest-value file IPC: no HTTP/socket/subprocess inside the IME thread.

Requests are short-lived UTF-8 files, claimed atomically and deleted on read.
Responses contain request IDs and kaomoji, never raw input. No Lua is evaluated.
"""
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from time import monotonic, time
from urllib.parse import unquote
from .config import Settings
from .service import RecommendationService

LOG = logging.getLogger("kaomoji.ipc")
NAME = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


@dataclass(frozen=True)
class Pending:
    session: str
    request_id: str
    text: str
    context: str
    top_k: int
    received: float


class FileBridge:
    def __init__(self, directory: Path, service: RecommendationService, settings: Settings = Settings()) -> None:
        self.directory = directory.resolve()
        self.service = service
        self.settings = settings
        self.pending: dict[str, Pending] = {}
        self._stop = Event()
        self._thread: Thread | None = None
        self._heartbeat_at = float("-inf")
        self._cleanup_at = float("-inf")
        self.processed = 0
        self._lock_file = None

    def _atomic_write(self, path: Path, content: str) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temporary, path)

    def start(self) -> None:
        """Start one worker per IPC directory; a second instance fails clearly."""
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock_file = (self.directory / "bridge.lock").open("a+b")
        self._lock_file.seek(0)
        self._lock_file.write(b"1")
        self._lock_file.flush()
        self._lock_file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self._lock_file.close()
            self._lock_file = None
            raise RuntimeError("An IPC bridge already uses this directory") from error
        # Stale requests left by a crash must never be replayed on restart.
        self._cleanup(all_requests=True)
        self._atomic_write(self.directory / "alive", f"1\t{int(time())}\n")
        self._heartbeat_at = monotonic()
        self._thread = Thread(target=self._run, name="kaomoji-file-ipc", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.pending.clear()
        # Only the owner may remove the heartbeat/requests of this directory.
        if self._lock_file is not None:
            (self.directory / "alive").unlink(missing_ok=True)
            self._cleanup(all_requests=True, all_results=True)
            self._lock_file.close()
            self._lock_file = None

    def _cleanup(self, all_requests: bool = False, all_results: bool = False) -> None:
        for path in self.directory.iterdir():
            if path.suffix not in {".req", ".work", ".tmp", ".out"} or path.is_symlink():
                continue
            try:
                expired = time() - path.stat().st_mtime > self.settings.result_ttl_seconds
                if expired or (all_requests and path.suffix != ".out") or (all_results and path.suffix == ".out"):
                    path.unlink(missing_ok=True)
            except OSError:
                pass

    def _read_request(self, path: Path, now: float) -> None:
        session = path.stem
        if not NAME.fullmatch(session) or path.is_symlink():
            return
        claimed = path.with_suffix(".work")
        try:
            # Claim before reading: deleting this file can never delete a newer request.
            os.replace(path, claimed)
            if time() - claimed.stat().st_mtime > self.settings.request_timeout_ms / 1000:
                return
            with claimed.open("rb") as handle:
                raw = handle.read(self.settings.max_body_bytes + 1)
            if len(raw) > self.settings.max_body_bytes:
                return
            lines = raw.decode("utf-8").splitlines()
            if len(lines) != 3:
                return
            header = lines[0].split("\t")
            if len(header) != 3 or header[0] != "1" or not NAME.fullmatch(header[1]):
                return
            top_k = int(header[2])
            text, context = unquote(lines[1], errors="strict"), unquote(lines[2], errors="strict")
            if not text.strip() or len(text) > self.settings.max_text_length or len(context) > self.settings.max_text_length or not 1 <= top_k <= 10:
                return
            # Overwrite earlier pending input; only the stable final sentence is analyzed.
            if len(self.pending) >= 64 and session not in self.pending:
                self.pending.pop(next(iter(self.pending)))
            self.pending[session] = Pending(session, header[1], text, context, top_k, now)
        except (OSError, UnicodeError, ValueError):
            LOG.debug("invalid_ipc_request")
        finally:
            try:
                claimed.unlink(missing_ok=True)
            except OSError:
                pass

    def tick(self, now: float | None = None) -> None:
        """Poll requests and process only values stable for the configured debounce."""
        now = monotonic() if now is None else now
        if now - self._heartbeat_at >= .5:
            self._atomic_write(self.directory / "alive", f"1\t{int(time())}\n")
            self._heartbeat_at = now
        if now - self._cleanup_at >= 1:
            self._cleanup()
            self._cleanup_at = now
        for path in list(self.directory.glob("*.req"))[:64]:
            self._read_request(path, now)
        for session, request in list(self.pending.items()):
            elapsed = (now - request.received) * 1000
            if elapsed > self.settings.request_timeout_ms:
                self.pending.pop(session, None)
                continue
            if elapsed < self.settings.debounce_ms:
                continue
            try:
                inference_started = monotonic()
                result = self.service.recommend(request.text, request.top_k, request.context)
                rows = [f"{r['text']}\t{r['score']:.4f}" for r in result["recommendations"]]
                if elapsed + (monotonic() - inference_started) * 1000 > self.settings.request_timeout_ms:
                    # A slow backend's late response is dropped; Lua never waits for it.
                    continue
                self._atomic_write(self.directory / f"{session}.out", f"1\t{request.request_id}\t{int(time())}\n" + "\n".join(rows) + "\n")
                self.processed += 1
                LOG.info("ipc_latency_ms=%s emotions=%s results=%s", result["latency_ms"], result["analysis"]["emotions"], [r["text"] for r in result["recommendations"]])
                if self.settings.debug_text:
                    LOG.warning("debug_text=%r context=%r", request.text, request.context)
            except Exception:
                LOG.warning("ipc_recommendation_failed")
            finally:
                self.pending.pop(session, None)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                LOG.warning("ipc_poll_failed")
            self._stop.wait(self.settings.ipc_poll_ms / 1000)
