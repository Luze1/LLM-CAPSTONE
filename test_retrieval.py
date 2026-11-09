from retrieval import search_stations


def test_search_returns_expected_station():
    assert search_stations("near Terminal 21")[0]["id"] == "S03"


def test_search_rejects_unsafe_limit():
    try:
        search_stations("Siam", limit=99)
    except ValueError:
        return
    raise AssertionError("invalid limit was accepted")
