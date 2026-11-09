import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
SYNONYMS = {"pickup": "bike", "return": "dock", "parking": "station", "close": "near"}


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def score(question: str, station: dict, expand: bool = False) -> int:
    query = tokenize(question)
    if expand:
        query |= {SYNONYMS[word] for word in query if word in SYNONYMS}
    document = tokenize(" ".join(str(value) for value in station.values()))
    return len(query & document)


def load_stations() -> list[dict]:
    return json.loads((ROOT / "data" / "stations.json").read_text(encoding="utf-8"))


def search_stations(query: str, area: str | None = None, covered_only: bool = False,
                    min_bikes: int = 0, limit: int = 3) -> list[dict]:
    if not 1 <= limit <= 5 or min_bikes < 0:
        raise ValueError("invalid search bounds")
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE stations (id, name, area, nearby, bikes, docks, covered)")
    db.executemany("INSERT INTO stations VALUES (:id,:name,:area,:nearby,:bikes,:docks,:covered)",
                   load_stations())
    rows = db.execute(
        "SELECT * FROM stations WHERE (:area IS NULL OR lower(area)=lower(:area)) "
        "AND (:covered_only=0 OR covered=1) AND bikes >= :min_bikes",
        {"area": area, "covered_only": int(covered_only), "min_bikes": min_bikes},
    ).fetchall()
    result = [dict(row) for row in rows]
    return sorted(result, key=lambda station: (-score(query, station, expand=True), station["id"]))[:limit]
