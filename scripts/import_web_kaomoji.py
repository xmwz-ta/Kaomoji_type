"""Offline, reproducible import of the pinned MIT kaomojikan snapshot."""
import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = '60c92ea4e85279ad42ff525e9a40464ebeb1003e'
SOURCE = 'https://github.com/kaomojikan/kaomoji-data'

# Reviewed Japanese labels -> our Chinese-searchable topic IDs.
TOPIC_TAGS = {
 'cat':['ねこ'], 'dog':['いぬ'], 'rabbit':['うさぎ'], 'bear':['くま','クマー'],
 'pig':['ぶた'], 'bird':['ふくろう'], 'hamster':['はむすたー'],
 'pat':['なでなで','よしよし','いいこ'], 'peek':['チラッ','壁チラ'],
 'hug':['ぎゅっ','ぎゅー','おいで'], 'kiss':['ちゅー','投げチュー'],
 'heart':['ハート','投げハート','好き','告白','愛してる','ラブラブ'],
 'wink':['ウインク'], 'tongue':['舌ぺろ'], 'sleep':['眠い','ねむい','zzz','スヤァ','おやすみ'],
 'eat':['もぐもぐ','食べる','おいしい','ぱくぱく','いただきます','よだれ'],
 'tea':['お茶'], 'drink':['飲む'], 'flower':['お花'], 'music':['音符','うたう'],
 'wave':['あいさつ','バイバイ','おーい'], 'bow':['お辞儀','おじぎ','土下座'],
 'tableflip':['ちゃぶ台返し'], 'throw':['投げる','ぽいっ','放り投げ'],
 'collapse':['倒れる','気絶','バタッ','orz'], 'exercise':['スポーツ','サッカー'],
 'star':['流れ星','星'], 'fan':['オタク','推し活','尊い'],
}
EMOTION_TAGS = {
 'crying':['泣く','涙','号泣','うるうる','ぴえん'], 'sad':['悲しい','しょんぼり','絶望'],
 'angry':['怒る','怒り','ぷんぷん','ぶちぎれ'], 'annoyed':['むかー','うざい','むすっ'],
 'shocked':['びっくり','驚き','仰天','ガーン'], 'confused':['はてな','きょとん','ぽかーん'],
 'embarrassed':['照れる','照れ','赤面','はにかみ','もじもじ'],
 'amused':['大笑い','爆笑','www','くすくす'], 'smug':['ドヤ','どや','にやり'],
 'tired':['眠い','ねむい','ぐったり','あくび'], 'helpless':['やれやれ','あきらめ','がっくり'],
 'happy':['嬉しい','笑顔','にっこり','にこにこ','うれしい','ごきげん'],
 'excited':['興奮','わくわく','大喜び','ばんざい','期待','キタ'],
 'cheering':['応援','がんばれ','がんばる','フレー','ファイト'],
 'pleading':['おねがい','あまえ'], 'relieved':['ほっこり','まったり'],
 'awkward':['汗','あせあせ','ごまかし'],
}
CATEGORY_DEFAULTS = {
 'cry':['crying','sad'], 'bikkuri':['shocked'], 'tereru':['embarrassed'],
 'ureshii':['happy','excited'], 'egao':['happy'], 'okoru':['angry','annoyed'],
 'nemui':['tired'], 'ouen':['cheering'], 'taoreru':['helpless','tired'],
 'chira':['suspicious','neutral'], 'suki':['happy','embarrassed'],
 'kirakira':['excited','happy'], 'tehepero':['amused','embarrassed'],
 'cute':['happy'], 'ryosangata':['happy'], 'animal':['neutral','happy'],
 'mogumogu':['happy'], 'nadenade':['relieved','happy'], 'otaku':['excited'],
}
NEW_TOPICS = [
 dict(id='cute',label='可爱',kind='emotion',phrases=['可爱','好萌','萌萌哒','卖萌','软萌','萌死了','卡哇伊']),
 dict(id='throw',label='扔东西',kind='action',phrases=['扔东西','丢东西','扔出去','丢出去','扔给你','丢给你','接住','投掷']),
 dict(id='collapse',label='倒地',kind='action',phrases=['倒地','倒下了','晕倒','累倒了','倒地不起','瘫倒','躺倒','两眼一黑']),
 dict(id='fan',label='追星',kind='action',phrases=['追星','应援','我的偶像','嗑到了','磕到了','嗑糖','磕糖','推し','本命']),
 dict(id='tongue',label='吐舌头',kind='action',phrases=['吐舌头','吐舌','略略略','调皮','做鬼脸']),
 dict(id='hamster',label='仓鼠',kind='animal',phrases=['仓鼠','小仓鼠','鼠鼠','仓鼠宝宝']),
]

def normalized(text):
    return ''.join(unicodedata.normalize('NFKC',text).split())

def convert(rows):
    """Treat upstream content as data only; reject unsafe/broken candidate text."""
    groups, seen, rejected = [], set(), Counter()
    for row in rows:
        text = row.get('text','').strip()
        if not text or len(text) > 80 or any(unicodedata.category(c).startswith('C') for c in text):
            rejected['invalid_or_multiline'] += 1
            continue
        if 'aa' in row['categories']:
            rejected['ascii_art_category'] += 1
            continue
        key = normalized(text)
        if key in seen:
            rejected['duplicate_in_source'] += 1
            continue
        tags = set(row['tags'])
        topics = [topic for topic, labels in TOPIC_TAGS.items() if tags.intersection(labels)]
        if 'tableflip' in topics and 'throw' in topics:
            topics.remove('throw')
        emotions = [emotion for emotion, labels in EMOTION_TAGS.items() if tags.intersection(labels)]
        if not emotions:
            emotions = next((CATEGORY_DEFAULTS[c] for c in row['categories'] if c in CATEGORY_DEFAULTS), [])
        if not topics and not emotions:
            rejected['unmapped_meaning'] += 1
            continue
        if not topics and set(row['categories']).intersection({'cute','ryosangata'}):
            topics = ['cute']
        seen.add(key)
        emotions = emotions or ['neutral']
        intents = ['neutral']
        if 'cheering' in emotions: intents = ['encouraging']
        elif 'crying' in emotions or 'angry' in emotions: intents = ['complaining']
        elif 'excited' in emotions or 'happy' in emotions: intents = ['celebrating']
        groups.append(dict(family='web_'+row['categories'][0],topics=topics,
            emotions=emotions,intents=intents,tones=['informal'],tags=[],intensity=.5,
            texts=[text],source='kaomojikan',source_id=row['slug']))
    return groups, dict(rejected)

def build():
    snapshot = ROOT / 'data/upstream/kaomojikan/kaomoji.json'
    data = snapshot.read_bytes()
    rows = json.loads(data)
    groups, rejected = convert(rows)
    (ROOT / 'data/web_collections.json').write_text(json.dumps(groups,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest = dict(repository=SOURCE,revision=REVISION,retrieved='2026-09-29',license='MIT',
        license_file='upstream/kaomojikan/LICENSE',sha256=hashlib.sha256(data).hexdigest(),
        source_records=len(rows),accepted_before_existing_dictionary_dedup=len(groups),rejected=rejected)
    (ROOT / 'data/web_sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lexicon_path = ROOT / 'data/lexicon.json'
    lexicon = json.loads(lexicon_path.read_text(encoding='utf-8'))
    existing = {topic['id'] for topic in lexicon['topics']}
    lexicon['topics'].extend(topic for topic in NEW_TOPICS if topic['id'] not in existing)
    lexicon_path.write_text(json.dumps(lexicon,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    build()
