"""Explainable retrieval with diversity and optional user-supplied repetition history."""
import json
import unicodedata
from pathlib import Path
from .config import ROOT
from .models import Analysis, Kaomoji, EMOTIONS, INTENTS, TONES


def signature(text: str) -> set[str]:
    value = "".join(unicodedata.normalize("NFKC", text).split())
    return {value[i:i + 2] for i in range(len(value) - 1)}


class Ranker:
    def __init__(self, path: Path = ROOT / "data/kaomoji.json") -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.entries = [Kaomoji(item["text"], tuple(item["emotions"]), tuple(item["intents"]),
                               tuple(item["tones"]), item["intensity"], tuple(item["tags"]), item["family"], tuple(item.get("topics", [])), item.get("category", "emotion")) for item in raw]
        if len({item.text for item in self.entries}) != len(self.entries):
            raise ValueError("Duplicate kaomoji")
        for item in self.entries:
            if not item.text or any(c in item.text for c in "\t\r\n"):
                raise ValueError("Invalid kaomoji text")
            if not set(item.emotions) <= EMOTIONS or not set(item.intents) <= INTENTS or not set(item.tones) <= TONES:
                raise ValueError("Unknown label in database")
            if not 0 <= item.intensity <= 1:
                raise ValueError("Invalid intensity")
        self.signatures = {item.text: signature(item.text) for item in self.entries}

    def rank(self, analysis: Analysis, top_k: int = 3, recent: tuple[str, ...] = ()) -> list[dict]:
        """Greedy maximal marginal relevance; every score includes its components."""
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 64:
            raise ValueError("top_k must be an integer from 1 to 64")
        pool = []
        for entry in self.entries:
            if analysis.topics:
                if not set(analysis.topics).intersection(entry.topics):
                    continue
            elif entry.topics or not any(analysis.emotions.get(e, 0) >= .25 for e in entry.emotions):
                continue
            values = sorted((analysis.emotions.get(e, 0) for e in entry.emotions), reverse=True)
            emotion = .55 * (values[0] * .85 + sum(values[1:]) / max(1, len(values) - 1) * .15)
            intent = .2 * (analysis.intent in entry.intents)
            tone = .06 * len(set(analysis.tone).intersection(entry.tones)) / max(1, len(analysis.tone))
            intensity = .1 * (1 - abs(analysis.intensity - entry.intensity))
            lexical = .09 * len(set(analysis.tags).intersection(entry.tags)) / max(1, len(analysis.tags))
            repetition = .18 * (entry.text in recent)
            components = dict(emotion_similarity=emotion, intent_match=intent, tone_match=tone,
                              intensity_similarity=intensity, lexical_trigger_bonus=lexical,
                              repetition_penalty=repetition)
            base = emotion + intent + tone + intensity + lexical - repetition
            pool.append((entry, base, components))
        selected: list[tuple[Kaomoji, float, dict]] = []
        pool.sort(key=lambda item: item[1], reverse=True)
        pool = pool[:max(96, top_k * 3)]
        while pool and len(selected) < top_k:
            best_index, best_score, best_penalty = 0, float("-inf"), 0.0
            for index, (entry, base, _) in enumerate(pool):
                family_penalty = min(.34, .17 * sum(entry.family == chosen.family for chosen, _, _ in selected))
                penalty = family_penalty
                for chosen, _, _ in selected:
                    a, b = self.signatures[entry.text], self.signatures[chosen.text]
                    similarity = len(a & b) / max(1, len(a | b))
                    penalty = max(penalty, .18 * similarity)
                if base - penalty > best_score:
                    best_index, best_score, best_penalty = index, base - penalty, penalty
            entry, _, components = pool.pop(best_index)
            selected.append((entry, best_score, {**components, "diversity_penalty": best_penalty}))
        return [dict(text=e.text, score=round(score, 4), family=e.family, topics=list(e.topics), category=e.category,
                     debug={k: round(v, 5) for k, v in components.items()}) for e, score, components in selected]
