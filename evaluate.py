import json
from pathlib import Path

from retrieval import load_stations, score, tokenize

ROOT = Path(__file__).parent


def retrieve(question: str, expand: bool) -> str:
    stations = load_stations()
    def rank(station: dict) -> int:
        if not expand:
            return len(tokenize(question) & tokenize(f"{station['name']} {station['area']}"))
        return score(question, station, expand=True)

    ranked = sorted(stations, key=lambda station: (-rank(station), station["id"]))
    return ranked[0]["id"]


def main() -> None:
    cases = json.loads((ROOT / "data" / "eval.json").read_text(encoding="utf-8"))
    results = {}
    for name, expand in [("lexical_baseline", False), ("expanded_retrieval", True)]:
        hits = sum(retrieve(case["question"], expand) == case["expected"] for case in cases)
        results[name] = hits / len(cases)
    print(json.dumps({"examples": len(cases), "recall_at_1": results}, indent=2))
    assert results["expanded_retrieval"] >= results["lexical_baseline"]


if __name__ == "__main__":
    main()
