import pytest
from python.analyzer import Analyzer
from python.ranker import Ranker
from python.models import EMOTIONS, INTENTS


@pytest.fixture(scope="module")
def ranker():
    return Ranker()


def test_database_coverage(ranker):
    assert len(ranker.entries) >= 900
    assert {e for item in ranker.entries for e in item.emotions} == EMOTIONS
    assert INTENTS <= {i for item in ranker.entries for i in item.intents}
    assert "ｷﾀ━━━━(ﾟ∀ﾟ)━━━━!!" in {e.text for e in ranker.entries}
    assert len({e.text for e in ranker.entries}) == len(ranker.entries)


@pytest.mark.parametrize("text,expected", [
    ("终于成功了", {"excited", "relieved", "happy"}),
    ("怎么又报错了", {"frustrated", "annoyed", "helpless"}),
    ("呵呵", {"sarcastic", "awkward", "suspicious"}),
    ("？？？", {"confused", "shocked", "suspicious"}),
    ("行吧", {"helpless", "awkward", "tired"}),
    ("谢谢你", {"happy", "relieved"}),
    ("救命地震了", {"scared", "pleading", "shocked"}),
])
def test_semantic_retrieval(ranker, text, expected):
    results = ranker.rank(Analyzer().analyze(text))
    entries = {e.text: e for e in ranker.entries}
    assert len(results) == 3
    assert all(set(entries[r["text"]].emotions) & expected for r in results)
    assert len({r["family"] for r in results}) >= 2


def test_scores_are_explainable_and_history_changes_order(ranker):
    analysis = Analyzer().analyze("终于成功了")
    first = ranker.rank(analysis)
    later = ranker.rank(analysis, recent=(first[0]["text"],))
    assert first[0]["text"] != later[0]["text"]
    for row in first:
        c = row["debug"]
        score = sum(v if "penalty" not in k else -v for k, v in c.items())
        assert abs(score - row["score"]) < .0001


@pytest.mark.parametrize("value", [0, 65, True, "3", 3.2])
def test_invalid_k(ranker, value):
    with pytest.raises(ValueError):
        ranker.rank(Analyzer().analyze("开心"), value)
