"""Measure uncached rules/ranking and cached total latency, never log user input."""
import argparse
import json
import platform
import statistics
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from python.config import ROOT
from python.service import RecommendationService


def summary(values: list[float]) -> dict:
    values = sorted(values)
    return {"mean_ms": round(statistics.mean(values), 4), "p95_ms": round(values[int((len(values) - 1) * .95)], 4), "max_ms": round(max(values), 4)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("iterations must be positive")
    service = RecommendationService()
    corpus = json.loads((ROOT / "data/test_sentences.json").read_text(encoding="utf-8"))
    timings: dict[str, list[float]] = {"analysis": [], "ranking": [], "cached_total": []}
    for index in range(args.iterations):
        text = corpus[index % len(corpus)]["text"]
        a = perf_counter()
        analysis = service.analyzer.analyze(text)
        b = perf_counter()
        service.ranker.rank(analysis)
        c = perf_counter()
        timings["analysis"].append((b - a) * 1000)
        timings["ranking"].append((c - b) * 1000)
        service.recommend(text)
        d = perf_counter()
        service.recommend(text)
        timings["cached_total"].append((perf_counter() - d) * 1000)
    result = dict(python=platform.python_version(), platform=platform.platform(), database_size=len(service.ranker.entries),
                  corpus_size=len(corpus), iterations=args.iterations, backend="rules", **{key: summary(values) for key, values in timings.items()})
    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
