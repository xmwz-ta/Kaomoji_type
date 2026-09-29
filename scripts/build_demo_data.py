"""Rebuild the authored demo database and regression corpus deterministically."""
import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_json(name: str, value: object) -> None:
    (ROOT / "data" / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_rules() -> None:
    rules = []

    def add(name: str, pattern: str, emotions: dict, intent: str = "neutral", priority: float = .7,
            tones: str = "", tags: str = "", negatable: bool = False) -> None:
        rules.append(dict(id=name, pattern=pattern, emotions=emotions, intent=intent, priority=priority,
                          tones=tones.split(), tags=tags.split(), negatable=negatable))

    add("completion", "终于|总算|搞完|跑通|成功|解决了", {"relieved": .82, "excited": .65, "happy": .55}, "celebrating", .88, tags="victory relief", negatable=True)
    add("joy", "开心|高兴|好耶|太好了|喜欢|好棒", {"happy": .85, "excited": .58}, "celebrating", .8, tags="smile", negatable=True)
    add("laugh", "哈哈|笑死|乐死|笑喷|搞笑|绷不住", {"amused": .92, "happy": .45}, "joking", .85, "humorous", "laugh", True)
    add("recurring_failure", "怎么又|又.{0,8}(?:报错|失败|坏了)|报错|跑不通|失败了", {"frustrated": .85, "annoyed": .57, "helpless": .36}, "complaining", .92, tags="stress sigh")
    add("annoyance", "烦死|烦躁|烦人|好烦|不耐烦", {"annoyed": .9, "frustrated": .7}, "complaining", .9, tags="stress", negatable=True)
    add("anger", "气死|生气|愤怒|混蛋|可恶|滚开", {"angry": .94, "annoyed": .65}, "complaining", .95, tags="rage tableflip", negatable=True)
    add("resignation", "行吧|算了|随便|就这样吧|认命|不想干了", {"helpless": .83, "awkward": .46, "tired": .32}, "resigning", .95, tags="shrug sigh")
    add("speechless", "我服了|无语|麻了|无力吐槽", {"helpless": .78, "frustrated": .75, "shocked": .36}, "complaining", .93, tags="sigh shrug")
    add("incredulous", "太离谱|离了大谱|好家伙", {"shocked": .77, "confused": .53, "sarcastic": .35}, "surprised_reaction", .82, "humorous", "surprise")
    add("surprise", "居然|竟然|没想到|震惊|吓一跳", {"shocked": .79, "excited": .26}, "surprised_reaction", .76, tags="surprise")
    add("questions", "[?]{2,}|怎么回事|为什么|不明白|看不懂", {"confused": .9, "shocked": .4}, "questioning", .9, tags="question")
    add("question_mark", "[?]", {"confused": .35}, "questioning", .45, tags="question")
    add("skeptic", "你认真的|真的假的|真的吗|骗我|不信|可疑", {"suspicious": .85, "confused": .55}, "questioning", .96, tags="doubt")
    add("hehe", "呵呵", {"sarcastic": .87, "awkward": .55}, "refusing", .98, "sarcastic", "sideeye")
    add("sadness", "难过|伤心|失落|心碎|好孤独|想念", {"sad": .88, "crying": .36}, "complaining", .8, "gentle", "sad", True)
    add("cry", "呜呜|哭了|泪目|想哭|😭|😢", {"crying": .92, "sad": .63}, "complaining", .82, "gentle", "tears", True)
    add("awkward", "尴尬|社死|冷场|汗颜", {"awkward": .91, "embarrassed": .55}, "complaining", .81, tags="sweat", negatable=True)
    add("shy", "害羞|脸红|不好意思|羞羞", {"embarrassed": .9, "happy": .28}, "neutral", .65, "gentle", "blush", True)
    add("smug", "我真厉害|果然是我|得意|小意思|我就知道", {"smug": .88, "happy": .42}, "celebrating", .8, "humorous", "smirk")
    add("tired", "困死|好困|累死|好累|疲惫|熬夜|睡觉|晚安", {"tired": .91, "helpless": .2}, "goodbye", .72, "gentle", "sleep", True)
    add("fear", "害怕|恐怖|可怕|危险|地震|着火|追杀|有人跟踪", {"scared": .92, "shocked": .52}, "complaining", .86, "serious", "fear", True)
    add("help", "救命|求求|拜托|帮帮我|求助", {"pleading": .83, "shocked": .42}, "questioning", .84, "gentle", "please")
    add("apology", "对不起|抱歉|我错了|不好意思打扰|请原谅", {"embarrassed": .57, "pleading": .5}, "apologizing", 1.05, "polite gentle", "bow")
    add("thanks", "谢谢|感谢|多谢|辛苦你|感激", {"happy": .67, "relieved": .36}, "thanking", 1.05, "polite gentle", "gratitude", True)
    add("encourage", "加油|你可以的|别放弃|冲鸭|支持你|坚持住", {"cheering": .91, "excited": .46}, "encouraging", 1.03, "gentle", "cheer")
    add("greeting", "你好|早上好|早安|嗨|哈喽|hello", {"happy": .5, "neutral": .2}, "greeting", 1.0, "polite", "wave")
    add("farewell", "再见|拜拜|回头见|走啦|晚安", {"neutral": .45, "happy": .25}, "goodbye", 1.02, "gentle", "wave")
    add("refusal", "不要|不行|拒绝|不可以|不愿意|不干", {"annoyed": .43, "neutral": .3}, "refusing", 1.0, tags="no")
    add("agreement", "没问题|可以呀|好的|同意|明白了|收到|当然", {"happy": .4, "neutral": .35}, "agreeing", 1.0, tags="yes")
    add("reassure", "没事|别担心|没关系", {"relieved": .58, "neutral": .36}, "encouraging", .9, "gentle", "comfort")
    add("impressed", "牛逼|牛批|厉害|绝了|太强|神了", {"excited": .85, "cheering": .55, "shocked": .3}, "celebrating", .88, tags="victory cheer", negatable=True)
    add("doom", "完蛋|凉了|(?:^|[ ,!。])寄(?:了|$)|芭比Q", {"helpless": .8, "frustrated": .66, "scared": .33}, "complaining", .9, tags="failure")
    add("slang_grass", "^(?:卧)?草[!。 ]*$|我草|卧槽", {"shocked": .87, "amused": .36}, "surprised_reaction", .9, "humorous", "surprise")
    add("laugh_emoji", "😂|🤣|😆|😄", {"amused": .89, "happy": .6}, "joking", .84, "humorous", "laugh")
    add("happy_emoji", "😊|🥰|🎉|🥳|😎", {"happy": .82, "excited": .68}, "celebrating", .86, tags="victory")
    add("angry_emoji", "😡|🤬|💢", {"angry": .93, "annoyed": .68}, "complaining", .9, tags="rage")
    add("fear_emoji", "😱|🥶|😨", {"scared": .84, "shocked": .74}, "surprised_reaction", .85, tags="fear")
    add("sleep_emoji", "😴|🥱", {"tired": .9}, "goodbye", .8, tags="sleep")
    write_json("rules.json", {"version": 1, "rules": rules})


def build_corpus() -> None:
    groups = {
        "relieved": "我终于搞完了|终于成功了|我终于把程序跑通了|总算解决了|没事|别担心",
        "excited": "居然成功了|牛逼|好耶|太强了|程序终于跑通了",
        "amused": "哈哈哈哈笑死我了|笑死|绷不住了|救命哈哈这也太好笑了|这个真的搞笑|😂😂😂",
        "frustrated": "怎么又报错|怎么又是这个报错|麻了|又失败了|跑不通|我服了",
        "helpless": "行吧|算了|随便|不想干了|完蛋|寄|无语了|我认命了",
        "confused": "？？？|怎么回事|为什么这样|我看不懂|不明白|？",
        "suspicious": "你认真的？|真的假的|真的吗|别骗我|这个很可疑",
        "sarcastic": "呵呵|呵呵你又来了|你可真行呵呵",
        "shocked": "好家伙|救命|太离谱了|草|卧槽|竟然还有这种事|没想到啊",
        "angry": "气死我了|真生气|可恶|😡|混蛋",
        "tired": "困死了|我要睡觉|好累啊|昨天又熬夜|🥱",
        "embarrassed": "对不起|抱歉|害羞|脸红了|我错了",
        "happy": "谢谢你|感谢帮助|你好|早上好|开心|好的|同意",
        "cheering": "加油|别放弃|你可以的|冲鸭|支持你",
        "scared": "救命地震了|有人跟踪我救命|好害怕|着火了|恐怖片太可怕了",
        "sad": "好难过|伤心了|今天有点失落|心碎",
        "crying": "呜呜呜|我要哭了|😭|泪目了",
        "awkward": "太尴尬了|社死现场|冷场了|汗颜",
        "smug": "我真厉害|果然是我|小意思|我就知道",
        "pleading": "求求你|拜托了|帮帮我|求助",
        "neutral": "今天下午开会|这是一棵草|寄快递|今天不开心但明天会好|不开​​心".replace("\u200b", ""),
    }
    corpus = []
    for emotion, sentences in groups.items():
        for sentence in sentences.split("|"):
            # Explicit negative examples have separate assertions.
            if sentence.startswith("今天不开心") or sentence == "不开心":
                continue
            corpus.append({"text": sentence, "expected_emotion": emotion, "minimum_score": .2})
    write_json("test_sentences.json", corpus)


def build_kaomoji() -> None:
    # Authored groups, not Cartesian products of interchangeable eyes and mouths.
    # Each pipe separates an independently selected, visible expression.
    groups = [
        ("happy", "happy", "celebrating agreeing", "informal gentle", .45, "smile", "(＾▽＾)|(´∀｀)|(≧◡≦)|(⌒▽⌒)☆|(o^▽^o)|(´｡• ᵕ •｡`)|(◕‿◕)|(*´▽｀*)"),
        ("ecstatic", "excited happy", "celebrating", "informal", .9, "victory", "ヽ(ﾟ∀ﾟ)ﾉ|٩(ˊᗜˋ*)و|ｷﾀ━━━━(ﾟ∀ﾟ)━━━━!!|＼(^o^)／|ヾ(≧▽≦*)o|ヽ(>∀<☆)ノ|(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧|╰(*°▽°*)╯"),
        ("relief", "relieved happy", "celebrating", "informal gentle", .55, "relief victory", "ε-(´∀｀; )|ε-(´・｀)|(*´ο`*)=3|( ´ ▽ ` )ﾉ|(*´ω｀*)|ヾ(´ー｀)ノ|( ˊᵕˋ )|(*˘︶˘*).｡.:*♡"),
        ("laugh", "amused happy", "joking", "informal humorous", .7, "laugh", "(≧▽≦)|｡ﾟ( ﾟ^∀^ﾟ)ﾟ｡|ꉂ(ˊᗜˋ*)|www(ﾉ∀`)www|(☞ﾟヮﾟ)☞|(*≧艸≦)|(ಡωಡ)|(つ≧▽≦)つ"),
        ("wry", "awkward sarcastic helpless", "joking resigning", "informal humorous", .4, "sweat sigh", '(￣▽￣")|(；・∀・)|(´∀｀；)|(＾＾；)|(⌒_⌒;)|(；´∀｀)|(￣ω￣;)|(；⌒▽⌒)'),
        ("speechless", "helpless frustrated", "complaining resigning", "informal", .5, "sigh", "(´-ω-`)|(눈_눈)|(ー_ー)!!|(-_-;)|(=_=)|(￣_￣)|(；一_一)|(¬_¬ )"),
        ("awkward", "awkward embarrassed", "apologizing complaining", "informal", .55, "sweat", "(・・;)|(；´д｀)ゞ|(〃￣ω￣〃ゞ|(￣▽￣;)ゞ|(；´ﾟдﾟ｀)|(；￣Д￣)|(・・；)ゞ|(；´・ω・)"),
        ("sad", "sad helpless", "complaining", "gentle informal", .4, "sad", "(´・ω・｀)|(´･_･`)|(｡•́︿•̀｡)|(︶︹︺)|(´；ω；｀)|(っ˘̩╭╮˘̩)っ|(｡•́︵•̀｡)|(◞‸◟)"),
        ("cry", "crying sad", "complaining", "gentle informal", .85, "tears", "｡･ﾟ･(ﾉД`)･ﾟ･｡|(ಥ_ಥ)|(╥﹏╥)|(T_T)|(つд⊂)|。゜゜(´Ｏ`) ゜゜。|｡ﾟ(ﾟ´Д｀ﾟ)ﾟ｡|(இдஇ; )"),
        ("angry", "angry annoyed", "complaining refusing", "informal serious", .85, "rage", "ヽ(`Д´)ﾉ|(＃`Д´)|(╬ Ò﹏Ó)|(＃￣0￣)|( `皿´ )|(凸ಠ益ಠ)凸|(╬ﾟдﾟ)|(ง •̀_•́)ง"),
        ("annoyed", "annoyed frustrated", "complaining refusing", "informal", .6, "stress", "(¬_¬)|(＃－.－)|(￣ヘ￣)|(눈‸눈)|(￢_￢;)|(ಠ_ಠ)|(｀ε´)|(；¬д¬)"),
        ("tableflip", "angry frustrated", "complaining", "informal humorous", .95, "rage tableflip", "(╯°□°）╯︵ ┻━┻|┻━┻ ︵ヽ(`Д´)ﾉ|┻━┻ミ＼(≧ﾛ≦＼)|(ノಠ益ಠ)ノ彡┻━┻|(┛◉Д◉)┛彡┻━┻|(ﾉ｀Д´)ﾉ彡┻━┻"),
        ("stress", "frustrated tired", "complaining", "informal", .65, "stress sigh", "(；´Д｀)|(；´Д`)ﾊｧﾊｧ|orz|OTL|(ノдヽ)|(；´Д｀)=3|＿|￣|○"),
        ("shrug", "helpless awkward", "resigning complaining", "informal humorous", .4, "shrug sigh", "┐(´д｀)┌|┐(￣ヘ￣)┌|┐(ﾟ～ﾟ)┌|¯\\_(ツ)_/¯|╮(￣▽￣)╭|┐(´ー｀)┌|( ´_ゝ`)|┐( ˘_˘ )┌"),
        ("shock", "shocked excited", "surprised_reaction", "informal", .9, "surprise", "Σ(ﾟДﾟ)|Σ(°ロ°)|(⊙_⊙;)|Σ(･ω･ﾉ)ﾉ！|(ﾟдﾟ)!|( Д ) ﾟ ﾟ|(ﾉﾟ0ﾟ)ﾉ|щ(゜ロ゜щ)"),
        ("question", "confused suspicious", "questioning", "informal", .5, "question doubt", "(・・?)|(・_・ヾ|(・・。)ゞ|(◎_◎;)|(´･ω･`)?|(⊙_⊙)?|(゜-゜)|(・・ ) ?"),
        ("sideeye", "suspicious sarcastic", "questioning refusing", "informal sarcastic", .5, "doubt sideeye", "(￢_￢)|(¬‿¬)|(¬д¬。)|(ಠಿ_ಠ)|(눈_눈)？|(→_→)|(←_←)|(￢ω￢)"),
        ("sarcasm", "sarcastic smug awkward", "joking refusing", "informal sarcastic humorous", .55, "sideeye smirk", "( ´,_ゝ`)|(￣ー￣)|(¬‿¬ )|( ´艸｀)|( ͡° ͜ʖ ͡°)|(ಡ‿ಡ)|(￣∀￣)|(￢‿￢ )"),
        ("shy", "embarrassed happy", "thanking apologizing", "gentle informal", .45, "blush", "(⁄ ⁄•⁄ω⁄•⁄ ⁄)|(〃ω〃)|(*/ω＼*)|(*/▽＼*)|(⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)|(〃▽〃)|(//ω//)|(｡･･｡)"),
        ("smug", "smug happy", "celebrating agreeing", "informal humorous", .65, "smirk victory", "(｀・ω・´)|<(￣︶￣)>|(๑•̀ㅂ•́)و✧|(￣^￣)ゞ|( •̀ ω •́ )✧|(⌐■_■)|(๑˃̵ᴗ˂̵)و|(｀∀´)"),
        ("sleep", "tired neutral", "goodbye resigning", "gentle informal", .2, "sleep", "( ˘ω˘ )|(－ω－) zzZ|(∪｡∪)｡｡｡zzz|(￣o￣) . z Z|(－_－) zzZ|(＿ ＿*) Z z z|(´-﹃-`) zzZ|(ᴗ˳ᴗ)"),
        ("fear", "scared shocked", "complaining surprised_reaction", "serious informal", .85, "fear", "((((；ﾟДﾟ))))|(((＞＜)))|(⊙﹏⊙)|(;;;*_*)|ヽ(ﾟДﾟ)ﾉ|(ﾟДﾟ;)|(；ﾟДﾟ；)|(／。＼)"),
        ("please", "pleading scared", "questioning apologizing", "gentle polite", .55, "please", "(人>ω<)|(｡•́人•̀｡)|(人´∀｀)|(つ﹏<。)|(＞人＜;)|(；人；)|(人´ω｀*)|(｡-人-｡)"),
        ("bow", "embarrassed pleading", "apologizing", "polite gentle", .5, "bow", "m(_ _)m|m(｡_｡)m|<(_ _)>|(*_ _)人|(シ_ _)シ|(_ _。)|ｍ（＿　＿）ｍ|m(_ _;m)"),
        ("thanks", "happy relieved", "thanking", "polite gentle", .55, "gratitude", "(人´∀`)♪|(*´∀人)|(人´ω｀)♡|ヾ(●´∇｀●)ﾉ|(* ˘⌣˘)◞♡|(*人´▽｀*)|(人 •͈ᴗ•͈)|(*´︶`*)♡"),
        ("cheer", "cheering excited", "encouraging", "gentle informal", .8, "cheer", "٩( 'ω' )و|୧(๑•̀⌄•́๑)૭|ᕦ(ò_óˇ)ᕤ|(ง •̀ω•́)ง|ヾ(｀・ω・´)ノ|٩(๑•̀ω•́๑)۶|o(≧▽≦)o|フレー！ヾ(≧▽≦)ﾉ"),
        ("hello", "happy neutral", "greeting", "polite informal", .4, "wave", "(・ω・)ノ|ヾ(＾-＾)ノ|(｡･ω･)ﾉﾞ|(￣▽￣)ノ|(^-^*)/|ヾ(´･ω･｀)ﾉ|( ´ ▽ ` )ﾉｼ|(*・ω・)ﾉ"),
        ("bye", "neutral relieved", "goodbye", "gentle informal", .3, "wave", "ヾ(￣▽￣) Bye~|(´･ω･`)ﾉｼ|(＾▽＾)／|ヾ(*'-'*)|(@^^)/~~~|ヾ(・ω・*)|(*￣▽￣)ﾉ~~|(o・・o)/"),
        ("no", "annoyed neutral", "refusing", "informal serious", .4, "no", "(乂'ω')|(￣×￣)|(乂｀д´)|(ヾﾉ･∀･`)ﾑﾘﾑﾘ|o(>< )o|(×_×)|٩(× ×)۶"),
        ("yes", "happy neutral", "agreeing", "informal", .35, "yes", "(￣▽￣)b|(･ω･)b|(•̀ᴗ•́)و ̑̑|(＾－＾)V|d(⌒ー⌒)|(*•̀ㅂ•́)و|(*^ーﾟ)b"),
        ("comfort", "relieved neutral", "encouraging", "gentle", .25, "comfort", "(づ｡◕‿‿◕｡)づ|(つ´∀｀)つ|(っ´▽｀)っ|(*´ω｀)っ|( T_T)＼(^-^ )|(๑´•.̫ • `๑)|(っ˘ω˘ς )"),
        ("neutral", "neutral", "neutral", "informal", .15, "calm", "(・ω・)|(￣︶￣)|( ˙꒳˙ )|(｡･ω･｡)|(・∀・)|(´ー｀)|(￣ー￣)ゞ"),
    ]
    entries = []
    seen = set()
    for family, emotions, intents, tones, intensity, tags, variants in groups:
        for text in variants.split("|"):
            # The classic collapsed-person expression contains vertical bars.
            if text in {"＿", "￣", "○"}:
                continue
            key = "".join(unicodedata.normalize("NFKC", text).split())
            if key in seen:
                continue
            seen.add(key)
            entries.append(dict(text=text, emotions=emotions.split(), intents=intents.split(),
                                tones=tones.split(), intensity=intensity, tags=tags.split(), family=family))
    entries.append(dict(text="＿|￣|○", emotions=["helpless", "frustrated"], intents=["complaining"],
                        tones=["informal"], intensity=.75, tags=["failure"], family="collapse"))
    write_json("kaomoji.json", entries)


if __name__ == "__main__":
    build_rules()
    build_corpus()
    build_kaomoji()
