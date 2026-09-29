import json
import logging
from dataclasses import replace
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest
from python.config import Settings
from python.server import create_server
from python.service import RecommendationService


@pytest.fixture
def api():
    server = create_server(Settings(port=0))
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def post(url, payload):
    request = Request(url + "/recommend", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=2) as response:
        return json.load(response)


def test_http_unicode_and_cache(api):
    result = post(api, {"text": "终于成功了"})
    assert result["analysis"]["intent"] == "celebrating"
    assert len(result["recommendations"]) == 3
    assert post(api, {"text": "终于成功了"})["cache_hit"]
    with urlopen(api + "/health", timeout=2) as response:
        assert json.load(response)["database_size"] >= 150


@pytest.mark.parametrize("payload", [{}, {"text": ""}, {"text": 3}, {"text": "x" * 513}, {"text": "开心", "top_k": True}, {"text": "开心", "top_k": 65}, {"text": "开心", "recent": "wrong"}, {"text": "x", "context": None}, [], {"text": "\x00"}])
def test_invalid_input_does_not_kill_service(api, payload):
    with pytest.raises(HTTPError) as error:
        post(api, payload)
    assert error.value.code == 400
    assert post(api, {"text": "谢谢你"})["analysis"]["intent"] == "thanking"


def test_corrupt_json(api):
    request = Request(api + "/recommend", data=b"{broken", headers={"Content-Type": "application/json"})
    with pytest.raises(HTTPError) as error:
        urlopen(request, timeout=2)
    assert error.value.code == 400


def test_large_body(api):
    request = Request(api + "/recommend", data=b" " * 20000, headers={"Content-Type": "application/json"})
    with pytest.raises(HTTPError) as error:
        urlopen(request, timeout=2)
    assert error.value.code == 413


def test_default_logs_exclude_text(api, caplog):
    with caplog.at_level(logging.INFO, logger="kaomoji"):
        post(api, {"text": "终于成功了私人内容", "context": "保密上下文"})
    assert "私人内容" not in caplog.text
    assert "保密上下文" not in caplog.text
    assert "latency_ms" in caplog.text


def test_cache_is_bounded_and_does_not_share_mutable_responses():
    service = RecommendationService(replace(Settings(), cache_size=2))
    original = service.recommend("开心")
    original["analysis"]["emotions"].clear()
    assert service.recommend("开心")["analysis"]["emotions"]
    service.recommend("开心2")
    service.recommend("开心3")
    assert not service.recommend("开心")["cache_hit"]


def test_expired_cache():
    service = RecommendationService(replace(Settings(), cache_ttl_seconds=0))
    service.recommend("开心")
    assert not service.recommend("开心")["cache_hit"]


def test_loopback_only():
    with pytest.raises(ValueError):
        create_server(Settings(host="0.0.0.0", port=0))

