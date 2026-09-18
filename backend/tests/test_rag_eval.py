"""Golden-set RAG eval score functions (pure, deterministic)."""

from app.services.rag.eval import (
    GOLDEN_CASES,
    NO_EVIDENCE_MESSAGE,
    aggregate,
    expected_present,
    score_answer,
    score_retrieval,
    value_floats,
)


def test_value_floats_parses_decimals_and_commas():
    assert 108.0 in value_floats("108.00 million tonnes")
    assert 474730.0 in value_floats("474,730 MT")
    assert 52.5 in value_floats("reserve 52.50 Mt")
    assert value_floats("no numbers here") == set()


def test_expected_present_exact():
    assert expected_present({1.0, 2.5}, [2.5]) == [2.5]
    assert expected_present({1.0}, [2.5]) == []


def test_score_retrieval_ok_when_docs_and_values_surface():
    case = GOLDEN_CASES[0]
    result = score_retrieval(
        case,
        [{"document_name": "Barkhola_Report.pdf", "text": "total reserve 108.00 MT"}],
    )
    assert result["retrieval_recall"] == 1.0
    assert result["ok"] is True
    assert result["values_in_retrieved"] == [108.0]


def test_score_retrieval_fails_on_wrong_document():
    case = GOLDEN_CASES[0]
    result = score_retrieval(
        case,
        [{"document_name": "geological_survey.pdf", "text": "108.0"}],
    )
    assert result["retrieval_recall"] == 0.0
    assert result["ok"] is False


def test_score_answer_validates_values_and_citations():
    case = GOLDEN_CASES[0]
    result = score_answer(
        case,
        "The total geological reserve was 108 MT.",
        [{"document_name": "Barkhola.pdf", "page_number": 2}],
        known_docs={"Barkhola.pdf", "other.pdf"},
    )
    assert result["ok"] is True
    assert result["values_in_answer"] == [108.0]
    assert result["unknown_citations"] == []


def test_score_answer_flags_hallucinated_citation():
    case = GOLDEN_CASES[0]
    result = score_answer(
        case,
        "The total geological reserve was 108 MT.",
        [{"document_name": "phantom_doc.pdf", "page_number": 9}],
        known_docs={"Barkhola.pdf"},
    )
    assert result["unknown_citations"] == ["phantom_doc.pdf"]
    assert result["ok"] is False


def test_refusal_control_ok_when_no_citations():
    case = next(c for c in GOLDEN_CASES if c.get("expect_refusal"))
    retrieval = score_retrieval(case, [])
    answer = score_answer(case, NO_EVIDENCE_MESSAGE, [], {"x.pdf"})
    assert retrieval["ok"] is True
    assert answer["ok"] is True
    assert answer["refused"] is True


def test_aggregate_skips_control_for_recall():
    ok = {"ok": True, "retrieval_recall": 1.0}
    control = {"ok": True, "retrieval_recall": 0.0, "expect_refusal_is_control": True}
    agg = aggregate([ok, ok, control])
    assert agg["passed"] == 3
    assert agg["retrieval_recall"] == 1.0