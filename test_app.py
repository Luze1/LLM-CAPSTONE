from app import answer_from_results, parse_answer
from retrieval import search_menu


def test_parse_answer_accepts_json():
    answer = parse_answer('{"answer":"Pad Thai","menu_ids":["M01"],"supported":true}')
    assert answer.menu_ids == ["M01"]


def test_answer_from_results():
    answer = answer_from_results(search_menu("vegan curry"))
    assert answer.menu_ids[0] == "M02"
    assert "160 baht" in answer.answer


def test_empty_results_are_unsupported():
    assert answer_from_results([]).supported is False
