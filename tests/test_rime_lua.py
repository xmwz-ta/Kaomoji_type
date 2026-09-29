import pytest
from lupa.lua54 import LuaRuntime
from python.config import ROOT
from python.analyzer import Analyzer
from python.ranker import Ranker

@pytest.fixture
def lua_env(tmp_path):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().package.path = (ROOT / 'rime/?.lua').as_posix() + ';' + lua.globals().package.path
    lua.execute((ROOT / 'tests/lua_harness.lua').read_text(encoding='utf-8'))
    module = lua.execute((ROOT / 'rime/kaomoji.lua').read_text(encoding='utf-8'))
    env, ctx = lua.globals().make_environment(tmp_path.as_posix())
    for component in (module.processor, module.filter, module.translator):
        component.init(env)
    yield lua, module, env, ctx, tmp_path
    for component in (module.processor, module.filter, module.translator):
        component.fini(env)

def source(lua, texts=('终于成功了','终于','中于','终于成功','终')):
    return lua.table_from([lua.globals().Candidate('phrase',0,18,t,'') for t in texts])

def test_offline_immediate_six_and_no_disk(lua_env):
    lua, mod, env, ctx, directory = lua_env
    result = lua.globals().run_filter(mod,env,source(lua))
    assert len(result) == 11
    assert result[1].text == '终于成功了'
    assert all(result[i].type == 'kaomoji' for i in range(4,10))
    assert result[4].text.startswith('终于成功了 ')
    assert not list(directory.iterdir())

def test_prefix_candidates_preserve_typed_chinese(lua_env):
    lua, mod, env, ctx, _ = lua_env
    candidates = source(lua, ('咖', '卡', '喀', '咔'))
    result = lua.globals().run_filter(mod, env, candidates)
    assert result[4].text.startswith('咖 ')
    assert '联想：咖啡' in result[4].comment
    ctx.selected, ctx.committed_text = candidates[1], '咖'
    mod.processor.func(lua.globals().make_key('F8'), env)
    expanded = lua.globals().run_filter(mod, env, candidates)
    assert expanded[1].text.startswith('咖 ')
    assert '咖啡' in expanded[1].comment

def test_selected_homophone_and_edit_reset(lua_env):
    lua,mod,env,ctx,_ = lua_env
    candidates = source(lua,('苦','哭','酷','库'))
    ctx.selected,ctx.committed_text = candidates[2],'哭'
    assert mod.processor.func(lua.globals().make_key('F8'),env) == 1
    result = lua.globals().run_filter(mod,env,candidates)
    assert len(result) > 13
    assert all(result[i].text.startswith('哭 ') for i in range(1,10))
    assert result[1].start == 0 and result[1]._end == 18
    ctx.input = 'newinput'
    result = lua.globals().run_filter(mod,env,candidates)
    assert result[1].text == '苦'

def test_normal_keys_disable_ascii_and_postcommit(lua_env):
    lua,mod,env,ctx,_ = lua_env
    for key in ('a','space','4','Escape','Return'):
        assert mod.processor.func(lua.globals().make_key(key),env) == 2
    mod.processor.func(lua.globals().make_key('F9'),env)
    assert len(lua.globals().run_filter(mod,env,source(lua))) == 5
    mod.processor.func(lua.globals().make_key('F9'),env)
    ctx.ascii = True
    assert len(lua.globals().run_filter(mod,env,source(lua))) == 5
    ctx.ascii = False
    ctx.callback(ctx)
    ctx.composing = False
    assert mod.processor.func(lua.globals().make_key('F8'),env) == 1
    assert ctx.input == 'km'
    result = lua.globals().run_translator(mod,env)
    assert len(result) == 36
    assert all('终于' not in result[i].text for i in range(1,len(result)+1))
    mod.processor.func(lua.globals().make_key('Shift+F9'),env)
    assert len(lua.globals().run_translator(mod,env)) == 0

@pytest.mark.parametrize('text,topic',[('抱抱','hug'),('亲亲','kiss'),('去吃饭','eat'),('晚安','sleep'),('学习','study'),('开黑','game'),('猫','cat'),('狗狗','dog'),('熊猫','panda'),('生日快乐','cake'),('喝咖啡','coffee'),('掀桌','tableflip'),('摸摸头','pat'),('鼓掌','clap'),('下雨了','umbrella'),('钱','money')])
def test_python_and_offline_topics(lua_env,text,topic):
    lua,*_ = lua_env
    engine = lua.eval('require("kaomoji_local")')
    if isinstance(engine,tuple): engine=engine[0]
    analysis = Analyzer().analyze(text)
    assert topic in analysis.topics
    assert engine.analyze(text).topics[topic]
    result = Ranker().rank(analysis,36)
    assert len(result) >= 8
    assert all(topic in item['topics'] for item in result)
    assert len(engine.recommend(text,36)) >= 8

@pytest.mark.parametrize('text,emotion',[('不开心','sad'),('太离谱了','shocked'),('笑不活了','amused'),('我好委屈','sad'),('程序跑通了','relieved'),('救命地震了','scared'),('救命笑死我了','amused'),('哭','crying'),('酷','smug'),('好生气，但是现在开心了','happy')])
def test_expanded_emotions(lua_env,text,emotion):
    lua,*_ = lua_env
    engine = lua.eval('require("kaomoji_local")')
    if isinstance(engine,tuple): engine=engine[0]
    assert engine.analyze(text).emotions[emotion] >= .6
    assert Analyzer().analyze(text).emotions[emotion] >= .6

def test_false_positive_and_negation(lua_env):
    lua,*_ = lua_env
    engine = lua.eval('require("kaomoji_local")')
    if isinstance(engine,tuple): engine=engine[0]
    for text in ('猫腻','寄快递','草坪'):
        assert not Analyzer().analyze(text).topics
        assert engine.analyze(text).emotions.neutral == .75
    assert not engine.analyze('不想睡觉').topics.sleep
    assert 'sleep' not in Analyzer().analyze('不想睡觉').topics
    assert engine.analyze('不生气').emotions.angry < .2
