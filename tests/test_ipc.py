from dataclasses import replace
from pathlib import Path
from time import monotonic, time
from urllib.parse import quote
import pytest
from python.config import Settings
from python.ipc import FileBridge
from python.service import RecommendationService


def write_request(directory, text, number=1, session="session", context=""):
    path = directory / f"{session}.req"
    path.write_text(f"1\t{session}-{number}\t3\n{quote(text)}\n{quote(context)}\n", encoding="utf-8")


def test_debounce_keeps_only_stable_latest_text(tmp_path):
    bridge = FileBridge(tmp_path, RecommendationService())
    start = monotonic()
    texts = ["怎", "怎么", "怎么又", "怎么又报", "怎么又报错了"]
    for index, text in enumerate(texts):
        write_request(tmp_path, text, index)
        bridge.tick(start + index * .03)
    assert bridge.processed == 0
    bridge.tick(start + .31)
    assert bridge.processed == 1
    output = (tmp_path / "session.out").read_text(encoding="utf-8")
    assert "session-4" in output
    assert "怎么" not in output
    assert not list(tmp_path.glob("*.req"))
    assert not list(tmp_path.glob("*.work"))


def test_unicode_and_literal_percent_roundtrip(tmp_path):
    bridge = FileBridge(tmp_path, RecommendationService())
    write_request(tmp_path, "终于成功了100%\n🎉", context="呵呵\t你好")
    now = monotonic()
    bridge.tick(now)
    assert bridge.pending["session"].text == "终于成功了100%\n🎉"
    bridge.tick(now + .2)
    assert bridge.processed == 1


@pytest.mark.parametrize("bad", ["", "1\tx\t3\nfoo", "1\tx\t100\nfoo\n\n", "1\t../x\t3\nfoo\n\n", "\xff\n\n\n", "x" * 20000])
def test_bad_request_does_not_poison_bridge(tmp_path, bad):
    bridge = FileBridge(tmp_path, RecommendationService())
    (tmp_path / "session.req").write_bytes(bad.encode("latin-1"))
    bridge.tick()
    assert bridge.processed == 0
    write_request(tmp_path, "开心")
    now = monotonic()
    bridge.tick(now)
    bridge.tick(now + .2)
    assert bridge.processed == 1


def test_timeout_drops_pending_without_processing(tmp_path):
    bridge = FileBridge(tmp_path, RecommendationService())
    write_request(tmp_path, "开心")
    now = monotonic()
    bridge.tick(now)
    bridge.tick(now + 2)
    assert bridge.processed == 0
    assert not bridge.pending


def test_service_failure_is_contained(tmp_path, monkeypatch):
    service = RecommendationService()
    bridge = FileBridge(tmp_path, service)
    def fail(*args):
        raise RuntimeError("bad backend")
    monkeypatch.setattr(service, "recommend", fail)
    write_request(tmp_path, "开心")
    now = monotonic()
    bridge.tick(now)
    bridge.tick(now + .2)
    assert not bridge.pending
    assert not (tmp_path / "session.out").exists()


def test_second_bridge_rejected_and_shutdown_cleans(tmp_path):
    first = FileBridge(tmp_path, RecommendationService())
    second = FileBridge(tmp_path, RecommendationService())
    first.start()
    try:
        with pytest.raises(RuntimeError):
            second.start()
        assert (tmp_path / "alive").exists()
        second.stop()
        assert (tmp_path / "alive").exists()
    finally:
        first.stop()
    assert not (tmp_path / "alive").exists()


def test_expired_request_removed_on_restart(tmp_path):
    write_request(tmp_path, "私人文本")
    bridge = FileBridge(tmp_path, RecommendationService())
    bridge.start()
    try:
        assert not (tmp_path / "session.req").exists()
        assert not bridge.pending
    finally:
        bridge.stop()
