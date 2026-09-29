"""Loopback-only HTTP API. Rime uses ipc.py, never synchronous HTTP."""
import argparse
import json
import logging
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from python.config import Settings
from python.service import RecommendationService

LOG = logging.getLogger("kaomoji")


def create_server(settings: Settings = Settings(), service: RecommendationService | None = None) -> ThreadingHTTPServer:
    """Bind only loopback; default HTTP access logging never includes user text."""
    if settings.host not in {"127.0.0.1", "::1"}:
        raise ValueError("Only loopback binding is supported")
    engine = service or RecommendationService(settings)

    class Handler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            self.request.settimeout(2.0)
            super().setup()

        def log_message(self, format: str, *args: object) -> None:
            pass

        def send_json(self, status: int, value: dict) -> None:
            raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                pass

        def do_GET(self) -> None:
            if self.path == "/health":
                self.send_json(200, {"status": "ok", "backend": "rules", "database_size": len(engine.ranker.entries)})
            else:
                self.send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            if self.path != "/recommend":
                self.send_json(404, {"error": "not_found"})
                return
            try:
                if self.headers.get("Transfer-Encoding"):
                    raise ValueError("Transfer-Encoding is unsupported")
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= settings.max_body_bytes:
                    self.send_json(413, {"error": "invalid_body_size"})
                    return
                if self.headers.get_content_type() != "application/json":
                    self.send_json(415, {"error": "use_application_json"})
                    return
                payload = json.loads(self.rfile.read(size).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Request must be an object")
                result = engine.recommend(payload.get("text"), payload.get("top_k", 3), payload.get("context", ""), payload.get("recent", ()))
                LOG.info("latency_ms=%s emotions=%s results=%s", result["latency_ms"], result["analysis"]["emotions"], [x["text"] for x in result["recommendations"]])
                if settings.debug_text:
                    LOG.warning("debug_text=%r context=%r", payload.get("text"), payload.get("context", ""))
                self.send_json(200, result)
            except (ValueError, UnicodeError):
                self.send_json(400, {"error": "invalid_request"})
            except (socket.timeout, ConnectionError):
                self.close_connection = True
            except Exception:
                # No exception traceback: malformed input must not leak text to logs.
                LOG.error("recommendation_failed")
                self.send_json(500, {"error": "recommendation_failed", "recommendations": []})

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        address_family = socket.AF_INET6 if settings.host == "::1" else socket.AF_INET

    return Server((settings.host, settings.port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ipc-dir", type=Path, help="Rime user directory/kaomoji_ipc")
    parser.add_argument("--debug-text", action="store_true", help="Explicitly log raw text; off by default")
    args = parser.parse_args()
    settings = Settings(port=args.port, debug_text=args.debug_text)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    engine = RecommendationService(settings)
    server = create_server(settings, engine)
    bridge = None
    if args.ipc_dir:
        from python.ipc import FileBridge
        bridge = FileBridge(args.ipc_dir, engine, settings)
        bridge.start()
    print(f"Local service: http://127.0.0.1:{server.server_port} (rules, {len(engine.ranker.entries)} kaomoji)", flush=True)
    if bridge:
        print(f"Rime IPC: {args.ipc_dir.resolve()}", flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if bridge:
            bridge.stop()
        engine.clear_cache()


if __name__ == "__main__":
    main()
