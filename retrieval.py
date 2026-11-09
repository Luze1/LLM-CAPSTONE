import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
SYNONYMS = {"shrimp": "prawn", "plant": "vegan", "beverage": "drink", "meat": "pork"}
THAI_TERMS = {
    "กุ้ง": "prawn", "มังสวิรัติ": "vegetarian", "วีแกน": "vegan",
    "เจ": "vegan", "แกง": "curry", "เผ็ด": "spicy", "ไม่เผ็ด": "mild",
    "ซุป": "soup", "สลัด": "salad", "ของหวาน": "dessert",
    "เครื่องดื่ม": "drink", "ชาไทย": "thai iced tea", "ข้าว": "rice",
    "ไก่": "chicken", "เนื้อ": "beef", "หมู": "pork", "มะม่วง": "mango",
    "ถั่วลิสง": "peanuts", "เต้าหู้": "tofu", "เส้น": "noodles",
}


def normalize(text: str) -> str:
    for thai, english in THAI_TERMS.items():
        text = text.replace(thai, f" {english} ")
    return text


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalize(text.lower())))


def score(question: str, item: dict, expand: bool = False) -> int:
    query = tokenize(question)
    if expand:
        query |= {SYNONYMS[word] for word in query if word in SYNONYMS}
    document = tokenize(" ".join(str(value) for value in item.values()))
    return len(query & document)


def load_menu() -> list[dict]:
    return json.loads((ROOT / "data" / "menu.json").read_text(encoding="utf-8"))


def search_menu(query: str, category: str | None = None, vegetarian_only: bool = False,
                vegan_only: bool = False, max_price: int | None = None,
                limit: int = 3) -> list[dict]:
    if not 1 <= limit <= 5 or (max_price is not None and max_price < 0):
        raise ValueError("invalid search bounds")
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE menu (id, name, category, description, price, spicy, vegetarian, vegan, allergens, nearby)")
    menu = load_menu()
    for item in menu:
        item["allergens"] = ", ".join(item["allergens"])
    db.executemany("INSERT INTO menu VALUES (:id,:name,:category,:description,:price,:spicy,:vegetarian,:vegan,:allergens,:nearby)", menu)
    rows = db.execute(
        "SELECT * FROM menu WHERE (:category IS NULL OR lower(category)=lower(:category)) "
        "AND (:vegetarian_only=0 OR vegetarian=1) AND (:vegan_only=0 OR vegan=1) "
        "AND (:max_price IS NULL OR price <= :max_price)",
        {"category": category, "vegetarian_only": int(vegetarian_only),
         "vegan_only": int(vegan_only), "max_price": max_price},
    ).fetchall()
    result = [dict(row) for row in rows]
    return sorted(result, key=lambda item: (-score(query, item, expand=True), item["id"]))[:limit]
