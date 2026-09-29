"""Reusable recommendation service shared by HTTP and asynchronous IPC."""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from time import monotonic, perf_counter
from .analyzer import Analyzer
from .config import Settings
from .ranker import Ranker


class RecommendationService:
    def __init__(self, settings: Settings = Settings()) -> None:
        self.settings = settings
        self.analyzer = Analyzer()
        self.ranker = Ranker()
        self._cache: OrderedDict[tuple, tuple[float, dict]] = OrderedDict()
        self._lock = RLock()

    def recommend(self, text: str, top_k: int = 3, context: str = "", recent: tuple[str, ...] = ()) -> dict:
        """Validate inputs and use a bounded, expiring in-memory LRU cache."""
        if not isinstance(text, str) or not isinstance(context, str):
            raise ValueError("text and context must be strings")
        if not text.strip() or len(text) > self.settings.max_text_length or len(context) > self.settings.max_text_length:
            raise ValueError("text must be nonempty; text/context maximum is 512 characters")
        if any(c in text + context for c in "\x00"):
            raise ValueError("NUL is not allowed")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 64:
            raise ValueError("top_k must be an integer from 1 to 64")
        if not isinstance(recent, (list, tuple)) or len(recent) > 10 or any(not isinstance(x, str) or len(x) > 100 for x in recent):
            raise ValueError("recent must contain at most 10 short strings")
        key = (text, top_k, context, tuple(recent))
        start = perf_counter()
        with self._lock:
            cached = self._cache.get(key)
            if cached and monotonic() - cached[0] < self.settings.cache_ttl_seconds:
                self._cache.move_to_end(key)
                result = deepcopy(cached[1])
                result.update(cache_hit=True, latency_ms=round((perf_counter() - start) * 1000, 3))
                return result
        analysis = self.analyzer.analyze(text, context)
        analyzed = perf_counter()
        recommendations = self.ranker.rank(analysis, top_k, tuple(recent))
        end = perf_counter()
        result = dict(analysis=analysis.to_dict(), recommendations=recommendations,
                      latency_ms=round((end - start) * 1000, 3), cache_hit=False,
                      timings_ms={"analysis": round((analyzed - start) * 1000, 3), "ranking": round((end - analyzed) * 1000, 3)})
        with self._lock:
            self._cache[key] = (monotonic(), deepcopy(result))
            self._cache.move_to_end(key)
            while len(self._cache) > self.settings.cache_size:
                self._cache.popitem(last=False)
        return result

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()
