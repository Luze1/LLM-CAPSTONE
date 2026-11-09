from retrieval import search_menu


def test_search_returns_expected_dish():
    assert search_menu("mango dessert")[0]["id"] == "M07"


def test_search_supports_thai_terms():
    assert search_menu("ของหวานมะม่วง")[0]["id"] == "M07"


def test_search_rejects_unsafe_limit():
    try:
        search_menu("curry", limit=99)
    except ValueError:
        return
    raise AssertionError("invalid limit was accepted")
