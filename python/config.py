"""Configuration and paths; no dependency on the process working directory."""
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    max_text_length: int = 512
    max_body_bytes: int = 16384
    cache_size: int = 256
    cache_ttl_seconds: float = 60.0
    debounce_ms: int = 180
    ipc_poll_ms: int = 20
    request_timeout_ms: int = 1000
    result_ttl_seconds: int = 30
    debug_text: bool = False
