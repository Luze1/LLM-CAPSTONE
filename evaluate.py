import json
from pathlib import Path

from retrieval import load_menu, score, tokenize

ROOT = Path(__file__).parent


def retrieve(question: str, expand: bool) -> str:
    menu = load_menu()
    def rank(item: dict) -> int:
        if not expand:
            return len(tokenize(question) & tokenize(f"{item['name']} {item['category']}"))
        return score(question, item, expand=True)
    return sorted(menu, key=lambda item: (-rank(item), item["id"]))[0]["id"]


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
