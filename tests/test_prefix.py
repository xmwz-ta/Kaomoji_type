import pytest
from lupa.lua54 import LuaRuntime
from python.config import ROOT
from python.analyzer import Analyzer
from python.ranker import Ranker

@pytest.fixture(scope="module")
def engines():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().package.path = (ROOT / 'rime/?.lua').as_posix() + ';' + lua.globals().package.path
    module = lua.execute('return require("kaomoji_local")')
    if isinstance(module, tuple): module = module[0]
    return Analyzer(), module

@pytest.mark.parametrize('text,topic', [('抱','hug'),('咖','coffee'),('晚','sleep'),('生日快','cake'),('我想喝咖','coffee'),('摸摸','pat'),('巧克力蛋','cake')])
def test_prefix_topics(engines,text,topic):
    python,lua = engines
    a,b = python.analyze(text),lua.analyze(text)
    assert topic in a.topics
    assert b.topics[topic]
    assert any(x.startswith('prefix:') for x in a.evidence)
    assert len(lua.recommend(text,6)) == 6
    assert all(topic in row['topics'] for row in Ranker().rank(a,6))

@pytest.mark.parametrize('text', ['我','好','太','猫腻','寄快递','草坪','不想抱','不想摸摸','咖。','咖?'])
def test_no_spurious_prefix(engines,text):
    python,lua = engines
    assert not any(x.startswith('prefix:') for x in python.analyze(text).evidence)
    assert len(lua.analyze(text).completions) == 0

@pytest.mark.parametrize('text', ['抱抱','喝咖啡','开心','不开心','睡觉','晚安'])
def test_complete_match_wins(engines,text):
    python,lua = engines
    assert not any(x.startswith('prefix:') for x in python.analyze(text).evidence)
    assert len(lua.analyze(text).completions) == 0

def test_partial_emotion(engines):
    python,lua = engines
    assert python.analyze('笑不活').emotions['amused'] >= .6
    assert lua.analyze('笑不活').emotions.amused >= .6
