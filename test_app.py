from app import answer_from_results, parse_answer
from retrieval import search_stations


def test_parse_answer_accepts_markdown_json():
    answer = parse_answer('```json\n{"answer":"Siam","station_ids":["S01"],"supported":true}\n```')
    assert answer.station_ids == ["S01"]


def test_answer_from_results_handles_empty_model_message():
    answer = answer_from_results([{
        "id": "S02", "name": "Chit Lom Garden", "area": "Chit Lom",
        "bikes": 3, "docks": 17,
    }])
    assert answer.station_ids == ["S02"]
    assert "3 bikes" in answer.answer


def test_local_search_supports_empty_model_fallback():
    answer = answer_from_results(search_stations("covered CentralWorld"))
    assert answer.station_ids[0] == "S02"
