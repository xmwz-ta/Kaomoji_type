import hashlib
import json
import unicodedata
import pytest
from lupa.lua54 import LuaRuntime
from python.config import ROOT
from python.analyzer import Analyzer
from python.ranker import Ranker
from scripts.import_web_kaomoji import convert

def test_snapshot_provenance_and_unique_import():
    manifest = json.loads((ROOT/'data/web_sources.json').read_text(encoding='utf-8'))
    snapshot = (ROOT/'data/upstream/kaomojikan/kaomoji.json').read_bytes()
    assert hashlib.sha256(snapshot).hexdigest() == manifest['sha256']
    rows = json.loads((ROOT/'data/kaomoji.json').read_text(encoding='utf-8'))
    source = {r['slug']:r['text'] for r in json.loads(snapshot)}
    imported = [r for r in rows if r.get('source') == 'kaomojikan']
    assert len(imported) == manifest['added_unique_entries'] >= 1000
    assert len(rows) == manifest['final_dictionary_size']
    assert len({''.join(unicodedata.normalize('NFKC',r['text']).split()) for r in rows}) == len(rows)
    for row in imported:
        assert row['text'] == source[row['source_id']].strip()
        assert not any(unicodedata.category(c).startswith('C') for c in row['text'])
    assert 'Copyright (c) 2026 kaomojikan' in (ROOT/'rime/kaomoji_data.lua').read_text(encoding='utf-8')

def test_import_rejects_multiline_and_control_characters():
    rows = [dict(text=t,slug=str(i),categories=['cute'],tags=['可愛い'])
            for i,t in enumerate(['(o_o)\n(> <)','(o_o)\x00','\u202e(o_o)','(o_o)'])]
    groups, rejected = convert(rows)
    assert [g['texts'][0] for g in groups] == ['(o_o)']
    assert rejected['invalid_or_multiline'] == 3

@pytest.mark.parametrize('text,topic',[('可爱','cute'),('扔东西','throw'),('晕倒','collapse'),('追星','fan'),('吐舌头','tongue'),('仓鼠','hamster'),('摸摸头','pat'),('偷看','peek'),('猫猫','cat')])
def test_imported_faces_reachable_in_both_engines(text,topic):
    entries = json.loads((ROOT/'data/kaomoji.json').read_text(encoding='utf-8'))
    imported = {e['text'] for e in entries if e.get('source')}
    analysis = Analyzer().analyze(text)
    assert topic in analysis.topics
    assert any(row['text'] in imported for row in Ranker().rank(analysis,36))
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().package.path = (ROOT/'rime/?.lua').as_posix()+';'+lua.globals().package.path
    module = lua.execute('local m=require("kaomoji_local"); return m')
    result = module.recommend(text,36)
    assert any(result[i].text in imported for i in range(1,len(result)+1))
