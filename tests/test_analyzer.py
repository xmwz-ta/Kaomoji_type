import json
import pytest
from python.analyzer import Analyzer
from python.config import ROOT
from python.models import EMOTIONS, INTENTS

CORPUS = json.loads((ROOT / "data/test_sentences.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def analyzer():
    return Analyzer()


@pytest.mark.parametrize("case", CORPUS, ids=[c["text"] for c in CORPUS])
def test_corpus(analyzer, case):
    analysis = analyzer.analyze(case["text"])
    assert analysis.emotions.get(case["expected_emotion"], 0) >= case["minimum_score"]
    assert analysis.intent in INTENTS
    assert set(analysis.emotions) <= EMOTIONS
    assert 0 <= analysis.intensity <= 1


def test_negation_and_clause_scope(analyzer):
    assert analyzer.analyze("不开心").emotions.get("happy", 0) < .2
    assert analyzer.analyze("不生气").emotions.get("angry", 0) < .2
    assert analyzer.analyze("不开心，但是终于成功了").emotions["relieved"] > .7
    assert analyzer.analyze("没有成功").intent != "celebrating"


def test_hyperbole_is_not_death_or_fear(analyzer):
    result = analyzer.analyze("救命哈哈笑死我了")
    assert result.emotions["amused"] > .85
    assert result.emotions.get("scared", 0) < .1
    assert analyzer.analyze("救命地震了").emotions["scared"] > .9


def test_sarcasm_context(analyzer):
    hostile = analyzer.analyze("呵呵", "又报错还怪我")
    friendly = analyzer.analyze("呵呵", "谢谢你，真开心")
    assert hostile.emotions["sarcastic"] > friendly.emotions["sarcastic"]
    assert hostile.emotions.get("happy", 0) < .3


def test_literal_and_slang(analyzer):
    assert analyzer.analyze("草").emotions["shocked"] > .8
    assert analyzer.analyze("给植物浇水，草长高了").intent == "neutral"
    assert analyzer.analyze("寄快递").intent == "neutral"
    assert analyzer.analyze("寄").intent == "complaining"


def test_intensity(analyzer):
    assert analyzer.analyze("开心！！！").intensity > analyzer.analyze("开心").intensity
    assert analyzer.analyze("哈哈哈哈哈哈").intensity > analyzer.analyze("哈哈").intensity


def test_empty_and_type(analyzer):
    assert analyzer.analyze("").intent == "neutral"
    with pytest.raises(TypeError):
        analyzer.analyze(None)
