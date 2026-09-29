"""Multi-label rules with scoped negation, context and discourse precedence."""
import json
import re
import unicodedata
from pathlib import Path

from .config import ROOT
from .models import Analysis, EMOTIONS, INTENTS, TONES

CLAUSE_BREAK = re.compile(r"[，。！？,!?；;\n]|但是|不过|可是|然而")
NEGATION = re.compile(r"(?:并不|不是|没有|没|不|别|无)(?:太|很|怎么|那么|特别|再|想)?$")


def normalize(text: str) -> str:
    """Normalize full-width punctuation without changing the stored kaomoji."""
    return unicodedata.normalize("NFKC", text).strip()


class Analyzer:
    def __init__(self, rules_path: Path = ROOT / "data" / "rules.json") -> None:
        config = json.loads(rules_path.read_text(encoding="utf-8"))
        self.topics = config.get("topics", [])
        self.rules: list[tuple[dict, re.Pattern]] = []
        for rule in config["rules"]:
            if not set(rule["emotions"]) <= EMOTIONS:
                raise ValueError("Unknown emotion in rules")
            if rule.get("intent", "neutral") not in INTENTS:
                raise ValueError("Unknown intent in rules")
            if not set(rule.get("tones", [])) <= TONES:
                raise ValueError("Unknown tone in rules")
            self.rules.append((rule, re.compile(rule["pattern"])))

    def analyze(self, text: str, context: str = "") -> Analysis:
        """Analyze the current utterance; context resolves ambiguity but has low weight."""
        if not isinstance(text, str) or not isinstance(context, str):
            raise TypeError("text and context must be strings")
        current = normalize(text)
        prior = normalize(context[-160:])
        clauses = [c for c in CLAUSE_BREAK.split(current) if c]
        scores: dict[str, float] = {}
        intents: dict[str, float] = {}
        tones = {"informal"}
        evidence: list[str] = []
        tags: set[str] = set()
        for rule, pattern in self.rules:
            if rule.get("match") == "exact" and current.strip(" 。！？，.!?,") not in rule.get("phrases", []):
                continue
            matches = list(pattern.finditer(current))
            for match in matches:
                prefix = CLAUSE_BREAK.split(current[:match.start()])[-1][-6:]
                negated = rule.get("negatable", False) and bool(NEGATION.search(prefix))
                weight = 0.13 if negated else 1.0
                # Later clauses usually carry the speaker's present stance.
                if len(clauses) > 1 and match.end() <= current.rfind(clauses[-1]):
                    weight *= 0.4
                if re.search(r"(?:太|非常|超级|特别|真的|好)$", prefix):
                    weight *= 1.12
                evidence.append(rule["id"] + (":negated" if negated else ""))
                for emotion, value in rule["emotions"].items():
                    old = scores.get(emotion, 0.0)
                    scores[emotion] = max(old, min(0.98, value * weight))
                intent = rule.get("intent", "neutral")
                intents[intent] = max(intents.get(intent, 0.0), rule.get("priority", 0.7) * weight)
                if not negated:
                    tones.update(rule.get("tones", []))
                    tags.update(rule.get("tags", []))
                break  # Repetition affects intensity, not duplicate lexical evidence.

        for rule, pattern in self.rules:
            if rule.get("suppress") and pattern.search(current):
                for emotion, cap in rule["suppress"].items():
                    scores[emotion] = min(scores.get(emotion, 0), cap)
        topics = []
        for topic in self.topics:
            matches = [current.find(p) for p in topic["phrases"] if p in current]
            exact = current.strip(" 。！？，.!?,") in topic.get("exact", [])
            if exact or any(not (topic["kind"] == "action" and NEGATION.search(current[:pos][-6:])) for pos in matches):
                topics.append(topic["id"])
        # Internet hyperbole must be resolved from the entire current utterance.
        if "救命" in current:
            danger = bool(re.search(r"地震|着火|火灾|追杀|溺水|危险|有人跟踪|喘不过气|害怕", current + prior))
            comedy = bool(re.search(r"哈哈|笑|搞笑|可爱|萌|乐死", current)) and not danger
            if comedy:
                scores["amused"] = max(scores.get("amused", 0), 0.92)
                scores["scared"] = 0.05
                intents["joking"] = 1.2
                tones.add("humorous")
            elif danger:
                scores.update(scared=0.96, pleading=0.88)
                intents["complaining"] = 1.1
                tones = {"serious"}
            else:
                scores.update(shocked=max(scores.get("shocked", 0), 0.7), pleading=0.45)
            evidence.append("context:help")
        if "呵呵" in current:
            friendly = bool(re.search(r"开心|好笑|哈哈|谢谢|喜欢", current + prior))
            scores["happy"] = min(scores.get("happy", 0), 0.25)
            scores["sarcastic"] = 0.5 if friendly else 0.92
            scores["awkward"] = 0.7 if friendly else 0.55
            intents["joking" if friendly else "refusing"] = 1.3
            tones.add("sarcastic")
            evidence.append("context:hehe")
        if "不" in current and re.search(r"不(?:是|太)?开心|不高兴", current):
            scores.update(sad=max(scores.get("sad", 0), 0.62), annoyed=max(scores.get("annoyed", 0), 0.45))
        if not scores or max(scores.values()) < 0.18:
            scores["neutral"] = 0.75
        intent = max(intents, key=intents.get) if intents and max(intents.values()) >= .18 else "neutral"
        # Repeated marks/characters and degree adverbs affect arousal separately.
        punctuation = len(re.findall(r"[!?]", current))
        repetition = bool(re.search(r"(.)\1{2,}", current))
        strength = 0.13 if re.search(r"死了|爆了|超级|太.*了|非常", current) else 0
        intensity = min(1.0, 0.15 + max(scores.values()) * 0.58 + min(punctuation, 4) * 0.05 + 0.08 * repetition + strength)
        if intent == "neutral":
            intensity *= 0.55
        return Analysis(
            {k: round(v, 4) for k, v in sorted(scores.items(), key=lambda item: -item[1])},
            intent, sorted(tones), round(intensity, 4), evidence, sorted(tags), topics,
        )
