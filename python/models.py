"""Shared, JSON-friendly domain models."""
from dataclasses import asdict, dataclass, field

EMOTIONS = frozenset("happy excited amused relieved sad crying angry annoyed frustrated helpless awkward embarrassed confused shocked suspicious sarcastic smug tired scared pleading cheering neutral".split())
INTENTS = frozenset("complaining celebrating joking questioning apologizing thanking greeting goodbye encouraging refusing agreeing resigning surprised_reaction neutral".split())
TONES = frozenset({"informal", "humorous", "sarcastic", "gentle", "polite", "serious"})


@dataclass
class Analysis:
    emotions: dict[str, float]
    intent: str
    tone: list[str]
    intensity: float
    evidence: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return values suitable for serialization, including explainable evidence."""
        return asdict(self)


@dataclass(frozen=True)
class Kaomoji:
    text: str
    emotions: tuple[str, ...]
    intents: tuple[str, ...]
    tones: tuple[str, ...]
    intensity: float
    tags: tuple[str, ...]
    family: str
    topics: tuple[str, ...] = ()
    category: str = "emotion"
